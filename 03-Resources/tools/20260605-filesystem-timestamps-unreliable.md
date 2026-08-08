---
tags:
  - created/20260605
  - type/investigation
---

# Filesystem Timestamps Are Unreliable in This Vault

## Finding

The oldest file timestamp anywhere in the vault is **2024-12-23 17:17**:

```
Oldest mtime:     2024-12-23 17:17  06-Archive/INDEX.md
Oldest birthtime: 2024-12-23 17:17  06-Archive/INDEX.md
```

Not a single file has a timestamp predating December 23, 2024 — even files with frontmatter tags like `created/20220411` written years earlier.

## What Caused This

| Date | Event |
|---|---|
| 2024-12-23 | A git operation on the old laptop (commit: "notes before archiving") reset all vault file timestamps to that date |
| 2025-11-04 | New laptop received |
| 2025-11-05 | Old laptop wiped; vault migrated to new machine |

The migration to the new laptop **did** preserve timestamps — that's why the floor is Dec 23, 2024 and not Nov 4, 2025. The damage happened 10 months earlier on the old machine. Since the old laptop is gone, the original pre-Dec-2024 timestamps are unrecoverable.

The git commit history is intact back to 2022-03-24 — content is fully preserved, just not filesystem metadata.

## Impact on `process_frontmatter.py`

`get_file_creation_date()` currently falls back to filesystem timestamps when no date can be extracted from the filename:

```python
def get_file_creation_date(file_path):
    stat = os.stat(file_path)
    timestamp = min(stat.st_ctime, stat.st_mtime)  # both reflect restore date
    return datetime.fromtimestamp(timestamp).strftime('%Y%m%d')
```

This means any file with no date in its filename would be stamped `created/20241223` (or later), silently assigning it a wrong date. On a vault with thousands of pre-2024 notes, this would corrupt metadata at scale.

## Decision

Remove the filesystem timestamp fallback entirely. `process_file()` should treat "no date found in path" as an unresolvable case and skip the file rather than stamping it with a wrong date.

The reliable date sources, in priority order:

| Priority | Source | Survives restore? |
|---|---|---|
| 1 | `YYYYMMDD` anywhere in the file path | ✅ |
| 2 | `created/YYYYMMDD` frontmatter tag | ✅ |
| 3 | `st_birthtime` / `st_mtime` | ❌ reset by git operation 2024-12-23 |

Files that have neither a path date nor a frontmatter tag should be reported as skipped so they can be handled intentionally (e.g. manually adding a `created:` field, or accepting that the date is unknown).

## Future idea: backfill script

Files already stamped with a wrong `created/20241223` date (from the old filesystem fallback) could be corrected retroactively by a script that:
1. Finds files with a `created/` tag matching a known-bad date (e.g. `20241223`)
2. Checks whether any parent folder in the path contains a `YYYYMMDD` date
3. If found, replaces the tag with the folder date

This would recover accurate dates for incident files, platform notes, and other thematic archive content where the folder name carries the real date even though the file itself doesn't.

## Related

- `03-Resources/tools/process_frontmatter/tests/test_process_frontmatter.py` — failing test `test_undated_file_returns_none_not_mtime` documents this
- [[03-Resources/tools/vault-indexer/CHANGELOG]] — vault-indexer v0.5.0 added frontmatter `created/` tag fallback for the same reason
