---
tags:
  - created/20260729
  - updated/20260924
  - domain/knowledge-management
  - type/standard
  - status/active
author: Claude (claude-opus-5)
---

# Contributing to `03-Resources/tools/`

Standards for vault tooling. Derived from the tools that already live here — this codifies the
patterns the good ones share, it does not invent new ones.

Related: [AGENTS](../../AGENTS.md) (vault-wide conventions), [CLAUDE](../../CLAUDE.md) (metadata + documentation
standards), [OrionOs](../../OrionOs.md) (folder model, "move files in Obsidian only" rule).

This doc renders on GitHub, so its links are relative markdown links rather than `[[wikilinks]]`.
See [AGENTS](../../AGENTS.md) § Markdown & Naming Conventions for when each form applies.

---

## Scope

Applies to every directory under `03-Resources/tools/`. One directory per tool. A tool is
"done" when it passes the [Definition of done](#definition-of-done) checklist — not when
the script runs.

### What belongs here

Anything **you** run that reads the vault, writes to it, or reports into it. That is the test —
not the subject matter. A tool that scans container images or cloud accounts rather than markdown
still belongs here if its output is material you triage and prioritise in the vault.

### What doesn't, and where it goes instead

The deciding question is **audience**, not subject matter. A tool whose audience is your team
cannot live in a personal vault — nobody else can reach it, and a vault path is not resolvable to
anyone but you.

| Destination | For | Notes |
| --- | --- | --- |
| `03-Resources/tools/` | You, operating on or reporting into the vault | This standard, in full |
| Your team's shared tooling repo | **Team-audience** ops tooling | Promote only after the tool has been run for real a few times — see below |
| The owning system's repo (e.g. its `hack/` or `scripts/` dir) | Ops tooling with an obvious upstream home | Prefer this over a new shared location when one exists |
| A personal portable-tools repo | Portable tooling with no employer specifics | Give it a verification gate that rejects employer identifiers, so work-specific tooling can never land there |

### Promotion to team-audience

A tool graduates outward the same way work graduates through the vault: it earns the move, it is
not born there.

1. The prototype lives in the work folder that produced it, alongside the doc explaining why it
   exists.
2. If you keep reaching for it, it comes here and takes on this standard.
3. Once it has been **battle-tested on real incidents a few times**, it is promoted to the team
   repo — at which point the rationale doc stays in the vault and links out to the tool, rather
   than the tool being copied in two places.

---

## Required layout

```
03-Resources/tools/
├── vault_config.py         # the ONE shared module — see below. Not a tool.
├── tests/                  # its suite
└── <tool-name>/
    ├── <tool_name>.py      # or .sh — the entrypoint
    ├── README.md           # required
    ├── CHANGELOG.md        # required
    ├── requirements.txt    # required if it imports anything outside the stdlib
    └── tests/
        ├── __init__.py     # empty, present so `tests` is a package
        └── test_<unit>.py  # one file per coherent unit
```

Supporting design notes, session logs, and screenshots may live in the tool folder
(`vault-indexer/improvements/`, `second-brain/2026*-*.md` are the precedent). Keep them
date-prefixed so [vault-indexer](vault-indexer/README.md) can date them.

---

## Naming

| Thing | Rule | Why |
|---|---|---|
| Directory | kebab-case (`vault-indexer`, `stamp-out`) | matches vault filename convention |
| Python module | snake_case (`vault_indexer.py`, `stamp_out.py`) | **must be importable** — a hyphen makes `import` a syntax error, so the module cannot be unit-tested with the pattern below |
| Shell script | kebab-case | not imported, so no constraint |
| Docs | exactly `README.md` and `CHANGELOG.md` | any other name is invisible to the index and to tag queries |

The module name does **not** have to match the directory name (`stamp-out/stamp_out.py` is the
model): keep the directory kebab-case and the module snake_case rather than renaming the folder.
As of 2026-08-08 there are no un-importable modules left in this folder.

---

## Script conventions

Every entrypoint:

1. **Shebang** — `#!/usr/bin/env python3` or `#!/usr/bin/env bash`.
2. **Module docstring** that states, in this order: one-line purpose, what it reads/writes,
   and a literal `Usage:` block with copy-pasteable invocations. `vault_indexer.py` and
   `stamp_out.py` are the reference examples.
3. **Non-obvious logic documented in the docstring, not just the code.** Where behaviour is
   a decision table (date resolution, link rewriting), write the table in the docstring and
   mirror it in the test file. `process_frontmatter.py` + its test module are the pattern.
4. **`argparse`**, always — no positional-only `sys.argv` parsing.
5. **`--dry-run` is mandatory for anything that mutates the vault** (writes frontmatter,
   moves files, deletes rows). **Dry-run is the default where the blast radius is large**, with
   `--apply` required to act — [tool-scaffold](../../templates/tool-scaffold/README.md) encodes this.
   [AGENTS](../../AGENTS.md) treats dry-run output as the acceptance test, so it must print *what* changes,
   not just *how many*.
   ⚠️ The cautionary tale is `archive-folders` (retired 2026-08-08): `--dry-run` was opt-in, so
   the documented invocation ran a **live** `git mv` with no preview. See
   the `archive-folders` post-mortem. Do not copy that shape.
6. **`if __name__ == "__main__": main()`** — no work at import time, or the tests can't
   import the module.
7. **Pure functions pulled out of I/O.** Date parsing, path mapping, formatting, and
   filtering go in functions that take values and return values. This is what makes the
   test suites cheap; `vault_indexer.week_monday` / `path_date` / `format_daily_summary`
   are the model.
8. **Never `mv`, `git mv` is the exception.** Tools that relocate vault files must use
   `git mv` and must rewrite wikilinks (`stamp_out.py` is the reference).
   Shell-moving vault files without link rewriting is the failure that broke ~1000
   wikilinks in the June 2026 reorg.
9. **PEP 8, short typed functions, comment only non-obvious logic** ([AGENTS](../../AGENTS.md) § Python Utilities).

Prefer the stdlib. Two of the four tools are stdlib-only (`sqlite3`, `urllib`, `pathlib`,
`argparse`); the only dependencies in the folder today are `PyYAML` and `mcp`.

---

## The shared config module

**Ratified 2026-08-08.** There is **exactly one** shared module in this folder:
`03-Resources/tools/vault_config.py`. It owns the vault's shape — vault-root discovery, pillar
folder names, the `Log/` and `CHANGELOG/` locations, the frontmatter tag prefixes, the default
`author`, and the skip-dir set — plus its own suite at `03-Resources/tools/tests/`.

**No tool may re-declare any of those.** Import them:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vault_config

VAULT = vault_config.find_vault_root(Path.cwd()) or Path.cwd()
CONFIG = vault_config.load_config(VAULT)
```

Same `sys.path.insert` shape the test convention below already uses, for the same reason — no
packaging, no `conftest.py`, no editable install. From `<tool>/<tool>.py`, `parent.parent` is this
folder. From `<tool>/tests/test_x.py`, use `parents[2]`.

Why the exception exists, in the words of the post-mortem that earned it:

> "it encoded the vault's shape in 2026-02 and had no way to notice the vault had changed. **A tool
> that hardcodes a taxonomy inherits every reorg as a silent bug.**"
> — the `archive-folders` post-mortem

Before this module, `find_vault_root` was copy-pasted into two tools and **missing from a third**
(which hardcoded an absolute path instead), and four tools each declared a slightly different
`SKIP_DIRS`. The divergence was not theoretical: `process_frontmatter` walked into dot-directories
that `vault-indexer` skipped, and was stamping vault frontmatter into seven
`.pytest_cache/README.md` files.

**This is a ceiling, not a precedent.** One shared module, at this path, for the taxonomy only.
Anything else two tools happen to need goes in both, or the tools get merged. Cross-tool helper
libraries are how a folder of four scripts becomes a framework nobody can test.

---

## README.md

Required sections, in this order:

1. `# <tool-name>` — the directory name, verbatim.
2. Two-sentence purpose. What it does and what it operates on.
3. `## How it works` — the algorithm in 3–6 bullets. Not a feature list.
4. `## Commands` / `## Usage` — fenced blocks with a comment above each invocation
   explaining when you'd run it.
5. `## Flags` — a table (`Flag | Applies to | Meaning`) once there is more than one flag.
6. `## Output` — where files land, exact path templates.
7. `## Tests` — the literal command to run them.
8. `## First run / new machine` — prerequisites and bootstrap steps.
9. `## Related` — `[[wikilinks]]` to upstream/downstream tools and design notes.

Two anti-patterns to avoid, both present in the older READMEs:

- **Emoji feature checklists** (`- ✅ **Dry Run Mode**`). They restate the flags table and
  go stale silently. Delete on next edit.
- **600-line READMEs** that document every error string and future enhancement. Cap the
  README at what someone needs to *run* the tool; move rationale and history into a dated
  design note beside it and link to it. `vault-indexer/README.md` (~90 lines + an
  `improvements/` folder) is the target shape. The anti-example was `archive-folders/README.md`
  — 630 lines with 48 stale path references, describing a workflow that had not worked since the
  June 2026 reorg. Length was how the rot stayed hidden.

**Absolute paths in a README rot.** Reference vault files with
**vault-absolute** `[[wikilinks]]` ([AGENTS](../../AGENTS.md) § Markdown & Naming Conventions) and write
repo-relative paths for everything else. Hardcoded
`<vault>/...` is acceptable only where the path is genuinely required verbatim
(hook and MCP registration blocks).

---

## CHANGELOG.md

Keep-a-Changelog, adapted. Format is fixed by [vault-indexer](vault-indexer/CHANGELOG.md) and
[second-brain](second-brain/CHANGELOG.md):

```markdown
# Changelog

## [0.7.0] — 2026-07-13

### Changed
- **One-line bold claim.** Then the detail, including *why*, and a link to the note
  that prompted it.

### Added
- New helper / new tests, named.

### Fixed
- What was broken, what the user-visible symptom was, and what to run to recover
  (`index --reindex`, `embed.py --reembed`).

### Known limitation
- Behaviour that is still wrong and consciously accepted.
```

Rules:

- **Semver.** Bump minor for behaviour changes and new flags; patch for fixes with no
  interface change. There is no `__version__` constant in any tool today — the CHANGELOG
  heading is the version of record. Keep it that way unless a tool starts being installed.
- **`## [x.y.z] — YYYY-MM-DD`** with an em dash. Newest first.
- **Every entry names the tests added with it.** `vault-indexer` 0.6.0 and 0.7.0 both do
  this; it's what makes the changelog reviewable.
- **Fixes that require a migration or a re-run say so inline.** A changelog entry the reader
  can't act on is a missing entry.
- **Never rewrite a released entry.** Add a new one.

---

## Tests

Non-negotiable for anything that writes to the vault.

Conventions, taken from the three existing suites:

- **`pytest`**, run from the tool directory: `python3 -m pytest tests/`.
- **`tests/__init__.py`** (empty) plus, in each test module:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent))
  from vault_indexer import path_date, week_monday
  ```
  No packaging, no `conftest.py` path hacks, no editable installs.
- **Module docstring restates the spec** the tests enforce — the decision table for
  `process_frontmatter`, the invariant for `prune_orphans`. The test file is the
  specification document.
- **Group with plain classes**, one behaviour per class: `class TestWeekMonday:` with
  `test_monday_maps_to_itself`, `test_crosses_month_boundary`. No `unittest.TestCase`.
- **Filesystem tests use `tmp_path`** and build a throwaway vault (`.obsidian/` + a
  handful of `.md` files); set mtimes explicitly with `os.utime` rather than depending on
  wall-clock. Note that [03-Resources/tools/20260605-filesystem-timestamps-unreliable](20260605-filesystem-timestamps-unreliable.md) applies — never
  assert on real vault timestamps.
- **DB tests use `sqlite3.connect(":memory:")`** with a fixture that mirrors the real
  schema (`second-brain/tests/conftest.py`).
- **No network, ever.** `second-brain`'s suite covers embedding bookkeeping without
  Ollama running; keep it that way so tests pass on a plane.
- **Never run tests against the live vault or `vault-index.db`.**

Minimum bar for a new tool: every pure function has a test, and every mutating path has a
dry-run test proving it doesn't write. Current suites for reference — `vault-indexer` 52
tests, `process_frontmatter` 16, `second-brain` 10.

---

## requirements.txt

Only if the tool imports outside the stdlib. Pinned with `>=`, one per line
(`PyYAML>=6.0`). Do not add a requirements file that just documents the stdlib.

---

## Frontmatter on tool docs

Every `README.md` and `CHANGELOG.md` carries frontmatter.

```yaml
---
created: "YYYYMMDD"      # first commit touching the file
updated: "YYYYMMDD"      # last commit touching the file
tags:
  - created/YYYYMMDD
  - updated/YYYYMMDD
  - type/readme          # or type/changelog
  - domain/tooling       # always
  - domain/<subject>     # optional second subject, e.g. platform-engineering
  - status/active
