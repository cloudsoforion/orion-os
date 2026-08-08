"""
Tests for pure functions in vault_indexer.py.
These have no filesystem or DB dependencies.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from vault_indexer import parse_frontmatter_tags, extract_sections, work_group, path_date, week_monday


# ---------------------------------------------------------------------------
# week_monday — ops-journal week-folder name
# ---------------------------------------------------------------------------

class TestWeekMonday:
    def test_monday_maps_to_itself(self):
        assert week_monday(date(2026, 7, 13)) == date(2026, 7, 13)

    def test_midweek_maps_back_to_monday(self):
        # Fri Jul 10 2026 -> Mon Jul 6 2026
        assert week_monday(date(2026, 7, 10)) == date(2026, 7, 6)

    def test_sunday_maps_to_its_own_monday(self):
        # Sun Jul 12 2026 -> Mon Jul 6 2026 (Sunday is the last day of the Mon-start week)
        assert week_monday(date(2026, 7, 12)) == date(2026, 7, 6)

    def test_crosses_month_boundary(self):
        # Wed Jul 1 2026 -> Mon Jun 29 2026
        assert week_monday(date(2026, 7, 1)) == date(2026, 6, 29)


# ---------------------------------------------------------------------------
# parse_frontmatter_tags
# ---------------------------------------------------------------------------

class TestParseFrontmatterTags:
    def test_yaml_list(self):
        fm = 'tags:\n  - "#created/20260522"\n  - "#work"\n  - "#kubecon"\n'
        assert parse_frontmatter_tags(fm) == ["created/20260522", "work", "kubecon"]

    def test_inline_list(self):
        fm = 'tags: ["#created/20260522", "#work"]\n'
        assert parse_frontmatter_tags(fm) == ["created/20260522", "work"]

    def test_tags_without_hash(self):
        fm = 'tags:\n  - created/20260522\n  - work\n'
        assert parse_frontmatter_tags(fm) == ["created/20260522", "work"]

    def test_empty_frontmatter(self):
        assert parse_frontmatter_tags("") == []

    def test_no_tags_key(self):
        assert parse_frontmatter_tags("created: 20260522\nauthor: dalorion\n") == []

    def test_tags_block_ends_at_non_indented_line(self):
        fm = 'tags:\n  - "#work"\nauthor: dalorion\n'
        assert parse_frontmatter_tags(fm) == ["work"]

    def test_tags_with_quoted_values(self):
        fm = 'tags:\n  - "created/20260522"\n  - "type/daily-summary"\n'
        assert parse_frontmatter_tags(fm) == ["created/20260522", "type/daily-summary"]

    def test_unindented_tag_list(self):
        # Obsidian sometimes writes tags without indentation
        fm = 'tags:\n- created/20220411\n- updated/20250922\n'
        assert parse_frontmatter_tags(fm) == ["created/20220411", "updated/20250922"]


# ---------------------------------------------------------------------------
# extract_sections
# ---------------------------------------------------------------------------

class TestExtractSections:
    def test_title_from_h1(self):
        content = "---\ntags: []\n---\n# My Great Note\n\nsome body\n"
        result = extract_sections(content, "some-path/my-note.md")
        assert result["title"] == "My Great Note"

    def test_title_falls_back_to_stem(self):
        content = "no heading here\n"
        result = extract_sections(content, "folder/my-note.md")
        assert result["title"] == "my-note"

    def test_headings_extracted(self):
        content = "# Title\n## Section One\n### Sub\n## Section Two\n"
        result = extract_sections(content, "note.md")
        h2s = [h for h in result["headings"] if h["level"] == 2]
        assert [h["text"] for h in h2s] == ["Section One", "Section Two"]

    def test_frontmatter_stripped_from_body(self):
        content = "---\ntags:\n  - \"#work\"\n---\n## Real Heading\n"
        result = extract_sections(content, "note.md")
        assert any(h["text"] == "Real Heading" for h in result["headings"])

    def test_tags_extracted_from_frontmatter(self):
        content = "---\ntags:\n  - \"#created/20260522\"\n  - \"#work\"\n---\n# Title\n"
        result = extract_sections(content, "note.md")
        assert "created/20260522" in result["tags"]
        assert "work" in result["tags"]

    def test_empty_content(self):
        result = extract_sections("", "note.md")
        assert result["title"] == "note"
        assert result["headings"] == []
        assert result["tags"] == []

    def test_no_frontmatter(self):
        content = "# Just a Title\n## A Section\n"
        result = extract_sections(content, "note.md")
        assert result["title"] == "Just a Title"
        assert len(result["headings"]) == 2


# ---------------------------------------------------------------------------
# work_group
# ---------------------------------------------------------------------------

class TestWorkGroup:
    def test_dated_work_folder(self):
        assert work_group("00-Inbox/work/20260519-enabling-WAF/file.md") == "20260519-enabling-WAF"

    def test_dated_project_folder(self):
        assert work_group("02-Projects/Create-GTM-Clusters/20260511-deploying-maverick/file.md") == "20260511-deploying-maverick"

    def test_flat_inbox_file(self):
        # No YYYYMMDD- component — falls back to parent dir
        result = work_group("00-Inbox/some-note.md")
        assert result == "00-Inbox"

    def test_nested_without_date(self):
        result = work_group("06-Archive/platform/something.md")
        assert result == "06-Archive/platform"

    def test_daily_note_with_date_in_filename(self):
        # Filename starts with date but is not a folder — should still match
        result = work_group("00-Inbox/wtf-am-i-doing/20260529-wtf-am-i-doing.md")
        assert result == "20260529-wtf-am-i-doing.md"

    def test_deeply_nested_dated_folder(self):
        result = work_group("02-Projects/smoking-section/EKS-1-33-Upgrade/20260225-deploy-to-prod/notes.md")
        assert result == "20260225-deploy-to-prod"


# ---------------------------------------------------------------------------
# path_date
# ---------------------------------------------------------------------------

class TestPathDate:
    def test_dated_folder(self):
        assert path_date("00-Inbox/work/20260519-enabling-WAF/file.md") == "20260519"

    def test_dated_filename(self):
        assert path_date("06-Archive/20260529-kubecon.md") == "20260529"

    def test_no_date(self):
        assert path_date("06-Archive/platform/something.md") is None

    def test_non_dated_prefix(self):
        # "00-Inbox" — 8-digit check fails (0019 not a plausible year)
        assert path_date("00-Inbox/regular-note.md") is None

    def test_date_in_middle_of_path(self):
        assert path_date("02-Projects/some-project/20260101-kickoff/notes.md") == "20260101"

    def test_date_at_end_of_folder_name(self):
        # Incident folders: OOMKilled-mcp-router-20231024
        assert path_date("06-Archive/incidents/production/OOMKilled-mcp-router-20231024/notes.md") == "20231024"

    def test_date_in_middle_of_filename(self):
        # e.g. notes-20220411.md
        assert path_date("06-Archive/applications/marketplace/notes-20220411.md") == "20220411"

    def test_date_embedded_in_long_folder(self):
        # cla-assistant-incident-20230228
        assert path_date("06-Archive/incidents/infra/cla-assistant-incident-20230228/cla-assistant-incident-20230228.md") == "20230228"

    def test_implausible_year_not_matched(self):
        # 8 digits but year 1234 is outside 1990-2099
        assert path_date("06-Archive/something/12340506-note.md") is None

    def test_implausible_month_not_matched(self):
        # month 13 is invalid
        assert path_date("06-Archive/something/20231301-note.md") is None

    def test_frontmatter_created_tag_fallback(self):
        import json
        extracted = json.dumps({"tags": ["created/20220411", "type/note"], "title": "shimmer notes", "headings": []})
        assert path_date("06-Archive/applications/marketplace/notes.md", extracted) == "20220411"

    def test_path_date_takes_priority_over_frontmatter(self):
        import json
        extracted = json.dumps({"tags": ["created/20220101"], "title": "t", "headings": []})
        assert path_date("06-Archive/20260519-some-note.md", extracted) == "20260519"

    def test_frontmatter_fallback_invalid_date_ignored(self):
        import json
        extracted = json.dumps({"tags": ["created/notadate", "work"], "title": "t", "headings": []})
        assert path_date("06-Archive/platform/note.md", extracted) is None

    def test_no_date_no_frontmatter(self):
        assert path_date("06-Archive/platform/note.md", None) is None

    def test_frontmatter_missing_tags_key(self):
        import json
        extracted = json.dumps({"title": "t", "headings": []})
        assert path_date("06-Archive/platform/note.md", extracted) is None
