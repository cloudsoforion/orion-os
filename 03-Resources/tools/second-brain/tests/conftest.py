"""Shared fixtures for second-brain tests."""
import sqlite3

import pytest


def _make_db(files, embedding_paths):
    """In-memory DB mirroring the vault index schema (files + embeddings tables).

    `files`           — current, post-index paths
    `embedding_paths` — paths the embeddings are keyed on (may be stale after a reorg)
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE files (path TEXT PRIMARY KEY, extracted TEXT)")
    conn.execute(
        "CREATE TABLE embeddings (path TEXT PRIMARY KEY, model TEXT, vector TEXT, embedded_at REAL)"
    )
    conn.executemany(
        "INSERT INTO files (path, extracted) VALUES (?, '{}')", [(f,) for f in files]
    )
    conn.executemany(
        "INSERT INTO embeddings (path, model, vector, embedded_at) VALUES (?, 'm', '[]', 0)",
        [(p,) for p in embedding_paths],
    )
    conn.commit()
    return conn


@pytest.fixture
def make_db():
    """Returns the DB factory: make_db(files, embedding_paths) -> sqlite3.Connection."""
    return _make_db
