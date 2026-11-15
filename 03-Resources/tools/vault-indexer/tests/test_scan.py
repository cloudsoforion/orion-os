"""
Tests for scan_vault() — filesystem + in-memory DB.
"""
import os
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from vault_indexer import scan_vault, open_db, format_daily_summary


def _set_mtime(p: Path, d: date):
    """Set a file's mtime to local noon on date d (epoch seconds)."""
    ts = time.mktime(d.timetuple()) + 12 * 3600
    os.utime(p, (ts, ts))


@pytest.fixture
def tmp_vault(tmp_path):
    """A minimal vault with a few markdown files."""
    (tmp_path / "vault.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "file-a.md").write_text("# Note A\n## Section One\n")
    (tmp_path / "notes" / "file-b.md").write_text("# Note B\n")
    (tmp_path / ".trash").mkdir()
    (tmp_path / ".trash" / "deleted.md").write_text("# Deleted\n")
    return tmp_path


@pytest.fixture
def mem_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE files (
            path TEXT NOT NULL PRIMARY KEY,
            inode INTEGER NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            extracted TEXT,
            indexed_at REAL NOT NULL,
            content_hash TEXT,
            content_mtime REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_inode ON files(inode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mtime ON files(mtime)")
    conn.commit()
    return conn


class TestScanVault:
    def test_new_files_are_inserted(self, tmp_vault, mem_db):
        stats = scan_vault(tmp_vault, mem_db)
        assert stats["new"] == 2
        assert stats["updated"] == 0
        rows = mem_db.execute("SELECT path FROM files").fetchall()
        paths = {r[0] for r in rows}
        assert "notes/file-a.md" in paths
        assert "notes/file-b.md" in paths

    def test_trash_is_skipped(self, tmp_vault, mem_db):
        scan_vault(tmp_vault, mem_db)
        paths = {r[0] for r in mem_db.execute("SELECT path FROM files").fetchall()}
        assert not any(".trash" in p for p in paths)

    def test_unchanged_files_are_skipped(self, tmp_vault, mem_db):
        scan_vault(tmp_vault, mem_db)
        stats = scan_vault(tmp_vault, mem_db)
        assert stats["unchanged"] == 2
        assert stats["new"] == 0
        assert stats["updated"] == 0

    def test_modified_file_is_updated(self, tmp_vault, mem_db):
        scan_vault(tmp_vault, mem_db)
        time.sleep(0.01)
        # Touch the file to update mtime
        p = tmp_vault / "notes" / "file-a.md"
        p.write_text("# Note A Modified\n## New Section\n")
        stats = scan_vault(tmp_vault, mem_db)
        assert stats["updated"] == 1
        assert stats["unchanged"] == 1

    def test_new_file_after_initial_scan(self, tmp_vault, mem_db):
        scan_vault(tmp_vault, mem_db)
        (tmp_vault / "notes" / "file-c.md").write_text("# Note C\n")
        stats = scan_vault(tmp_vault, mem_db)
        assert stats["new"] == 1

    def test_move_detection(self, tmp_vault, mem_db):
        scan_vault(tmp_vault, mem_db)
        # Move file-b to a new location
        src = tmp_vault / "notes" / "file-b.md"
        dst = tmp_vault / "notes" / "file-b-renamed.md"
        os.rename(src, dst)
        stats = scan_vault(tmp_vault, mem_db)
        assert stats["moved"] == 1
        paths = {r[0] for r in mem_db.execute("SELECT path FROM files").fetchall()}
        assert "notes/file-b-renamed.md" in paths
        assert "notes/file-b.md" not in paths

    def test_non_markdown_files_skipped(self, tmp_vault, mem_db):
        (tmp_vault / "notes" / "script.py").write_text("print('hello')")
        (tmp_vault / "notes" / "config.yaml").write_text("key: value")
        scan_vault(tmp_vault, mem_db)
        paths = {r[0] for r in mem_db.execute("SELECT path FROM files").fetchall()}
        assert not any(p.endswith(".py") or p.endswith(".yaml") for p in paths)

    def test_folder_filter(self, tmp_vault, mem_db):
        (tmp_vault / "other").mkdir()
        (tmp_vault / "other" / "excluded.md").write_text("# Excluded\n")
        scan_vault(tmp_vault, mem_db, folders=["notes"])
        paths = {r[0] for r in mem_db.execute("SELECT path FROM files").fetchall()}
        assert not any("other" in p for p in paths)
        assert any("notes" in p for p in paths)

    def test_extracted_json_stored(self, tmp_vault, mem_db):
        scan_vault(tmp_vault, mem_db)
        row = mem_db.execute(
            "SELECT extracted FROM files WHERE path = 'notes/file-a.md'"
        ).fetchone()
        assert row is not None
        import json
        ext = json.loads(row[0])
        assert ext["title"] == "Note A"
        assert any(h["text"] == "Section One" for h in ext["headings"])


class TestDailySummaryExcludesMovedOnlyFiles:
    """A file that was only *moved* (content unchanged) must not appear as
    activity in the daily summary for the move day — even though the move
    bumped its filesystem mtime (as the 2026-07-07 reorg did to ~120 files)."""

    def test_moved_only_file_excluded_from_daily_summary(self, tmp_vault, mem_db):
        p = tmp_vault / "notes" / "file-a.md"
        content_day = date(2026, 1, 1)
        _set_mtime(p, content_day)
        scan_vault(tmp_vault, mem_db)

        # Simulate an Obsidian move on a later day: path changes, content
        # identical, but the move bumps mtime to move-time.
        move_day = date(2026, 6, 15)
        (tmp_vault / "notes" / "moved").mkdir()
        dst = tmp_vault / "notes" / "moved" / "file-a.md"
        os.rename(p, dst)
        _set_mtime(dst, move_day)
        stats = scan_vault(tmp_vault, mem_db)
        assert stats["moved"] == 1

        summary = format_daily_summary(mem_db, move_day, None)
        assert "file-a" not in summary, "moved-only file leaked into the daily summary"

    def test_content_edit_still_appears(self, tmp_vault, mem_db):
        """Guard: a genuine content edit on the day still shows up."""
        scan_vault(tmp_vault, mem_db)
        edit_day = date(2026, 6, 15)
        p = tmp_vault / "notes" / "file-b.md"
        p.write_text("# Note B edited\n## New Section\n")
        _set_mtime(p, edit_day)
        scan_vault(tmp_vault, mem_db)

        summary = format_daily_summary(mem_db, edit_day, None)
        assert "file-b" in summary

    def test_moved_and_edited_file_still_appears(self, tmp_vault, mem_db):
        """Guard: moved *and* edited the same day → content changed → shows."""
        p = tmp_vault / "notes" / "file-a.md"
        _set_mtime(p, date(2026, 1, 1))
        scan_vault(tmp_vault, mem_db)

        move_day = date(2026, 6, 15)
        (tmp_vault / "notes" / "moved").mkdir()
        dst = tmp_vault / "notes" / "moved" / "file-a.md"
        os.rename(p, dst)
        dst.write_text("# Note A rewritten\n## Different\n")  # content changed too
        _set_mtime(dst, move_day)
        scan_vault(tmp_vault, mem_db)

        summary = format_daily_summary(mem_db, move_day, None)
        assert "file-a" in summary
