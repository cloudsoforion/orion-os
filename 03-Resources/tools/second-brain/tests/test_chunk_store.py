#!/usr/bin/env python3
"""
test_chunk_store.py — the chunk-store contract in common.py.

Specification enforced here:

| Behaviour                                   | Expected                                      |
| ------------------------------------------- | --------------------------------------------- |
| `ensure_chunk_schema` on a fresh DB          | Creates `chunks` + its indexes, idempotently   |
| `ensure_chunk_schema` beside `embeddings`    | Leaves the legacy table untouched (additive)   |
| `retrieve_chunks` with no DB                 | Returns `[]` — never raises                    |
| `retrieve_chunks` with DB but no matrix      | Returns `[]` — never raises                    |
| `chunk_vectors_path`                         | Sidecar sits next to the DB                    |
| `normalise`                                  | Unit length; zero vector survives without NaN  |
| `format_chunk_hits`                          | Wikilink + score, heading when present, snippet |
| `format_chunk_hits` snippet                  | Collapsed whitespace, truncated with an ellipsis |

No network and no Ollama: every test here exercises bookkeeping, not embedding.
The retrieval maths itself needs a real matrix and is covered by the live
calibration run, not by unit tests.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from common import (  # noqa: E402
    chunk_vectors_path,
    ensure_chunk_schema,
    format_chunk_hits,
    normalise,
    retrieve_chunks,
)


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


class TestEnsureChunkSchema:
    def test_creates_chunks_table(self):
        conn = sqlite3.connect(":memory:")
        ensure_chunk_schema(conn)
        assert "chunks" in _tables(conn)

    def test_is_idempotent(self):
        conn = sqlite3.connect(":memory:")
        ensure_chunk_schema(conn)
        ensure_chunk_schema(conn)          # must not raise
        assert "chunks" in _tables(conn)

    def test_creates_expected_columns(self):
        conn = sqlite3.connect(":memory:")
        ensure_chunk_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(chunks)")}
        assert cols == {"id", "path", "ordinal", "heading", "body",
                        "vec_row", "model", "embedded_at"}

    def test_does_not_disturb_legacy_embeddings_table(self):
        # The migration is additive so retrieval can be rolled back.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE embeddings (path TEXT PRIMARY KEY, model TEXT, "
                     "vector TEXT, embedded_at REAL)")
        conn.execute("INSERT INTO embeddings VALUES ('a.md','m','[0.1]',1.0)")
        conn.commit()
        ensure_chunk_schema(conn)
        assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 1
        assert {"embeddings", "chunks"} <= _tables(conn)


class TestVectorsPath:
    def test_sidecar_sits_next_to_the_db(self, tmp_path):
        db = tmp_path / "sub" / "vault-index.db"
        db.parent.mkdir()
        db.touch()
        assert chunk_vectors_path(db) == db.parent / "vault-vectors.npy"


class TestNormalise:
    def test_returns_unit_length(self):
        import numpy as np
        out = normalise([3.0, 4.0])
        assert abs(float(np.linalg.norm(out)) - 1.0) < 1e-6

    def test_zero_vector_does_not_produce_nan(self):
        import numpy as np
        out = normalise([0.0, 0.0, 0.0])
        assert not np.isnan(np.asarray(out)).any()


class TestRetrieveChunksDegradesGracefully:
    def test_missing_db_returns_empty(self, tmp_path):
        # Must not raise: the hook sits in front of a human pressing enter.
        assert retrieve_chunks(tmp_path / "nope.db", "anything") == []

    def test_db_without_matrix_returns_empty(self, tmp_path):
        db = tmp_path / "vault-index.db"
        conn = sqlite3.connect(db)
        ensure_chunk_schema(conn)
        conn.close()
        assert retrieve_chunks(db, "anything") == []


class TestFormatChunkHits:
    def test_renders_wikilink_score_and_heading(self):
        out = format_chunk_hits([
            {"path": "01-Areas/x/note.md", "score": 0.812,
             "heading": "Findings > Root cause", "snippet": "the body"}])
        assert out[0] == "- [[01-Areas/x/note]] (0.81) — Findings > Root cause"
        assert out[1].strip() == "the body"

    def test_omits_heading_when_absent(self):
        out = format_chunk_hits([
            {"path": "a/b.md", "score": 0.5, "heading": "", "snippet": "text"}])
        assert out[0] == "- [[a/b]] (0.50)"

    def test_collapses_whitespace_in_snippet(self):
        out = format_chunk_hits([
            {"path": "a.md", "score": 0.5, "heading": "", "snippet": "one\n\ntwo   three"}])
        assert out[1].strip() == "one two three"

    def test_truncates_long_snippet_with_ellipsis(self):
        out = format_chunk_hits(
            [{"path": "a.md", "score": 0.5, "heading": "", "snippet": "x" * 500}],
            snippet_chars=50)
        assert out[1].strip().endswith("…")
        assert len(out[1].strip()) == 51

    def test_empty_results_render_nothing(self):
        assert format_chunk_hits([]) == []
