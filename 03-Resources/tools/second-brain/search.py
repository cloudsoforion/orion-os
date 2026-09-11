#!/usr/bin/env python3
"""
search.py — semantic search over the vault using stored embeddings

Searches chunked body text when the chunk store exists (`embed_chunks.py`),
printing the matching passage; falls back to the legacy title-only store
otherwise.

Usage:
  python search.py "cluster upgrade rollback plan"
  python search.py "alerting integration setup" --top 10
  python search.py "credential rotation" --json
  python search.py "istio sidecar" --no-archive     # skip 04-Archive/
  python search.py "old incident" --legacy          # force the title-only store
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DEFAULT_TOP_K,
    default_db_path,
    embed,
    format_chunk_hits,
    retrieve_chunks,
    score_rows,
)


def search(db_path: Path, query: str, top_k: int) -> list[dict]:
    """Every embedding scored, no relevance floor — this is the exploratory CLI,
    so a weak best match is more useful than an empty result.

    Returns [] when the legacy `embeddings` table does not exist. On a fresh vault
    only `embed_chunks.py` has ever run, so that table is absent and querying it
    raised OperationalError instead of reporting an empty index.
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT path, vector FROM embeddings").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return score_rows(rows, embed(query))[:top_k]


def main():
    parser = argparse.ArgumentParser(description="Semantic search over vault embeddings")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_K, help=f"Number of results (default: {DEFAULT_TOP_K})")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    parser.add_argument("--db", type=Path, help="DB path (default: ../vault-indexer/vault-index.db)")
    parser.add_argument("--no-archive", action="store_true",
                        help="Exclude 04-Archive/ (usually the largest, least current pillar)")
    parser.add_argument("--legacy", action="store_true",
                        help="Force the title-only store instead of chunked body text")
    args = parser.parse_args()

    db_path = args.db or default_db_path()

    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    if not args.legacy:
        exclude = ("04-Archive/",) if args.no_archive else ()
        chunked = retrieve_chunks(db_path, args.query, top_k=args.top,
                                  min_score=0.0, exclude_prefixes=exclude)
        if chunked:
            if args.as_json:
                print(json.dumps(chunked, indent=2))
            else:
                print("\n".join(format_chunk_hits(chunked)))
            return
        print("(no chunk store — falling back to the title-only index)", file=sys.stderr)

    results = search(db_path, args.query, args.top)

    if not results:
        print("No results. The index may be empty — run:\n"
              "  python3 ../vault-indexer/vault_indexer.py index\n"
              "  python3 embed_chunks.py", file=sys.stderr)
        if args.as_json:
            print("[]")
        return

    if args.as_json:
        print(json.dumps(results, indent=2))
        return

    for r in results:
        link = str(Path(r["path"]).with_suffix(""))
        print(f"[[{link}]]  ({r['score']:.3f})")


if __name__ == "__main__":
    main()
