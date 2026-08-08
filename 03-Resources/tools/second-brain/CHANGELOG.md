---
created: "20260707"
updated: "20260707"
tags:
  - created/20260707
  - updated/20260707
  - type/changelog
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# Changelog

## [0.3.0] — 2026-08-08

### Added
- **`common.py`** — the primitives all four entry points need: `OLLAMA_URL`, `EMBED_MODEL`,
  `default_db_path()`, `embed()`, `cosine_similarity()`, `score_rows()`, `format_hits()`,
  `retrieve()`, `compute_index_stats()`, `format_index_stats()`. Each of `embed.py`,
  `search.py`, `hook.py`, and `mcp_server.py` previously carried its own copy of the endpoint,
  the model name, and the similarity function, plus its own retrieval threshold — equal only by
  accident. Changing the embedding model meant four edits, and missing one silently mixed vector
  spaces: the vectors still compare, just meaninglessly.
- **Environment overrides** — `SECOND_BRAIN_OLLAMA_URL`, `SECOND_BRAIN_EMBED_MODEL`,
  `SECOND_BRAIN_DB`. A second vault or a different model now needs no code edit.
- **`register.py`** — writes the `UserPromptSubmit` hook into `.claude/settings.json` and the
  `vault-search` server into `.mcp.json` with this checkout's absolute paths resolved. Dry-run by
  default; the merge is additive, so unrelated hooks, hook events, MCP servers, and settings keys
  survive, and re-running is a no-op rather than a duplicate entry.
- **`hook.py` gained `argparse`** with `--db`, `--top`, and `--min-score`. It had none, so it
  could only ever point at one vault — a gap recorded in
  `20260605-using-on-another-vault.md` and unclosed until now. This also brings the tool into
  line with [[03-Resources/tools/CONTRIBUTING]] § Script conventions, which requires argparse
  on every entrypoint.
- **`mcp_server.py` gained `--name`**, so a second vault's server doesn't also call itself
  `vault-search` and shadow the first in the client's tool list. `top_k` is now clamped to the
  maximum its own docstring advertises.

### Changed
- The `README` no longer prints a machine-specific absolute path in its registration blocks; it shows
  `<vault>` and points at `register.py`. The `$CLAUDE_PROJECT_DIR` alternative is mentioned and
  **explicitly marked unverified** rather than recommended.
- Example queries genericised.
- `test_stats.py` imports the stats functions from `common` instead of `mcp_server`, so the
  suite no longer needs the `mcp` package installed to run.

### Tests
- **10 → 56 tests.** New: `test_common.py` (21 — similarity edge cases including the
  zero-vector guard, `score_rows` 2- vs 3-column handling, heading caps, ordering, the
  `min_score` floor, wikilink formatting, and the `SECOND_BRAIN_DB` override),
  `test_register.py` (18 — the additive merge policy, idempotence, stale-path recognition,
  second-vault coexistence, and that a malformed config raises instead of being overwritten),
  `test_hook.py` (12 — every malformed-input path degrades to "no prompt" rather than raising,
  because a traceback here surfaces as a broken Claude Code session).

### Known limitation
- `embed.py --stats` still counts rows in `files` that no longer exist on disk;
  `scan_vault` does not prune them. Orphaned *embeddings* are pruned; orphaned *file rows*
  are not. Surfaces as a `Missing:` count higher than reality.


## [0.2.0] — 2026-06-18

### Added
- `tests/` — first `pytest` suite for second-brain (`python3 -m pytest tests/`, 10 tests). In-memory SQLite fixtures, no Ollama required.
- `embed.py :: prune_orphans(conn)` — deletes embeddings whose path no longer maps to a file in the index; runs at the end of every `run_embed` and reports `pruned=N`.

### Changed
- `get_vault_stats` (MCP) now reports **usable** coverage — embeddings joined to a live file, which is what `search_vault` actually returns — instead of the raw embeddings row count. Surfaces an `N stale embeddings … run embed.py --reembed` warning when paths have drifted. New testable helpers `compute_index_stats` / `format_index_stats`.
- `embed.py --stats` now shows `Usable (join files)` and `Orphaned (stale path)` instead of a raw embedded count.

### Fixed
- Stale-path embeddings left by the June 2026 folder reorg (`06-Archive→04-Archive`, `04-Projects→02-Projects`, `05-Resources→03-Resources`) made ~96% of the vault unsearchable while stats reported a false 98%. Re-embedded (`embed.py --reembed`); the prune + usable-coverage changes prevent a silent recurrence. See folder-reorg-broke-embeddings.

## [0.1.0] — 2026-06-02

Initial release — RAG layer on top of [[03-Resources/tools/vault-indexer/README|vault-indexer]].

- `embed.py` — generate embeddings via Ollama (`nomic-embed-text`), stored in `vault-index.db`
- `search.py` — CLI semantic search (cosine similarity), returns wikilinks
- `hook.py` — Mode 1: automatic context injection via `UserPromptSubmit` hook
- `mcp_server.py` — Mode 2: on-demand vault search via MCP (`search_vault`, `get_vault_stats`)
