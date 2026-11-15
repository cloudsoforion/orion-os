---
created: "20260616"
updated: "20260924"
tags:
  - created/20260616
  - updated/20260924
  - type/readme
  - domain/tooling
  - domain/knowledge-management
  - status/active
status: active
---

# scan-broken-wikilinks

Finds wikilinks that don't resolve, the ones that resolve by luck, and relative markdown links that
don't resolve. Reports all three by default and writes nothing. Repairs are opt-in and never rewrite a
link toward a target that doesn't exist.

> The name predates markdown-link support. It still says "wikilinks" because renaming a tool
> touches every doc and hook that calls it, so that's a separate change.

This enforces the standard in [AGENTS](../../../AGENTS.md) § Markdown & Naming Conventions — vault-absolute links,
always — which until now had no automated check.

## How it works

- Walks every `.md` file, skipping the directories `skip_dirs` names in `vault.json` plus anything
  hidden. That excludes `.trash/`, `.git/`, and the stale pre-reorg vault copy under
  `.claude/worktrees/`.
- Skips fenced code blocks and inline code spans. `[[ -d "$dir" ]]` is bash, and the reorg
  write-ups quote broken paths like `[[04-Projects/foo]]` on purpose.
- Indexes **every** file in the vault by name and stem, not just `.md` — Obsidian links
  attachments (`[[manifest.yaml]]`, `[[postmortem.pdf]]`) the same way notes are linked.
- Classifies each link as a path link (does the target exist? does a remap fix it?) or a bare
  basename (how many candidates does the name have — none, one, or several?).
- Checks **markdown links** (`[label](path)`, `![alt](path)`) the way GitHub resolves them:
  **relative to the linking file**, with `%20` decoded, `#fragment` ignored, and a leading `/`
  meaning the vault root. External URLs, `mailto:`-style schemes, same-page `#anchors`, and nested
  pasted links (`[a]([b](url))`) are skipped. A target may contain one level of balanced
  parentheses, as in CommonMark. These are the links the GitHub-facing docs use; see
  [AGENTS](../../../AGENTS.md) § Markdown & Naming Conventions, *Exception*.
- Optionally rewrites, in two independent modes, then **re-scans** so the summary reports what
  remains rather than the work just done.

## Statuses

| Status | Meaning | Fix |
|---|---|---|
| `fixable` | Broken path link; the remapped target exists | `--apply` |
| `remap-no-target` | Matched a remap prefix, but the target still doesn't exist | human |
| `no-remap` | Broken path link, no remap matched | human |
| `basename-ambiguous` | Bare basename with **>1** candidate — Obsidian picks one, silently | human |
| `basename-unresolved` | Bare basename with **no** candidate — an invisible break | human |
| `basename-single` | Bare basename with exactly **1** candidate — resolves, but violates the standard | `--promote-basenames` |
| `md-broken` | Markdown link whose target exists nowhere | human |
| `md-root-relative` | Markdown link that resolves only when read from the vault root. Obsidian falls back to that, so it works there, but it's broken on GitHub | `--apply` |

A bare name whose single candidate is a **root-level** file is not a finding: for `[[AGENTS]]` the
bare name already *is* the vault-absolute path.

`basename-unresolved` includes links to Claude memory files under
`~/.claude/projects/.../memory/`. Those live outside the vault and can never resolve; reference
them as plain text, not as links.

## Commands

```bash
# Report on the whole vault. Writes nothing.
python3 scan_broken_wikilinks.py

# Same, plus a dated markdown report in the ops journal
python3 scan_broken_wikilinks.py --report

# Repair broken path links left by a folder rename, verified target-by-target
python3 scan_broken_wikilinks.py --remap 09-archive/=04-Archive/ --apply

# Rewrite [[name]] -> [[full/path|name]] wherever exactly one file matches
python3 scan_broken_wikilinks.py --promote-basenames

# Counts only — suitable for a pre-commit or CI gate
python3 scan_broken_wikilinks.py --quiet
```

## Flags

| Flag | Meaning |
|---|---|
| `--vault PATH` | Vault root. Default: found by walking up for `vault.json`. |
| `--remap OLD/=NEW/` | Prefix rewrite, repeatable. Adds to `link_remaps` in `vault.json`. |
| `--exclude GLOB` | Skip files matching a vault-relative glob, repeatable. Adds to `exclude_paths`. |
| `--apply` | Rewrite `fixable` path links, and `md-root-relative` links to the correct file-relative path. Nothing else. |
| `--promote-basenames` | Rewrite `basename-single` links to full paths, keeping the old name as the alias. |
| `--no-basenames` | Only check path links; skip the basename analysis entirely. |
| `--no-markdown` | Skip markdown links; check wikilinks only (the pre-2.1.0 behaviour). |
| `--report [PATH]` | Write a markdown report. Bare `--report` puts a dated one in `log_dir`. |
| `--quiet` | Counts only. |

**There is no remap baked in.** A default remap is a hardcoded taxonomy, and that is what killed
`archive-folders` — see the `archive-folders` post-mortem. Durable remaps go
in `vault.json` under `link_remaps`; one-offs go on the command line.

## Output

Counts to stdout. `--report` writes a note with frontmatter (tag prefixes from `vault.json`), a
summary table, a breakdown by link prefix, and one table per status listing file, line, target, and
proposed replacement.

```
<log_dir>/<YYYYMMDDHHMM>-broken-wikilinks-report.md
```

## Why the counts moved

Measured on this vault, 2026-08-08. The previous script reported **906** broken path links; the
same vault now reports **158**:

| Change | Effect |
|---|---|
| Skip `skip_dirs` + hidden dirs | `.trash/` and the `.claude/worktrees/` pre-reorg vault copy stop being scanned |
| Skip fenced + inline code | The reorg write-ups' illustrative `[[04-Projects/…]]` paths stop counting |
| `exclude_paths` | The two auto-generated `work-chronology` notes held **273 of 475** findings — they cite historical paths deliberately. Also excludes `templates/*-README.md`, whose `<placeholder>` links are meant to be filled in |

The basename analysis is new, and it is the larger finding: **3,907** bare-basename links, almost
all in `04-Archive/` legacy notes, plus **26** genuinely ambiguous ones worth fixing by hand.
Nothing has been applied.

## Tests

```bash
python3 -m pytest tests/
```

90 tests, no network, never the live vault. The two load-bearing ones:
`test_does_not_rewrite_when_the_remapped_target_is_missing` (a repair must never convert a visibly
broken link into a plausibly broken one) and the `TestScanDryRun` pair (a bare run leaves the vault
byte-identical).

## First run / new machine

Stdlib only — no `requirements.txt`. Run from anywhere inside the vault.

## Related

- [AGENTS](../../../AGENTS.md) — § Markdown & Naming Conventions, the standard this checks
- `vault_config.py` — skip-dirs, `link_remaps`, `exclude_paths`, tag prefixes
- the July link triage —
  the July triage that asked for the basename mode
- [03-Resources/tools/CONTRIBUTING](../CONTRIBUTING.md) — the standard this tool is measured against
