"""
Tests for index-stats reporting (common.py, surfaced by mcp_server's get_vault_stats).

`get_vault_stats` must report *usable* coverage — embeddings that join to a live
file — not the raw embeddings row count. Otherwise stale-path embeddings (e.g.
after a folder reorg) hide as a false ~100% while search is actually broken.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
# Imported from common, not mcp_server: the stats maths needs no `mcp` package,
# so this suite still runs on a machine without the MCP dependency installed.
from common import compute_index_stats, format_index_stats


class TestComputeIndexStats:
    def test_all_valid(self, make_db):
        conn = make_db(["a.md", "b.md"], ["a.md", "b.md"])
        s = compute_index_stats(conn)
        assert s["total"] == 2
        assert s["usable"] == 2
        assert s["orphaned"] == 0
        assert s["coverage"] == 100.0

    def test_stale_paths_do_not_count_as_coverage(self, make_db):
        # The reorg scenario: 2 live files; 1 valid embedding + 3 stale-path ones.
        conn = make_db(
            ["new/a.md", "new/b.md"],
            ["new/a.md", "old/a.md", "old/b.md", "old/c.md"],
        )
        s = compute_index_stats(conn)
        assert s["total"] == 2
        assert s["usable"] == 1          # only new/a.md joins to a live file
        assert s["orphaned"] == 3
        assert s["coverage"] == 50.0     # 1/2 usable, NOT 4 embeddings / 2 files

    def test_no_files_is_zero_not_error(self, make_db):
        conn = make_db([], ["x.md"])
        s = compute_index_stats(conn)
        assert s["total"] == 0
        assert s["coverage"] == 0.0      # no ZeroDivisionError

    def test_partial_coverage(self, make_db):
        conn = make_db(["a.md", "b.md", "c.md", "d.md"], ["a.md", "b.md"])
        s = compute_index_stats(conn)
        assert s["usable"] == 2
        assert s["orphaned"] == 0
        assert s["coverage"] == 50.0


class TestFormatIndexStats:
    def test_warns_on_orphans(self):
        out = format_index_stats({"total": 10, "usable": 2, "orphaned": 8, "coverage": 20.0})
        assert "20%" in out
        assert "stale" in out.lower()
        assert "reembed" in out.lower()

    def test_clean_when_no_orphans(self):
        out = format_index_stats({"total": 10, "usable": 10, "orphaned": 0, "coverage": 100.0})
        assert "100%" in out
        assert "stale" not in out.lower()
