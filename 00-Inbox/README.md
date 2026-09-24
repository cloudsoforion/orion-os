---
created: "20260808"
updated: "20260924"
tags:
  - created/20260808
  - updated/20260924
  - type/readme
  - domain/knowledge-management
  - status/active
status: active
author: Claude (claude-opus-5)
---

# 00-Inbox — capture, and nothing else

The landing zone. Anything arriving without a decided home lands here, and **nothing stays**. The
inbox is a queue, not a folder — if something has lived here for more than about two weeks, it is
either a Project or it is done.

The purpose test: **does this need a home?** If you can already answer where it belongs, put it
there instead.

## What lives here

- **Fresh captures** — links, quotes, screenshots, half-thoughts, things pasted mid-meeting.
- **Work-dirs** (`00-Inbox/work/YYYYMMDD-<slug>/`) — a dated folder per piece of work in flight,
  scaffolded by `setup_work_dir`. This is where troubleshooting starts before anyone knows whether
  it's a one-off or a project.
- **`random-thoughts/`** — unsorted, unjudged.

## What does NOT live here

| Kind | Goes to |
|---|---|
| An ongoing responsibility with no finish line | `01-Areas/<Area>/` |
| Committed work with a finish line | `02-Projects/` |
| Reference you'll search for later | `03-Resources/` |
| Daily summaries, standups, weekly priorities | `Log/` |
| Done or irrelevant | `04-Archive/` |
| Shipped vault changes | `CHANGELOG/` |

**A to-do is not an inbox item.** "When will I get to it?" is a `status:`, not a folder — a
not-yet-started improvement is a `paused` backlog item in the relevant Area, not a note rotting in
the inbox. See [[OrionOs]].

## Routing rules

1. **Captures** are processed at the weekly review. Each one becomes a Project, files to Resources,
   archives, or is deleted. Nothing "lives" here as a to-do.
2. **Work-dirs graduate, or wait to be mined** — they leave by two different rules
   ([[OrionOs]] § Inbox):
   - Grows multi-week, spawns follow-on work, or acquires a ticket → **promote to `02-Projects/`**.
     Promotion is never gated.
   - Finished → mined into the brag doc, then **archived to `04-Archive/work/<review-period>/`
     after the review cycle runs**. Retention is gated on the review cycle, not on age.
   - Before archiving, sweep its open to-dos into the owning Area's backlog.
3. **The ops journal is not capture.** Daily summaries, standups, and priorities docs are a
   recurring stream with its own home in `Log/` — see [[Log/README]].

## Processing rituals

- **The 2-minute rule.** On landing, decide immediately: do it now if it takes under two minutes,
  or route it — Resources (reference) / Archive (done) / Projects (has a finish line). Never let it
  just sit. Processing friction is what bloats an inbox, not a missing bucket.
- **Progressive summarization on the way to Resources.** Add two lines and stop:
  `> Why I saved this:` and `> Key takeaway:`. Don't over-process; perfectionism is itself a cause
  of the backlog.
- **Boundaries by purpose, not content** — the test that resolves almost every "where does this
  go?": Inbox = *needs a home?* · Areas = *regularly return?* · Projects = *a finish line?* ·
  Resources = *search for it later?* · Archive = *done/irrelevant?*

## Structure convention

```
00-Inbox/
  work/
    YYYYMMDD-<slug>/          <- one folder per piece of work in flight
      YYYYMMDD-<slug>.md      <- the note; same name as its folder
  random-thoughts/
  <loose captures>.md
```

Filenames are kebab-case and date-prefixed where temporal. See [[AGENTS]] § Markdown & Naming
Conventions.

## Retention

Nothing here is permanent, but nothing leaves on a timer either: finished work-dirs are archived
after the review cycle that mines them. See [[OrionOs]] § Inbox.

⚠️ **There is currently no retention tool.** `archive-folders` was retired 2026-08-08 and has no
successor, so promoting and archiving is a manual move — in Obsidian, never `mv`. The requirements a
replacement must meet are in [[03-Resources/tools/README]] (§ There is deliberately no archival or retention tool).

## Related

- [[OrionOs]] — the operating model and the `status:` vocabulary
- [[OrionOs]] — where
  these rules were decided, and why the fix was rituals rather than a new folder
- [[Log/README]] — the ops journal, which used to live here
- [[01-Areas/README]] · [[02-Projects/README]] · [[03-Resources/README]] · [[04-Archive/README]]
