---
created: "20260808"
updated: "20260808"
tags:
  - created/20260808
  - updated/20260808
  - type/how-to
  - domain/tooling
  - status/active
status: active
---

# Wiring OrionOs into Claude Code

Two optional integrations, both provided by
[[03-Resources/tools/second-brain/README|second-brain]]. Everything else in this vault works without
either.

| Integration | Behaviour |
|---|---|
| **Hook** (`UserPromptSubmit`) | Fires before *every* prompt, injects the most relevant notes as context. Passive, automatic, always on. |
| **MCP server** (`vault-search`) | Exposes vault search as a tool Claude calls *when the query warrants it*. Explicit, on demand. |

Use one, both, or neither. The hook is better when you want vault context always present; the MCP
server is better when you'd rather Claude decide.

## Prerequisites

```bash
# 1. Ollama, with an embedding model pulled
ollama pull nomic-embed-text

# 2. The MCP dependency (only needed for the MCP server)
pip install -r 03-Resources/tools/second-brain/requirements.txt

# 3. Index the vault, then embed it
python3 03-Resources/tools/vault-indexer/vault_indexer.py index
python3 03-Resources/tools/second-brain/embed.py
```

Check it worked before wiring anything up:

```bash
python3 03-Resources/tools/second-brain/search.py "something you know you've written about"
```

## Registration

The two config files need an **absolute** path, and they are the only files in this vault where
that's true: the client launches the process, so neither the vault root nor the working directory is
guaranteed. Don't type the path — generate it:

```bash
python3 03-Resources/tools/second-brain/register.py            # preview the exact diff
python3 03-Resources/tools/second-brain/register.py --apply     # write both files
```

That writes the hook into `.claude/settings.json` and the server into `.mcp.json`, with this
checkout's paths resolved. The merge is **additive** — existing hooks, hook events, MCP servers, and
settings keys survive, and re-running is a no-op rather than a duplicate entry. Restart Claude Code
afterwards.

Flags worth knowing: `--hook-only` / `--mcp-only`, `--python` if `python3` isn't the interpreter you
want invoked, and `--name` to give a second vault's server a distinct name.

> The repo ships `.claude/settings.json` with a literal `<vault>` placeholder and `.mcp.json.example`
> rather than a real `.mcp.json`, so a fresh clone can't half-work with someone else's paths baked in.
> `register.py` replaces both.

### About `$CLAUDE_PROJECT_DIR`

Claude Code exposes `$CLAUDE_PROJECT_DIR` to hooks. If your version expands it inside the hook's
`command` string, then

```json
"command": "python3 $CLAUDE_PROJECT_DIR/03-Resources/tools/second-brain/hook.py"
```

removes the need for a resolved path at all, and the same file works on every machine.

⚠️ **This was not verified when these docs were written.** Test it before relying on it — a hook that
silently fails to launch looks identical to one that found nothing relevant. `register.py`'s resolved
absolute path is the option that is known to work.

## Multiple vaults

Point `--db` at the other vault's index and give the server its own `--name`, or the two register as
servers with the same name and one shadows the other:

```bash
python3 03-Resources/tools/second-brain/register.py --apply \
  --name vault-search-personal \
  --db ~/other-vault/03-Resources/tools/vault-indexer/vault-index.db
```

The tools also read three environment variables, so a second vault or a different model needs no code
edit: `SECOND_BRAIN_DB`, `SECOND_BRAIN_OLLAMA_URL`, `SECOND_BRAIN_EMBED_MODEL`.

⚠️ Changing the embed model invalidates every stored vector — different models produce different
vector spaces, and mixed vectors still compare, just meaninglessly. Run `embed.py --reembed` after
any model change.

## What the hook sends

The injected notes are included in the request sent to the model provider. For a vault with sensitive
content, either raise the relevance floor (`--min-score`, default `0.55`), or don't use the hook and
use the MCP server instead so retrieval only happens when Claude asks for it.

The hook **never blocks a prompt**. A missing index, a dead Ollama, or unparseable input all exit
silently — you lose the context, not the session.

## Keeping it fresh

Embeddings go stale as notes change. Re-run after any significant batch of writing, and always after
a bulk move:

```bash
python3 03-Resources/tools/vault-indexer/vault_indexer.py index
python3 03-Resources/tools/second-brain/embed.py
```

`embed.py --stats` reports coverage. It counts only embeddings that still join to a live file, so a
path drift shows up as a falling number instead of hiding behind a false 100%.

## Related

- [[03-Resources/tools/second-brain/README]] — the tool itself, in full
- [[docs/adopting-into-an-existing-vault]] — if this vault isn't a fresh clone
- [[CLAUDE]] — the guidance Claude Code reads from this repo
