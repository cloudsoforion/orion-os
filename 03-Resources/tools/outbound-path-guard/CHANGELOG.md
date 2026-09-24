---
tags:
  - type/changelog
  - domain/tooling
  - domain/knowledge-management
  - status/active
  - created/20260924
  - updated/20260924
author: Claude (claude-opus-5-5)
created: "20260924"
updated: "20260924"
status: active
---

# Changelog

## [0.1.1] — 2026-08-20

### Fixed
- **The guard blocked purely local file writes.** `is_outbound` matched publishing commands
  anywhere in a Bash command, so any local command that *quoted* or documented one (`echo "gh pr
  create …"`, or a heredoc writing docs about it) was treated as outbound and denied. It's now
  anchored to command position (the start, or after `;`/`&&`/`||`/`|`/newline), and heredoc bodies
  are stripped first. A guard that blocks local work gets switched off, so this was fixed rather
  than documented as a known limitation.
- Tests: 4 added. The suite is now 27.

## [0.1.0] — 2026-08-20

### Added
- **`PreToolUse` guard that denies outbound calls carrying local-only paths.** It matches on
  whether a reference can be opened, not on its syntax. That catches wikilinks, vault paths in
  backticks, and absolute or home-relative paths alike.
- Vault directory names come from `vault_config` instead of being hardcoded, so renaming a pillar
  can't silently disable matching.
- Outbound gating: `Bash` is scanned only for publishing commands (`gh pr create`, `curl` at a chat
  or tracker API), so a local `cat 02-Projects/foo.md` is never blocked.
- Generic-directory narrowing: `Log/`, `CHANGELOG/`, and `templates/` only match `.md` targets, so
  repos that happen to use those names aren't affected.
- Tests: `tests/test_outbound_path_guard.py`.

### Known limitation
- **Fails open by design.** Any internal error exits 0 and the call goes ahead.
- It only covers tool calls. Text pasted into a tracker or chat by hand isn't checked.
