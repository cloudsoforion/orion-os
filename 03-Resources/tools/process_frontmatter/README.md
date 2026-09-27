---
created: "20260604"
updated: "20260808"
tags:
  - created/20260604
  - updated/20260808
  - type/readme
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# process_frontmatter

Stamps `created/YYYYMMDD` and `updated/YYYYMMDD` tags into the YAML frontmatter of every
markdown file under a directory. It works out the most accurate creation date it can from the
filename, the folder path, or git — and skips the file rather than guessing when it can't.

**Dry-run is the default.** The blast radius is every note in the vault, so nothing is written
without `--apply`.

## How it works

- Collects every `.md` file under the target, skipping the directories named in
  `vault_config.py` (`skip_dirs` plus, by default, anything hidden).
- Builds a `path → first-commit-date` map in **one** `git log` pass over the whole history —
  about 2s for a 96k-path repo, versus minutes of per-file subprocesses.
- Resolves each file's creation date through the decision table below, most-trustworthy source
  first: filename → folder path → git.
- Rewrites the `tags` list: strips any existing `created/` tag, inserts the resolved one first,
  appends `updated/<today>`. Tag prefixes come from `vault_config`, not from this script.
- Prints what it would change, then stops. `--apply` is the only thing that writes.

## Date resolution

| Filename has date? | Path has date? | Has `created/` tag? | Git date | Action |
|---|---|---|---|---|
| Yes | — | Yes | — | Do nothing — filename is authoritative |
| Yes | — | No | — | Stamp with filename date |
| No | Yes (older) | Yes | — | Update tag to the older path date |
| No | Yes (newer) | Yes | — | Do nothing — existing tag is correct |
| No | Yes | No | — | Stamp with path date |
| No | No | Yes | newer/absent | Do nothing — existing tag is correct |
| No | No | Yes | older | Update tag to the git date |
| No | No | No | present | Stamp with the git date |
| No | No | No | absent | **Skip, and say so** |

A date is `YYYYMMDD`, or the date part of the vault's `YYYYMMDDHHMM` stamp — the 12-digit form
is tried first, because a bare `\d{8}` never matches inside a 12-digit run and 283 notes here
carry that prefix.

**The fallback is git, not the filesystem.** `min(st_ctime, st_mtime)` was removed in 0.3.0.
Measured on this vault, mtime dated `CLAUDE.md` to `20260729` where git says `20250924` — a
fabricated date, ten months wrong, and indistinguishable from a real one once written. See
[03-Resources/tools/20260605-filesystem-timestamps-unreliable](../20260605-filesystem-timestamps-unreliable.md). Git reports when a path was
*added*, so a moved file carries its move date; files moved in a bulk reorg are almost always
dated by filename or path anyway and never reach that branch.

## Commands

```bash
# Preview across the whole vault. The vault root is found by walking up for .obsidian/
python3 process_frontmatter.py

# Preview one subtree
python3 process_frontmatter.py --directory 02-Projects

# Write the changes you just previewed
python3 process_frontmatter.py --apply
```

## Flags

| Flag | Meaning |
|---|---|
| `--directory PATH` | Directory to process. Default: the vault root, found via `.obsidian/`. |
| `--apply` | Write the changes. Without it, nothing is written. |
| `--dry-run` | Explicitly preview only. Already the default; wins if combined with `--apply`. |

## Output

Everything goes to stdout — no files are generated. Each pending change prints as
`Would add|update created/<date>, updated/<date> in <path>`, followed by a summary of files
processed, changes pending, skips, and errors.

## Tests

```bash
python3 -m pytest tests/
```

51 tests. The module docstring's decision table is mirrored in
`tests/test_process_frontmatter.py`, which is the specification of record. The git tests build a
throwaway repo with `git init`; no network, and never the live vault.

## First run / new machine

```bash
pip install -r requirements.txt   # PyYAML
```

Requires `git` on `PATH` for the fallback. Without it the git map comes back empty and undated
files are skipped rather than misdated — the tool still runs.

## Related

- `vault_config.py` — tag prefixes, skip-dirs, vault-root discovery
- [03-Resources/tools/20260605-filesystem-timestamps-unreliable](../20260605-filesystem-timestamps-unreliable.md) — why the mtime fallback went
- [03-Resources/tools/CONTRIBUTING](../CONTRIBUTING.md) — the standard this tool is measured against
- [CLAUDE](../../../CLAUDE.md) — the vault's metadata standards, which the tags implement
