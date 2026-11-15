---
tags:
  - type/readme
  - domain/tooling
  - status/active
  - created/20260729
  - updated/20260808
  - domain/knowledge-management
author: Claude (claude-opus-5)
created: "20260729"
updated: "20260808"
status: active
---

# stamp-out

Stamp out a timestamped copy of a vault folder **with its internal links and paths
repointed at the copy**.

Built for DR-exercise runbooks: you copy a runbook folder per exercise run, then
annotate the copy live. A plain `cp -R` looks like it works and doesn't.

## The problem it solves

After `cp -R runbook-x 202607290947-runbook-x`, links inside the copy still resolve
to the **original**:

| Link form in the source | What it does in a plain `cp` copy |
| --- | --- |
| `[[02-Projects/.../runbook-x/read-replica.yaml]]` | still opens the **original** file |
| `[[runbook-design-notes]]` | now **ambiguous** — that basename exists twice |
| `DR=~/notes/.../runbook-x` (shell var) | applies manifests from the **original** |

So you annotate one copy and read another, and `kubectl apply -f $DR/...` fires the
original folder's manifests. All three failures are silent.

## What it does

1. `cp -Rp` the folder to `<YYYYMMDDHHMM>-<name>` (mtimes preserved, so
   `process_frontmatter.py` doesn't restamp everything as new).
2. Rewrites wikilinks in the copy's `.md` files: any link resolving to a file
   *inside* the copied set becomes a vault-absolute path into the copy.
3. Repoints filesystem path references (shell vars, apply-paths) at the copy.
4. Writes a report note listing every link — repointed, external, and unresolved.

## Deliberate constraints

These are load-bearing; changing them will break runbooks.

- **Nothing is renamed.** Filenames stay identical, so `kubectl apply -f <path>`,
  `NN-` apply ordering, and script-to-script `source` calls keep working.
- **Only `.md` files get link rewriting.** `[[ ... ]]` is also bash test syntax
  (`[[ -d "$nsdir" ]]`); rewriting it inside `.sh` would corrupt deploy scripts.
- **Fenced code blocks and inline code spans are skipped** by the link pass.
- **Basename fallback only applies to links naming no directory.** A link like
  `[[dedicated-controlplane-mrs/README]]` is *not* retargeted at some other
  `README.md` just because the basename matches — that silently changes meaning.
  It gets reported as unresolved instead.
- **Path rewriting is boundary-guarded** (`(?![\w-])`), so a sibling folder that
  merely shares a prefix — `runbook-x-CLAIM` vs `runbook-x` — is never caught.
- **External links are left alone.** Links to canonical notes elsewhere in the
  vault should keep pointing there.
- **Unresolvable links are reported, never guessed at.**
- **Idempotent.** Re-running reports links as "already correct" and changes nothing.

## Usage

```bash
TOOL=03-Resources/tools/stamp-out/stamp_out.py   # relative to the vault root

# preview (writes nothing; report lands in $PWD)
python $TOOL path/to/runbook-folder --dry-run

# stamp it out
python $TOOL path/to/runbook-folder

# pin the timestamp instead of using "now"
python $TOOL path/to/runbook-folder --timestamp 202607290947

# fix up a copy you already made by hand with cp
python $TOOL 202607290947-runbook-folder --rewrite-existing --source runbook-folder
```

### Options

| Flag | Effect |
| --- | --- |
| `--dry-run` | Report only; writes nothing. Report goes to `$PWD`. |
| `--timestamp TS` | Use `TS` instead of now (`YYYYMMDDHHMM`). |
| `--dest-parent DIR` | Place the copy somewhere other than the source's parent. |
| `--rewrite-existing` | Skip the copy; rewrite an existing folder. Needs `--source`. |
| `--no-rewrite-paths` | Skip the filesystem-path pass (links only). |
| `--no-report` | Don't write the report note. |
| `--author NAME` | `author:` value for the report note. Default: `author` from `vault.json`. |
| `--vault PATH` | Vault root. Default: auto-detected via `vault.json`. |

**`--dry-run` is opt-in here, unlike `process_frontmatter`.** The blast radius is a *new copy*,
not the original — a bad run leaves a wrong folder beside a correct one rather than rewriting
your notes. Always `--dry-run` first anyway, and read the report.

## What it does NOT do

**It does not touch the contents of yaml manifests.** The copy is byte-identical
there, which means identifiers from the *previous* run are still baked in — DNS
names, cluster suffixes, DB instance names, IPs.
A stamped copy looks ready to apply and isn't. Updating those is a manual step;
nothing here should guess at them.

Moving a stamped folder afterwards must be done **in Obsidian**, not with `mv` —
the links inside it are vault-absolute and Obsidian rewrites them on move.

## Tests

```bash
python3 -m pytest tests/
```

27 tests, no network, never touches the live vault. They pin the constraints listed under
[Deliberate constraints](#deliberate-constraints) — escaped `\|` alias pipes, inline-code masking,
`.md`-only suffix handling, and the basename-collision case that makes bare-basename wikilinks
unsafe — plus the report frontmatter, which now comes from `vault.json` rather than being
hardcoded.

## Related

- `vault_config.py` — vault-root discovery, tag prefixes,
  `author`, skip-dirs
- [03-Resources/tools/README](../README.md) — tool index
- [03-Resources/tools/CONTRIBUTING](../CONTRIBUTING.md) — the standard this meets
- [CHANGELOG](CHANGELOG.md) — version history
