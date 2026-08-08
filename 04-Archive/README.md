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
---

# 04-Archive — done, or no longer true

Everything that has finished or stopped being relevant: completed projects, retired
responsibilities, superseded reference, and old work-dirs. Preserved rather than deleted, because
the archive is the raw material the distillation pipeline mines.

The purpose test: **is this done or irrelevant?**

## What lives here

- **Completed projects**, moved whole from `02-Projects/`.
- **Finished work-dirs** from `00-Inbox/work/` that turned out to be one-offs.
- **Superseded reference** — runbooks and how-tos that are no longer true.
- **Retired responsibilities** — Areas you no longer hold.
- **Aged-out ops journal** — `Log/` weeks older than ~30 days.

## What does NOT live here

| Kind | Goes to |
|---|---|
| Anything still `active`, `blocked`, `review`, or `paused` | `02-Projects/`, or the Area's backlog |
| Reference that is still true | `03-Resources/` |
| Shipped **vault** changes | `CHANGELOG/` — permanent, never archived |
| A responsibility you still hold | `01-Areas/<Area>/` |

**`blocked` and `paused` are not archived.** Both are live states — one is waiting on someone else,
one you deliberately set down. Archiving them loses the thread. Only `done` and no-longer-relevant
come here.

## This is not a graveyard

The archive earns its keep by being mined. Monthly: pick one folder, read the old notes, extract
what's still true into `03-Resources/`, and link back to the source here.

```
Archived note → "still relevant?" → yes → extract the insight (1–3 sentences)
              → create or update a Resource note → link back to this archive source
```

That pipeline is why nothing here is deleted. See [[03-Resources/README]] and
[[OrionOs]] § Routines.

## Structure convention

Organised **by topic**, not by where things came from — the archive predates the PARA pillars and is
grouped by subject (`incidents/`, `platform/`, `infrastructure/`, `conferences/`, …).

This matters more than it looks: *"where does `02-Projects/foo` go when archived?"* has **no
mechanical answer**, because the destination is a topic judgement. A tool that pretended otherwise
is exactly what killed `archive-folders` — see
[[03-Resources/tools/README]] (§ There is deliberately no archival or retention tool). Archiving is a human decision followed by an
Obsidian move.

## Retention

Permanent. ⚠️ **Archiving is currently manual** — move files **in Obsidian**, never with `mv`, so
wikilinks are rewritten. There is no retention tool; `archive-folders` was retired 2026-08-08 and
the requirements a successor must meet are in the eulogy above.

Before and after any bulk move, run the link check:

```bash
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py
```

## Related

- [[OrionOs]] — the model and the `status:` vocabulary
- [[03-Resources/tools/README]] (§ There is deliberately no archival or retention tool) — why archiving has no tool
- [[00-Inbox/README]] · [[01-Areas/README]] · [[02-Projects/README]] · [[03-Resources/README]] ·
  [[Log/README]] · [[CHANGELOG/README]]
