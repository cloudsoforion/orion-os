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

## [0.5.0] — 2026-11-15

### Added
- **`embed_chunks.py --vault`, and `SECOND_BRAIN_VAULT`.** The vault root used to be inferred from
  the DB's location, four directories up, which was right only when the DB sat at
  `<vault>/03-Resources/tools/vault-indexer/` and silently wrong everywhere else: pointing `--db` at
  a second vault's index made every file "unreadable" and wrote an empty chunk store. Resolution is
  now `--vault`, else `SECOND_BRAIN_VAULT`, else the nearest `vault.json` above the script via the
  shared `vault_config.find_vault_root`. No root found is an error that says what to pass.
- **A wrong root is an error, not a quiet zero.** If none of the indexed paths exist under the
  resolved root, the run stops before embedding and names the root it tried.
- Tests: `tests/test_embed_chunks.py` (7) — `resolve_vault_root` precedence and the no-guess rule,
  `plan_chunks` relative-path reads and the all-unreadable signal. Suite 117 → 124.

### Changed
- **`register.py` finds the vault by `vault.json`, not `.obsidian/`.** Its deliberately duplicated
  `find_vault_root` now matches the shared `vault_config.find_vault_root`, which changed the same day
  (see `CHANGELOG/20261115-vault-json-is-the-root-marker`). A bare checkout with no `vault.json` now
  stops with "no vault.json above here; pass --vault" instead of registering against a guessed root.
  No tests added: `register.py` has no suite; the shared module's suite covers the marker rule.

## [0.4.0] — 2026-09-11

Body text is now embedded. Before this release the index was built from
`path | title | headings | tags` only — a table of contents, not a search index. With
headings alone, notes sharing a structural vocabulary (Findings / Impact / Decision) all
look equally similar to any query: real questions and nonsense land in the same narrow
score band, and the best a query can do is rediscover a note you could have found by
filename.

### Added
- **`chunker.py`** — pure, heading-aware markdown chunking. Text in, chunks out; no I/O,
  no network, no DB, so the whole contract is unit-testable. Splits on headings first, then
  paragraph boundaries; prepends a `title > H1 > H2` context trail to every chunk so a
  passage about "Root cause" still knows which document it came from.
- **`embed_chunks.py`** — builds the chunk index. `--dry-run` reports chunk counts per
  pillar and writes nothing; `--limit N` is a smoke test; `--stats` shows coverage.
- **`common.retrieve_chunks()`** — scores every chunk with one numpy matmul over a
  memory-mapped matrix and returns the best passage per file, deduped.
- **`chunks` table + `vault-vectors.npy` sidecar.** Chunk metadata in SQLite; vectors in a
  float32 `(N, 768)` L2-normalised matrix. A 768-dim vector is ~15,900 chars as JSON text
  and 3,072 bytes as float32 — **5.2x smaller** — which is the difference between a
  manageable sidecar and a multi-hundred-megabyte database. `np.load(mmap_mode="r")` makes
  the per-prompt hook's startup a page-cache hit rather than a full-matrix read.
- **Snippets in results.** `format_chunk_hits()` returns the matching passage and its
  heading trail, so one search is usually enough without a follow-up read.
- **Pillar filtering** — `exclude_prefixes` in the API, `--no-archive` in `search.py`,
  `exclude_archive` in the MCP tool. An archive pillar is typically the largest and least
  current share of the index.
- **`tests/test_chunker.py`** (21) and **`tests/test_chunk_store.py`** (14) — the chunking
  contract and the store's bookkeeping. No network, no live vault.
- **numpy** in `requirements.txt`. Scoring tens of thousands of chunks per query is one
  matmul in numpy and unusably slow as a pure-Python loop.
- **`benchmark.py` + `probes.example.json`** — measures retrieval quality so *"did that
  change help?"* has an answer instead of an opinion. Probes are declared in JSON, not in
  code, because the queries that prove a vault works are specific to that vault.
  `--save` records a baseline and `--compare` shows the per-probe delta.
  The headline metric is **separation** — mean best `signal` score minus mean best `noise`
  score. Noise probes are gibberish that *should* rank low; if they don't, retrieval is
  matching structure rather than meaning and every other number is decoration. Measured on
  the reference vault, chunking moved separation **+0.141 → +0.199**, with signal probes up
  and keyboard mash *down*.
- **`tests/test_benchmark.py`** (24) — probe validation, separation maths, baseline diffing.

### Changed
- `hook.py`, `mcp_server.py` and `search.py` prefer the chunk store and **fall back to the
  title-only store** when it is absent, so nothing breaks mid-rebuild or before the first
  `embed_chunks.py` run.
- Vectors are L2-normalised **at write time**, so retrieval is a dot product rather than a
  per-query cosine.

### Known limitations
- **`embed_chunks.py` is a full rebuild, not incremental.** It re-embeds everything. An
  mtime-keyed incremental mode is the obvious next step, and matters more than it sounds:
  an index is only as fresh as its last build, and the notes you most want to find are the
  ones you just wrote.
- **`MIN_SCORE = 0.55` is now loosely calibrated.** Chunking raises scores across the board,
  so far more chunks clear the floor than notes used to. Ranking carries the results; the
  floor does little. A higher floor is probably right but should be measured per vault.
- **Short keyword queries gain nothing.** Body text only helps when the query carries enough
  meaning to match prose. Ask a question, not a keyword.
- **`vault-vectors.npy` is a large generated artifact** — gitignore it. A fresh checkout has
  no index until `vault_indexer.py index` and `embed_chunks.py` have both run.
- **The chunk store contains verbatim note text.** Previously the index leaked only a table
  of contents; it now contains the content of every indexed note. Treat the database and the
  matrix as being as sensitive as the vault itself.
- The legacy `embeddings` table and `embed.py` remain for rollback and are now redundant.


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
