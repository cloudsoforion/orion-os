---
created: "20260615"
updated: "20260707"
tags:
  - created/20260615
  - updated/20260707
  - type/readme
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# second-brain

Local-first RAG system for the Obsidian vault. Surfaces relevant context from
past work before every Claude Code prompt — automatically or on demand.

Builds on [vault-indexer](../vault-indexer/README.md), which handles file scanning and metadata extraction.
This layer adds embeddings, vector search, and two integration modes.

## Architecture (layered)

### Layer 1 — SQLite + a numpy vector matrix (local, zero new services) ✅ **the only layer that exists**
- Chunk metadata in `vault-index.db`; vectors in a float32 `vault-vectors.npy` sidecar
- At query time: memory-map the matrix, one matmul, top-k. Vectors are L2-normalised at write
  time so similarity is a dot product
- Requires only Ollama (`nomic-embed-text`) and numpy — no new infrastructure
- Good for: daily use, laptops, offline

> Layers 2 and 3 below are **design intent, not shipped code.** Nothing in this repo talks to
> Postgres or Kubernetes today. See [docs/deploying-second-brain](../../../docs/deploying-second-brain.md) for what each would actually
> take, and why Layer 1 covers more ground than it looks like it should.

### Layer 2 — Local pgvector (Docker)
- `docker run -p 5432:5432 pgvector/pgvector:pg16`
- Proper ANN vector search, faster at scale
- Same Ollama embeddings, same integration modes — just a better query backend
- Good for: daily driver, closer to production architecture

### Layer 3 — Kubernetes (CloudNativePG + Argo Workflows)
- CloudNativePG for pgvector (CNCF Incubating)
- Argo Workflows for scheduled re-embedding pipeline
- KEDA for event-driven scaling
- Good for: homelab, talk demo, production

---

## Integration modes

Two ways to surface vault context in Claude Code. Use one or both.

### Mode 1 — Hook (automatic, passive)

`hook.py` is a Claude Code `UserPromptSubmit` hook. It fires before every prompt,
retrieves semantically relevant notes, and injects them as context — silently,
without you doing anything.

**Wired up in** `.claude/settings.json` (project) or `~/.claude/settings.json` (global).
Replace `<vault>` with the absolute path to your vault:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 <vault>/03-Resources/tools/second-brain/hook.py",
            "timeout": 15,
            "statusMessage": "Searching vault..."
          }
        ]
      }
    ]
  }
}
```

An absolute path is required here and in `.mcp.json` — these two files are the only
place in the vault where that's true, because the client launches the process and
neither the vault root nor the cwd is guaranteed. Generate them rather than typing
the path:

```bash
python3 03-Resources/tools/second-brain/register.py --dry-run   # preview
python3 03-Resources/tools/second-brain/register.py --apply     # write both files
```

> Claude Code also exposes `$CLAUDE_PROJECT_DIR` to hooks. If your version expands it
> inside the `command` string, `"$CLAUDE_PROJECT_DIR/03-Resources/..."` removes the need
> for a resolved path entirely. **Not verified here** — test it before relying on it.

**Behaviour**: runs on every prompt. Low-score matches are filtered by `MIN_SCORE`
(default 0.55, `--min-score` to override). Fails silently — never blocks a prompt, so a
dead Ollama or a missing index costs you nothing but the context.

**Privacy note**: injected context is included in the API request sent to Anthropic.
For sensitive vaults, raise `MIN_SCORE` or scope the hook to specific folders.

**Fully local alternative** — use a shell function with Ollama instead of Claude:
```bash
function ask() {
  context=$(echo "{\"prompt\": \"$*\"}" | python3 <vault>/03-Resources/tools/second-brain/hook.py)
  echo -e "$context\n\nUser: $*" | ollama run llama3.2-vision:11b
}
```

---

### Mode 2 — MCP server (on-demand, explicit)

`mcp_server.py` exposes vault search as an MCP tool. Claude calls it when the
query warrants it — not on every prompt. Works with any MCP-compatible client
(Claude Code, Continue.dev, etc.).

**Registered in** `.mcp.json` (project). `register.py` writes this for you:
```json
{
  "mcpServers": {
    "vault-search": {
      "command": "python3",
      "args": ["<vault>/03-Resources/tools/second-brain/mcp_server.py"]
    }
  }
}
```

**For a second vault**, point `--db` at the other vault's index and give the server its
own `--name`, so the client sees two distinct tools rather than one shadowing the other:
```json
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
```

See using-on-another-vault for the full multi-vault setup guide.

**Tools exposed**:
- `search_vault(query, top_k=5)` — semantic search, returns wikilinks
- `get_vault_stats()` — index coverage report. Reports *usable* coverage (embeddings that
  join to a live file, which is what's actually searchable) and warns when stale-path
  embeddings exist — see folder-reorg-broke-embeddings

**When to use**: prefer MCP over the hook when you want Claude to decide
when vault context is relevant, rather than injecting it on every prompt.

---

## Components

| File | Purpose |
|---|---|
| `chunker.py` | **Pure** heading-aware markdown chunking — text in, chunks out. No I/O; fully unit-tested. |
| `embed_chunks.py` | **Builds the body-text index**: chunks every file, embeds each chunk, writes the `chunks` table + `vault-vectors.npy`. `--dry-run` writes nothing. |
| `embed.py` | *Legacy* title-only store (`path \| title \| headings \| tags`). Kept for rollback; superseded by `embed_chunks.py`. |
| `search.py` | CLI semantic search — returns wikilinks **plus the matching passage** |
| `common.py` | Shared primitives: Ollama endpoint, model, DB location, similarity, scoring, formatting. Not an entry point. |
| `register.py` | Writes the hook + MCP registrations with resolved absolute paths. Dry-run by default. |
| `hook.py` | Mode 1: automatic context injection via `UserPromptSubmit` hook |
| `mcp_server.py` | Mode 2: on-demand vault search via MCP |
| `benchmark.py` | Measures retrieval quality against probe queries; `--save` / `--compare` for before-and-after |
| `probes.example.json` | Probe template — copy to `probes.json` and write signal queries for your vault |
| `tests/` | `pytest` suite (`python3 -m pytest tests/`) |
| `README.md` | This file |
| `CHANGELOG.md` | Version history |

---

## Setup

### Configuration

Endpoint, model, and index location are read from the environment, so a second vault or a
different embedding model needs no code edit:

| Variable | Default |
|---|---|
| `SECOND_BRAIN_OLLAMA_URL` | `http://localhost:11434/api/embeddings` |
| `SECOND_BRAIN_EMBED_MODEL` | `nomic-embed-text` |
| `SECOND_BRAIN_DB` | `../vault-indexer/vault-index.db` |
| `SECOND_BRAIN_VAULT` | the nearest `vault.json` above `embed_chunks.py` (only `embed_chunks.py` reads this; `--vault` overrides it) |

