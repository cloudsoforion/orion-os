#!/usr/bin/env python3
"""
common.py — the embedding primitives shared by second-brain's four entry points.

`embed.py`, `search.py`, `hook.py`, and `mcp_server.py` all need the same Ollama
endpoint, the same model name, the same DB location, and the same similarity
maths. Before this module each carried its own copy: four `OLLAMA_URL` constants,
four `cosine_similarity` functions, and three different retrieval thresholds that
were only equal by accident. Changing the embedding model meant four edits, and
missing one silently mixed vector spaces — the embeddings would still compare,
just meaninglessly.

Not an entry point: no argparse, no main(). See
[[03-Resources/tools/CONTRIBUTING]] § The shared config module for the
one-shared-module rule; this is the tool-local equivalent, scoped to this folder.

Overrides come from the environment so a second vault or a different model needs
no code edit:
  SECOND_BRAIN_OLLAMA_URL   default http://localhost:11434/api/embeddings
  SECOND_BRAIN_EMBED_MODEL  default nomic-embed-text
  SECOND_BRAIN_DB           default ../vault-indexer/vault-index.db
"""

import json
import math
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

DB_NAME = "vault-index.db"

OLLAMA_URL = os.environ.get("SECOND_BRAIN_OLLAMA_URL", "http://localhost:11434/api/embeddings")
EMBED_MODEL = os.environ.get("SECOND_BRAIN_EMBED_MODEL", "nomic-embed-text")

# Retrieval defaults. MIN_SCORE is the confidence floor below which a match is
# noise rather than context — shared so the hook and the MCP tool can't drift.
DEFAULT_TOP_K = 5
MIN_SCORE = 0.55


def default_db_path() -> Path:
    """The index second-brain reads: SECOND_BRAIN_DB, else vault-indexer's DB."""
    from_env = os.environ.get("SECOND_BRAIN_DB")
    if from_env:
        return Path(from_env).expanduser()
    return Path(__file__).resolve().parent.parent / "vault-indexer" / DB_NAME


def embed(text: str, timeout: int = 30) -> list[float]:
    """Embedding vector for `text` from Ollama.

    `timeout` is a parameter because the callers have genuinely different
    budgets: a batch run can wait 30s for a slow first token, but the
    UserPromptSubmit hook sits in front of a human and must give up fast.
    """
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read())["embedding"]
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unreachable at {OLLAMA_URL}: {exc}") from exc


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def score_rows(rows, query_vec: list[float], min_score: float = 0.0) -> list[dict]:
    """Score `(path, vector_json, extracted_json?)` rows against a query vector.

    Accepts 2- or 3-column rows so `search.py` (paths only) and the retrieval
    callers (which want titles and headings) share one scoring pass. Returned
    highest-score first.
    """
    scored = []
    for row in rows:
        path, vector_json = row[0], row[1]
        extracted_json = row[2] if len(row) > 2 else None
        score = cosine_similarity(query_vec, json.loads(vector_json))
        if score < min_score:
            continue
        entry = {"path": path, "score": score}
        if len(row) > 2:
            ext = json.loads(extracted_json) if extracted_json else {}
            entry["title"] = ext.get("title") or Path(path).stem
            entry["headings"] = [
                h["text"] for h in ext.get("headings", []) if h.get("level") == 2
            ][:4]
        scored.append(entry)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def format_hits(results: list[dict]) -> list[str]:
    """`- [[wikilink]] (score) — heading · heading` lines, Obsidian-clickable."""
    lines = []
    for r in results:
        link = str(Path(r["path"]).with_suffix(""))
        line = f"- [[{link}]] ({r['score']:.2f})"
        if r.get("headings"):
            line += f" — {' · '.join(r['headings'])}"
        lines.append(line)
    return lines


def retrieve(db_path: Path, query: str, top_k: int = DEFAULT_TOP_K,
             min_score: float = MIN_SCORE, timeout: int = 30) -> list[dict]:
    """Top-k vault notes for `query`, joined to live files so stale paths drop out."""
    if not Path(db_path).exists():
        return []
    query_vec = embed(query, timeout=timeout)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT e.path, e.vector, f.extracted FROM embeddings e "
            "JOIN files f ON e.path = f.path"
        ).fetchall()
    finally:
        conn.close()
    return score_rows(rows, query_vec, min_score)[:top_k]


def compute_index_stats(conn: sqlite3.Connection) -> dict:
    """Index coverage based on *usable* embeddings — those that join to a live file.

    Stale-path embeddings (e.g. left behind by a folder rename) are counted as
    orphaned, never as coverage, so a path drift surfaces instead of hiding behind
    a false ~100%. Retrieval inner-joins embeddings to files, so `usable` is
    exactly what is actually searchable.
    """
    total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    usable = conn.execute(
        "SELECT COUNT(*) FROM embeddings e JOIN files f ON e.path = f.path"
    ).fetchone()[0]
    embeddings_total = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    orphaned = embeddings_total - usable
    coverage = (usable / total * 100) if total else 0.0
    return {"total": total, "usable": usable, "orphaned": orphaned, "coverage": coverage}


def format_index_stats(stats: dict) -> str:
    line = (
        f"Vault index: {stats['total']} files indexed, "
        f"{stats['usable']} embedded & searchable ({stats['coverage']:.0f}%)"
    )
    if stats["orphaned"]:
        line += (
            f"; {stats['orphaned']} stale embeddings match no file "
            f"— run `embed.py --reembed`"
        )
    return line


