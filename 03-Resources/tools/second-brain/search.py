#!/usr/bin/env python3
"""
search.py — semantic search over the vault using stored embeddings

Usage:
  python search.py "cluster upgrade rollback plan"
  python search.py "alerting integration setup" --top 10
  python search.py "credential rotation" --json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_TOP_K, default_db_path, embed, score_rows  # noqa: E402


def search(db_path: Path, query: str, top_k: int) -> list[dict]:
    """Every embedding scored, no relevance floor — this is the exploratory CLI,
    so a weak best match is more useful than an empty result."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT path, vector FROM embeddings").fetchall()
    finally:
        conn.close()
    return score_rows(rows, embed(query))[:top_k]


def main():
    parser = argparse.ArgumentParser(description="Semantic search over vault embeddings")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_K, help=f"Number of results (default: {DEFAULT_TOP_K})")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    parser.add_argument("--db", type=Path, help="DB path (default: ../vault-indexer/vault-index.db)")
    args = parser.parse_args()

    db_path = args.db or default_db_path()

    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    results = search(db_path, args.query, args.top)

    if args.as_json:
        print(json.dumps(results, indent=2))
        return

    for r in results:
        link = str(Path(r["path"]).with_suffix(""))
        print(f"[[{link}]]  ({r['score']:.3f})")


if __name__ == "__main__":
    main()