⚠️ Changing `SECOND_BRAIN_EMBED_MODEL` invalidates every stored vector — different models
produce different vector spaces, and mixed vectors still compare, just meaninglessly. Run
`embed.py --reembed` after any model change.

### Prerequisites
```bash
ollama pull nomic-embed-text
python vault_indexer.py index   # from vault-indexer/
python embed.py                 # generate embeddings (~4300 files, one-time)
```

### Test search
```bash
python search.py "cluster upgrade rollback plan"
python search.py "alerting integration setup" --top 10
```

### Enable Mode 1 (hook)
Add the hook config above to `.claude/settings.json`, then restart Claude Code
or open `/hooks` to reload.

### Enable Mode 2 (MCP)
`.mcp.json` is already configured in this vault. Restart Claude Code to load it,
then approve `vault-search` when prompted.

---

## New machine / first run

1. `ollama pull nomic-embed-text`
2. `pip install -r requirements.txt`
3. `python3 vault_indexer.py index` — populates the `files` table
4. `python3 embed_chunks.py --dry-run` — sanity-check the chunk counts
5. `python3 embed_chunks.py` — build the index
6. Restart Claude Code — hook and MCP server load automatically from the config files

Both artifacts are generated and should be gitignored: `vault-index.db` and
`vault-vectors.npy`. Expect roughly **8 chunks per file** and a few minutes of embedding
for a mid-sized vault; the matrix is ~3 KB per chunk.

---

## Maintenance

### Rebuilding the body-text index

```bash
python3 embed_chunks.py --dry-run    # chunk counts per pillar; embeds nothing, writes nothing
python3 embed_chunks.py              # full rebuild
python3 embed_chunks.py --stats      # chunks stored, files covered, matrix shape
```

Indexing a **second vault** from this checkout: give both tools the same root, and the
embedder a DB of its own. The `files` table holds paths relative to the root the indexer
used, so the embedder must be told that root; if none of the indexed paths exist under
it, the run stops with an error instead of writing an empty chunk store.

```bash
python3 ../vault-indexer/vault_indexer.py index --vault ~/other-vault --db ~/other-vault/.index/vault-index.db
python3 embed_chunks.py --db ~/other-vault/.index/vault-index.db --vault ~/other-vault --dry-run
```