# ---------------------------------------------------------------------------
# Chunked body-text retrieval
#
# The original store held ONE vector per file, built from `path | title |
# headings | tags` — no body text. That makes the index a table of contents
# rather than a search index.
#
# Two storage decisions, both forced by chunk counts (tens of thousands):
#
#   1. Vectors live in a float32 .npy sidecar, NOT as JSON in SQLite. A 768-dim
#      vector is ~15,900 chars as JSON text but 3,072 bytes as float32 — 5.2x.
#      At 40k chunks that is ~120 MB instead of ~600 MB.
#   2. Vectors are L2-normalised AT WRITE TIME, so retrieval is a plain dot
#      product and cosine never has to be recomputed per query.
#
# Retrieval loads the matrix with mmap and does one matmul; SQLite is touched
# only for the winning rows, never for a full scan. The old `embeddings` table
# and `retrieve()` are left untouched so this can be rolled back.
# ---------------------------------------------------------------------------

CHUNK_VECTORS_NAME = "vault-vectors.npy"


def chunk_vectors_path(db_path) -> Path:
    """Sidecar matrix that pairs with `db_path`'s `chunks` table."""
    return Path(db_path).resolve().parent / CHUNK_VECTORS_NAME


def ensure_chunk_schema(conn: sqlite3.Connection) -> None:
    """Create the `chunks` table. Additive — never touches `embeddings`."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY,
            path        TEXT NOT NULL,
            ordinal     INTEGER NOT NULL,
            heading     TEXT,
            body        TEXT NOT NULL,
            vec_row     INTEGER NOT NULL,
            model       TEXT NOT NULL,
            embedded_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS chunk_idx_path ON chunks(path)")
    conn.execute("CREATE INDEX IF NOT EXISTS chunk_idx_vecrow ON chunks(vec_row)")
    conn.commit()


def normalise(vec) -> "list[float]":
    """L2-normalise so a dot product equals cosine similarity."""
    import numpy as np
    a = np.asarray(vec, dtype="float32")
    n = float(np.linalg.norm(a))
    return (a / n) if n else a


def retrieve_chunks(db_path, query: str, top_k: int = DEFAULT_TOP_K,
                    min_score: float = MIN_SCORE, timeout: int = 30,
                    per_file: int = 1, exclude_prefixes: tuple = ()) -> list[dict]:
    """Top-k vault chunks for `query`, best-chunk-first, deduped to `per_file`.

    Returns dicts with `path`, `score`, `heading`, `snippet`. Falls back to an
    empty list (never raises) when the chunk store has not been built, so the
    hook keeps working during a rebuild.

    `exclude_prefixes` drops whole pillars before ranking — e.g. ("04-Archive/",)
    — which is the cheap half of hybrid filtering, since an archive pillar is
    typically the largest share of chunks and the least current.
    """
    import numpy as np

    db_path = Path(db_path)
    vec_path = chunk_vectors_path(db_path)
    if not db_path.exists() or not vec_path.exists():
        return []

    matrix = np.load(vec_path, mmap_mode="r")
    if matrix.shape[0] == 0:
        return []

    q = np.asarray(embed(query, timeout=timeout), dtype="float32")
    n = float(np.linalg.norm(q))
    if not n:
        return []
    q /= n

    scores = matrix @ q                      # cosine: both sides normalised
    # Pull a generous candidate pool so dedup-per-file still fills top_k.
    pool = min(len(scores), max(top_k * 40, 200))
    idx = np.argpartition(-scores, pool - 1)[:pool]
    idx = idx[np.argsort(-scores[idx])]

    conn = sqlite3.connect(db_path)
    try:
        rows = {}
        marks = ",".join("?" * len(idx))
        for vr, path, heading, body in conn.execute(
            f"SELECT vec_row, path, heading, body FROM chunks WHERE vec_row IN ({marks})",
            [int(i) for i in idx],
        ):
            rows[vr] = (path, heading, body)
    finally:
        conn.close()

    out: list[dict] = []
    seen: dict = {}
    for i in idx:
        score = float(scores[i])
        if score < min_score:
            break                            # idx is sorted, so nothing below qualifies
        row = rows.get(int(i))
        if row is None:
            continue                         # stale matrix row, chunk deleted
        path, heading, body = row
        if any(path.startswith(p) for p in exclude_prefixes):
            continue
        if seen.get(path, 0) >= per_file:
            continue
        seen[path] = seen.get(path, 0) + 1
        out.append({"path": path, "score": score,
                    "heading": heading or "", "snippet": body})
        if len(out) >= top_k:
            break
    return out


def format_chunk_hits(results: list[dict], snippet_chars: int = 220) -> list[str]:
    """`- [[wikilink]] (score) — heading` + an indented snippet line."""
    lines = []
    for r in results:
        link = str(Path(r["path"]).with_suffix(""))
        head = f" — {r['heading']}" if r.get("heading") else ""
        lines.append(f"- [[{link}]] ({r['score']:.2f}){head}")
        snip = " ".join(r.get("snippet", "").split())
        if snip:
            lines.append(f"    {snip[:snippet_chars]}{'…' if len(snip) > snippet_chars else ''}")
    return lines
