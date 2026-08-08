"""
Tests for process_frontmatter.py.

## Date resolution logic

The goal is to stamp every file with the most accurate `created/YYYYMMDD` tag
possible, and to correct previously-stamped tags when a better (older) date is
found — without ever inventing one.

Decision table — evaluated in order:

| Filename has date? | Path has date? | Has created/ tag? | Git date | Action |
|--------------------|----------------|-------------------|----------|--------|
| Yes                | —              | Yes               | —        | Do nothing — filename date is authoritative |
| Yes                | —              | No                | —        | Stamp with filename date |
| No                 | Yes (older)    | Yes               | —        | Update tag to older path date |
| No                 | Yes (newer)    | Yes               | —        | Do nothing — existing tag is older/correct |
| No                 | Yes            | No                | —        | Stamp with path date |
| No                 | No             | Yes               | newer/absent | Do nothing — existing tag is older/correct |
| No                 | No             | Yes               | older    | Update tag to git date |
| No                 | No             | No                | present  | Stamp with git date |
| No                 | No             | No                | absent   | Skip, and say so |

"Filename date" = date in the bare filename (e.g. `notes-20220411.md`).
"Path date" = date in a parent folder component (e.g. `OOMKilled-20231024/notes.md`).
"Git date" = date of the first commit that added the file, supplied by the caller
from a single `git log` pass.

**The fallback is git, not the filesystem.** `min(st_ctime, st_mtime)` was removed
on 2026-08-08. Vault mtimes do not survive bulk copies
([[03-Resources/tools/20260605-filesystem-timestamps-unreliable]]); measured on the
live vault, mtime dated `CLAUDE.md` to 20260729 where git says 20250924. An
untracked file is skipped rather than dated from a timestamp that means
"last touched", because a fabricated date is indistinguishable from a real one
once it is written.

**Dry-run is the CLI default.** `process_file(..., dry_run=False)` still writes,
because the safety default belongs at the argparse layer where a human types it;
these tests exercise the writing path directly.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from process_frontmatter import (
    add_created_and_updated_tags,
    collect_markdown,
    date_from_text,
    extract_date_from_filename,
    get_existing_created_date,
    get_filename_date,
    get_path_date,
    git_add_dates,
    process_file,
    resolve_created_date,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import vault_config


# ---------------------------------------------------------------------------
# extract_date_from_filename
# ---------------------------------------------------------------------------

class TestExtractDateFromPath:
    def test_date_in_filename(self):
        assert extract_date_from_filename("20220411-notes.md") == "20220411"

    def test_date_at_end_of_filename(self):
        assert extract_date_from_filename("notes-20220411.md") == "20220411"

    def test_date_in_parent_folder_not_filename(self):
        full_path = "04-Archive/incidents/production/OOMKilled-mcp-router-20231024/notes.md"
        assert extract_date_from_filename(full_path) == "20231024"

    def test_date_in_grandparent_folder(self):
        full_path = "04-Archive/incidents/OOMKilled-mcp-router-20231024/logs/pod-events.md"
        assert extract_date_from_filename(full_path) == "20231024"

    def test_no_date_anywhere_returns_none(self):
        assert extract_date_from_filename("04-Archive/platform/notes.md") is None


# ---------------------------------------------------------------------------
# date_from_text — the YYYYMMDD / YYYYMMDDHHMM recogniser
# ---------------------------------------------------------------------------

class TestDateFromText:
    def test_plain_eight_digit_date(self):
        assert date_from_text("20220411-notes.md") == "20220411"

    def test_twelve_digit_stamp_yields_its_date_part(self):
        """283 notes in this vault use the %Y%m%d%H%M convention that
        stamp-out and vault-indexer write. A bare \\d{8} never matches one."""
        assert date_from_text("202605261954-spike-doc.md") == "20260526"

    def test_twelve_digit_stamp_beats_an_embedded_eight_digit_date(self):
        """The range-summary case: the file's own stamp wins over the dates
        of the period it covers."""
        name = "202605291147-20250529-20260529-range-summary.md"
        assert date_from_text(name) == "20260529"

    def test_invalid_eight_digit_run_is_rejected(self):
        assert date_from_text("99999999-notes.md") is None

    def test_invalid_twelve_digit_run_falls_through(self):
        # 9999 is not a month; no valid 8-digit run either
        assert date_from_text("999999999999-notes.md") is None

    def test_nine_digit_run_is_not_a_date(self):
        assert date_from_text("202511208-typo.md") is None

    def test_no_digits_returns_none(self):
        assert date_from_text("notes.md") is None


class TestFilenameAndPathDate:
    def test_filename_date_ignores_parent_folders(self):
        assert get_filename_date("incident-20231024/notes.md") is None

    def test_filename_stamp_is_recognised(self):
        assert get_filename_date("dir/202605261954-spike.md") == "20260526"

    def test_path_date_ignores_the_filename(self):
        assert get_path_date("dir/20231024-notes.md") is None

    def test_path_stamp_is_recognised(self):
        assert get_path_date("202606161028-broken-wikilinks-report/report.md") == "20260616"


# ---------------------------------------------------------------------------
# add_created_and_updated_tags — NameError regression
# ---------------------------------------------------------------------------

class TestAddCreatedAndUpdatedTags:
    def test_adds_both_tags_to_empty_frontmatter(self):
        result = add_created_and_updated_tags({}, "20220411", "20260605")
        assert "created/20220411" in result["tags"]
        assert "updated/20260605" in result["tags"]

    def test_adds_updated_tag_when_created_already_present(self):
        # Was: UnboundLocalError — updated_tag defined inside if block, used outside
        fm = {"tags": ["created/20220411"]}
        result = add_created_and_updated_tags(fm, "20220411", "20260605")
        assert any(t.startswith("updated/") for t in result["tags"])

    def test_does_not_duplicate_created_tag(self):
        fm = {"tags": ["created/20220411"]}
        result = add_created_and_updated_tags(fm, "20220411", "20260605")
        assert result["tags"].count("created/20220411") == 1

    def test_honours_renamed_tag_prefixes(self):
        config = {**vault_config.DEFAULTS,
                  "tag_prefixes": {**vault_config.DEFAULTS["tag_prefixes"],
                                   "created": "made-on/", "updated": "touched/"}}
        result = add_created_and_updated_tags({}, "20220411", "20260605", config=config)
        assert result["tags"] == ["made-on/20220411", "touched/20260605"]


class TestGetExistingCreatedDate:
    def test_reads_created_tag(self):
        assert get_existing_created_date({"tags": ["created/20220411"]}) == "20220411"

    def test_reads_created_scalar(self):
        assert get_existing_created_date({"created": "2022-04-11"}) == "20220411"

    def test_ignores_malformed_tag(self):
        assert get_existing_created_date({"tags": ["created/nope"]}) is None

    def test_honours_renamed_prefix(self):
        config = {**vault_config.DEFAULTS,
                  "tag_prefixes": {**vault_config.DEFAULTS["tag_prefixes"], "created": "made-on/"}}
        fm = {"tags": ["made-on/20220411"]}
        assert get_existing_created_date(fm, config) == "20220411"
        assert get_existing_created_date(fm) is None


# ---------------------------------------------------------------------------
# resolve_created_date — the decision table as pure values
# ---------------------------------------------------------------------------

class TestResolveCreatedDate:
    def test_filename_date_with_tag_is_noop(self):
        assert resolve_created_date("20220411-notes.md", "20220411", None) == (None, "noop")

    def test_filename_date_without_tag_stamps(self):
        assert resolve_created_date("20220411-notes.md", None, None) == ("20220411", "filename")

    def test_older_path_date_corrects_tag(self):
        got = resolve_created_date("incident-20231024/notes.md", "20241223", None)
        assert got == ("20231024", "path")

    def test_newer_path_date_is_noop(self):
        got = resolve_created_date("incident-20241223/notes.md", "20220411", None)
        assert got == (None, "noop")

    def test_path_date_without_tag_stamps(self):
        got = resolve_created_date("incident-20231024/notes.md", None, None)
        assert got == ("20231024", "path")

    def test_older_git_date_corrects_tag(self):
        assert resolve_created_date("notes.md", "20241223", "20240426") == ("20240426", "git")

    def test_newer_git_date_is_noop(self):
        assert resolve_created_date("notes.md", "20220411", "20260808") == (None, "noop")

    def test_absent_git_date_with_tag_is_noop(self):
        assert resolve_created_date("notes.md", "20220411", None) == (None, "noop")

    def test_git_date_without_tag_stamps(self):
        assert resolve_created_date("notes.md", None, "20250924") == ("20250924", "git")

    def test_untracked_and_undated_is_skipped(self):
        assert resolve_created_date("notes.md", None, None) == (None, "skip")


# ---------------------------------------------------------------------------
# process_file — decision table integration tests
# ---------------------------------------------------------------------------

class TestProcessFileDecisionTable:

    def test_filename_date_and_existing_tag_not_touched(self, tmp_path):
        f = tmp_path / "20220411-notes.md"
        f.write_text("---\ntags:\n- created/20220411\n---\n# Notes\n")
        assert process_file(str(f)) is None
        assert "created/20220411" in f.read_text()

    def test_filename_date_no_tag_stamps(self, tmp_path):
        f = tmp_path / "20220411-notes.md"
        f.write_text("# Notes\n")
        process_file(str(f))
        assert "created/20220411" in f.read_text()

    def test_parent_folder_date_corrects_newer_existing_tag(self, tmp_path):
        folder = tmp_path / "OOMKilled-mcp-router-20231024"
        folder.mkdir()
        f = folder / "notes.md"
        f.write_text("---\ntags:\n- created/20241223\n---\n# Notes\n")
        process_file(str(f))
        content = f.read_text()
        assert "created/20231024" in content
        assert "created/20241223" not in content

    def test_parent_folder_date_does_not_overwrite_older_existing_tag(self, tmp_path):
        folder = tmp_path / "incident-20241223"
        folder.mkdir()
        f = folder / "notes.md"
        f.write_text("---\ntags:\n- created/20220411\n---\n# Notes\n")
        assert process_file(str(f)) is None
        assert "created/20220411" in f.read_text()

    def test_parent_folder_date_stamps_when_no_tag(self, tmp_path):
        folder = tmp_path / "OOMKilled-mcp-router-20231024"
        folder.mkdir()
        f = folder / "notes.md"
        f.write_text("# Notes\n")
        process_file(str(f))
        assert "created/20231024" in f.read_text()

    def test_git_date_corrects_newer_existing_tag(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("---\ntags:\n- created/20991231\n---\n# Notes\n")
        process_file(str(f), git_date="20240426")
        content = f.read_text()
        assert "created/20240426" in content
        assert "created/20991231" not in content

    def test_git_date_does_not_overwrite_older_existing_tag(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("---\ntags:\n- created/20220411\n---\n# Notes\n")
        assert process_file(str(f), git_date="20260808") is None
        assert "created/20220411" in f.read_text()

    def test_git_date_stamps_when_no_tag(self, tmp_path):
        f = tmp_path / "notes.md"
        f.write_text("# Notes\n")
        process_file(str(f), git_date="20250924")
        assert "created/20250924" in f.read_text()

    def test_undated_untracked_file_is_skipped_not_guessed(self, tmp_path):
        """The mtime fallback used to stamp here. It must not come back."""
        f = tmp_path / "notes.md"
        original = "# Notes\n"
        f.write_text(original)
        result = process_file(str(f))
        assert result.startswith("Skipped (no date available)")
        assert f.read_text() == original


class TestProcessFileDryRun:
    def test_dry_run_writes_nothing(self, tmp_path):
        f = tmp_path / "20220411-notes.md"
        original = "# Notes\n"
        f.write_text(original)
        result = process_file(str(f), dry_run=True)
        assert result.startswith("Would add")
        assert f.read_text() == original


# ---------------------------------------------------------------------------
# collect_markdown — skip-dir handling comes from vault_config
# ---------------------------------------------------------------------------

class TestCollectMarkdown:
    def test_skips_hidden_directories(self, tmp_path):
        """The regression this closes: process_frontmatter walked into
        .pytest_cache/ and stamped 7 of its README.md files in the live vault."""
        (tmp_path / ".pytest_cache").mkdir()
        (tmp_path / ".pytest_cache" / "README.md").write_text("cache\n")
        (tmp_path / "02-Projects").mkdir()
        (tmp_path / "02-Projects" / "real.md").write_text("real\n")
        found = collect_markdown(tmp_path, vault_config.DEFAULTS)
        assert [p.name for p in found] == ["real.md"]

    def test_skips_named_directories(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "doc.md").write_text("x\n")
        (tmp_path / "keep.md").write_text("y\n")
        found = collect_markdown(tmp_path, vault_config.DEFAULTS)
        assert [p.name for p in found] == ["keep.md"]

    def test_hidden_dir_can_be_opted_in(self, tmp_path):
        (tmp_path / ".notes").mkdir()
        (tmp_path / ".notes" / "doc.md").write_text("x\n")
        config = {**vault_config.DEFAULTS, "skip_hidden_dirs": False, "skip_dirs": []}
        found = collect_markdown(tmp_path, config)
        assert [p.name for p in found] == ["doc.md"]


# ---------------------------------------------------------------------------
# git_add_dates — no network, a real throwaway repo
# ---------------------------------------------------------------------------

def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture
def tiny_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "Test")
    return repo


class TestGitAddDates:
    def test_returns_add_date_per_path(self, tiny_repo):
        (tiny_repo / "first.md").write_text("a\n")
        git(tiny_repo, "add", "first.md")
        git(tiny_repo, "commit", "-q", "-m", "one", "--date", "2024-04-26T10:00:00")
        env_second = tiny_repo / "second.md"
        env_second.write_text("b\n")
        git(tiny_repo, "add", "second.md")
        git(tiny_repo, "commit", "-q", "-m", "two", "--date", "2025-09-24T10:00:00")

        dates = git_add_dates(tiny_repo)
        assert dates["first.md"] == "20240426"
        assert dates["second.md"] == "20250924"

    def test_untracked_file_is_absent(self, tiny_repo):
        (tiny_repo / "tracked.md").write_text("a\n")
        git(tiny_repo, "add", "tracked.md")
        git(tiny_repo, "commit", "-q", "-m", "one")
        (tiny_repo / "untracked.md").write_text("b\n")
        assert "untracked.md" not in git_add_dates(tiny_repo)

    def test_earliest_date_wins_for_a_readded_path(self, tiny_repo):
        f = tiny_repo / "note.md"
        f.write_text("a\n")
        git(tiny_repo, "add", "note.md")
        git(tiny_repo, "commit", "-q", "-m", "add", "--date", "2024-04-26T10:00:00")
        git(tiny_repo, "rm", "-q", "note.md")
        git(tiny_repo, "commit", "-q", "-m", "remove", "--date", "2024-05-01T10:00:00")
        f.write_text("a\n")
        git(tiny_repo, "add", "note.md")
        git(tiny_repo, "commit", "-q", "-m", "re-add", "--date", "2026-01-01T10:00:00")
        assert git_add_dates(tiny_repo)["note.md"] == "20240426"

    def test_non_repo_returns_empty_map(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert git_add_dates(plain) == {}
