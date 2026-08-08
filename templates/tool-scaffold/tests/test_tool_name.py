"""Specification for <tool_name>.

This module is the spec of record — restate the behaviour the tool promises, especially any
decision table in the module docstring. If the table and these tests disagree, the tests win.

Run:  python3 -m pytest tests/
No network. Never touches the live vault.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tool_name import collect_targets, run  # noqa: E402


class TestCollectTargets:
    def test_finds_markdown_recursively(self, tmp_path):
        (tmp_path / "00-Inbox").mkdir()
        (tmp_path / "00-Inbox" / "a.md").write_text("x")
        (tmp_path / "b.md").write_text("y")
        (tmp_path / "c.txt").write_text("skip me")

        found = {p.name for p in collect_targets(tmp_path, None)}

        assert found == {"a.md", "b.md"}

    def test_skips_hidden_and_named_directories(self, tmp_path):
        """Skip-dirs come from vault_config, so every tool inherits the same set.
        Delete this test only if your tool genuinely wants cache files."""
        (tmp_path / ".pytest_cache").mkdir()
        (tmp_path / ".pytest_cache" / "README.md").write_text("cache")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.md").write_text("dep")
        (tmp_path / "real.md").write_text("keep")

        found = {p.name for p in collect_targets(tmp_path, None)}

        assert found == {"real.md"}

    def test_folders_arg_restricts_scope(self, tmp_path):
        (tmp_path / "00-Inbox").mkdir()
        (tmp_path / "02-Projects").mkdir()
        (tmp_path / "00-Inbox" / "in.md").write_text("x")
        (tmp_path / "02-Projects" / "proj.md").write_text("y")

        found = {p.name for p in collect_targets(tmp_path, ["00-Inbox"])}

        assert found == {"in.md"}


class TestDryRun:
    """Every mutating path needs a test proving dry-run writes nothing."""

    def test_dry_run_does_not_modify_files(self, tmp_path):
        target = tmp_path / "note.md"
        target.write_text("original")

        run(tmp_path, None, apply=False)

        assert target.read_text() == "original"
