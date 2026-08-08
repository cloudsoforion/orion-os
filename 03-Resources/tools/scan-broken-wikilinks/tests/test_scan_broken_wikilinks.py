"""Specification for scan_broken_wikilinks.

The two behaviours that matter most, and why:

  1. **A repair never invents a wrong link.** A remap is applied only when the
     remapped target actually exists on disk. Rewriting toward a target that
     isn't there converts a visibly-broken link into a plausibly-broken one,
     which is strictly worse.
  2. **Dry-run writes nothing.** Both mutating modes (`--apply`,
     `--promote-basenames`) are opt-in; a bare run must leave the vault byte-identical.

Also pinned: escaped `\\|` alias pipes survive a rewrite (they are how an alias
lives inside a markdown table cell), fenced and inline code are not scanned
(`[[ -d "$dir" ]]` is bash, and reorg write-ups quote broken paths on purpose),
and the basename index covers non-`.md` files (Obsidian links attachments the
same way, and a markdown-only index called every one of those an invisible break).

Run:  python3 -m pytest tests/
No network. Never touches the live vault.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import vault_config  # noqa: E402
from scan_broken_wikilinks import (  # noqa: E402
    classify_basename_link,
    classify_path_link,
    index_basenames,
    is_excluded,
    mask_code,
    parse_remap,
    rebuild,
    resolves,
    scan,
    split_link,
    summarize,
    top_prefix,
)

CONFIG = vault_config.DEFAULTS


@pytest.fixture
def vault(tmp_path):
    """Throwaway vault root, marked with `.obsidian/` so discovery finds it."""
    root = tmp_path / "vault"
    (root / ".obsidian").mkdir(parents=True)
    return root


def add(vault: Path, rel: str, text: str = "") -> Path:
    """Create `rel` under `vault` with `text`, making parents as needed."""
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(vault, **kwargs):
    by_name = index_basenames(vault, CONFIG)
    return scan(vault, CONFIG, kwargs.pop("remap", {}), by_name, **kwargs)


class TestSplitLink:
    def test_plain_target(self):
        assert split_link("02-Projects/a") == ("02-Projects/a", "", "", False)

    def test_alias(self):
        assert split_link("path/a|Label") == ("path/a", "", "Label", False)

    def test_escaped_alias_pipe_is_flagged(self):
        assert split_link("path/a\\|Label") == ("path/a", "", "Label", True)

    def test_anchor(self):
        assert split_link("path/a#Heading") == ("path/a", "Heading", "", False)

    def test_anchor_and_alias(self):
        assert split_link("path/a#H|L") == ("path/a", "H", "L", False)

    def test_whitespace_stripped(self):
        assert split_link("  path/a  ")[0] == "path/a"


class TestRebuild:
    def test_round_trips_a_plain_link(self):
        assert rebuild("a/b", "", "", False, "") == "[[a/b]]"

    def test_preserves_embed_marker(self):
        assert rebuild("a/b", "", "", False, "!") == "![[a/b]]"

    def test_preserves_anchor_and_alias(self):
        assert rebuild("a/b", "H", "L", False, "") == "[[a/b#H|L]]"

    def test_preserves_an_escaped_pipe(self):
        """Unescaping here would break the markdown table the link sits in."""
        assert rebuild("a/b", "", "L", True, "") == "[[a/b\\|L]]"


class TestMaskCode:
    def test_marks_a_backtick_span(self):
        mask = mask_code("a `b` c")
        assert mask[2] and mask[3] and mask[4]
        assert not mask[0] and not mask[6]

    def test_no_backticks_masks_nothing(self):
        assert not any(mask_code("plain [[link]] here"))

    def test_unbalanced_backtick_masks_to_end_of_line(self):
        assert mask_code("a `b c")[-1]


class TestParseRemap:
    def test_parses_a_pair(self):
        assert parse_remap(["04-Projects/=02-Projects/"]) == {"04-Projects/": "02-Projects/"}

    def test_parses_several(self):
        got = parse_remap(["a/=b/", "c/=d/"])
        assert got == {"a/": "b/", "c/": "d/"}

    def test_rejects_a_spec_without_equals(self):
        with pytest.raises(ValueError):
            parse_remap(["04-Projects"])

    def test_rejects_an_empty_side(self):
        with pytest.raises(ValueError):
            parse_remap(["=b/"])


class TestResolves:
    def test_finds_an_md_file_without_the_extension(self, vault):
        add(vault, "02-Projects/a.md")
        assert resolves(vault, "02-Projects/a")

    def test_finds_a_non_md_file_by_full_name(self, vault):
        add(vault, "02-Projects/manifest.yaml")
        assert resolves(vault, "02-Projects/manifest.yaml")

    def test_missing_target_does_not_resolve(self, vault):
        assert not resolves(vault, "02-Projects/nope")

    def test_a_directory_is_not_a_link_target(self, vault):
        add(vault, "02-Projects/a.md")
        assert not resolves(vault, "02-Projects")


class TestClassifyPathLink:
    def test_existing_target_is_ok(self, vault):
        add(vault, "02-Projects/a.md")
        assert classify_path_link(vault, "02-Projects/a", {}) == ("ok", None)

    def test_broken_with_no_remap(self, vault):
        assert classify_path_link(vault, "02-Projects/a", {}) == ("no-remap", None)

    def test_remap_whose_target_exists_is_fixable(self, vault):
        add(vault, "02-Projects/a.md")
        got = classify_path_link(vault, "04-Projects/a", {"04-Projects/": "02-Projects/"})
        assert got == ("fixable", "02-Projects/a")

    def test_remap_whose_target_is_missing_is_not_fixable(self, vault):
        """The load-bearing case: never rewrite toward a target that isn't there."""
        got = classify_path_link(vault, "04-Projects/a", {"04-Projects/": "02-Projects/"})
        assert got[0] == "remap-no-target"

    def test_non_matching_prefix_falls_through_to_no_remap(self, vault):
        got = classify_path_link(vault, "09-old/a", {"04-Projects/": "02-Projects/"})
        assert got == ("no-remap", None)


