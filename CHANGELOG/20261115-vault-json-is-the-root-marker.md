---
created: "20261115"
updated: "20261115"
tags:
  - created/20261115
  - updated/20261115
  - type/changelog
  - domain/knowledge-management
  - status/done
status: done
author: Claude (claude-fable-5-1)
---

# 2026-11-15 — `vault.json` is the root marker

The tools find the vault root by walking up to the nearest `vault.json` file. `.obsidian/` no longer counts.

## Why

- `.obsidian/` named one editor, and the tools never read anything inside it. It was a marker and nothing more.
- Every published vault gitignores `.obsidian/`, so a fresh clone had no root until someone opened it in Obsidian. CI never does.
- `vault.json` already had to sit at the root and already described the vault. The marker and the config are now the same file, the way `.git`, `pyproject.toml` and `package.json` work.
- A vault with `.obsidian/` and no `vault.json` was the worst case: found, then described with the stock defaults, which were wrong for it. Now it stops with a clear message. A visible gap beats a confident guess.

## What changed

- **[[03-Resources/tools/README|vault_config]]** `find_vault_root` looks for a `vault.json` file. A directory by that name is not a marker. `load_config` still falls back to DEFAULTS for an explicit `--vault` path that has no file, so pointing a tool at a bare folder keeps working.
- **[[03-Resources/tools/second-brain/README|second-brain]] 0.5.0.** `register.py` keeps its deliberate duplicate of the finder, now on the same marker. `embed_chunks.py` gains `--vault` and `SECOND_BRAIN_VAULT` and stops inferring the root from the DB's location, which was the other place a tool guessed where the vault was.
- **[[templates/tool-scaffold/README|tool-scaffold]]** bootstrap walks up for `vault.json` when run in place.
- **Help and error text** in vault-indexer, process_frontmatter, scan-broken-wikilinks, stamp-out and register say `vault.json`. The error reads "no vault.json above here; pass --vault".
- **Docs:** README step 3, [[CLAUDE]], [[03-Resources/tools/CONTRIBUTING]] § Tests, [[docs/adopting-into-an-existing-vault]] step 1, [[docs/verifying-a-fresh-install]] test 1.

## Tests

- `tests/test_vault_config.py`: `make_vault` writes a `vault.json`. New: `test_vault_json_as_a_directory_is_not_a_vault_marker`, `test_obsidian_dir_alone_is_not_a_vault_marker`, `test_an_empty_object_is_a_valid_marker`, `test_empty_config_file_yields_defaults`. 32 → 35.
- `vault-indexer/tests/test_scan.py` and `scan-broken-wikilinks/tests/test_scan_broken_wikilinks.py`: fixtures mark the throwaway vault with `vault.json`.
- `second-brain/tests/test_embed_chunks.py`: 7 new tests for `resolve_vault_root` and `plan_chunks`.
- All suites: 410 passing, up from 400.

## Migration

If you adopted the tools into an existing vault without copying `vault.json`, copy it now, or write `{}` to `<vault>/vault.json`. Until then every tool reports no vault root and asks for `--vault`.
