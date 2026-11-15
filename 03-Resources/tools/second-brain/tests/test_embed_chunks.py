"""Spec for embed_chunks.py's vault-root resolution and its read-side planning.

The contract these tests pin:

  resolve_vault_root(explicit, start, env)
    - `--vault` wins over everything
    - else `SECOND_BRAIN_VAULT`
    - else the nearest `vault.json` at or above `start` (shared vault_config rule)
    - else None — never the old "four parents above the DB" guess, which was right
      at exactly one depth and silently wrong everywhere else

  plan_chunks(conn, vault_root, ...)
    - reads each indexed path relative to `vault_root`
    - counts a missing file as unreadable instead of raising, so the caller can
      tell "wrong root" (everything unreadable) from "a few files moved"

No network: nothing here calls Ollama. numpy is not imported by these paths.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from embed_chunks import VAULT_ENV, plan_chunks, resolve_vault_root  # noqa: E402


def make_vault(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "vault.json").write_text("{}", encoding="utf-8")
    return root


class TestResolveVaultRoot:
    def test_explicit_flag_wins(self, tmp_path):
        chosen = tmp_path / "chosen"
        chosen.mkdir()
        env = {VAULT_ENV: str(tmp_path / "ignored")}
        assert resolve_vault_root(chosen, tmp_path, env) == chosen.resolve()

    def test_env_var_beats_discovery(self, tmp_path):
        discovered = make_vault(tmp_path / "discovered")
        from_env = tmp_path / "from-env"
        from_env.mkdir()
        start = discovered / "03-Resources" / "tools" / "second-brain"
        start.mkdir(parents=True)
        assert resolve_vault_root(None, start, {VAULT_ENV: str(from_env)}) == from_env.resolve()

    def test_discovery_walks_up_to_vault_json(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        start = vault / "03-Resources" / "tools" / "second-brain"
        start.mkdir(parents=True)
        assert resolve_vault_root(None, start, {}) == vault.resolve()

    def test_no_marker_returns_none_not_a_guess(self, tmp_path):
        """The pre-2026-11-15 behaviour would have returned tmp_path.parent here."""
        start = tmp_path / "a" / "03-Resources" / "tools" / "second-brain"
        start.mkdir(parents=True)
        assert resolve_vault_root(None, start, {}) is None

    def test_empty_env_value_is_ignored(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        assert resolve_vault_root(None, vault, {VAULT_ENV: ""}) == vault.resolve()


def db_with_paths(paths: list[str]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE files (path TEXT PRIMARY KEY, extracted TEXT)")
    conn.executemany("INSERT INTO files (path, extracted) VALUES (?, '{}')", [(p,) for p in paths])
    conn.commit()
    return conn


class TestPlanChunks:
    def test_reads_paths_relative_to_the_given_root(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        (vault / "notes").mkdir()
        (vault / "notes" / "a.md").write_text("# A\n\nA paragraph long enough to keep.\n")
        conn = db_with_paths(["notes/a.md"])
        records, ok, bad = plan_chunks(conn, vault, target=1500, max_chunks=40)
        assert (ok, bad) == (1, 0)
        assert records and records[0][0] == "notes/a.md"

    def test_wrong_root_makes_every_file_unreadable(self, tmp_path):
        """This is the symptom the old root guess produced on a second vault, and
        the signal main() now turns into an error instead of an empty index."""
        vault = make_vault(tmp_path / "vault")
        (vault / "notes").mkdir()
        (vault / "notes" / "a.md").write_text("# A\n")
        wrong_root = tmp_path / "elsewhere"
        wrong_root.mkdir()
        conn = db_with_paths(["notes/a.md", "notes/b.md"])
        records, ok, bad = plan_chunks(conn, wrong_root, target=1500, max_chunks=40)
        assert (ok, bad, records) == (0, 2, [])
