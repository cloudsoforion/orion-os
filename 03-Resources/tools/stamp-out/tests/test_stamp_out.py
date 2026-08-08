"""Specification for stamp_out.

Added 2026-08-07 (remediation item 10 of
a dated compliance audit).

These tests restate the constraints the module docstring promises — in particular that only `.md`
files are rewritten, that code spans and fences are skipped, and that an escaped `\\|` alias pipe
survives a round trip. Those three are the ones that would silently corrupt a stamped copy.

Run:  python3 -m pytest tests/
No network. Never touches the live vault.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from stamp_out import (  # noqa: E402
    build_target,
    index_folder,
    mask_inline_code,
    split_link_body,
    write_report,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import vault_config  # noqa: E402


class TestSplitLinkBody:
    def test_plain_path(self):
        assert split_link_body("03-Resources/tools/README") == (
            "03-Resources/tools/README", None, None, False,
        )

    def test_alias_pipe(self):
        target, anchor, alias, escaped = split_link_body("path/to/note|Short Label")

        assert (target, anchor, alias, escaped) == ("path/to/note", None, "Short Label", False)

    def test_escaped_alias_pipe_is_flagged(self):
        """`\\|` is how a pipe survives inside a markdown table cell."""
        target, anchor, alias, escaped = split_link_body("path/to/note\\|Short Label")

        assert (target, alias, escaped) == ("path/to/note", "Short Label", True)

    def test_anchor_is_split_off(self):
        target, anchor, alias, _ = split_link_body("path/to/note#Some Heading")

        assert (target, anchor, alias) == ("path/to/note", "Some Heading", None)

    def test_anchor_and_alias_together(self):
        target, anchor, alias, _ = split_link_body("path/note#Heading|Label")

        assert (target, anchor, alias) == ("path/note", "Heading", "Label")

    def test_surrounding_whitespace_is_stripped(self):
        assert split_link_body("  path/to/note  ")[0] == "path/to/note"

    def test_only_first_pipe_separates(self):
        _, _, alias, _ = split_link_body("path|a|b")

        assert alias == "a|b"


class TestMaskInlineCode:
    def test_marks_span_between_backticks(self):
        mask = mask_inline_code("a `b` c")

        # backticks themselves and the char between them are masked
        assert mask[2] is True and mask[3] is True and mask[4] is True
        assert mask[0] is False and mask[6] is False

    def test_no_backticks_masks_nothing(self):
        assert not any(mask_inline_code("plain [[link]] here"))

    def test_unbalanced_backtick_masks_to_end_of_line(self):
        mask = mask_inline_code("a `b c")

        assert mask[-1] is True

    def test_empty_line(self):
        assert mask_inline_code("") == []


class TestBuildTarget:
    def test_md_suffix_is_dropped(self):
        assert build_target("02-Projects/copy", "notes/a.md") == "02-Projects/copy/notes/a"

    def test_non_md_keeps_suffix(self):
        assert build_target("02-Projects/copy", "manifests/x.yaml") == (
            "02-Projects/copy/manifests/x.yaml"
        )

    def test_root_level_file(self):
        assert build_target("dest", "a.md") == "dest/a"


class TestIndexFolder:
    """Returns (set of posix paths relative to root, basename/stem -> [rel paths])."""

    def test_paths_are_posix_and_relative_to_root(self, tmp_path):
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "a.md").write_text("x")
        (src / "sub" / "b.md").write_text("y")

        rel_paths, _ = index_folder(src)

        assert rel_paths == {"a.md", "sub/b.md"}

    def test_indexes_both_filename_and_stem(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.md").write_text("x")

        _, by_name = index_folder(src)

        assert by_name["a.md"] == ["a.md"]
        assert by_name["a"] == ["a.md"]

    def test_non_md_file_has_no_separate_stem_entry(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "Makefile").write_text("all:")

        _, by_name = index_folder(src)

        # stem == filename, so only one key is added
        assert by_name["Makefile"] == ["Makefile"]

    def test_skips_dot_directories(self, tmp_path):
        src = tmp_path / "src"
        (src / ".git").mkdir(parents=True)
        (src / ".git" / "config.md").write_text("should be skipped")
        (src / "real.md").write_text("keep")

        rel_paths, _ = index_folder(src)

        assert rel_paths == {"real.md"}

    def test_skips_dotfiles(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / ".DS_Store").write_text("junk")
        (src / "real.md").write_text("keep")

        rel_paths, _ = index_folder(src)

        assert rel_paths == {"real.md"}

    def test_basename_collision_records_both_paths(self, tmp_path):
        """This collision is exactly why bare-basename wikilinks are ambiguous."""
        src = tmp_path / "src"
        (src / "one").mkdir(parents=True)
        (src / "two").mkdir(parents=True)
        (src / "one" / "README.md").write_text("a")
        (src / "two" / "README.md").write_text("b")

        _, by_name = index_folder(src)

        assert sorted(by_name["README.md"]) == ["one/README.md", "two/README.md"]

    def test_skips_hidden_and_named_directories_from_config(self, tmp_path):
        src = tmp_path / "src"
        (src / ".pytest_cache").mkdir(parents=True)
        (src / ".pytest_cache" / "README.md").write_text("cache")
        (src / "node_modules").mkdir()
        (src / "node_modules" / "doc.md").write_text("dep")
        (src / "real.md").write_text("keep")

        rel_paths, _ = index_folder(src, vault_config.DEFAULTS)

        assert rel_paths == {"real.md"}


class TestWriteReportFrontmatter:
    """The report's frontmatter is vault vocabulary, so it comes from vault.json.

    It used to hardcode `author: Claude (claude-opus-5)` — crediting a specific
    model version for a file this script writes, and going stale every release.
    """

    def write(self, tmp_path, config=None, author=None):
        out = tmp_path / "report.md"
        write_report(out, tmp_path / "src", tmp_path / "dest", records=[],
                     ts="202608081200", dry_run=False, config=config, author=author)
        return out.read_text(encoding="utf-8")

    def test_author_comes_from_config(self, tmp_path):
        config = {**vault_config.DEFAULTS, "author": "A. Person"}
        assert "author: A. Person" in self.write(tmp_path, config)

    def test_explicit_author_wins_over_config(self, tmp_path):
        config = {**vault_config.DEFAULTS, "author": "A. Person"}
        assert "author: Someone Else" in self.write(tmp_path, config, author="Someone Else")

    def test_falls_back_to_tool_name_when_unset(self, tmp_path):
        config = {**vault_config.DEFAULTS, "author": ""}
        assert "author: stamp-out" in self.write(tmp_path, config)

    def test_no_hardcoded_model_name(self, tmp_path):
        assert "claude-opus" not in self.write(tmp_path)

    def test_tag_prefixes_come_from_config(self, tmp_path):
        config = {**vault_config.DEFAULTS,
                  "tag_prefixes": {**vault_config.DEFAULTS["tag_prefixes"],
                                   "created": "made-on/", "type": "kind/"},
                  "default_domain": "notes"}
        text = self.write(tmp_path, config)
        assert "  - made-on/" in text
        assert "  - kind/report" in text
        assert "  - domain/notes" in text


class TestCliHelp:
    """`--help` must not raise.

    It used to: TIMESTAMP_FMT (`%Y%m%d%H%M`) was interpolated into an argparse
    help string, and argparse runs %-formatting over help text, so building the
    help raised "unsupported format character 'Y'". Nothing exercised `--help`,
    so it went unnoticed — a tool whose own usage message crashes is worse than
    one with no usage message.
    """

    def test_help_builds_without_raising(self, capsys):
        import stamp_out
        with pytest.raises(SystemExit) as exc:
            stamp_out.main(["--help"])
        assert exc.value.code == 0
        assert "--timestamp" in capsys.readouterr().out
