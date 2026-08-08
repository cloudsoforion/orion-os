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

# 01-Areas — ongoing responsibilities

One folder per **standing responsibility with a standard to maintain, and no finish line**. An Area
is never "done": the access pings never stop, the alerts keep firing, the vault keeps needing
tending. That's what separates an Area from a Project.

The purpose test: **is this something I regularly return to?**

**"Area" is not a status — it's a type.** It lives in the folder structure, not the `status:` field.
See [[OrionOs]].

## What lives here

- **One folder per Area**, each with a `README.md` that is its operating manual.
- **A backlog** per Area — the Someday/Maybe list for that responsibility. Candidate improvements
  not being worked yet.
- **Standing reference for that responsibility** — known-issues ledgers, conventions, the cadences
  that keep it healthy.

## What does NOT live here

| Kind | Goes to |
|---|---|
| Active, committed work with a finish line | `02-Projects/` |
| An unprocessed capture | `00-Inbox/` |
| General reference not tied to one responsibility | `03-Resources/` |
| Daily summaries, standups, weekly priorities | `Log/` |
| A responsibility you no longer hold | `04-Archive/` |

**An Area is not a place for active project work.** It holds the *backlog* for that responsibility,
not the execution.

## Areas hold a Someday/Maybe backlog

- **"When will I get to it?" is a status, not a folder.** A not-yet-started improvement sits in the
  Area's backlog as `paused` (deliberately deferred) or `someday` (an idea, uncommitted). It does
  **not** become a Project until it is actually `active`.
- **Graduation is the only move.** backlog item → committed and started → moves into `02-Projects/`
  as `active` → ships → recorded in `CHANGELOG/` or archived. *That* is the one moment a doc moves,
  and it moves **in Obsidian**, never by `mv`.

## Deciding where a recurring issue goes

One recurring problem produces up to four artifacts, in different places. Without this split,
recurring issues become forever-`active` Projects that never close:

| The thing | Where it goes |
|---|---|
| Today's flare-up — what happened, what you ran | `Log/` (the ops journal) |
| The remediation you committed to | `02-Projects/`, then `CHANGELOG/` when it ships |
| The reusable how-to that came out of it | `03-Resources/` (or the Area, if it's specific to that responsibility) |
| "Keep this healthy" + the known-issues ledger | the Area |

## Structure convention

```
01-Areas/
  <Area-Name>/
    README.md        <- the Area's manual: what lives here, what does NOT, current threads
    backlog.md       <- Someday/Maybe for this responsibility
    <standing reference notes>
```

Each Area README follows one shape: a one-paragraph statement that this is an ongoing
responsibility with no finish line, `## What lives here`, a `## What does NOT live here` table, then
current threads and conventions. Copy [[templates/area-README]] to start one.

## Creating an Area

There are no Areas yet — they're yours to define. An Area is worth creating when you notice you keep
returning to the same kind of work with no end in sight.

```bash
mkdir 01-Areas/<Area-Name>
cp templates/area-README.md 01-Areas/<Area-Name>/README.md
```

Then fill in the placeholders and start a `backlog.md` beside it. Candidates that tend to earn an
Area: the knowledge system itself, access and identity, monitoring and alerting, the recurring
cadences you maintain, on-call.

**One Area should own the vault system itself.** It's the Area that holds this operating manual's
conventions, the vault's own backlog, and the rituals in [[OrionOs]] § Routines — otherwise
improvements to the system compete with delivery work for attention and always lose.

## Related

- [[OrionOs]] — the model, the `status:` vocabulary, and the graduation rule
- [[00-Inbox/README]] · [[02-Projects/README]] · [[03-Resources/README]] · [[04-Archive/README]] ·
  [[Log/README]] · [[CHANGELOG/README]]
- [[templates/area-README]] — the shape to copy for a new Area
