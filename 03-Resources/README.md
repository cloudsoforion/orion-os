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

# 03-Resources — reference, and the tooling

Durable material that supports Areas and Projects but belongs to neither: how-tos, architecture
notes, runbooks, distilled knowledge, and the vault's own tools.

The purpose test: **will I search for this later?**

## What lives here

- **Reference notes** — how a system works, how to do a thing, why a decision was made.
- **Runbooks** — minimal walkthroughs. The "why" goes in a sibling `runbook-design-notes.md`, not
  in the runbook itself.
- **Architecture and topology maps.**
- **Distilled knowledge** mined out of `04-Archive/` — see the distillation pipeline below.
- **[[03-Resources/tools/README|tools/]]** — every vault tool, one directory each, plus the shared
  `vault_config.py`. Governed by [[03-Resources/tools/CONTRIBUTING]].
- **Operating-mode docs** — how you want to be worked with in a given mode (project management,
  system maintenance, incident response). Worth writing down once you notice yourself re-explaining it.

## What does NOT live here

| Kind | Goes to |
|---|---|
| Work with a finish line | `02-Projects/` |
| An ongoing responsibility | `01-Areas/<Area>/` |
| Reference specific to one responsibility | that Area's folder |
| An unprocessed capture | `00-Inbox/` |
| Daily summaries, standups, weekly priorities | `Log/` |
| Superseded or no-longer-true reference | `04-Archive/` |

**Resources is not an attic.** If a note is no longer true, archive it — a stale runbook is worse
than a missing one, because someone will follow it.

## The distillation pipeline

This is what makes Resources the knowledge layer rather than a dumping ground. There is no separate
"knowledge" pillar by deliberate decision (2026-07-10) — knowledge is Resources plus Archive plus
this habit:

```
Archived note → "still relevant?" → yes → extract the insight (1–3 sentences)
              → create or update a Resource note → link back to the Archive source
```

Run it as a **monthly archive-mining session**: pick one folder, read the old notes, pull what's
still true into Resources, link back. It is what keeps the Archive from being a graveyard. Currently
a monthly routine — see [[OrionOs]] § Routines.

When promoting an Inbox capture into Resources, use **progressive summarization**: add
`> Why I saved this:` and `> Key takeaway:`, then stop. Don't over-process.

## Structure convention

```
03-Resources/
  tools/                     <- vault tooling; see its own CONTRIBUTING
    vault_config.py          <- the one shared module
    <tool-name>/
  <topic>/                   <- reference grouped by subject
  <topic-note>.md
```

Topic folders and filenames are kebab-case; date-prefix only where the note is genuinely temporal.
Reference notes are usually *not* temporal — a how-to shouldn't carry a date in its name.

## Adding a tool

Tools have their own standard, which is stricter than the rest of the vault:
[[03-Resources/tools/CONTRIBUTING]]. Start from [[templates/tool-scaffold/README|tool-scaffold]] so
it begins compliant, and read the § shared config module rule first — no tool declares its own
folder names, tag prefixes, `author`, or skip-dirs.

## Related

- [[03-Resources/tools/README]] — the tool index
- [[03-Resources/tools/CONTRIBUTING]] — the tooling standard
- [[OrionOs]] — the operating model
- [[00-Inbox/README]] · [[01-Areas/README]] · [[02-Projects/README]] · [[04-Archive/README]] ·
  [[Log/README]] · [[CHANGELOG/README]]
