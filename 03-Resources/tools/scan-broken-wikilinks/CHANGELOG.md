---
created: "20260616"
updated: "20260808"
tags:
  - created/20260616
  - updated/20260808
  - type/changelog
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# Changelog

Versions 1.0.0 and 1.1.0 were developed at
`CHANGELOG/20260616-updating-folder-structure/scan-broken-wikilinks/` as session tooling for the
June 2026 reorg. 2.0.0 promoted it into a real tool under `03-Resources/tools/`; those two entries
are carried forward verbatim rather than rewritten.

## [2.0.0] — 2026-08-08

Promoted from session tooling to a compliant tool, per
[[03-Resources/tools/CONTRIBUTING]]. Module renamed `scan-broken-wikilinks.py` →
`scan_broken_wikilinks.py` so it is importable and therefore testable.

### Added
- **Bare-basename analysis** — the enhancement requested at
  the July link triage
  item 7. 1.x skipped basename links on the belief that "Obsidian resolves those by name", which is
  exactly the belief [[AGENTS]] § Markdown & Naming Conventions contradicts: a basename with
  several candidates resolves unpredictably and a basename with none renders as unclickable text.
  Three new statuses — `basename-single`, `basename-ambiguous`, `basename-unresolved`.
  First measurement on this vault: **3,907 / 26 / 126**.
  A bare name whose single candidate sits at the **vault root** is treated as already correct, not
  as a violation: for `[[AGENTS]]` the bare name *is* the vault-absolute path, which
  [[AGENTS]] § Markdown & Naming Conventions states outright. Without that branch the tool nagged
  about every reference to `OrionOs`, `AGENTS`, and `CLAUDE`.
- **`--promote-basenames`** — rewrites `[[name]]` to `[[full/path|name]]` where exactly one file
  matches, keeping the old name as the alias so prose reads unchanged. Independent of `--apply`;
  both are opt-in.
- **`--exclude GLOB`** and `exclude_paths` in `vault.json`. On this vault the two auto-generated
  `work-chronology` notes held **273 of 475** path-link findings — they cite historical
  paths on purpose, and counting them every run buried the ~150 a human could act on.
- **`--quiet`** for use as a pre-commit or CI gate.
- `tests/` — **62 tests**, from zero. The two load-bearing ones:
  `test_does_not_rewrite_when_the_remapped_target_is_missing` and the `TestScanDryRun` pair.

### Changed
- **Skip-dirs come from `vault_config`**, so `.trash/`, `.git/`, and the stale pre-reorg vault copy
  under `.claude/worktrees/` are no longer scanned. 1.x skipped only `.git`.
- **Fenced code blocks and inline code spans are no longer scanned.** `[[ -d "$dir" ]]` is bash,
  and the reorg write-ups quote broken paths deliberately. Both were counted as findings before.
- **The basename index covers every file type, not just `.md`.** Obsidian links attachments the
  same way notes are linked, so a markdown-only index called `[[manifest.yaml]]` an invisible
  break. This alone moved the unresolved count from 1,092 to 129.
- ⚠️ **The default remap is gone.** 1.x baked in the June 2026 reorg map
  (`04-Projects→02-Projects`, `06-Archive→04-Archive`, `05-Resources→03-Resources`). That is a
  hardcoded taxonomy, which is what killed `archive-folders`
  (the `archive-folders` post-mortem) — and the reorg it encoded is long
  finished, so it now matches nothing. Durable remaps go in `vault.json` under `link_remaps`;
  one-offs go on `--remap`. **Any invocation relying on the built-in map must now pass it
  explicitly.**
- The hardcoded `--root` default (`~/notes`) is replaced by vault-root discovery;
  the flag is now `--vault`, matching every other tool here.
- Report frontmatter is generated from `vault.json` tag prefixes and carries the current date.
  1.x hardcoded `created/20260616` into every report it ever wrote.
- `--report` with no argument now writes a dated report into `log_dir` instead of requiring a path.

### Net effect on this vault
Same vault, same day: **906 → 158** broken path links, all of the difference being false positives
that 1.x counted. Nothing was applied.

### Known limitation
- `basename-single` numbers in the thousands and is concentrated in `04-Archive/` legacy notes.
  `--promote-basenames` would touch ~4,000 links in one pass; it has **not** been run. Whether
  archived notes are worth rewriting at all is an open call.

## [1.1.0] — 2026-06-16

### Changed
- **`--apply` now runs two passes** so the summary and report reflect the **post-fix
  remaining** state, not the in-pass tally. Previously an apply printed the same counts as
  a dry-run (it reported what it *found and fixed*, labelled `(APPLIED)`), which read as if
  nothing changed.
- stdout now prints `APPLIED: <N> link(s) rewritten in place` followed by
  `remaining broken …` with `remaining fixable: 0` after a successful apply.
- The written report (when `--apply --report`) gains an `applied: <N>` line and labels its
  counts as **remaining**.

### Fixed
- "fixable" count after an apply now shows what's left to fix (~0), resolving the
  "did anything change?" confusion. See
  broken-wikilinks-resolution.

## [1.0.0] — 2026-06-16

### Added
- Initial version of `scan-broken-wikilinks.py`.
- Scans a vault for path-style `[[...]]` wikilinks whose target is missing on disk;
  ignores basename-only links (Obsidian resolves those by name).
- Verified prefix remap: rewrites a stale top-level prefix to its current one **only when
  the remapped target actually exists**. Defaults cover the 2026-06 reorg
  (`04-Projects→02-Projects`, `06-Archive→04-Archive`, `05-Resources→03-Resources`).
- Dry-run by default; `--apply` to edit in place; `--report` to emit a full markdown
  report; `--remap OLD/=NEW/` to add prefix mappings.
- Preserves `#heading`, `|alias`, and `!embed` syntax on rewrite.

### Notes
- First scan of the vault (2026-06-16): **1,467 broken** path-style wikilinks
  — **1,130 fixable** by remap, 166 matched-but-target-missing, 171 misc/no-remap.
  No `--apply` run yet; fixes pending review (see
  updating-folder-structure).
