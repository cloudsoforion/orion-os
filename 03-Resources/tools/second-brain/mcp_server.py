#!/usr/bin/env python3
"""
mcp_server.py — Vault search MCP server

Exposes vault semantic search as an MCP tool, compatible with Claude Code,
Continue.dev, and any other MCP-enabled AI assistant.

Usage:
  # Normally launched by an MCP client over stdio, not by hand.
  python3 mcp_server.py
  python3 mcp_server.py --db /path/to/other-vault/vault-index.db --name vault-search-personal

Register in .mcp.json — see [[03-Resources/tools/second-brain/README]] for how to
keep the path portable:
  {
    "mcpServers": {
      "vault-search": {
        "command": "python3",
        "args": ["<vault>/03-Resources/tools/second-brain/mcp_server.py"]
      }
    }
  }

For a second vault, point --db at its index and give the server its own --name,
so the two appear as distinct tools to the client:
  {
    "mcpServers": {
      "vault-search-personal": {
        "command": "python3",
        "args": [
          "<other-vault>/03-Resources/tools/second-brain/mcp_server.py",
          "--db", "<other-vault>/03-Resources/tools/vault-indexer/vault-index.db",
          "--name", "vault-search-personal"
        ]
      }
    }
  }
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DEFAULT_TOP_K,
    MIN_SCORE,
    compute_index_stats,
    default_db_path,
    format_hits,
    format_index_stats,
    retrieve,
)

MAX_TOP_K = 20
EMBED_TIMEOUT = 10   # an assistant is waiting on the tool call

# Parse args before FastMCP takes over stdio. parse_known_args so we don't
# choke on anything the MCP transport layer injects.
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument("--db", type=Path, default=None)
_parser.add_argument("--name", default="vault-search",
                     help="MCP server name; give a second vault its own so the "
                          "client sees two distinct tools")
_args, _ = _parser.parse_known_args()

DB_PATH = _args.db or default_db_path()

mcp = FastMCP(_args.name)


@mcp.tool()
def search_vault(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    """
    Search the Obsidian vault for notes relevant to a topic.

    IMPORTANT: `query` is a natural language search string ONLY.
    `top_k` is a separate integer parameter for the number of results.
    Never combine them — pass "cluster upgrade rollback" not "cluster upgrade, top_k=10".

    Args:
        query: Natural language search string, e.g. "cluster upgrade rollback plan"
        top_k: Integer number of results to return. Default is 5. Maximum is 20.
    """
    if not DB_PATH.exists():
        return "Vault index not found. Run vault_indexer.py index first."

    results = retrieve(DB_PATH, query, top_k=min(top_k, MAX_TOP_K),
                       min_score=MIN_SCORE, timeout=EMBED_TIMEOUT)
    if not results:
        return f"No vault notes found above relevance threshold for: {query}"

    return "\n".join([f"Vault notes relevant to: {query}\n", *format_hits(results)])


@mcp.tool()
def get_vault_stats() -> str:
    """Return current vault index statistics."""
    if not DB_PATH.exists():
        return "Vault index not found."
    conn = sqlite3.connect(DB_PATH)
    try:
        stats = compute_index_stats(conn)
    finally:
        conn.close()
    return format_index_stats(stats)


if __name__ == "__main__":
    mcp.run(transport="stdio")
