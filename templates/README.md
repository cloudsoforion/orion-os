---
created: "20250528"
updated: "20260808"
tags:
  - created/20250528
  - updated/20260808
  - type/readme
  - domain/knowledge-management
  - status/active
status: active
---

# templates

Note and document templates. Obsidian's Templates plugin points here (`.obsidian/templates.json`),
and the daily note is wired up in `.obsidian/daily-notes.json`.

## The templates

| Template | For | Notes |
|---|---|---|
| `wtf-am-i-doing-YYYYMMDD.md` | The daily note | Meetings, plan, inbox review, TODO/DONE/WONT-DO, work context. Rebuilt 2026-08-08 — every folder reference in the previous version had been dead since the June 2026 reorg. |
| `tasks-week-WW-YYYYMMDD.md` | The weekly note | Carryover / new / done, plus the weekly-review checklist that is `00-Inbox`'s retention mechanism. |
| `new-note.md` | A blank note | Frontmatter + `# overview` / `# details`. |
| `metadata-template.md` | Frontmatter only | When you just need the tag block. |
| [[templates/pillar-README]] | A pillar folder's `README.md` | Purpose test · what lives here · what does NOT (table) · structure · retention. |
| [[templates/area-README]] | An Area's `README.md` | The no-finish-line statement, the backlog pointer, the graduation rule. |
| [[templates/project-README]] | A project's `README.md` | Why · Scope · Deliverables · 🎯 Done when · Notes. Write the "done when" before starting. |
| [[templates/tool-scaffold/README]] | A new vault tool | Copy with `cp`, not Obsidian. Ships compliant with [[03-Resources/tools/CONTRIBUTING]]. |
| `template-resources.md` | — | Link to Obsidian's template-variable docs. |

`template-archive/` holds superseded versions, stamped with the date they were retired.

## Copying: `cp` vs Obsidian

- **Notes and note templates** — copy inside Obsidian so wikilinks are rewritten.
- **`tool-scaffold/`** — copy with `cp -r`. Those are scripts, not notes; the
  "move files in Obsidian only" rule in [[OrionOs]] protects wikilinks in markdown and doesn't
  apply to code.

## Deprecating a template

Templater can't copy a file within the templates folder, so a superseded template is archived
*outside* it:

1. Copy the current template into `template-archive/`, stamped with today's date:
   ```bash
   cp templates/wtf-am-i-doing-YYYYMMDD.md \
      templates/template-archive/wtf-am-i-doing-YYYYMMDD-archived-$(date +%Y%m%d).md
   ```
2. Add or update `archived: "YYYYMMDD"` in the copy's frontmatter.
3. Bump the `template:` value in the live template to today's date.

Applied 2026-08-08 to the daily and weekly templates.

## Related

- [[OrionOs]] — the operating model the templates encode
- [[AGENTS]] — filename and wikilink conventions
- [[03-Resources/tools/CONTRIBUTING]] — the standard `tool-scaffold` encodes
