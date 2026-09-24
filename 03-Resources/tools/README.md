---
created: "20260807"
updated: "20260924"
tags:
  - type/readme
  - domain/tooling
  - created/20260807
  - updated/20260924
  - domain/knowledge-management
  - status/active
author: Claude (claude-opus-5)
---

# `03-Resources/tools/`

Vault tooling. One directory per tool. The standard every tool here is measured against is
[03-Resources/tools/CONTRIBUTING](CONTRIBUTING.md) — read it before adding anything.

**One standard, one place.** If you keep tools elsewhere too, conform them to
[03-Resources/tools/CONTRIBUTING](CONTRIBUTING.md) rather than letting a second standard grow.

---

## The shared module

| File | What it does |
| --- | --- |
| `vault_config.py` | The one place that knows the vault's shape: vault-root discovery, pillar folder names, `log_dir`, tag prefixes, `author`, skip-dirs, and the `YYYYMMDD`/`YYYYMMDDHHMM` date recogniser. Reads `vault.json` at the vault root. **Not a tool** — no tool re-declares any of it. |

Run `python3 03-Resources/tools/vault_config.py` to see exactly what a tool would resolve.
The rule and its rationale are in [03-Resources/tools/CONTRIBUTING](CONTRIBUTING.md) § The shared config module.

---

## The tools

| Tool | What it does | Entrypoint |
| --- | --- | --- |
| [vault-indexer](vault-indexer/README.md) | SQLite index of the vault plus daily/range work summaries. **Reference implementation of the standard.** | `vault_indexer.py` |
| [second-brain](second-brain/README.md) | Local RAG over the vault — Ollama embeddings, MCP server, session hook. `register.py` wires both into Claude Code with resolved paths. | `embed.py` / `mcp_server.py` |
| [process_frontmatter](process_frontmatter/README.md) | Stamps `created/YYYYMMDD` + `updated/YYYYMMDD` tags from the filename, the folder path, or git. **Dry-run by default.** | `process_frontmatter.py` |
| [stamp-out](stamp-out/README.md) | Stamps out a timestamped copy of a vault folder with internal links and paths rewritten. | `stamp_out.py` |
| [scan-broken-wikilinks](scan-broken-wikilinks/README.md) | Finds wikilinks that don't resolve, and bare basenames that resolve by luck. Enforces the vault-absolute standard. | `scan_broken_wikilinks.py` |
| [outbound-path-guard](outbound-path-guard/README.md) | Claude Code `PreToolUse` hook that denies outbound tool calls (tracker, chat, `gh pr create`) carrying wikilinks, vault paths or machine-local paths. **Fails open.** | `outbound_path_guard.py` |

> ### There is deliberately no archival or retention tool
>
> Moving finished work to `04-Archive/` is a manual Obsidian move. That is not an oversight and not
> a gap waiting for a quick script — it is a design conclusion from a tool that was built, run
> **once**, and retired:
>
> `04-Archive/` is organised by **topic**, so *"where does `02-Projects/foo` go when archived?"* has
> **no mechanical answer**. The retired tool's folder map pretended otherwise, encoded the vault's
> shape at a point in time, and had no way to notice when the pillars were renamed underneath it.
> Measured at retirement: one run ever, and **0 of 3,344** archived files carried its tag.
>
> If you build a successor, it must: not hardcode a destination taxonomy; treat retention as a
> **date** question rather than a folder question; default to dry-run and print the resolved
> destination *before* touching anything; use `git mv` and rewrite wikilinks; and ship with tests.
> See [03-Resources/tools/CONTRIBUTING](CONTRIBUTING.md) § Retiring a tool for the note you write when it, too,
> turns out to be unused.

## Common commands

```bash
# What shape does the vault think it is?
python3 03-Resources/tools/vault_config.py

# Rebuild the index, then summarize a date range
python3 03-Resources/tools/vault-indexer/vault_indexer.py index
python3 03-Resources/tools/vault-indexer/vault_indexer.py summary --from 2026-06-05 --to 2026-07-20

# Preview frontmatter stamping across the whole vault. Previewing IS the default;
# --apply is what writes.
python3 03-Resources/tools/process_frontmatter/process_frontmatter.py

# Check that every wikilink resolves, and find bare basenames
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py
```

## Compliance at a glance

Counts below come from running the suites, not from grepping for `def test_`. Re-verify
the same way after any change.

| Tool | README | CHANGELOG | Tests | requirements | Config from `vault_config` |
| --- | --- | --- | --- | --- | --- |
| vault-indexer | ✅ | ✅ | ✅ 52 | n/a (stdlib) | ✅ |
| second-brain | ✅ | ✅ | ✅ 56 | ✅ | n/a (own `common.py`) |
| process_frontmatter | ✅ | ✅ | ✅ 51 | ✅ | ✅ |
| stamp-out | ✅ | ✅ | ✅ 27 | n/a | ✅ |
| scan-broken-wikilinks | ✅ | ✅ | ✅ 62 | n/a (stdlib) | ✅ |
| outbound-path-guard | ✅ | ✅ | ✅ 27 | n/a (stdlib) | ✅ |
| `vault_config` (shared) | in this file | n/a | ✅ 32 | n/a (stdlib) | — |
| [tool-scaffold](../../templates/tool-scaffold/README.md) | ✅ | ✅ (stub) | ✅ 4 | ✅ (stub) | ✅ |

**284 tests across 7 suites, all passing** (98 before the 2026-08-08 convergence). Every tool
is fully compliant, and no tool declares its own folder names, tag prefixes, `author`, or
skip-dirs.

Track per-tool compliance in a **dated audit note** rather than by editing this table's history —
re-run it as a new dated doc so the trend stays visible. See [03-Resources/tools/CONTRIBUTING](CONTRIBUTING.md)
§ Compliance.

## Adding a tool

Start from [templates/tool-scaffold](../../templates/tool-scaffold/README.md) so it begins compliant, then
work the Definition of done in [03-Resources/tools/CONTRIBUTING](CONTRIBUTING.md). Add a row to both tables above.

## Related

- [03-Resources/tools/CONTRIBUTING](CONTRIBUTING.md) — the standard every tool here is measured against
- [03-Resources/tools/20260605-filesystem-timestamps-unreliable](20260605-filesystem-timestamps-unreliable.md) — why tests must not assert on
  real vault timestamps, and why dates come from git
- [AGENTS](../../AGENTS.md) · [CLAUDE](../../CLAUDE.md) · [OrionOs](../../OrionOs.md) — vault-wide conventions and the operating model
