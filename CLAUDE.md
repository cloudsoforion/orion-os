# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Repository Purpose

A knowledge-management repository structured as an Obsidian vault, running the **OrionOs** operating
model. It holds work notes, reference material, and the tooling that maintains them.

## Operating Model & Structure

The vault runs on **OrionOs** (PARA + GTD + Routines). **[[OrionOs]] is the source of truth** for the
pillar folders (`00-Inbox`, `01-Areas`, `02-Projects`, `03-Resources`, `04-Archive`), the `status:`
frontmatter values and their meanings, the graduation/lifecycle flow (idea → Area backlog →
`02-Projects/` → `CHANGELOG/` or `04-Archive/`), and the standing **"move files in Obsidian only,
never `mv`"** rule. Do not restate any of that here — read [[OrionOs]] and the per-pillar READMEs.

Two operational folders sit outside the PARA pillars:

- `Log/` — the ops journal. Daily summaries and weekly priorities live in per-week folders:
  `Log/<week-Monday>/<YYYYMMDD>-daily-summary.md` and
  `Log/<week-Monday>/priorities-week-of-<week-Monday>.md`. See [[Log/README]].
- `CHANGELOG/` — the record of shipped changes to the vault itself. See [[CHANGELOG/README]].
- `templates/` — note templates. See [[templates/README]].

**Folder names are configuration, not constants.** They live in `vault.json`; no tool hardcodes them.

## Key Tools and Scripts

Vault tooling lives under `03-Resources/tools/`, one directory per tool, plus one shared module.
Full index: [[03-Resources/tools/README]]. Standard: [[03-Resources/tools/CONTRIBUTING]].

```bash
# What shape does the vault think it is? (resolves vault.json)
python3 03-Resources/tools/vault_config.py

# SQLite index + work summaries
python3 03-Resources/tools/vault-indexer/vault_indexer.py index
python3 03-Resources/tools/vault-indexer/vault_indexer.py summary --from 2026-06-05 --to 2026-07-20

# Stamp created/updated tags. Previewing is the DEFAULT; --apply writes.
python3 03-Resources/tools/process_frontmatter/process_frontmatter.py

# Check every wikilink resolves, and find bare basenames
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py

# Local RAG over the vault (needs Ollama)
python3 03-Resources/tools/second-brain/embed.py
python3 03-Resources/tools/second-brain/search.py "cluster upgrade rollback plan"
```

New tools go in `03-Resources/tools/<tool-name>/`, started from
[[templates/tool-scaffold/README|tool-scaffold]] so they begin compliant.

### Daily Note Template

`templates/wtf-am-i-doing-YYYYMMDD.md` is the primary daily note — meeting tracking, inbox review,
Tasks queries, and Dataview queries for files created or updated today. Other templates live
alongside it; see [[templates/README]].

## Metadata Standards

- All markdown files include YAML frontmatter with `tags`.
- `created/YYYYMMDD` and `updated/YYYYMMDD` tags track dates, maintained by `process_frontmatter.py`.
  **Dates come from the filename, the folder path, or git — never from filesystem mtime**, which does
  not survive a bulk copy. See [[03-Resources/tools/20260605-filesystem-timestamps-unreliable]].
- `author` names the creator, e.g. `Claude (claude-opus-5)` for AI-generated content.
- Cross-cutting discovery tags: `domain/`, `type/`, `status/`, `project/`, `product/`.
  **`type/` is the document genre, never the subject** — that's what makes "show me every changelog,
  newest first" a single Dataview query. Subject matter goes on `domain/`.
- Exactly one `type/` and one `status/` per file, and the `status:` scalar must agree with the
  `status/` tag.
- **Lifecycle `status:`** values (`inbox`, `active`, `review`, `blocked`, `paused`, `done`) are
  defined in [[OrionOs]] — use those.

The prefixes themselves are configuration: `tag_prefixes` in `vault.json`.

## Documentation Standards

This vault is a record, not a scratchpad — its value depends on every claim being true. The recurring
failure mode is asserting facts that were never verified. Follow these rules when writing anything
into the vault:

1. **Verify before you write.** Every factual claim goes in only after it's confirmed against a
   source — read the source doc, run the command, query the index. Do not restate inferences, verbal
   descriptions, or memory as documented fact.
2. **Flag gaps; never guess.** If something can't be verified (expired auth, missing doc, ambiguous
   source), stop and mark it explicitly — `⚠️ unverified` inline, or a note at the top of the doc —
   rather than filling the gap with a plausible guess. **A visible gap is a feature; a confident
   fabrication is a bug.**
3. **Ground summaries and chronologies in the index, not recall.** For work-history or roll-up docs,
   build from the `vault-indexer` database or a raw `date|path` extract and grep it per theme. Don't
   narrate from memory.
4. **Confirm the source file before drafting a summary.** Use today's dated notes, not a stale dated
   file or an unreliable file-activity listing. If the intended source is ambiguous or looks wrong,
   ask which file before drafting.
5. **Don't declare done prematurely.** Never claim a file was written, a task is complete, or an
   action succeeded without confirming it — and don't close a task while human-gated sub-steps
   remain. State plainly what's done versus still pending.
6. **Edit additively; confirm before overwriting.** When changing existing config, policy, or
   template files, prefer additive or duplicated changes over replacing content, and confirm before
   overwriting anything you didn't create.
7. **Stay scoped.** If you find a related issue mid-task, note it in a `## Follow-ups` section and
   keep going — don't chase it. Ask before broadening scope.

## Integration Notes

- The vault integrates with Obsidian for editing and graph visualization.
- Dataview queries power dynamic content in templates; task management uses the Tasks plugin format.
  Required community plugins are listed in `.obsidian/community-plugins.json`.
- Cross-references use Obsidian wikilinks and embeds. **Always vault-absolute** — the full path from
  the vault root, no leading slash, no `.md`: `[[03-Resources/tools/vault-indexer/README]]`, alias
  form `[[full/path|short label]]` for readable prose, `![[full/path]]` to embed. Bare basenames are
  ambiguous or unresolved and break silently. Confirm the target exists before writing the link, and
  check your work with `scan_broken_wikilinks.py`. Full rationale: [[AGENTS]] § Markdown & Naming
  Conventions.
