#!/usr/bin/env python3
"""
hook.py — Claude Code UserPromptSubmit hook

Reads the incoming prompt from stdin (JSON), retrieves semantically relevant
vault files, and injects them as context before Claude sees the prompt.

Usage:
  # Normally invoked by Claude Code, not by hand. To test a prompt:
  echo '{"prompt": "cluster upgrade rollback plan"}' | python3 hook.py

  # Point at a different vault's index
  echo '{"prompt": "..."}' | python3 hook.py --db /path/to/other-vault/vault-index.db

Registered in .claude/settings.json — see
[[03-Resources/tools/second-brain/README]] for the block to paste and for how to
keep the path portable:

  {
    "hooks": {
      "UserPromptSubmit": [
        {
          "hooks": [
            {"type": "command", "command": "python3 <vault>/03-Resources/tools/second-brain/hook.py"}
          ]
        }
      ]
    }
  }

Failure policy: this sits in front of a human pressing enter, so it **never
blocks a prompt**. A missing index, a dead Ollama, or unparseable stdin all exit
0 with no output. The embedding call uses a short timeout for the same reason.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DEFAULT_TOP_K,
    MIN_SCORE,
    default_db_path,
    format_chunk_hits,
    format_hits,
    retrieve,
    retrieve_chunks,
)

MAX_PROMPT_CHARS = 500   # only the opening of the prompt is embedded
MIN_PROMPT_CHARS = 10    # below this there's nothing to retrieve on
EMBED_TIMEOUT = 10       # a human is waiting; give up fast


def format_context(results: list[dict], chunked: bool = False) -> str:
    if not results:
        return ""
    lines = ["<vault-context>",
             "Relevant notes from your knowledge vault (use as background context):\n"]
    lines.extend(format_chunk_hits(results) if chunked else format_hits(results))
    lines.append("</vault-context>")
    return "\n".join(lines)


def read_prompt(raw: str) -> str:
    """Pull the prompt text out of the hook payload. Returns "" if there isn't one."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return ""
    if isinstance(data, dict):
        # Claude Code passes {"prompt": "...", ...}
        return data.get("prompt", "") or ""
    if isinstance(data, str):
        return data
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="UserPromptSubmit hook: inject relevant vault notes as context.")
    parser.add_argument("--db", type=Path, default=None,
                        help="Index path (default: ../vault-indexer/vault-index.db, "
                             "or $SECOND_BRAIN_DB)")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_K,
                        help=f"Number of notes to inject (default: {DEFAULT_TOP_K})")
    parser.add_argument("--min-score", type=float, default=MIN_SCORE,
                        help=f"Relevance floor; below this a match is noise (default: {MIN_SCORE})")
    args = parser.parse_args()

    prompt = read_prompt(sys.stdin.read())
    if len(prompt.strip()) < MIN_PROMPT_CHARS:
        sys.exit(0)

    try:
        db = args.db or default_db_path()
        query = prompt[:MAX_PROMPT_CHARS]
        # Chunked body-text retrieval is the real index; the title-only store is
        # the fallback so the hook still works mid-rebuild or before the first
        # `embed_chunks.py` run.
        results = retrieve_chunks(db, query, top_k=args.top,
                                  min_score=args.min_score, timeout=EMBED_TIMEOUT)
        chunked = bool(results)
        if not results:
            results = retrieve(db, query, top_k=args.top,
                               min_score=args.min_score, timeout=EMBED_TIMEOUT)
        context = format_context(results, chunked=chunked)
        if context:
            print(context)
    except Exception:
        # Never block the prompt — fail silently.
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
