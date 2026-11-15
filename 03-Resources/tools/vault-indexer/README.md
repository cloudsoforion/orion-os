---
created: "20260615"
updated: "20260808"
tags:
  - created/20260615
  - updated/20260808
  - type/readme
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# vault-indexer

Incremental file tracker for an Obsidian vault. Maintains a SQLite index so daily work summaries don't require re-reading the entire vault.

## How it works

- `os.stat` every `.md` file (fast — just syscalls), compare `(mtime, size)` against the DB
- Only reads file content when a file actually changed
- Tracks **inodes** to detect moves/renames without re-reading content
- Tracks a **`content_hash`** so a *move* (which bumps mtime but not content) isn't mistaken for an edit — the daily summary uses `content_mtime` (advances only on a real content change), so moved-only files don't pollute it. *(v0.6.0)*

## Commands

> **Note:** `index` and `summary` are the two **commands** (required, positional). Everything with `--` is an **option** — e.g. `--reindex` attaches to `index`, so it's `index --reindex`, **not** `--reindex` alone.

```bash
# Update the index — incremental, safe to run anytime.
# Only reads files that are new or changed; skips everything else.
python vault_indexer.py index

# Force a full re-read of every file (repopulates extracted data + content hashes).
# Run this once after upgrading so move-detection has a content baseline.
python vault_indexer.py index --reindex

# Restrict indexing to certain top-level folders
python vault_indexer.py index --folders 00-Inbox/work 02-Projects

# Write today's summary to the ops journal:
#   Log/<week-Monday>/<YYYYMMDD>-daily-summary.md
python vault_indexer.py summary

# Summary for a specific past date (uses file mtime — "what did I touch that day")
python vault_indexer.py summary --date 2026-05-20

# Summary for a date range (uses the path date — "what work lived in this window")
# Writes Log/<runtimestamp>-<from>-<to>-range-summary.md
python vault_indexer.py summary --from 2026-06-01 --to 2026-06-30
python vault_indexer.py summary --from 2026-06-01 --to 2026-06-30 --folders 02-Projects

# Write the summary somewhere other than the configured log_dir
python vault_indexer.py summary --output-dir /tmp/vault-summaries
```

### All flags

| Flag | Applies to | Meaning |
|---|---|---|
| `--reindex` | `index` | force-read every file (ignore the mtime/size skip) |
| `--folders F [F …]` | `index`, `summary` | restrict to files under these path prefixes |
| `--date YYYY-MM-DD` | `summary` | single-day summary via **mtime** (default: today) |
| `--from` / `--to YYYY-MM-DD` | `summary` | date-range summary via **path date** (not mtime) |
| `--output-dir PATH` | `summary` | where summaries are written (default: `log_dir` from `vault.json`). Relative paths resolve against the vault root |
| `--vault PATH` | both | vault root (auto-detected from `vault.json` if omitted) |
| `--db PATH` | both | database path (default: `<script-dir>/vault-index.db`) |

## Output

`summary` writes to the **ops journal** — `log_dir` in
`vault.json`, `Log/` by default (see
[Log/README](../../../Log/README.md)):

- **daily** → `<log>/<week-Monday>/<YYYYMMDD>-daily-summary.md`
  (flat in the week folder; the week folder is the Monday of that date's week, created automatically)
- **range** → `<log>/<runtimestamp>-<from>-<to>-range-summary.md` (range reports span weeks, so they sit at the log root)

Rename the folder in `vault.json` and both paths follow; `--output-dir` overrides it for one run.

Files are grouped by work folder — any folder whose name starts with `YYYYMMDD-`
is treated as a work item. All files touched within that folder appear as a
bullet list under one heading, keeping related artifacts (audit outputs,
changelogs, READMEs) together rather than scattered across the summary.

Each file line shows:
- `[[wikilink]]` to the file — clickable in Obsidian
- Time last modified
- H2 section headings — gives the shape of the work at a glance

### Getting a narrative summary

Open the daily summary in Obsidian or hand it to Claude Code:
> "Summarize what I worked on today based on this file."

## Files

| File | Purpose |
|---|---|
| `vault_indexer.py` | Main script |
| `vault-index.db` | SQLite database (gitignored) |
| `tests/` | pytest suite — see below |

## Tests

Run from this directory:

```bash
python3 -m pytest tests/
```

52 tests, ~0.05s, no network. Split across `tests/test_pure_functions.py` (40 — date
resolution, week-Monday math, path mapping, summary formatting) and `tests/test_scan.py`
(12 — filesystem walking against a throwaway vault built with `tmp_path`).

Tests never touch the live vault or `vault-index.db`. Filesystem tests set mtimes
explicitly with `os.utime` rather than depending on wall-clock — see
[03-Resources/tools/20260605-filesystem-timestamps-unreliable](../20260605-filesystem-timestamps-unreliable.md) for why asserting on real
vault timestamps is unsafe.

## Related

- `vault_config.py` — vault-root discovery, `log_dir`, tag
  prefixes, skip-dirs, and the shared date recogniser
- [process_frontmatter](../process_frontmatter/README.md) — reads the same date
  convention to stamp `created/` tags
- [second-brain](../second-brain/README.md) — embeds into the same
  `vault-index.db`
- [03-Resources/tools/CONTRIBUTING](../CONTRIBUTING.md) — the standard this tool is the reference implementation of

## First run / new machine

`vault-index.db` is not committed to git — it's derived data that's fully
reproducible from the vault files. When pulling to a new machine, run:

```bash
python vault_indexer.py index
```

This reads every `.md` file on first run to populate the DB (~few seconds).
After that, runs are incremental and only re-read files that changed.
