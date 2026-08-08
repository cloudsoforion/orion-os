---
created: "20260808"
updated: "20260808"
tags:
  - created/20260808
  - updated/20260808
  - type/standard
  - domain/knowledge-management
  - status/active
status: active
---

# OrionOs — the operating model

An operating model for a working knowledge repository: **PARA + GTD + Routines**.

- **PARA** — Projects, Areas, Resources, Archive
- **GTD** — capture everything, decide immediately, review on a cadence
- **Routines** — the non-negotiables that keep it running

This file is the **source of truth** for the folder model, the `status:` vocabulary, and the
lifecycle. Everything else in the repo points here rather than restating it — [[CLAUDE]] for the
agent-facing rules, [[AGENTS]] for the conventions that apply when changing files, and each pillar's
own `README.md` for what belongs in it.

Horizons are deliberately omitted. They're personal and very high-level; this model is for work.

## The pillars

```
00-Inbox      capture — nothing stays
01-Areas      ongoing responsibilities — no finish line
02-Projects   committed work — has a finish line
03-Resources  reference and tooling — you'll search for it later
04-Archive    done or no longer true
Log/          the ops journal — the recurring work-logging stream
CHANGELOG/    the record of shipped changes to the repo itself
templates/    note and document templates
```

The numbering is not decoration: it sorts the pillars into the order work moves through them. Two
operational folders sit outside PARA because they are streams rather than states — see
[[Log/README]] and [[CHANGELOG/README]].

**The folder names live in `vault.json`.** Rename a pillar there and the tooling follows; nothing
hardcodes them. See [[03-Resources/tools/CONTRIBUTING]] § The shared config module.

### Boundaries by purpose, not content

The test that resolves almost every "where does this go?", and the reason the model holds up:

| Ask | If yes |
|---|---|
| Does this **need a home**? | `00-Inbox` |
| Will I **regularly return** to it? | `01-Areas` |
| Does it have **a finish line**? | `02-Projects` |
| Will I **search for it later**? | `03-Resources` |
| Is it **done or irrelevant**? | `04-Archive` |

Sort by *purpose*, never by topic. Topic-sorting is what produces a folder that means nothing and
holds everything.

## Statuses

Set in frontmatter as a single field: `status: active`. Each value answers *"why isn't this moving,
and what do I do about it?"*

Status is the **lifecycle state** — not what you're focused on today. That's the weekly priorities
doc in `Log/`. Many things can be `active` at once.

| status | meaning | what to do |
|---|---|---|
| `inbox` | captured, not yet triaged or committed | triage it |
| `active` | a live thread you're carrying (several at once is normal) | work it |
| `review` | your part is done; handed off, awaiting feedback or approval | await; nudge if it stalls |
| `blocked` | waiting on someone or something **external** | go nudge |
| `paused` | **you** deliberately set it down until a later date or trigger | leave it |
| `done` | complete | nothing |

- **`blocked` vs `paused`** — blocked means someone *else* is the holdup; paused means *you* chose to
  defer. They call for opposite actions: nudge, versus leave alone.
- **`review` vs `blocked`** — both wait on others, but `review` means you've finished your part and
  handed it off (PR up, draft sent); `blocked` means you can't start or continue until someone
  unblocks you. `review` is a healthy "in flight"; `blocked` is a stall.
- **"Area" is not a status** — it's a *type*: an ongoing responsibility that never completes. It
  lives in the folder structure, not the status field.

## Areas hold a Someday/Maybe backlog

An Area is an **ongoing responsibility with a standard to maintain** — no finish line — and *not* a
place for active project work. But an Area **does** hold a **backlog** for that responsibility:
candidate improvements you aren't working yet.

- **"When will I get to it?" is a status, not a folder.** A not-yet-started improvement sits in the
  backlog as `paused` (committed but set down) or `someday` (an idea). It does *not* become a
  Project until it's actually `active`.
- **Graduation:** backlog item → you commit and start → it moves into `02-Projects/` as `active` →
  it ships → recorded in `CHANGELOG/` or archived.

**That is the only moment a doc moves.** Everything else is a status change and a link.

```
00-Inbox  ──capture──▶  triage
                          ├─▶ 01-Areas/<Area>/backlog   (someday / paused)
                          │            └──commit──▶ 02-Projects/  (active)
                          ├─▶ 02-Projects/             (active, if committed now)
                          ├─▶ 03-Resources/            (reference)
                          └─▶ 04-Archive/              (done)

02-Projects  ──ships──▶  CHANGELOG/   (changes to the repo itself)
                     └▶  04-Archive/  (everything else)
```

> ### Standing rule — move files in Obsidian only
> Never `mv` or shell-move a note. Drag it in Obsidian, with "Automatically update internal links"
> on. A shell move leaves every inbound wikilink pointing at nothing, and a broken wikilink renders
> as unclickable text — invisible in reading view. This rule exists because a shell-based reorg
> broke roughly a thousand links in a single afternoon, and finding them took far longer than the
> reorg did.
>
> Code is the exception: scripts under `03-Resources/tools/` are not notes, and `cp`/`mv` are fine
> there. Before and after any bulk move of *notes*, run:
> ```bash
> python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py
> ```

## Routines

The repeatable rhythms and non-negotiables that keep the work and the repo running. Routines are
**ongoing standards you maintain**, so they're implemented as an Area sub-folder rather than a new
top-level pillar — which also avoids renumbering `00`–`04`.

**Implementation**

- One doc per routine under `01-Areas/Routines/` (an Area you create — see [[01-Areas/README]]),
  with a `README.md` index.
- Tag each step **non-negotiable** (established) or **building** (new, not yet automatic).
  Aspirational-only steps get their own section — honest beats aspirational.
- **Define the degradation floor.** A cadence with no defined floor doesn't degrade under pressure,
  it collapses entirely. Write down what the minimum version of each routine is when a deadline is
  eating the day, and what the exit criteria are.

**A starting set**

| Routine | Cadence | Purpose |
|---|---|---|
| Daily summary | End of day | The record of what you did. `vault-indexer summary` generates it. |
| Weekly priorities | Monday | What this week is for. Lives in `Log/<week-Monday>/`. |
| Weekly review | Weekly | Process the inbox; graduate or archive every work-dir older than two weeks. This is `00-Inbox`'s retention mechanism. |
| Archive mining | Monthly | Pick one archived folder, pull what's still true into `03-Resources/`, link back. Keeps the archive from being a graveyard. |

## Related

- [[CLAUDE]] — metadata standards and the documentation-quality rules
- [[AGENTS]] — naming, wikilinks, and the conventions for changing files
- [[00-Inbox/README]] · [[01-Areas/README]] · [[02-Projects/README]] · [[03-Resources/README]] ·
  [[04-Archive/README]] · [[Log/README]] · [[CHANGELOG/README]]
- [[docs/adopting-into-an-existing-vault]] — if you already have a vault