class TestClassifyBasenameLink:
    def test_single_candidate_is_promotable(self):
        got = classify_basename_link("a", {"a": ["02-Projects/a.md"]})
        assert got == ("basename-single", "02-Projects/a")

    def test_multiple_candidates_are_ambiguous(self):
        got = classify_basename_link("a", {"a": ["x/a.md", "y/a.md"]})
        assert got == ("basename-ambiguous", None)

    def test_no_candidate_is_unresolved(self):
        assert classify_basename_link("a", {}) == ("basename-unresolved", None)

    def test_root_level_file_is_already_vault_absolute(self):
        """`[[AGENTS]]` names a root-level file, so the bare name IS the full path.
        AGENTS.md says so explicitly; flagging it would nag about correct links."""
        assert classify_basename_link("AGENTS", {"AGENTS": ["AGENTS.md"]}) == ("ok", None)

    def test_promotion_target_drops_the_extension(self):
        got = classify_basename_link("a.md", {"a.md": ["dir/a.md"]})
        assert got[1] == "dir/a"


class TestIsExcluded:
    def test_matching_glob_excludes(self):
        assert is_excluded("03-Resources/x-work-chronology/y.md", ["03-Resources/*work-chronology*"])

    def test_non_matching_glob_does_not(self):
        assert not is_excluded("02-Projects/a.md", ["03-Resources/*"])

    def test_no_patterns_excludes_nothing(self):
        assert not is_excluded("anything.md", [])


class TestIndexBasenames:
    def test_indexes_name_and_stem(self, vault):
        add(vault, "02-Projects/a.md")
        by_name = index_basenames(vault, CONFIG)
        assert by_name["a.md"] == ["02-Projects/a.md"]
        assert by_name["a"] == ["02-Projects/a.md"]

    def test_indexes_non_markdown_files(self, vault):
        """Obsidian links attachments the same way notes are linked."""
        add(vault, "02-Projects/manifest.yaml")
        assert index_basenames(vault, CONFIG)["manifest.yaml"] == ["02-Projects/manifest.yaml"]

    def test_skips_hidden_directories(self, vault):
        add(vault, ".pytest_cache/README.md")
        add(vault, "real.md")
        assert "README.md" not in index_basenames(vault, CONFIG)

    def test_records_every_candidate_for_a_collision(self, vault):
        add(vault, "x/README.md")
        add(vault, "y/README.md")
        assert sorted(index_basenames(vault, CONFIG)["README.md"]) == ["x/README.md", "y/README.md"]


