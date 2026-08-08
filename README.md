# OrionOs

A working operating system for a knowledge repository, as an Obsidian vault you can clone and start
using. **PARA + GTD + Routines**, plus the tooling that keeps it honest.

This isn't a folder-structure gist. It's the folder model *and* the conventions that stop it rotting
*and* five tested Python tools that enforce them — extracted from a vault that has been in daily use
for five years, with the failure modes it accumulated written down as rules.

```
00-Inbox      capture — nothing stays
01-Areas      ongoing responsibilities — no finish line
02-Projects   committed work — has a finish line
03-Resources  reference and tooling — you'll search for it later
04-Archive    done or no longer true
Log/          the ops journal — daily summaries, weekly priorities, standups
CHANGELOG/    the record of shipped changes to the vault itself
templates/    note templates, including a compliant tool scaffold
```

## Start here

1. **Use this template** (or clone it), then open the directory as a vault in Obsidian.
2. Install the community plugins the templates need: **Dataview**, **Tasks**, **Calendar**.
3. Edit `vault.json` — set `author`, and rename any pillar you want called something else. The
   tooling reads that file; nothing hardcodes folder names.
4. Read [[OrionOs]]. It's the source of truth for the model, the `status:` vocabulary, and the one
   rule that matters most: **move notes in Obsidian, never with `mv`**.
5. Create your first Area: `cp templates/area-README.md 01-Areas/<Area-Name>/README.md`.

Already have a vault? See [[docs/adopting-into-an-existing-vault]].

## What's actually in here

### The model

| Doc | What it defines |
|---|---|
| [[OrionOs]] | The pillars, the 6-state `status:` vocabulary, the graduation rule, the Routines |
| [[CLAUDE]] | Metadata standards and seven documentation-quality rules, written for an AI agent but true for a human |
| [[AGENTS]] | Naming, the vault-absolute wikilink standard, and the rules for changing files |

Each pillar folder has a `README.md` stating what belongs in it and — more usefully — a table of what
does **not**, with where each near-miss goes instead. That table is what makes the model
self-enforcing.

### The tools

Five tools, one shared config module, **284 passing tests**, stdlib-only except where noted. Full
index: [[03-Resources/tools/README]].

| Tool | What it does |
|---|---|
| [[03-Resources/tools/vault-indexer/README\|vault-indexer]] | SQLite index of the vault; generates daily and date-range work summaries. Tracks inodes and content hashes so a *move* isn't mistaken for an *edit*. |
| [[03-Resources/tools/process_frontmatter/README\|process_frontmatter]] | Stamps `created/` and `updated/` tags, resolving the date from the filename, the folder path, or git — and skipping rather than guessing. |
| [[03-Resources/tools/scan-broken-wikilinks/README\|scan-broken-wikilinks]] | Finds links that don't resolve, and bare basenames that resolve *by luck*. Enforces the wikilink standard. |
| [[03-Resources/tools/stamp-out/README\|stamp-out]] | Copies a folder with its internal wikilinks and path references repointed at the copy. For per-run runbooks. |
| [[03-Resources/tools/second-brain/README\|second-brain]] | Local semantic search over the vault — Ollama embeddings, an MCP server, and a Claude Code hook. Needs Ollama; the rest don't. |

```bash
python3 03-Resources/tools/vault_config.py                                      # what shape is this vault?
python3 03-Resources/tools/vault-indexer/vault_indexer.py index
python3 03-Resources/tools/process_frontmatter/process_frontmatter.py           # previews; --apply writes
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py
```

## The opinions worth stealing even if you don't use the rest

- **Sort by purpose, not by topic.** Inbox = *needs a home?* · Areas = *regularly return?* ·
  Projects = *a finish line?* · Resources = *search for it later?* · Archive = *done?* A
  topic-sorted folder means nothing and holds everything.
- **"When will I get to it?" is a status, not a folder.** Not-yet-started work is a `paused` backlog
  item in an Area, not a note rotting in the inbox.
- **`blocked` and `paused` are different states** and call for opposite actions — go nudge, versus
  leave alone. Collapsing them is why status fields stop being useful.
- **A doc moves once**, at graduation. Everything else is a status change and a link.
- **Dry-run is the default for anything that mutates the vault**, and dry-run output must print
  *what* changes, not just how many. A tool whose documented invocation writes by default will
  eventually be run by someone who didn't read the docs.
- **A tool that hardcodes a taxonomy inherits every reorg as a silent bug.** That's why folder names
  and tag prefixes live in `vault.json` and there is exactly one shared module that reads it.
- **A visible gap is a feature; a confident fabrication is a bug.** If you can't verify it, mark it
  `⚠️ unverified` rather than writing the plausible version.
- **Retire tools with a eulogy, not a `git rm`.** Write down what killed it, or the same idea comes
  back in six months.

## Requirements

- **Python 3.10+** — the tools are stdlib-only except `PyYAML` (process_frontmatter) and `mcp`
  (second-brain's MCP server). No packaging, no virtualenv required.
- **Obsidian** with Dataview, Tasks, and Calendar for the templates to render.
- **git** — `process_frontmatter` uses commit history for dates. It degrades to skipping without it.
- **Ollama** — only for `second-brain`. Everything else works without it.

## Docs

- [[docs/adopting-into-an-existing-vault]] — folding this into a vault you already have
- [[docs/claude-code-setup]] — wiring the semantic-search hook and MCP server
- [[03-Resources/tools/CONTRIBUTING]] — the standard every tool here meets, and how to add one

## License

MIT — see [`LICENSE`](LICENSE).
