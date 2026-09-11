#!/usr/bin/env python3
"""
embed_chunks.py — build the chunked body-text index for second-brain.

Reads every file in `vault-index.db`'s `files` table, splits it with `chunker.py`,
embeds each chunk via Ollama, and writes two artifacts side by side:

  * `chunks` table in vault-index.db — chunk metadata (path, ordinal, heading, body)
  * `vault-vectors.npy`             — float32 (N, 768) L2-normalised matrix

Why a sidecar matrix instead of a BLOB column: a 768-dim vector is ~15,900 chars as
JSON text and 3,072 bytes as float32. At ~40k chunks that is ~120 MB instead of
~600 MB, and `np.load(mmap_mode="r")` makes the per-prompt hook's startup cost a
page-cache hit rather than a full-matrix SQLite read.

This supersedes `embed.py` for retrieval but does NOT touch it: the old
`embeddings` table is left intact so retrieval can be rolled back by reverting
the callers. Run `embed.py --stats` for the legacy store.

Usage:
  python3 embed_chunks.py --dry-run             # count chunks, embed nothing, write nothing
  python3 embed_chunks.py --limit 200           # small real run, for a smoke test
  python3 embed_chunks.py                       # full rebuild (minutes; scales with vault size)
  python3 embed_chunks.py --stats               # what is in the chunk store now
  python3 embed_chunks.py --db /path/to/other/vault-index.db
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chunker import DEFAULT_MAX_CHUNKS, DEFAULT_TARGET_CHARS, chunk_markdown  # noqa: E402
from common import (  # noqa: E402
    EMBED_MODEL,
    chunk_vectors_path,
    default_db_path,
    embed,
    ensure_chunk_schema,
)

PROGRESS_EVERY = 2000


def vault_root_for(db_path: Path) -> Path:
    """The vault the index describes: <vault>/03-Resources/tools/vault-indexer/db."""
    return db_path.resolve().parent.parent.parent.parent


def plan_chunks(conn: sqlite3.Connection, vault_root: Path, target: int,
                max_chunks: int, limit: int | None = None) -> tuple[list, int, int]:
    """Chunk every indexed file. Pure-ish: reads files, embeds nothing, writes nothing.

    Returns (records, files_chunked, files_unreadable) where each record is
    (path, ordinal, heading, body, text_to_embed).
    """
    paths = [r[0] for r in conn.execute("SELECT path FROM files ORDER BY path")]
    if limit:
        paths = paths[:limit]
    records, ok, bad = [], 0, 0
    for p in paths:
        f = vault_root / p
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            bad += 1
            continue
        ok += 1
        for c in chunk_markdown(text, title=f.stem, target_chars=target,
                                max_chunks=max_chunks):
            records.append((p, c.ordinal, c.heading, c.body, c.text))
    return records, ok, bad


def show_stats(conn: sqlite3.Connection, vec_path: Path) -> None:
    try:
        n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        files = conn.execute("SELECT COUNT(DISTINCT path) FROM chunks").fetchone()[0]
    except sqlite3.OperationalError:
        print("No `chunks` table yet — run without --stats to build it.")
        return
    indexed = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    print(f"Chunks stored      : {n:,}")
    # The percentage is the only part that needs guarding; an earlier version put the
    # conditional around the whole print and silently emitted a blank line on an empty vault.
    pct = f" ({files / indexed * 100:.0f}%)" if indexed else ""
    print(f"Files covered      : {files:,} / {indexed:,} indexed{pct}")
    if not indexed:
        print("Index is empty     : run `vault_indexer.py index` first")
    if vec_path.exists():
        mb = vec_path.stat().st_size / 1024 / 1024
        print(f"Vector matrix      : {vec_path.name}, {mb:.0f} MB")
        try:
            import numpy as np
            print(f"Matrix shape       : {np.load(vec_path, mmap_mode='r').shape}")
        except Exception as exc:
            print(f"Matrix unreadable  : {exc}")
    else:
        print(f"Vector matrix      : MISSING ({vec_path.name}) — retrieval will return nothing")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the chunked body-text index (chunks table + vector matrix)")
    parser.add_argument("--db", type=Path, default=None,
                        help="Index path (default: ../vault-indexer/vault-index.db)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Chunk and report only — no embedding, no writes")
    parser.add_argument("--stats", action="store_true", help="Show chunk-store coverage and exit")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the first N files (smoke test)")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET_CHARS,
                        help=f"Target chunk size in chars (default: {DEFAULT_TARGET_CHARS})")
    parser.add_argument("--max-chunks", type=int, default=DEFAULT_MAX_CHUNKS,
                        help=f"Per-file chunk cap (default: {DEFAULT_MAX_CHUNKS})")
    args = parser.parse_args()

    db_path = (args.db or default_db_path()).resolve()
    if not db_path.exists():
        print(f"DB not found: {db_path}\nRun vault_indexer.py index first.", file=sys.stderr)
        sys.exit(1)
    vec_path = chunk_vectors_path(db_path)
    conn = sqlite3.connect(db_path)

    if args.stats:
        show_stats(conn, vec_path)
        conn.close()
        return

    vault_root = vault_root_for(db_path)
    print(f"Vault root : {vault_root}", file=sys.stderr)
    print(f"Index      : {db_path}", file=sys.stderr)

    t0 = time.time()
    records, ok, bad = plan_chunks(conn, vault_root, args.target, args.max_chunks, args.limit)
    print(f"Chunked {ok:,} files ({bad} unreadable) -> {len(records):,} chunks "
          f"in {time.time() - t0:.1f}s", file=sys.stderr)

    if args.dry_run:
        est = len(records) * 0.028
        print(f"\n--dry-run: nothing embedded, nothing written.", file=sys.stderr)
        print(f"  would embed   : {len(records):,} chunks (~{est / 60:.0f} min)", file=sys.stderr)
        print(f"  would write   : {vec_path} (~{len(records) * 768 * 4 / 1024 / 1024:.0f} MB)",
              file=sys.stderr)
        print(f"  would replace : `chunks` table ({len(records):,} rows)", file=sys.stderr)
        by = {}
        for p, *_ in records:
            by[p.split("/")[0]] = by.get(p.split("/")[0], 0) + 1
        print("  by pillar:", file=sys.stderr)
        for k, v in sorted(by.items(), key=lambda x: -x[1]):
            print(f"    {k:<22} {v:>7,}", file=sys.stderr)
        conn.close()
        return

    import numpy as np
    matrix = np.zeros((len(records), 768), dtype="float32")
    rows, errors = [], 0
    t0 = time.time()
    for i, (path, ordinal, heading, body, text) in enumerate(records):
        try:
            v = np.asarray(embed(text), dtype="float32")
            n = float(np.linalg.norm(v))
            matrix[i] = v / n if n else v     # normalise once, at write time
            rows.append((i, path, ordinal, heading, body, i, EMBED_MODEL, time.time()))
        except Exception as exc:
            errors += 1
            if errors <= 5:
                print(f"  ERROR {path}#{ordinal}: {exc}", file=sys.stderr)
        if (i + 1) % PROGRESS_EVERY == 0:
            rate = (i + 1) / (time.time() - t0)
            eta = (len(records) - i - 1) / rate / 60
            print(f"  {i + 1:,}/{len(records):,}  {rate:.0f}/s  ETA {eta:.1f} min",
                  file=sys.stderr)

    ensure_chunk_schema(conn)
    conn.execute("DELETE FROM chunks")
    conn.executemany(
        "INSERT INTO chunks (id, path, ordinal, heading, body, vec_row, model, embedded_at) "
        "VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    np.save(vec_path, matrix)
    conn.close()

    print(f"\nDone in {(time.time() - t0) / 60:.1f} min. "
          f"chunks={len(rows):,} errors={errors} matrix={vec_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
