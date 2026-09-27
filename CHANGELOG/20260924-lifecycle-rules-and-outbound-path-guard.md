---
created: "20260924"
updated: "20260924"
tags:
  - created/20260924
  - updated/20260924
  - type/changelog
  - domain/knowledge-management
  - status/done
status: done
author: Claude (claude-opus-5-5)
---

# 2026-09-24 — lifecycle rules, tool placement, outbound-path-guard

Carries back three improvements that settled in the parent vault after the 2026-08-08 extraction.

## What changed

- **[[OrionOs]]: deferred work and retention.**
  - Every Area has a `backlog.md`.
  - A new section, *Where deferred and out-of-scope work goes*: always the owning Area's backlog, as a link and not a move.
  - A new `## Inbox` section: promotion is never gated, and retention is **gated on the review cycle, not on age**.
  - *Sweep before you archive* under Archives.
  - The weekly-review routine no longer archives by age. [[00-Inbox/README]] was updated to match.
- **[[03-Resources/tools/CONTRIBUTING]]: where a tool belongs.** New sections:
  - *What belongs here*: you run it, and it reads, writes or reports into the vault.
  - *What doesn't*: audience decides, not subject matter.
  - A promotion ladder toward a team repo.
- **New tool: [[03-Resources/tools/outbound-path-guard/README|outbound-path-guard]] 0.1.1.** A `PreToolUse` hook that denies outbound tool calls carrying references only this machine can resolve. Registration is in [[docs/claude-code-setup]].

## Why

- **Age-based retention archives work before anyone has mined it.** An archived folder reads as finished, so nobody reopens it to pull out the result for a review.
- **To-dos left inside a closed project are as good as lost.**
- **Banning wikilinks in external writing only moved the leak into backticks.** The guard checks whether a reference can be opened, not its syntax.
