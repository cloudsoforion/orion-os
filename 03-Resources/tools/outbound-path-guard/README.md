---
tags:
  - type/readme
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

# outbound-path-guard

A Claude Code `PreToolUse` hook that stops local-only path references from leaving this machine.
It scans outbound tool calls, such as issue-tracker, chat, docs and email writes and publishing
`gh`/`curl` commands. If the payload contains a reference that no other reader can open, it denies
the call.

## Why

A vault path in a ticket, chat message or PR body leads nowhere for every reader except the author.
Banning `[[wikilinks]]` in external writing isn't enough: the same reference comes back as a
backticked `02-Projects/...` path. So the guard checks whether a reference can be opened, not what
syntax it uses. **If the reader can't open it, it isn't a reference.**

## How it works

- Reads the hook payload on stdin and **first decides whether the call is outbound at all.**
  - Local tools (`Read`, `Write`, `Edit`, …) are ignored entirely.
  - MCP tools are scanned only for the servers in `OUTBOUND_SERVERS`, and read-only calls
    (`get_`, `list_`, `search`, …) are skipped.
  - `Bash` is scanned only for publishing commands, matched at **command position** (the start
    of the command or after a shell separator), with heredoc bodies stripped first. A local command
    that merely quotes or documents `gh pr create` is not treated as outbound.
- Walks every string anywhere in `tool_input` and matches it against five patterns.
- Reads vault directory names from `vault_config` instead of hardcoding them, so renaming a pillar
  can't silently stop the guard working.
- On a hit, it returns `permissionDecision: "deny"` with the offending matches and how to fix them.
  On a clean call it prints nothing, which is how a `PreToolUse` hook says "proceed".
- **Fails open.** Any internal error exits 0 silently. A bug in the guard must not block every
  outbound call, and the cost of a miss is an embarrassing link, not a breach.

## What it blocks

| Reference | Verdict |
|---|---|
| `[[anything]]` | blocked: wikilinks only resolve in Obsidian |
| `00-Inbox/…` … `04-Archive/…` | blocked: distinctive vault directories |
| `Log/…md`, `CHANGELOG/…md`, `templates/…md` | blocked: the directory name is generic, but `.md` marks it as vault content |
| `Log/out.json`, `templates/base.html` | allowed: generic directory, not a vault doc |
| `/Users/…`, `~/…` | blocked: paths that only exist on this machine |
| `apps/api/dev/infra/queue.yaml` | allowed: repo-relative, so a teammate can open it |

## Usage

```bash
# check one string by hand; exits 1 and prints the reason if it finds anything
python3 outbound_path_guard.py --text 'see 02-Projects/foo/bar.md'

# show the patterns actually in force, resolved from vault_config
python3 outbound_path_guard.py --list-patterns

# simulate a hook call
echo '{"tool_name":"mcp__linear-server__save_issue","tool_input":{"description":"see Log/20260817/x.md"}}' \
  | python3 outbound_path_guard.py
```

## Flags

| Flag | Applies to | Meaning |
|---|---|---|
| `--text STR` | CLI use | scan one string instead of reading stdin; exit 1 if it finds anything |
| `--list-patterns` | CLI use | print each label + regex, then exit |

There's no `--dry-run` because the tool never writes to the vault. Its only side effect is the
decision it prints, and `--text` is the safe way to preview that.

## Output

Nothing is written to disk. On a blocked call, stdout carries:

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse",
 "permissionDecision":"deny","permissionDecisionReason":"…"}}
```

## Configuration

Which MCP servers count as outbound is set by `OUTBOUND_SERVERS` at the top of the script. It ships
with Linear, Slack, Notion and Gmail. Edit it to match the servers you have connected, and make the
hook `matcher` in `.claude/settings.json` cover the same set. Registration is covered in
[docs/claude-code-setup](../../../docs/claude-code-setup.md) § Outbound path guard.

## Tests

```bash
python3 -m pytest tests/
```

There are 27 tests. They cover the allow-list of repo-relative paths, `is_outbound` gating, the
false positives from quoted mentions and heredocs, and an end-to-end check of the stdin/stdout hook
contract, including malformed input.

## First run / new machine

Uses only the standard library, so there's no `requirements.txt`. It needs
`03-Resources/tools/vault_config.py` in its parent directory, which is where it already lives. After
you register the hook, open `/hooks` once or restart Claude Code so the settings watcher reloads.

To confirm the guard is live, make a deliberately dirty outbound call and check that it's denied.

## Limitations

- **Fails open by design**, so it builds a habit rather than acting as a security control.
- It only sees tool calls. Text you paste into a tracker or chat by hand isn't checked.

## Related

- [03-Resources/tools/CONTRIBUTING](../CONTRIBUTING.md): the standard this tool follows
- [AGENTS](../../../AGENTS.md) § Markdown & Naming Conventions: the vault-absolute wikilink rule, which this guard
  limits to inside the vault
