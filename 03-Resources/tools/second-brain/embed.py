#!/usr/bin/env python3
"""
embed.py — generate and store embeddings for all indexed vault files

Reads from vault-index.db (produced by vault_indexer.py), generates embeddings
via Ollama, and stores them back in the same DB. Endpoint, model, and DB
location come from common.py (overridable via SECOND_BRAIN_* env vars).

Usage:
  python embed.py               # embed all un-embedded files
  python embed.py --reembed     # re-embed everything (after model change)
  python embed.py --stats       # show embedding coverage
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DB_NAME, EMBED_MODEL, default_db_path, embed  # noqa: E402

BATCH_SIZE = 50


def get_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            path     TEXT NOT NULL PRIMARY KEY,
            model    TEXT NOT NULL,
            vector   TEXT NOT NULL,
            embedded_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS emb_idx_path ON embeddings(path)")
    conn.commit()
    return conn


def prune_orphans(conn: sqlite3.Connection) -> int:
    """Delete embeddings whose path no longer maps to a file in the index.

    After a bulk move/rename the `files` table gets the new paths but old
    embeddings linger under the stale paths — orphaned rows that can never join
    to a file and silently inflate the embedded count. Returns the number removed.
    """
    cur = conn.execute("DELETE FROM embeddings WHERE path NOT IN (SELECT path FROM files)")
    conn.commit()
    return cur.rowcount


def text_for_embedding(path: str, extracted_json: str) -> str:
    """Build the text we embed: path + title + headings. Short and signal-rich."""
    ext = json.loads(extracted_json) if extracted_json else {}
    parts = [path]
    if ext.get("title"):
        parts.append(ext["title"])
    headings = [h["text"] for h in ext.get("headings", []) if h.get("text")]
    if headings:
        parts.extend(headings[:10])
    tags = ext.get("tags", [])
    if tags:
        parts.extend(tags[:5])
    return " | ".join(parts)


def run_embed(conn: sqlite3.Connection, reembed: bool) -> dict:
    stats = {"total": 0, "embedded": 0, "skipped": 0, "errors": 0}

    files = conn.execute("SELECT path, extracted FROM files").fetchall()
    stats["total"] = len(files)

    if not reembed:
        already = {row[0] for row in conn.execute("SELECT path FROM embeddings").fetchall()}
    else:
        already = set()
        conn.execute("DELETE FROM embeddings")
        conn.commit()

    import time
    todo = [(p, e) for p, e in files if p not in already]
    print(f"Files to embed: {len(todo)} / {len(files)}", file=sys.stderr)

    for i, (path, extracted_json) in enumerate(todo):
        text = text_for_embedding(path, extracted_json)
        try:
            vector = embed(text)
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (path, model, vector, embedded_at) VALUES (?,?,?,?)",
                (path, EMBED_MODEL, json.dumps(vector), time.time()),
            )
            stats["embedded"] += 1
        except Exception as e:
            print(f"  ERROR {path}: {e}", file=sys.stderr)
            stats["errors"] += 1

        if (i + 1) % BATCH_SIZE == 0:
            conn.commit()
            print(f"  {i + 1}/{len(todo)}...", file=sys.stderr)

    conn.commit()
    stats["skipped"] = len(already)
    stats["pruned"] = prune_orphans(conn)
    return stats


def main():
    parser = argparse.ArgumentParser(description="Generate vault embeddings via Ollama")
    parser.add_argument("--reembed", action="store_true", help="Re-embed all files")
    parser.add_argument("--stats", action="store_true", help="Show embedding coverage and exit")
    parser.add_argument("--db", type=Path, help="DB path (default: ../vault-indexer/vault-index.db)")
    args = parser.parse_args()

    db_path = args.db or default_db_path()

    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        print("Run vault_indexer.py index first.", file=sys.stderr)
        sys.exit(1)

    conn = get_db(db_path)

    if args.stats:
        total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        embedded = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        usable = conn.execute(
            "SELECT COUNT(*) FROM embeddings e JOIN files f ON e.path = f.path"
        ).fetchone()[0]
        print(f"Files indexed:        {total}")
        print(f"Embeddings stored:    {embedded}")
        print(f"Usable (join files):  {usable}")
        print(f"Missing:              {total - usable}")
        print(f"Orphaned (stale path):{embedded - usable}")
        return

    stats = run_embed(conn, reembed=args.reembed)
    print(
        f"Done. embedded={stats['embedded']} skipped={stats['skipped']} "
        f"pruned={stats['pruned']} errors={stats['errors']}",
        file=sys.stderr,
    )
    conn.close()


if __name__ == "__main__":
    main()
