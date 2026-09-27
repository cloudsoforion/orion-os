---
created: "20260808"
updated: "20260808"
tags:
  - created/20260808
  - updated/20260808
  - type/how-to
  - domain/knowledge-management
  - status/active
status: active
---

# Adopting OrionOs into a vault you already have

A fresh clone is the easy case. This is the other one: you have notes, they're already organised
somehow, and you want the model and the tooling without a weekend of breakage.

**The short version: adopt the conventions first, rename folders last — or never.** The tools read
`vault.json`, so they work against *your* folder names. Renaming is the expensive, risky step and it
is entirely optional.

## Order of operations

### 1. Copy the tooling and the config (safe, reversible)

```bash
cp -r <orion-os>/03-Resources/tools  <your-vault>/03-Resources/tools
cp    <orion-os>/vault.json          <your-vault>/vault.json
```

Then edit `vault.json` so the pillar names, `log_dir`, and `changelog_dir` match **what you already
have**:

```json
{
  "pillars": {
    "inbox": "0-inbox",
    "areas": "areas",
    "projects": "active-projects",
    "resources": "reference",
    "archive": "archive"
  },
  "log_dir": "journal",
  "author": "Your Name"
}
```

Only the keys you're changing — the rest fall back to the defaults. Confirm the tools agree with you:

```bash
python3 03-Resources/tools/vault_config.py
```

That prints the vault root it found and the merged config. If the root is wrong, you're running it
outside the vault; if a folder name is wrong, `vault.json` is wrong.

If you keep tools somewhere other than `03-Resources/tools/`, that path is the one thing you can't
configure — the shared-module import is relative (`parent.parent`). Either use that path, or adjust
the `sys.path.insert` line in each tool.

### 2. Take a baseline before changing anything

```bash
# What the link graph looks like today
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py > /tmp/links-before.txt

# What frontmatter stamping would do. This PREVIEWS — it does not write.
python3 03-Resources/tools/process_frontmatter/process_frontmatter.py > /tmp/frontmatter-before.txt
```

Read both. `process_frontmatter` will propose changes to a lot of files on first contact with an
existing vault; the point of the baseline is to be able to diff it after you change config, and to
decide deliberately rather than discovering.

Commit before anything else. Everything below is recoverable from git and from nothing else.

### 3. Adopt the conventions (this is the actual value)

None of this requires moving a file:

- **[OrionOs](../OrionOs.md) § Statuses** — put a `status:` field on your active work. The `blocked` vs `paused`
  distinction is the one that pays for itself immediately.
- **[AGENTS](../AGENTS.md) § Wikilinks** — vault-absolute links. Set `"newLinkFormat": "absolute"` and
  `"alwaysUpdateLinks": true` in `.obsidian/app.json` so Obsidian stops generating bare ones, then
  work through what the scanner reports.
- **[CLAUDE](../CLAUDE.md) § Metadata Standards** — the tag namespaces, and one `type/` + one `status/` per file.
- **[CLAUDE](../CLAUDE.md) § Documentation Standards** — the seven rules. Free, and the highest-leverage part of
  this whole repo.

### 4. Add the pillar READMEs

Copy `templates/pillar-README.md` into each of your top-level folders and fill it in. Do the
**"What does NOT live here"** table properly — that table is what makes the model self-enforcing, and
writing it is what surfaces the folders that are secretly doing two jobs.

### 5. Rename folders — optional, last, and carefully

Only if you actually want the numbered pillars. This is the step that breaks links.

```bash
# Baseline the link graph first
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py --report before.md
```

Then, **in Obsidian** — never `mv` — rename one folder at a time with "Automatically update internal
links" on. After each rename:

```bash
# Update vault.json to the new name, then re-check
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py
```

If a rename left broken links behind, the scanner can repair the ones it can verify:

```bash
python3 03-Resources/tools/scan-broken-wikilinks/scan_broken_wikilinks.py \
  --remap old-name/=01-Areas/ --apply
```

A remap only rewrites a link when the remapped target **actually exists**, so it can't convert a
visibly broken link into a plausibly broken one. Anything it can't verify is reported for you.

> ⚠️ **Why "in Obsidian, never `mv`" is the loudest rule here.** A shell move leaves every inbound
> wikilink pointing at nothing, and a broken wikilink renders as *unclickable text* — it looks like
> prose. Nothing warns you. The vault this repo was extracted from lost roughly a thousand links to a
> single shell-based reorg, and the recovery cost far exceeded the reorg.
>
> Put the remaps you needed into `link_remaps` in `vault.json` while you're mid-migration, so every
> run applies them without you retyping.

## Adopting only some of it

Perfectly reasonable. The pieces are genuinely independent:

| Want just… | Take |
|---|---|
| The link discipline | `scan-broken-wikilinks/` + [AGENTS](../AGENTS.md) § Wikilinks |
| Consistent created/updated dates | `process_frontmatter/` + [CLAUDE](../CLAUDE.md) § Metadata Standards |
| A record of what you did each day | `vault-indexer/` + [Log/README](../Log/README.md) |
| Semantic search over your notes | `second-brain/` + [docs/claude-code-setup](claude-code-setup.md) |
| The folder model, nothing else | [OrionOs](../OrionOs.md) and the pillar READMEs |
| A standard for your own scripts | [03-Resources/tools/CONTRIBUTING](../03-Resources/tools/CONTRIBUTING.md) |

Every tool except `second-brain` depends only on `vault_config.py` and the stdlib
(plus `PyYAML` for `process_frontmatter`).

## Things that will surprise you

- **`process_frontmatter` proposes a lot on first run.** That's it discovering that your notes have no
  `created/` tags, not a bug. It previews by default; read the output, then `--apply` when you're
  ready. It skips a file rather than inventing a date for it.
- **`scan-broken-wikilinks` reports thousands of `basename-single` links.** Every `[[note-name]]` in
  an established vault counts. They *work* today; they're fragile. `--promote-basenames` rewrites the
  unambiguous ones, but consider whether archived notes are worth touching at all.
- **Dates come from git, not mtime.** If your vault isn't a git repo, undated notes get skipped
  instead of dated. That's deliberate: mtime does not survive a bulk copy, and a fabricated date is
  indistinguishable from a real one once written. See
  [03-Resources/tools/20260605-filesystem-timestamps-unreliable](../03-Resources/tools/20260605-filesystem-timestamps-unreliable.md).
- **The index is derived data.** `vault-index.db` is gitignored and rebuilds from your notes in
  seconds. Delete it freely.

## Related

- The repo `README.md` — what OrionOs is
- [OrionOs](../OrionOs.md) — the model
- [docs/claude-code-setup](claude-code-setup.md) — the optional AI integrations
- [03-Resources/tools/README](../03-Resources/tools/README.md) — the tool index
