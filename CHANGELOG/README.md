---
created: "20260808"
updated: "20260808"
tags:
  - created/20260808
  - updated/20260808
  - type/readme
  - domain/knowledge-management
  - status/active
status: active
author: Claude (claude-opus-5)
---

# CHANGELOG — the record of shipped vault changes

Where work **on the vault itself** goes once it has shipped. This is the done-log for the system, not
for delivery work: a reorg that landed, a convention that got ratified, a migration that completed.

The purpose test: **is this a vault change that is finished?**

## What lives here

- **Shipped vault changes** — one dated folder or file per change, with the plan, the session notes,
  and the evidence it worked.
- **Migration plans and their outcomes** — including the ones that were abandoned, and why.
- **Ratification records** — when a convention was adopted, and what it replaced.

## What does NOT live here

| Kind | Goes to |
|---|---|
| A vault change still in flight | `02-Projects/`, or the Area's backlog if not started |
| Delivery work that shipped | `04-Archive/` |
| A tool's own version history | that tool's `CHANGELOG.md` under `03-Resources/tools/<tool>/` |
| Reference that is still true and still consulted | `03-Resources/` |
| Daily summaries, standups, weekly priorities | `Log/` |

**Two different changelogs, on purpose.** This folder records *vault* changes. Each tool keeps its
own `CHANGELOG.md` in its own directory, in Keep-a-Changelog form, per
[[03-Resources/tools/CONTRIBUTING]]. Don't merge them: `type/changelog` on the per-tool files makes
*"show me every tool changelog, newest first"* a single Dataview query.

## Structure convention

```
CHANGELOG/
  <YYYYMM>-<slug>/                <- a change spanning a while
    <slug>-plan.md
    <YYYYMMDD>-session-summary.md
  <YYYYMMDD>-<slug>/              <- a change that landed on a day
  <YYYYMMDD>-<slug>.md            <- a change small enough to be one file
```

Date-prefixed, kebab-case. A folder once the change has more than one artifact; a bare file until
then.

## Retention

Permanent. This is the folder that explains why the vault looks the way it does, and every entry
gets more valuable as the reasoning fades from memory. **Nothing here is archived or deleted** —
including plans for changes that were abandoned, which are the entries that stop a bad idea coming
back.

The same principle governs tool retirement: a retired tool gets a eulogy rather than a silent
deletion. See [[03-Resources/tools/CONTRIBUTING]] § Retiring a tool.

## Related

- [[OrionOs]] — the model; shipping is what moves a doc here
- [[03-Resources/tools/CONTRIBUTING]] — per-tool changelog format, and the retirement ritual
- [[00-Inbox/README]] · [[01-Areas/README]] · [[02-Projects/README]] · [[03-Resources/README]] ·
  [[04-Archive/README]] · [[Log/README]]
