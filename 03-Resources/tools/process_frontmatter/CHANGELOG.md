---
created: "20260807"
updated: "20260808"
tags:
  - created/20260807
  - updated/20260808
  - type/changelog
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# Changelog

Promoted 2026-08-07 from the ad-hoc `## Version History` section in `README.md`
(remediation item 4 of a dated compliance audit).

Versions at 0.2.1 and below were reconstructed from git history, not invented — commit dates and
subjects are the source. Entries predating this file are necessarily coarser than the format in
[[03-Resources/tools/CONTRIBUTING]] requires; they are not retrofitted beyond what git supports.

## [0.3.0] — 2026-08-08

### Changed
- ⚠️ **Breaking invocation change: dry-run is now the default, and `--apply` is required to
  write.** Previously `--dry-run` was opt-in, so the invocation documented in the README rewrote
  frontmatter across all ~4,900 notes. This is the shape [[03-Resources/tools/CONTRIBUTING]]
  § Script conventions outlaws and the one that killed `archive-folders`
  (the `archive-folders` post-mortem). `--dry-run` is still accepted and
  wins if combined with `--apply`. **Any script or habit that ran this tool bare now previews
  instead of writing — add `--apply`.**
- ⚠️ **The filesystem-timestamp fallback is gone; the fallback is now the git add-date.**
  Decided on 2026-06-05 ([[03-Resources/tools/20260605-filesystem-timestamps-unreliable]]) and
  unimplemented until now. Measured on the live vault: mtime dated `CLAUDE.md` to `20260729`
  where git says `20250924`. An undated, untracked file is now **skipped** rather than stamped
  with a date that means "last touched". Git dates come from one `git log --reverse
  --diff-filter=A` pass (~2s for 96k paths), not a subprocess per file.
  Measured effect on this vault: 220 mtime-derived stamps became 174 accurate git stamps plus
  46 honest skips, and two files still carrying the bogus `20241223` floor date were corrected.
- ⚠️ **`YYYYMMDDHHMM` filename stamps are now recognised.** A bare `\d{8}` never matches inside
  a 12-digit run, so the 283 notes named with the vault's `%Y%m%d%H%M` convention looked
  undated and fell through to the fallback. Where a name holds both forms — e.g.
  `202605291147-20250529-20260529-range-summary.md` — the file's own stamp now wins over an
  embedded content date. Measured effect: 145 files resolve to a more accurate date, typically
  their own creation stamp instead of their parent work-folder's date.
- Vault root, tag prefixes, and skip-dirs now come from
  `vault_config.py` instead of being declared here. The
  hardcoded `--directory` default (`<vault>`) is gone — the vault is
  found by walking up for `.obsidian/`.
- Skip-dirs now exclude hidden directories by default, which stopped the tool stamping vault
  frontmatter into seven `.pytest_cache/README.md` files. Running the test suite used to create
  another one.
- `README.md` cut from 378 lines to the sections [[03-Resources/tools/CONTRIBUTING]] requires;
  the emoji feature checklist and the stale `10-tools/` paths went with it.

### Added
- `resolve_created_date()` — the decision table as a pure function, so every row is a unit test
  rather than a filesystem fixture.
- `date_from_text()` — the shared `YYYYMMDD` / `YYYYMMDDHHMM` recogniser.
- `git_add_dates()` — the one-pass git date map. Returns `{}` outside a repo, so the tool
  degrades to skipping rather than failing.
- `collect_markdown()` — file collection with `vault_config`-driven skip-dirs.
- A `Usage:` block in the module docstring, which was missing.

### Tests
- `tests/test_process_frontmatter.py` — **16 → 51 tests**. New: `TestDateFromText` (7),
  `TestFilenameAndPathDate` (4), `TestResolveCreatedDate` (10, one per decision-table row),
  `TestGetExistingCreatedDate` (4), `TestCollectMarkdown` (3), `TestGitAddDates` (4, against a
  throwaway `git init` repo), `TestProcessFileDryRun` (1), plus
  `test_undated_untracked_file_is_skipped_not_guessed` pinning that the mtime fallback cannot
  come back.

### Migration
- No data migration. Re-run `python3 process_frontmatter.py` to see the new pending set; it is
  smaller and more accurate than 0.2.1's. Nothing was applied when this version landed.

## [0.2.1] — 2026-06-15

### Changed
- Folder references updated for the June 2026 reorg: `04-Projects` → `02-Projects`,
  `05-Resources` → `03-Resources`, `06-Archive` → `04-Archive` (`e9047e66`). See
  memory `project_vault-folder-reorg-2026-06` — paths in older docs elsewhere are still stale.

## [0.2.0] — 2026-06-05

### Added
- Date-resolution decision table, documented in the module docstring and mirrored in
  `tests/test_process_frontmatter.py` — the test module is the specification of record.
- Multi-vault support via `--directory`.

### Changed
- Date resolution now prefers a `YYYYMMDD` filename prefix over filesystem mtime.
  Rationale: mtime is unreliable in this vault — see
  [[03-Resources/tools/20260605-filesystem-timestamps-unreliable]].

## [0.1.0] — 2026-06-04

Initial version (`5d584923`).

- Adds `created/YYYYMMDD` and `updated/YYYYMMDD` tags to frontmatter
- Extracts dates from filenames, falling back to file timestamps
- Converts legacy `created:` fields to tags
- `--dry-run` for safe previewing
- Recursive directory processing with exclusions

### Tests
- `tests/test_process_frontmatter.py` — 16 tests, passing via `python3 -m pytest tests/`.

## Known limitation

- No `__version__` constant in the script; per [[03-Resources/tools/CONTRIBUTING]] the
  CHANGELOG heading is the version of record.
