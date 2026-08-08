---
created: "20260807"
updated: "20260807"
tags:
  - type/readme
  - domain/tooling
  - created/20260807
  - updated/20260807
  - domain/knowledge-management
  - status/active
author: Claude (claude-opus-5)
---

# tool-scaffold

Starting point for a new vault tool, so it begins compliant with
[[03-Resources/tools/CONTRIBUTING]] instead of being retrofitted later. Retrofitting is how
`archive-folders` ended up un-testable (and ultimately retired) and `process_frontmatter` went two months without a
CHANGELOG.

## How to use it

```bash
# 1. Copy the scaffold. <tool-name> is kebab-case; the module is snake_case.
cp -r templates/tool-scaffold 03-Resources/tools/<tool-name>
cd 03-Resources/tools/<tool-name>

# 2. Rename the entrypoint and its test to match (snake_case, importable)
mv tool_name.py <tool_name>.py
mv tests/test_tool_name.py tests/test_<tool_name>.py

# 3. Promote the doc templates into place
mv tool-README.md README.md
mv tool-CHANGELOG.md CHANGELOG.md

# 4. Delete requirements.txt if the tool is stdlib-only
# 5. Replace every <placeholder>, then confirm the suite runs
python3 -m pytest tests/
```

⚠️ **Copy with `cp`, not Obsidian's "make a copy."** These are scripts, not notes — the
"move files in Obsidian only" rule in [[OrionOs]] protects wikilinks in markdown and doesn't
apply to code. Do not `mv` the *notes* in this vault by shell.

## Contents

| File | Becomes | Notes |
| --- | --- | --- |
| `tool_name.py` | `<tool_name>.py` | shebang, module docstring with `Usage:`, `argparse`, `--dry-run`, `main()` guard, and the `vault_config` import already wired |
| `tool-README.md` | `README.md` | the 9 required sections, in order, pre-stubbed |
| `tool-CHANGELOG.md` | `CHANGELOG.md` | opens at `[0.1.0]` |
| `tests/__init__.py` | unchanged | empty; present so `tests` is a package |
| `tests/test_tool_name.py` | `tests/test_<tool_name>.py` | the `sys.path.insert` import pattern, a skip-dirs test, plus a dry-run-writes-nothing test |
| `requirements.txt` | delete if stdlib-only | pin floors to **verified installed** versions, never guesses |

## What it already does for you

- **Dry-run is the default**; `--apply` is required to write. This is the shape
  [[03-Resources/tools/CONTRIBUTING]] mandates for anything that mutates the vault.
- **Vault root, tag prefixes, `author`, and skip-dirs come from
  `vault_config.py`** — do not re-declare them. The scaffold
  finds the tools directory whether it is still in `templates/` or already copied into
  `03-Resources/tools/<tool>/`, so `python3 -m pytest tests/` passes before you change a line.
- **It never counts directories to find the vault.** The previous version used
  `Path(__file__).resolve().parents[3]`, which is correct at exactly one depth and wrong
  *silently* everywhere else — from the scaffold's own location it pointed at `~/Documents`.

## Related

- [[03-Resources/tools/CONTRIBUTING]] — the standard this encodes
- [[03-Resources/tools/README]] — the tool index; add your tool to both tables
- [[03-Resources/tools/vault-indexer/README]] — reference implementation
