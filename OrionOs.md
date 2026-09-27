---
created: "20260808"
updated: "20260924"
tags:
  - created/20260808
  - updated/20260924
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
lifecycle. Everything else in the repo points here rather than restating it — [CLAUDE](CLAUDE.md) for the
agent-facing rules, [AGENTS](AGENTS.md) for the conventions that apply when changing files, and each pillar's
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
[Log/README](Log/README.md) and [CHANGELOG/README](CHANGELOG/README.md).

**The folder names live in `vault.json`.** Rename a pillar there and the tooling follows; nothing
hardcodes them. See [03-Resources/tools/CONTRIBUTING](03-Resources/tools/CONTRIBUTING.md) § The shared config module.

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
- **Every Area has a `backlog.md`.** If a piece of work has no Area that owns it, that is the signal
  to *create the Area* — not to file the work somewhere convenient.

**That is the only moment a doc moves.** Everything else is a status change and a link.

### Where deferred and out-of-scope work goes

**The owning Area's backlog. Always.** This is the answer for every kind of "I'm not doing this now,
but it must not be lost":

| What | Goes to | As |
|---|---|---|
| An idea you haven't committed to | Area backlog | `someday` |
| Work you committed to and deliberately set down | Area backlog | `paused` |
| Something found mid-task that was **out of scope** (a `## Follow-ups` item) | Area backlog | `someday` |
| **Unfinished `## Next actions` from work that is wrapping up** | Area backlog | `paused` |

- **Route it when it goes out of scope, not when the project ends.** Archiving is the *deadline*,
  not the trigger — the moment something is deliberately not-now, it gets a backlog row, even if the
  work it came from is still `active`.
- **Links, not moves.** The backlog row points at wherever the doc already lives. The finding stays
  next to the work that produced it; the backlog is the *index* that makes it findable. Nothing
  moves until it graduates to `02-Projects/`.
- **A row with no link and no next step is a wish, not a backlog item.** Every row says what it is
  and *what picking it up would start with*.
- **No Area owns it?** Create the Area. A responsibility with recurring deferred work and no home is
  a missing Area, and burying the work in a finished Project is how it dies.

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

## Inbox

`00-Inbox/` is a queue, not a folder — see [00-Inbox/README](00-Inbox/README.md) for what lands there. Two things
leave it, and they leave by different rules.

### Graduation (work-dirs → Projects)

A work-dir that grows multi-week, spawns follow-on work, or acquires a ticket is a **Project**:
promote it to `02-Projects/` (Obsidian drag) and give it a `README` from
`templates/project-README.md`. Promotion is **never gated** — do it the moment the work is
recognisably a project.

### Retention is gated on your review cycle, not on age

Finished work-dirs are **mined for your performance review first, then archived.** Archiving is the
*last* step, and it does not happen on a timer:

```
work-dir finishes → mined into the brag doc → review cycle runs → THEN archive to 04-Archive/work/<review-period>/
```

- **Never archive ahead of the mining pass.** In a brag-doc entry, the Result — the number, and
  who it affected — is the one beat you cannot reconstruct cold. An archived folder reads as
  finished, so nobody reopens it to look for the number.
- **The buckets in `04-Archive/work/` are review periods**, not calendar quarters. Name them as
  ranges.
- **If the cycle slips, retention slips with it — and that is correct, not neglect.** A full inbox
  after a skipped or delayed review cycle means the ritual that empties the queue has not run yet,
  not that anything is broken.

> Do not replace this with an "older than N days" sweep. Age does not know whether the work has
> been mined yet. An earlier age-based archiving tool was retired for exactly this reason: it
> encoded one moment's assumptions and archived work nobody had harvested.

## Archives

### Sweep before you archive

**Nothing is archived or written to `CHANGELOG/` while it still holds live to-dos that exist nowhere
else.** Ideally these were routed as they arose (see *Where deferred and out-of-scope work goes*) —
this is the **last call**, not the first pass. Archiving is the moment unfinished work is most
likely to be lost: the project reads as finished, so nobody opens it again.

Before moving a work item to `04-Archive/` or recording it in `CHANGELOG/`:

1. **Read its unticked boxes** — `## Next actions`, `## Follow-ups`, any `- [ ]` left open, and
   every warning with no ticket behind it.
2. **For each one, decide out loud:** genuinely dead (say so in the doc), already tracked elsewhere
   (link it), or still wanted → **add a row to the owning Area's backlog** pointing back at the doc.
3. **Then** archive. The archived doc keeps its unticked boxes as a record; the backlog row is what
   keeps them alive.

An unfinished task that only ever existed inside a closed project is indistinguishable from one that
was never written down.

## Routines

The repeatable rhythms and non-negotiables that keep the work and the repo running. Routines are
**ongoing standards you maintain**, so they're implemented as an Area sub-folder rather than a new
top-level pillar — which also avoids renumbering `00`–`04`.

**Implementation**

- One doc per routine under `01-Areas/Routines/` (an Area you create — see [01-Areas/README](01-Areas/README.md)),
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
| Weekly review | Weekly | Process the inbox; graduate any work-dir that has become a project, and route stray to-dos to Area backlogs. Archiving waits for the review cycle (see *Inbox*). |
| Archive mining | Monthly | Pick one archived folder, pull what's still true into `03-Resources/`, link back. Keeps the archive from being a graveyard. |

## Related

- [CLAUDE](CLAUDE.md) — metadata standards and the documentation-quality rules
- [AGENTS](AGENTS.md) — naming, wikilinks, and the conventions for changing files
- [00-Inbox/README](00-Inbox/README.md) · [01-Areas/README](01-Areas/README.md) · [02-Projects/README](02-Projects/README.md) · [03-Resources/README](03-Resources/README.md) ·
  [04-Archive/README](04-Archive/README.md) · [Log/README](Log/README.md) · [CHANGELOG/README](CHANGELOG/README.md)
- [docs/adopting-into-an-existing-vault](docs/adopting-into-an-existing-vault.md) — if you already have a vault
