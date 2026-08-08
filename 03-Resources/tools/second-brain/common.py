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
