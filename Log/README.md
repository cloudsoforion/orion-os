---
tags:
  - created/20260713
  - updated/20260808
  - type/area
  - domain/knowledge-management
  - status/active
created: 2026-07-13
updated: 2026-08-08
author: Claude (claude-opus-4-8)
---

# Log — the ops journal

Home for the **recurring work-logging stream**, kept separate from delivery work (Projects) and from
maintenance of the vault system itself (Areas).

The ops journal is not capture and it is not a project — it's a stream. Left in `00-Inbox` it buries
the actual captures; filed under `02-Projects` it never closes. So it gets its own home, outside the
PARA pillars, with its own retention.

## What lives here
- **Weekly priorities** (`priorities-week-of-YYYYMMDD.md`)
- **Daily summaries** (vault-indexer output)
- **Standups**
- **Reports** (progress check-ins, range summaries, review-cycle updates)
- **Meeting notes**

## What does NOT live here
| Kind | Goes to |
|---|---|
| Captures / quick notes | `00-Inbox` until processed |
| Active work-dirs | `02-Projects` |
| Reference / how-tos | `03-Resources` |
| KM-system work | `01-Areas/Knowledge-Management` |
| Shipped vault changes | `CHANGELOG/` |

## Structure convention
```
Log/
  YYYYMMDD/                         <- week folder = the week's MONDAY
    priorities-week-of-YYYYMMDD.md
    YYYYMMDD-daily-summary.md       <- daily files sit FLAT in the week folder
    YYYYMMDD-standup.md
```
- **Flat within the week folder** — the date is in the filename prefix, so no per-day subfolders. One file each per day (summary + standup) doesn't warrant its own folder.
- Meeting notes live under `Log/meetings/`.

## Retention
Ops journal is not permanent. Older-than-~30-day weeks are candidates for `04-Archive/`. ⚠️ This previously said "or an `archive-folders` sweep" — that tool was **retired 2026-08-08** and has no successor yet, so this is a manual move for now. See [[03-Resources/tools/README]] (§ There is deliberately no archival or retention tool) for the retention requirements a replacement must meet.

## Tooling
Nothing hardcodes this folder's name:
- **vault-indexer** writes `Log/<week-Monday>/<YYYYMMDD>-daily-summary.md` and range summaries at the `Log/` root. The folder name is no longer hardcoded — it comes from `log_dir` in `vault.json`, so renaming this pillar is one edit. `--output-dir` overrides it per run.
- Any standup or report generator should read and write the same layout.

Rename this folder in `vault.json` and the tooling follows.

## Related

- [[OrionOs]] — the operating model, including the Routines that write into this folder
- [[00-Inbox/README]] · [[01-Areas/README]] · [[02-Projects/README]] · [[03-Resources/README]] ·
  [[04-Archive/README]] · [[CHANGELOG/README]]
