"""
Tests for embed.prune_orphans + run_embed wiring.

prune_orphans removes embeddings whose path no longer maps to a live file
(e.g. after a folder rename), so they don't linger and skew coverage.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import embed


class TestPruneOrphans:
    def test_removes_stale_keeps_valid(self, make_db):
        conn = make_db(["a.md", "b.md"], ["a.md", "b.md", "old/a.md", "old/b.md"])
        removed = embed.prune_orphans(conn)
        assert removed == 2
        remaining = {r[0] for r in conn.execute("SELECT path FROM embeddings")}
        assert remaining == {"a.md", "b.md"}

    def test_noop_when_clean(self, make_db):
        conn = make_db(["a.md"], ["a.md"])
        assert embed.prune_orphans(conn) == 0
        assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 1

    def test_all_orphans(self, make_db):
        conn = make_db(["a.md"], ["x.md", "y.md"])
        assert embed.prune_orphans(conn) == 2
        assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0


class TestRunEmbedPrunes:
    def test_run_embed_embeds_new_and_prunes_stale(self, make_db, monkeypatch):
        # files has the current path; embeddings holds only a stale path.
        conn = make_db(["a.md"], ["old/a.md"])
        monkeypatch.setattr(embed, "embed", lambda text: [0.1, 0.2, 0.3])
        stats = embed.run_embed(conn, reembed=False)
        paths = {r[0] for r in conn.execute("SELECT path FROM embeddings")}
        assert paths == {"a.md"}          # new embedded, stale pruned
        assert stats["pruned"] == 1
        assert stats["embedded"] == 1