status: active
---
```

Rules:

- **`type/` is the document genre, never the subject.** `type/readme` and `type/changelog`
  are separate values on purpose: it makes *"show me every changelog, newest first"* a single
  Dataview query — a cross-tool history of the tooling. A merged `type/tooling` cannot express
  that, because it cannot tell instructions from history. Subject matter goes on `domain/`.
- **Exactly one `type/` and one `status/` per file.** `type/tool` and `type/reference` on tool
  docs are superseded — they were removed on ratification.
- **`status:` scalar and the `status/` tag must agree.** A tool that is unsafe to run gets
  `blocked` in both, not `active` in one and `blocked` in the other.
- **Dates come from git, not the filesystem** — first and last commit touching the file.
  Vault mtimes are unreliable; see [03-Resources/tools/20260605-filesystem-timestamps-unreliable](20260605-filesystem-timestamps-unreliable.md).
  Untracked files fall back to the current date.

⚠️ **GitHub caveat.** GitHub renders YAML frontmatter as a **table at the top of the rendered
page**. If this repo's tool docs are browsed on GitHub rather than in Obsidian, that table is the
accepted cosmetic cost of keeping one frontmatter convention everywhere — not an oversight.

New tools get this for free from [tool-scaffold](../../templates/tool-scaffold/README.md).

---

## Git

- `*.db` and `__pycache__/` are already in the vault `.gitignore`. Do not commit
  `vault-index.db` or `.pytest_cache/`.
- Anything a tool generates that could exceed 10 MB needs a `.gitignore` entry before the
  first commit. GitHub hard-fails at 100 MB, and a large-file pre-commit hook is worth adding
  before you find that out.
- Commits: short, present-tense; don't mix a tool change with the vault notes it produced.

---

## Definition of done

A tool may not be described as finished until all of these are true:

- [ ] Directory is kebab-case; Python module is snake_case and importable
- [ ] Entrypoint has shebang, docstring with `Usage:`, `argparse`, `main()` guard
- [ ] Vault root, pillar names, tag prefixes, `author`, and skip-dirs come from
      `vault_config` — the tool declares none of its own
- [ ] `--dry-run` exists and is verified if the tool mutates the vault
- [ ] `README.md` with the required sections, wikilinks not absolute paths
- [ ] `CHANGELOG.md` with a `[0.1.0]` entry
- [ ] `tests/` with `__init__.py`, passing via `python3 -m pytest tests/`, no network
- [ ] `requirements.txt` if there are third-party imports
- [ ] Generated artifacts gitignored
- [ ] Listed in this folder's index

---

## Retiring a tool

**Ratified 2026-08-08**, generalising the shape the two existing eulogies arrived at
independently: the `archive-folders` post-mortem and
the `vault-map.py` eulogy.

Deleting a tool without a note is how the same broken idea gets rebuilt in six months. Retirement
is a documented act with an artifact, not a `git rm`.

**When to retire.** Any one of these is sufficient:

- **Nobody runs it.** Measure before deciding — `archive-folders` had **one run, ever**, and
  **0 of 3,344** archived files carried its tag. Measurement, not impression.
- **It encodes a taxonomy the vault has moved past** and has no way to notice. This is the
  failure mode the shared config module exists to prevent; a tool that predates it and still
  hardcodes pillar names is a candidate.
- **Its job is now done elsewhere.** Say by whom.
- **Its documented invocation is unsafe** and fixing it means rewriting the tool anyway.

**The ritual.** Write the eulogy *first* — if you can't say what killed it, you don't yet know
whether the successor will inherit the same flaw.

1. **Write `<YYYYMMDD>-eulogy-<tool-name>.md`** beside the tool (or at the tools root if the
   directory is going away), with `status: done` and `type/reference` frontmatter. Required sections:

   | Section | Contents |
   |---|---|
   | `## What it did` | The honest version, including what it never did. |
   | `## Its whole life, in commits` | Or "in one day". Dates and commit ids. |
   | `## The measurement that ended it` | The **numbers**. Run counts, tag counts, coverage. Not "it felt unused". |
   | `## What killed it` | The root cause, stated so a successor can avoid it. |
   | `## Requirements for the successor` | Only if something still needs doing. This is the section that makes a eulogy worth writing. |
   | `## Recovery` | The exact commands to undo what the tool did, if it did anything. |
   | `## Related` | Where its remaining mentions live. |

2. **Remove the tool**, and its row from this folder's index (`README.md`), replacing the row with
   a strikethrough entry that links the eulogy — the index is where someone looks first.
3. **Grep for every remaining mention** and fix each one, or list it in the eulogy's `## Related`
   as knowingly stale. A retired tool still named as live in a runbook is worse than no tool.
4. **Say plainly if the capability is now missing.** `README.md` carries
   *"There is currently no archival tool"* for exactly this reason. Do not let a retirement read
   as a completed cleanup when it is actually an open gap.
5. **Never delete the eulogy.** It ages into the reason a bad idea doesn't come back.

Config files and shell functions count as tools for this purpose if something depended on them —
see the `.ascii-tree-config.json` retirement note for the smallest reasonable version
of this ritual.

---

## Compliance

Per-tool compliance is tracked in a dated audit, not here — this doc is the standard, the
audit is the snapshot:

- a dated compliance audit — current state, findings,
  and the remediation queue.

Re-run the audit as a new dated doc rather than editing the existing one, so the trend stays
visible.
