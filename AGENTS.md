# Repository Guidelines

This is an Obsidian knowledge-management vault, not a traditional codebase. For the repository
structure, the operating model, tool locations and commands, metadata standards, and the
documentation-quality rules, read **[CLAUDE](CLAUDE.md)** and its source of truth **[OrionOs](OrionOs.md)** — this file
only adds the conventions specific to *changing files* in the vault.

## Structure & Tooling

See [CLAUDE](CLAUDE.md) (Operating Model & Structure, Key Tools and Scripts). The vault uses PARA pillars
(`00-Inbox`/`01-Areas`/`02-Projects`/`03-Resources`/`04-Archive`) plus `Log/`, `CHANGELOG/`, and
`templates/`. Folder names come from `vault.json`, not from any script. Run maintenance scripts from
the repository root so relative paths resolve.

## Moving & Renaming Files

**Never `mv`/shell-move vault notes** — drag them in Obsidian, with "Automatically update internal
links" on. A shell move leaves every inbound wikilink pointing at nothing. This is the standing rule
in [OrionOs](OrionOs.md); it applies to every agent.

Code is the exception. Scripts under `03-Resources/tools/` are not notes; `cp` and `mv` are fine
there.

## Markdown & Naming Conventions

- Frontmatter, tags, and `status:` values: follow [CLAUDE](CLAUDE.md) (Metadata Standards) — don't restate them.
- Kebab-case filenames, date-prefixed where temporal (`20250312-updating-repository-mr.md`).
- `-` for bullets, fenced code blocks for commands, `[[wikilinks]]` for cross-references.

### Wikilinks — always vault-absolute

Write the **full path from the vault root**, no leading slash, no `.md` extension:

```markdown
✅ [[03-Resources/tools/vault-indexer/README]]
✅ [[03-Resources/tools/vault-indexer/README|vault-indexer]]   ← alias for readable prose
✅ [[AGENTS]]                                                  ← root-level file, path IS the name
❌ [[README]]              ← ambiguous: dozens of README.md files in a mature vault
❌ [[vault-indexer]]       ← unresolved: that's a *directory*, there is no vault-indexer.md
❌ [[03-Resources/tools/vault-indexer/README.md]]  ← drop the extension
```

Why, concretely:

- The vault is configured `"newLinkFormat": "absolute"` (`.obsidian/app.json`), so every link
  Obsidian generates is already vault-absolute. Hand-written bare links are the outlier.
- **Bare basenames are ambiguous and resolve unpredictably.** `[[README]]` has dozens of candidates;
  Obsidian silently picks one. You won't be told which.
- **Bare links break silently when a file moves**, and a broken wikilink is invisible in reading
  view — it just renders as unclickable text. That invisibility is what makes a bulk move expensive
  to recover from: the damage is real and nothing reports it.

Use the alias form (`[[full/path/to/note|short label]]`) to keep prose readable — the path is for the
machine, the label is for the human.

**This rule has an automated check.** Run it before and after any bulk move:

```bash
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py
```

### Exception — docs that render on GitHub

GitHub does not render wikilinks; they show as literal `[[…]]` text. The repo's front door — the
root `README.md` and the docs it links to (`OrionOs.md`, `CLAUDE.md`, `AGENTS.md`, `docs/`, the
tools index, `CONTRIBUTING.md`, and each tool's `README.md`) — therefore uses **relative markdown
links**, which work in both GitHub and Obsidian:

```markdown
✅ [vault-indexer](03-Resources/tools/vault-indexer/README.md)   ← relative to *this* file, with .md
✅ [AGENTS](../../AGENTS.md) § Markdown & Naming Conventions     ← section named outside the link
```

Everything else — notes, pillar READMEs, templates, changelogs — keeps vault-absolute wikilinks.
`scan_broken_wikilinks.py` checks these too (2.1.0+), resolving each link relative to its own
file the way GitHub does. Run it after moving a front-door doc.

It reports links whose target is missing, and separates bare basenames into the ones with several
candidates (Obsidian picks one, silently), the ones with none (an invisible break), and the ones with
exactly one (`--promote-basenames` rewrites those to full paths). See
[03-Resources/tools/scan-broken-wikilinks/README](03-Resources/tools/scan-broken-wikilinks/README.md).

**Before writing any wikilink, confirm the target exists.** A path that looks right but points at a
directory, a `.py` file, or a note outside the vault will never resolve. Reference those as plain
text or inline code instead.

## Python Utilities

Vault scripts under `03-Resources/tools/` follow PEP 8 — short, typed functions; comment only
non-obvious logic.

Per-tool standards — required layout, naming, the `--dry-run` rule, README/CHANGELOG shape, test
conventions, the shared-config rule, and the Definition of done — live in
[03-Resources/tools/CONTRIBUTING](03-Resources/tools/CONTRIBUTING.md). Read it before adding or changing a tool.

## Testing

No CI by default. Two things stand in for it:

1. **Every tool has a suite**, run from its own directory: `python3 -m pytest tests/`.
2. **Dry-run output is the acceptance test.** Run the tool bare, read what it says it would change,
   *then* pass `--apply`. A tool that prints only a count instead of what changes has failed this
   rule — see [03-Resources/tools/CONTRIBUTING](03-Resources/tools/CONTRIBUTING.md).

Log manual validation steps in the note that prompted the change.

## Commits & Pull Requests

Short, present-tense commit summaries. Group related note-moves and metadata updates together; don't
mix structural changes with content edits. PRs describe the goal, list affected top-level folders,
and reference relevant notes. Attach key command outputs rather than screenshots unless a UI artifact
changed.
