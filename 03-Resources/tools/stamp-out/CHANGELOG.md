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

## [0.3.0] — 2026-08-08

### Changed
- **The report note's frontmatter now comes from `vault_config.py`.**
  `author:` was hardcoded to `Claude (claude-opus-5)`, which credited a specific model version for
  a file this script writes and went stale on every release; it now takes `author` from
  `vault.json`, overridable per-run. The `created/`, `updated/`, `type/`, and `domain/` prefixes
  come from the same place, so renaming one in `vault.json` is a single edit.
- Vault-root discovery and the skip-dir set are no longer declared here. The local
  `find_vault_root` copy is gone (re-exported from `vault_config` so the module's public surface
  is unchanged), and `SKIP_DIRS` is replaced by `vault_config.prune_dirs` — which also skips
  hidden directories, so a `.pytest_cache/` inside a stamped folder is no longer indexed.

### Fixed
- **`--help` crashed.** `TIMESTAMP_FMT` (`%Y%m%d%H%M`) was interpolated into an argparse help
  string, and argparse runs %-formatting over help text, so building the help raised
  `ValueError: unsupported format character 'Y'`. Present since 0.1.0 and unnoticed because
  nothing ever invoked `--help`. Now escaped, with `TestCliHelp` pinning it.

### Added
- **`--author NAME`** for the report note.
- `README.md` now says why `--dry-run` is opt-in here while `process_frontmatter` defaults to it:
  the blast radius is a new copy, not the original.

### Tests
- `tests/test_stamp_out.py` — **20 → 27 tests**. New: `TestWriteReportFrontmatter` (5 — author
  precedence, the tool-name fallback, config-driven tag prefixes, and one asserting no hardcoded
  model name can come back), `test_skips_hidden_and_named_directories_from_config`, and
  `TestCliHelp::test_help_builds_without_raising`.

## [0.2.0] — 2026-08-07

### Added
- `tests/test_stamp_out.py` — 20 tests, passing via `python3 -m pytest tests/`. Covers the three
  constraints that would silently corrupt a stamped copy if they regressed: escaped `\|` alias
  pipes surviving a round trip, inline-code masking, and `.md`-only suffix handling in
  `build_target`. Also pins `index_folder`'s contract, including the basename-collision case that
  is the whole reason bare-basename wikilinks are unsafe.
- This CHANGELOG (remediation item 10 of
  a dated compliance audit).

### Note
- No behaviour changed in this release. The version bump records that the tool reached the
  Definition of done in [[03-Resources/tools/CONTRIBUTING]].

## [0.1.0] — 2026-07-29

Initial version.

- Copies a vault folder to a timestamped destination and rewrites wikilinks inside the copy so
  links resolving to files *within* the copied set point at the copy. Links to notes elsewhere in
  the vault are left alone.
- `--dry-run`, `--timestamp`, and `--rewrite-existing <folder> --source <original>` modes.
- Deliberate constraints, all documented in the module docstring:
  - **Nothing is renamed** — filenames stay byte-identical so `kubectl apply -f` paths, `NN-`
    apply ordering, and script-to-script `source` calls keep working.
  - **Only `.md` files are edited** — `[[ ... ]]` is also bash test syntax, so rewriting yaml/sh/txt
    would corrupt shell scripts.
  - Fenced code blocks and inline code spans are skipped.
  - Unresolvable links are reported, never guessed at.

### Known limitation
- README has no `## Tests` section as of 0.1.0; added in 0.2.0.
