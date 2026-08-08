---
created: "20260615"
updated: "20260808"
tags:
  - created/20260615
  - updated/20260808
  - type/changelog
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# Changelog

## [0.8.0] — 2026-08-08

### Changed
- **The vault's shape now comes from `vault_config.py`.** The
  local `find_vault_root` copy, the `LOG_DIR` constant, the `SKIP_DIRS` set, and the hardcoded
  `created/` + `type/` tag strings in generated summaries are gone. Rename `log_dir` or a tag
  prefix in `vault.json` and this tool follows. Rationale in
  the `archive-folders` post-mortem: a tool that hardcodes a taxonomy
  inherits every reorg as a silent bug.
- **`path_date()` now recognises `YYYYMMDDHHMM` stamps**, via the shared recogniser. A bare
  `\d{8}` never matches inside a 12-digit run, so notes named with the vault's own `%Y%m%d%H%M`
  convention looked undated and dropped out of range summaries. Where a name holds both forms —
  `202605291147-20250529-20260529-range-summary.md` — the file's own stamp now wins over the
  dates of the period it covers.
  Measured effect on the July 2026 range summary: 3 files correctly included, and 1 range
  summary correctly excluded from a window it never belonged in. Index rows are byte-identical.
- The plausible-year bound (1990–2099) that `path_date` applied moved into the shared recogniser
  with it, so `process_frontmatter` gets it too — an 8-digit identifier is no longer read as a date.

### Added
- **`--output-dir`** for `summary`, overriding `log_dir` for one run. The flag was already
  documented in `second-brain/20260605-using-on-another-vault.md` before it existed; now it does.
  Relative paths resolve against the vault root.
- `summary_frontmatter()` — the generated-note frontmatter as a function, so the tag vocabulary
  has one source and one test.

### Tests
- `tests/` — 52, unchanged in count and all passing. `test_pure_functions.py`'s
  `TestPathDate::test_implausible_year_not_matched` is what caught the dropped year bound during
  the refactor; the shared recogniser's own bound is pinned by
  `tests/test_vault_config.py::TestDateFromText` (10 tests) at the tools root.

## [0.7.0] — 2026-07-13

### Changed
- **Summaries now write to the ops journal (`Log/`) instead of `00-Inbox/`.** Implements the ops-journal decision in `01-Areas/Knowledge-Management/20260707-inbox-refactor-para` (logs get their own home, out of the inbox). New layout:
  - daily → `Log/<week-Monday>/<YYYYMMDD>-daily-summary.md` (flat in the week folder)
  - range → `Log/<runtimestamp>-<from>-<to>-range-summary.md`
  - The week folder is created automatically (`mkdir -p`) before writing.
- Base folder is a new `LOG_DIR` constant (default `"Log"`) — one-line change if the folder is ever renumbered (e.g. `05-Log`).

### Added
- `week_monday(d)` helper — maps any date to the Monday of its week (the week-folder name).
- Tests: `TestWeekMonday` (Monday/midweek/Sunday/month-boundary).

### Known limitation (unchanged from 0.6.0)
- During a **mass migration**, Obsidian rewrites wikilinks *inside* files that point at moved files. That's a genuine content change, so those files' `content_mtime` advances and they surface in that day's summary even though you only "moved things." Pure moves are still excluded; link-rewrite-only edits are not. One-time noise on big reorg days.

## [0.6.0] — 2026-07-09

### Fixed
- **Daily summary no longer lists files that were only *moved*.** A move (e.g. reorganizing folders in Obsidian) bumps a file's filesystem mtime without changing its content; the old summary filtered on mtime, so the 2026-07-07 reorg dumped ~120 untouched files into that day's summary. Now each file tracks a **`content_hash`** and a **`content_mtime`** that advances *only* when the hash actually changes — the daily summary filters on `content_mtime`, so pure moves are excluded while genuine edits (and moved-**and**-edited files) still appear.

### Added
- Schema: `content_hash` (TEXT) + `content_mtime` (REAL) columns, with an in-place migration for existing DBs (backfills `content_mtime = mtime`; `content_hash` populates lazily as files are next read). No `--reindex` required, though it repopulates hashes immediately.
- Tests: `TestDailySummaryExcludesMovedOnlyFiles` — proves moved-only files are excluded, and guards that content-edits + moved-and-edited files still surface.

## [0.5.1] — 2026-06-05

### Changed
- `PATH_DATE_RE` relaxed from `^(\d{8})-` (date-prefix only) to `(?<!\d)(\d{8})(?!\d)` (date anywhere in path component) — folders like `OOMKilled-mcp-router-20231024` and files like `notes-20220411.md` now resolve correctly. Year/month plausibility check added to avoid false matches. Archive date coverage: 94% → 98%.

## [0.5.0] — 2026-06-05

### Changed
- `path_date()` now falls back to the `created/YYYYMMDD` frontmatter tag when no `YYYYMMDD-` prefix exists in the path — range summaries now surface files from thematic archive folders (incidents, platform, etc.) that predate the date-prefix naming convention. Path prefix still takes priority when present.

### Fixed
- `parse_frontmatter_tags()` silently dropped tags written without indentation (e.g. `- created/20220411` at column 0). Obsidian uses both indented and unindented formats depending on version. Run `vault_indexer.py index --reindex` once to repopulate extracted data for affected files.

## [0.4.0] — 2026-05-29

### Added
- `--from` / `--to` flags on `summary` for date range queries — uses `YYYYMMDD-` prefix in path (not mtime), so it reflects when work was created rather than last touched. Output: `YYYYMMDD-YYYYMMDD-range-summary.md`
- `--folders` flag on both `index` and `summary` — restrict to specific folder prefixes (e.g. `00-Inbox/work 04-Projects`)
- `--reindex` flag on `index` — forces re-read of all files regardless of mtime; needed after schema changes to pick up new extracted fields
- Tags extracted from YAML frontmatter and stored in index; shown inline in summary output

## [0.3.0] — 2026-05-22

### Changed
- Files now grouped by work folder (`YYYYMMDD-*` pattern) — related files consolidated under one heading instead of repeating
- Paths now rendered as `[[wikilinks]]` instead of backtick strings — clickable in Obsidian
- Removed assumed section extraction (`# prompt`, `# findings`, `# context`) — only headings listed, no content pulled

### Before / after
See daily-summary-before for the v0.1 output format and update-requests for the reasoning.

## [0.2.0] — 2026-05-22

### Changed
- Renamed `today` command to `summary`
- `summary` now writes `00-Inbox/YYYYMMDD-daily-summary.md` instead of printing to stdout
- Output includes Obsidian frontmatter (`created`, `#type/daily-summary` tag)

## [0.1.0] — 2026-05-21

Initial release.

- SQLite-backed incremental file index
- Inode tracking for move/rename detection
- `index` command: scan vault, update DB
- `today` command: print touched files with extracted section content to stdout
