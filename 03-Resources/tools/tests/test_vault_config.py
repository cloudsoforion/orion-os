"""Spec for vault_config — the shared taxonomy loader.

The contract these tests pin:

  find_vault_root(start)
    - returns the nearest ancestor (including `start`) containing `.obsidian/`
    - `.obsidian` must be a directory; a file by that name is not a vault marker
    - returns None when there is none, so callers own their fallback

  load_config(vault_root)
    - absent vault.json           -> DEFAULTS, unchanged
    - present vault.json          -> merged over DEFAULTS, recursing into dicts,
                                     so renaming one pillar keeps the other four
    - malformed vault.json        -> raises, never silently falls back to a
                                     different taxonomy than the author wrote
    - DEFAULTS is never mutated by a load

  is_skipped_dir / prune_dirs
    - hidden directories are skipped when skip_hidden_dirs is on. This is the
      rule that keeps `.pytest_cache/README.md` out of vault scans; before the
      shared module, process_frontmatter walked into it and stamped 7 files.
    - skip_hidden_dirs off leaves hidden dirs to the explicit skip_dirs list

  tag(config, kind, value)
    - composes prefix + value, and rejects an unknown prefix loudly
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vault_config import (  # noqa: E402
    DEFAULTS,
    date_from_text,
    find_vault_root,
    is_skipped_dir,
    load_config,
    prune_dirs,
    tag,
)


def make_vault(root: Path, config: dict | None = None) -> Path:
    """Throwaway vault: `.obsidian/` plus an optional vault.json."""
    (root / ".obsidian").mkdir(parents=True)
    if config is not None:
        (root / "vault.json").write_text(json.dumps(config), encoding="utf-8")
    return root


class TestFindVaultRoot:
    def test_finds_marker_in_start_dir(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        assert find_vault_root(vault) == vault.resolve()

    def test_walks_up_from_a_nested_tool_dir(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        nested = vault / "03-Resources" / "tools" / "some-tool"
        nested.mkdir(parents=True)
        assert find_vault_root(nested) == vault.resolve()

    def test_returns_none_when_no_marker_anywhere(self, tmp_path):
        plain = tmp_path / "not-a-vault"
        plain.mkdir()
        assert find_vault_root(plain) is None

    def test_obsidian_as_a_file_is_not_a_vault_marker(self, tmp_path):
        decoy = tmp_path / "decoy"
        decoy.mkdir()
        (decoy / ".obsidian").write_text("not a directory", encoding="utf-8")
        assert find_vault_root(decoy) is None

    def test_picks_the_nearest_marker_when_vaults_nest(self, tmp_path):
        outer = make_vault(tmp_path / "outer")
        inner = make_vault(outer / "inner")
        assert find_vault_root(inner) == inner.resolve()


class TestLoadConfig:
    def test_no_config_file_yields_defaults(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        assert load_config(vault) == DEFAULTS

    def test_no_vault_root_yields_defaults(self):
        assert load_config() == DEFAULTS

    def test_top_level_key_is_overridden(self, tmp_path):
        vault = make_vault(tmp_path / "vault", {"log_dir": "05-Log"})
        assert load_config(vault)["log_dir"] == "05-Log"

    def test_nested_override_keeps_sibling_keys(self, tmp_path):
        vault = make_vault(tmp_path / "vault", {"pillars": {"inbox": "0-in"}})
        pillars = load_config(vault)["pillars"]
        assert pillars["inbox"] == "0-in"
        assert pillars["projects"] == DEFAULTS["pillars"]["projects"]

    def test_list_values_are_replaced_not_merged(self, tmp_path):
        vault = make_vault(tmp_path / "vault", {"skip_dirs": ["only-this"]})
        assert load_config(vault)["skip_dirs"] == ["only-this"]

    def test_defaults_are_not_mutated_by_a_load(self, tmp_path):
        before = json.dumps(DEFAULTS, sort_keys=True)
        vault = make_vault(tmp_path / "vault", {"pillars": {"inbox": "clobbered"}})
        load_config(vault)
        assert json.dumps(DEFAULTS, sort_keys=True) == before

    def test_explicit_config_path_wins_over_vault_root(self, tmp_path):
        vault = make_vault(tmp_path / "vault", {"log_dir": "ignored"})
        other = tmp_path / "other.json"
        other.write_text(json.dumps({"log_dir": "chosen"}), encoding="utf-8")
        assert load_config(vault, config_path=other)["log_dir"] == "chosen"

    def test_malformed_json_raises(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        (vault / "vault.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_config(vault)

    def test_non_object_top_level_raises(self, tmp_path):
        vault = make_vault(tmp_path / "vault")
        (vault / "vault.json").write_text('["a", "list"]', encoding="utf-8")
        with pytest.raises(ValueError):
            load_config(vault)


class TestIsSkippedDir:
    def test_hidden_dir_is_skipped_by_default(self):
        assert is_skipped_dir(".pytest_cache", DEFAULTS)
        assert is_skipped_dir(".some-future-tool-cache", DEFAULTS)

    def test_named_non_hidden_dir_is_skipped(self):
        assert is_skipped_dir("node_modules", DEFAULTS)
        assert is_skipped_dir("__pycache__", DEFAULTS)

    def test_ordinary_dir_is_not_skipped(self):
        assert not is_skipped_dir("02-Projects", DEFAULTS)

    def test_hidden_dirs_can_be_opted_back_in(self):
        config = {**DEFAULTS, "skip_hidden_dirs": False, "skip_dirs": [".git"]}
        assert is_skipped_dir(".git", config)
        assert not is_skipped_dir(".pytest_cache", config)


class TestPruneDirs:
    def test_filters_in_place_and_preserves_order(self):
        dirnames = ["00-Inbox", ".git", "02-Projects", "node_modules", "Log"]
        prune_dirs(dirnames, DEFAULTS)
        assert dirnames == ["00-Inbox", "02-Projects", "Log"]


class TestDateFromText:
    def test_plain_eight_digit_date(self):
        assert date_from_text("20220411-notes.md") == "20220411"

    def test_twelve_digit_stamp_yields_its_date_part(self):
        assert date_from_text("202605261954-spike-doc.md") == "20260526"

    def test_twelve_digit_stamp_beats_an_embedded_eight_digit_date(self):
        """The range-summary case: the file's own stamp wins over the dates of
        the period it covers."""
        assert date_from_text("202605291147-20250529-20260529-range-summary.md") == "20260529"

    def test_impossible_calendar_date_is_rejected(self):
        assert date_from_text("20260231-notes.md") is None

    def test_out_of_range_eight_digit_run_is_rejected(self):
        assert date_from_text("99999999-notes.md") is None

    def test_calendar_valid_but_implausible_year_is_rejected(self):
        """8 digits that parse as a date can still be an identifier."""
        assert date_from_text("04-Archive/something/12340506-note.md") is None

    def test_year_bounds_are_inclusive(self):
        assert date_from_text("19900101-note.md") == "19900101"
        assert date_from_text("20991231-note.md") == "20991231"

    def test_invalid_twelve_digit_run_falls_through(self):
        assert date_from_text("999999999999-notes.md") is None

    def test_nine_digit_run_is_not_a_date(self):
        assert date_from_text("202511208-typo.md") is None

    def test_no_digits_returns_none(self):
        assert date_from_text("notes.md") is None


class TestTag:
    def test_composes_prefix_and_value(self):
        assert tag(DEFAULTS, "created", "20260808") == "created/20260808"
        assert tag(DEFAULTS, "type", "daily-summary") == "type/daily-summary"

    def test_unknown_prefix_raises(self):
        with pytest.raises(KeyError):
            tag(DEFAULTS, "nope", "x")

    def test_honours_a_renamed_prefix(self, tmp_path):
        vault = make_vault(tmp_path / "vault", {"tag_prefixes": {"created": "made-on/"}})
        config = load_config(vault)
        assert tag(config, "created", "20260808") == "made-on/20260808"
        assert tag(config, "updated", "20260808") == "updated/20260808"