class TestScanFindings:
    def test_resolving_link_is_not_reported(self, vault):
        add(vault, "02-Projects/a.md")
        add(vault, "note.md", "see [[02-Projects/a]]\n")
        findings, _ = run(vault)
        assert [f for f in findings if f["target"] == "02-Projects/a"] == []

    def test_broken_path_link_is_reported_with_file_and_line(self, vault):
        add(vault, "note.md", "line one\nsee [[02-Projects/gone]]\n")
        findings, _ = run(vault)
        broken = [f for f in findings if f["target"] == "02-Projects/gone"]
        assert broken[0]["file"] == "note.md"
        assert broken[0]["line"] == 2
        assert broken[0]["status"] == "no-remap"

    def test_links_in_a_fenced_block_are_ignored(self, vault):
        add(vault, "note.md", "```\n[[02-Projects/gone]]\n```\n")
        findings, _ = run(vault)
        assert findings == []

    def test_links_in_inline_code_are_ignored(self, vault):
        add(vault, "note.md", "bash: `[[ -d \"$dir\" ]]` and `[[02-Projects/gone]]`\n")
        findings, _ = run(vault)
        assert findings == []

    def test_excluded_files_are_not_scanned(self, vault):
        add(vault, "generated/chronology.md", "[[02-Projects/gone]]\n")
        findings, _ = run(vault, exclude=["generated/*"])
        assert findings == []

    def test_root_level_link_is_not_reported(self, vault):
        add(vault, "OrionOs.md")
        add(vault, "note.md", "see [[OrionOs]]\n")
        findings, _ = run(vault)
        assert findings == []

    def test_promote_basenames_leaves_a_root_level_link_alone(self, vault):
        add(vault, "OrionOs.md")
        note = add(vault, "note.md", "see [[OrionOs]]\n")
        _, written = run(vault, promote_basenames=True)
        assert written == 0
        assert "[[OrionOs]]" in note.read_text()

    def test_no_basenames_skips_the_basename_analysis(self, vault):
        add(vault, "note.md", "[[nowhere]]\n")
        findings, _ = run(vault, check_basenames=False)
        assert findings == []

    def test_embed_links_are_classified_too(self, vault):
        add(vault, "note.md", "![[02-Projects/gone]]\n")
        findings, _ = run(vault)
        assert findings[0]["target"] == "02-Projects/gone"


class TestScanDryRun:
    def test_writes_nothing_by_default(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "see [[04-Projects/a]]\n")
        original = note.read_text()
        _, written = run(vault, remap={"04-Projects/": "02-Projects/"})
        assert written == 0
        assert note.read_text() == original

    def test_promote_basenames_is_off_by_default(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "see [[a]]\n")
        original = note.read_text()
        run(vault)
        assert note.read_text() == original


class TestScanApply:
    def test_rewrites_a_fixable_link(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "see [[04-Projects/a]]\n")
        _, written = run(vault, remap={"04-Projects/": "02-Projects/"}, apply_repairs=True)
        assert written == 1
        assert "[[02-Projects/a]]" in note.read_text()

    def test_does_not_rewrite_when_the_remapped_target_is_missing(self, vault):
        note = add(vault, "note.md", "see [[04-Projects/a]]\n")
        _, written = run(vault, remap={"04-Projects/": "02-Projects/"}, apply_repairs=True)
        assert written == 0
        assert "[[04-Projects/a]]" in note.read_text()

    def test_preserves_anchor_and_alias_through_a_rewrite(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "see [[04-Projects/a#Heading|Label]]\n")
        run(vault, remap={"04-Projects/": "02-Projects/"}, apply_repairs=True)
        assert "[[02-Projects/a#Heading|Label]]" in note.read_text()

    def test_preserves_an_escaped_pipe_through_a_rewrite(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "| [[04-Projects/a\\|Label]] |\n")
        run(vault, remap={"04-Projects/": "02-Projects/"}, apply_repairs=True)
        assert "[[02-Projects/a\\|Label]]" in note.read_text()

    def test_preserves_the_embed_marker_through_a_rewrite(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "![[04-Projects/a]]\n")
        run(vault, remap={"04-Projects/": "02-Projects/"}, apply_repairs=True)
        assert "![[02-Projects/a]]" in note.read_text()


class TestPromoteBasenames:
    def test_promotes_an_unambiguous_basename_and_keeps_the_label(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "see [[a]]\n")
        _, written = run(vault, promote_basenames=True)
        assert written == 1
        assert "[[02-Projects/a|a]]" in note.read_text()

    def test_leaves_an_ambiguous_basename_alone(self, vault):
        add(vault, "x/a.md")
        add(vault, "y/a.md")
        note = add(vault, "note.md", "see [[a]]\n")
        _, written = run(vault, promote_basenames=True)
        assert written == 0
        assert "[[a]]" in note.read_text()

    def test_leaves_an_unresolved_basename_alone(self, vault):
        note = add(vault, "note.md", "see [[nowhere]]\n")
        _, written = run(vault, promote_basenames=True)
        assert written == 0
        assert "[[nowhere]]" in note.read_text()

    def test_keeps_an_existing_alias_rather_than_replacing_it(self, vault):
        add(vault, "02-Projects/a.md")
        note = add(vault, "note.md", "see [[a|Custom]]\n")
        run(vault, promote_basenames=True)
        assert "[[02-Projects/a|Custom]]" in note.read_text()


class TestSummarizeAndPrefix:
    def test_counts_by_status(self):
        findings = [{"status": "no-remap"}, {"status": "no-remap"}, {"status": "fixable"}]
        assert summarize(findings) == {"no-remap": 2, "fixable": 1}

    def test_empty_findings_summarize_to_nothing(self):
        assert summarize([]) == {}

    def test_top_prefix_of_a_path(self):
        assert top_prefix("02-Projects/a/b") == "02-Projects/"

    def test_top_prefix_of_a_basename(self):
        assert top_prefix("a") == "(basename)"