⚠️ **The index is only as fresh as its last build, and there is no incremental mode yet.**
`vault_indexer.py index` populates `files`; `embed_chunks.py` chunks them. Neither runs
automatically, so a note written today is invisible until both have run again — and the
notes you most want to find are usually the ones you just wrote. Wire both into a cron job
or a shell alias.

### Why chunked

The original store embedded `path | title | headings | tags` and never the body, which made
it a table of contents rather than a search index. Two consequences, both reproducible on
any vault:

- **Everything looks equally similar to everything.** Ops notes share a structural
  vocabulary — Findings, Impact, Decision — so unrelated documents cluster in a narrow band
  and nonsense input can score above the retrieval floor.
- **You can only find what you could already name.** A note's *title* may say nothing about
  the thing you remember from its body, so the search cannot reach it.

Chunked body text fixes both: real questions rank well above noise, and results return the
passage rather than a filename.

### Legacy title-only store

Embeddings are keyed by **path**. Any bulk move or folder rename leaves the old
embeddings pointing at paths that no longer exist — `search_vault` inner-joins to
the `files` table, so those stale rows silently drop out of results. After a reorg:

```bash
python embed.py --reembed     # regenerate every embedding against current paths
```

`embed.py` prunes orphaned (stale-path) rows on every run, and `get_vault_stats`
reports *usable* coverage so a drift shows up instead of hiding behind a false
~100%. Full write-up: folder-reorg-broke-embeddings.

```bash
python embed.py --stats       # Files indexed / Usable (join files) / Orphaned
```

---

## Measuring retrieval quality

Tuning retrieval by feel does not work — scores live in a narrow band, and a change that
*looks* better on one query often is not. `benchmark.py` makes it measurable.

```bash
cp probes.example.json probes.json     # then write signal queries for YOUR vault
python3 benchmark.py                   # per-probe scores + separation
python3 benchmark.py --save base.json  # record a baseline before changing anything
python3 benchmark.py --compare base.json
```

Probes come in two kinds:

- **`signal`** — real questions with documented answers. These *should* score high.
- **`noise`** — gibberish. These *should* score low. They are the control.

The headline number is **separation** = mean best signal score − mean best noise score.

Separation is the honest measure because a raw score means very little on its own. An index
that has only seen titles and headings will rank *everything* in one narrow band — including
nonsense — because ops notes share a structural vocabulary. Only the gap between a real
question and gibberish tells you whether the index understands meaning. At or below zero,
it does not.

Keep the noise probes as shipped; they are vault-independent. Write your own signal probes,
and include at least one whose answer lives in a note **body** rather than any title — that
is the case a title-only index cannot reach, and the clearest thing chunking buys.

---

## Verifying a fresh install

The empty-vault path is the one that breaks, and it is the first thing a new adopter runs — the
first time that test was written it found two bugs a populated vault could not surface. Procedure:
[docs/verifying-a-fresh-install](../../../docs/verifying-a-fresh-install.md).

---

## Tests

```bash
python3 -m pytest tests/
```

56 tests. `test_common.py` pins the shared primitives (similarity edge cases, scoring,
wikilink formatting, the `SECOND_BRAIN_DB` override); `test_register.py` pins the additive
merge policy for the two config files; `test_hook.py` pins that malformed hook input
degrades to "no prompt" instead of raising; `test_stats.py` covers usable-coverage
reporting; `test_prune.py` covers `prune_orphans` and its wiring into `run_embed`.

**No Ollama and no `mcp` package required.** The fixtures use an in-memory SQLite DB, and
the stats tests import from `common` rather than `mcp_server` so the suite runs on a
machine that has neither installed.

---

## Hook vs MCP — when to use which

| | Hook | MCP |
|---|---|---|
| Fires | Every prompt | When Claude decides |
| Effort | Zero — fully automatic | Claude calls it explicitly |
| Scope | Configurable by folder/score | Per-call |
| Privacy | Context sent to Anthropic | Same |
| Local-only | Yes (swap Claude for Ollama shell fn) | Yes |
| MCP clients | Claude Code only | Any MCP client |

Use **both**: hook for passive background context, MCP for deliberate deep dives.

---

## Related

- [vault-indexer](../vault-indexer/README.md) — upstream indexer this builds on
- vault-indexer-update-requests — vault-indexer improvement backlog
- https://cloudrumble.net/blog/2026/02/24/rag-homelab-kubernetes/ — colleague's Layer 2/3 implementation
