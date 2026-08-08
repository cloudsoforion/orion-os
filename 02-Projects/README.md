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

# 02-Projects — committed work with a finish line

One folder per piece of work that is **started, committed to, and can be finished**. If it can't be
finished, it's an Area. If it hasn't been started, it's a backlog item in an Area.

The purpose test: **does this have a finish line?**

## What lives here

- **One folder per project**, with a `README.md` stating why it exists and what "done" means.
- The working notes, investigations, session summaries, runbooks, and artifacts of that project.
- Nested sub-projects where a large effort genuinely decomposes.

## What does NOT live here

| Kind | Goes to |
|---|---|
| An ongoing responsibility with no finish line | `01-Areas/<Area>/` |
| Something not yet started | the relevant Area's `backlog.md`, as `paused` or `someday` |
| An unprocessed capture, or work still being scoped | `00-Inbox/work/` |
| Reference that outlives the project | `03-Resources/` |
| Daily summaries, standups, weekly priorities | `Log/` |
| A finished project | `04-Archive/`, or `CHANGELOG/` if it was a vault change |

## Status, not folder

Every project carries a single `status:` field in frontmatter. It answers *"why isn't this moving,
and what do I do about it?"* — it is **not** what you're focused on today (that's the weekly
priorities doc in `Log/`). Many projects can be `active` at once.

| `status` | Meaning | What to do |
|---|---|---|
| `inbox` | Captured, not yet triaged | Triage it |
| `active` | A live thread you're carrying | Work it |
| `review` | Your part is done; handed off, awaiting feedback | Await; nudge if it stalls |
| `blocked` | Waiting on someone/something **external** | Go nudge |
| `paused` | **You** deliberately set it down | Leave it |
| `done` | Complete | Nothing |

- **`blocked` vs `paused`** — blocked means someone *else* is the holdup; paused means *you* chose to
  defer. Opposite actions: nudge vs. leave alone.
- **`review` vs `blocked`** — `review` means you finished your part and handed it off (PR up, draft
  sent); `blocked` means you can't continue until someone unblocks you. `review` is healthy
  in-flight; `blocked` is a stall.

Full definitions live in [[OrionOs]] — that is the source of truth, not this file.

## Lifecycle

```
Area backlog (paused/someday)
  → commit + start        → 02-Projects/<name>/  (status: active)
  → ship                  → CHANGELOG/  (vault changes)  or  04-Archive/  (everything else)
```

A doc moves **once**, at graduation, and it moves **in Obsidian** — never `mv`. Shell moves are what
broke ~1000 wikilinks in the June 2026 reorg. See [[AGENTS]].

## Structure convention

```
02-Projects/
  <project-name>/
    README.md                     <- why / scope / deliverables / done when
    YYYYMMDD-<slug>.md            <- dated working notes
    <sub-area>/                   <- only where the work genuinely decomposes
```

Project folders are kebab-case; notes inside are date-prefixed where temporal. Start a project
README from [[templates/project-README]]: `## Why` · `## Scope` · `## Deliverables` ·
`## 🎯 Done when` · `## Notes`.

**Write the "done when" before starting.** A project without a stated finish line is an Area
wearing the wrong hat, and it will sit `active` forever.

## Related

- [[OrionOs]] — the model and the full `status:` table
- [[templates/project-README]] — the shape to copy
- [[00-Inbox/README]] · [[01-Areas/README]] · [[03-Resources/README]] · [[04-Archive/README]] ·
  [[Log/README]] · [[CHANGELOG/README]]
