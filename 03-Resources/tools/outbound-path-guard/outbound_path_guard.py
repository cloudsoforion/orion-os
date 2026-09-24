#!/usr/bin/env python3
"""outbound_path_guard.py — stop local-only references from leaving the vault.

Reads a Claude Code `PreToolUse` hook payload on stdin, scans the outbound text
for references that only this machine can resolve, and denies the tool call if it
finds any. Reads nothing from disk except `vault_config`; writes nothing.

Why: a vault path in a Linear ticket, Slack message, or PR body is a dead end for
every reader but the author. The recurring failure is not a syntax slip — it is
that `AGENTS.md` trains "always use full vault paths" for internal links and never
states the boundary. `[[brackets]]` were already forbidden in Linear, so the same
leak simply reappeared in backticks.

The test is resolvability, not syntax: if the reader cannot open it, it is not a
reference. Repo-relative paths (`apps/api/dev/infra/queue.yaml`) stay
allowed — a teammate can open those.

Two decisions worth knowing:

1. **Bash is scanned only when the command is outbound** (`gh pr create`, `gh issue
   comment`, a curl at Slack/Linear). Scanning every Bash call would block
   `cat 02-Projects/foo.md`, which is a local read and perfectly fine.
2. **Generic directories are scanned only for `.md` targets.** `00-Inbox/` … `04-Archive/`
   are distinctive enough to block outright; `Log/`, `CHANGELOG/`, and `templates/`
   are common repo names, so those match only when the path ends in `.md` — which
   is what a vault reference looks like.

Fails open. A crash here must not wedge every outbound call, and the cost of a miss
is an embarrassing link, not a breach.

Usage:
  # as a PreToolUse hook (registered in .claude/settings.json)
  echo '{"tool_name":"...","tool_input":{...}}' | python3 outbound_path_guard.py

  # check one string by hand
  python3 outbound_path_guard.py --text 'see 02-Projects/foo/bar.md'

  # show the patterns it enforces, resolved from vault_config
  python3 outbound_path_guard.py --list-patterns
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import vault_config

# MCP servers that carry text off this machine.
OUTBOUND_SERVERS = ("linear-server", "claude_ai_Slack", "notion", "claude_ai_Gmail")

# Substrings marking a tool as read-only — those send no prose outward.
READONLY_HINTS = ("get_", "get-", "list_", "list-", "search", "read_", "read-",
                  "fetch", "query", "extract", "prepare_", "resolve_")

# Bash invocations that publish. Anything else may reference vault paths freely.
#
# Anchored to *command position* — the start of the command or just after a shell
# separator. Matching anywhere would classify `echo "gh pr create …"` and any
# heredoc that merely mentions the command as outbound, blocking local file
# writes. That happened on this guard's first real use; see the heredoc strip below.
OUTBOUND_BASH = re.compile(
    r"""(?x)
    (?:^|[;&|]|\n)\s*
    (?:
        gh\s+(?:pr|issue|release|gist)\s+(?:create|comment|edit|review|close|reopen)\b
      | gh\s+api\b
      | curl\b[^|;&\n]*\b(?:hooks\.slack\.com|api\.slack\.com
                          |api\.linear\.app|api\.notion\.com)\b
    )
    """
)

# Heredoc bodies are data, not commands — `cat > f <<'EOF' … EOF` may contain
# anything. Strip them before deciding whether a command publishes.
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?\n.*?^\1\b", re.DOTALL | re.MULTILINE)


def strip_heredocs(command):
    """Remove heredoc bodies so their contents can't look like a command."""
    if not isinstance(command, str):
        return ""
    return HEREDOC.sub("<<STRIPPED", command)


def _vault_dirs(config):
    """Return (distinctive, generic) vault directory names from vault_config."""
    distinctive = sorted(config.get("pillars", {}).values())
    generic = [config.get("log_dir", "Log"),
               config.get("changelog_dir", "CHANGELOG"),
               config.get("templates_dir", "templates")]
    return distinctive, [g for g in generic if g]


def build_patterns(config=None):
    """Build the (label, compiled regex) list. Vault dirs come from vault_config."""
    if config is None:
        root = vault_config.find_vault_root(Path.cwd()) or Path.cwd()
        config = vault_config.load_config(root)
    distinctive, generic = _vault_dirs(config)

    d_alt = "|".join(re.escape(d) for d in distinctive)
    g_alt = "|".join(re.escape(g) for g in generic)

    return [
        ("wikilink",
         re.compile(r"\[\[[^\]\n]+\]\]")),
        ("vault path",
         re.compile(rf"(?<![\w/.-])(?:{d_alt})/[^\s`'\"),;]+")),
        ("vault markdown path",
         re.compile(rf"(?<![\w/.-])(?:{g_alt})/[^\s`'\"),;]*\.md\b")),
        ("absolute local path",
         re.compile(r"/Users/[^\s`'\"),;]+")),
        ("home-relative path",
         re.compile(r"(?<![\w])~/[^\s`'\"),;]+")),
    ]


def find_violations(text, patterns=None):
    """Return a de-duplicated [(label, matched_text)] for one string."""
    if not isinstance(text, str) or not text:
        return []
    if patterns is None:
        patterns = build_patterns()
    seen, out = set(), []
    for label, rx in patterns:
        for m in rx.findall(text):
            key = (label, m)
            if key not in seen:
                seen.add(key)
                out.append(key)
    return out


def is_outbound(tool_name, tool_input):
    """True when this call carries text off the machine and should be scanned."""
    if not tool_name:
        return False
    if tool_name == "Bash":
        command = strip_heredocs((tool_input or {}).get("command", ""))
        return bool(OUTBOUND_BASH.search(command))
    if not tool_name.startswith("mcp__"):
        return False
    if not any(server in tool_name for server in OUTBOUND_SERVERS):
        return False
    return not any(hint in tool_name for hint in READONLY_HINTS)


def iter_strings(value):
    """Yield every string nested anywhere in a tool_input payload."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_strings(item)


def scan_payload(payload, patterns=None):
    """Return violations for a hook payload, or [] if the call isn't outbound."""
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    if not is_outbound(tool_name, tool_input):
        return []
    if patterns is None:
        patterns = build_patterns()
    seen, out = set(), []
    for text in iter_strings(tool_input):
        for label, match in find_violations(text, patterns):
            if (label, match) not in seen:
                seen.add((label, match))
                out.append((label, match))
    return out


def format_reason(violations):
    """Build the message the model sees when a call is denied."""
    found = "\n".join(f"  • {label}: {match}" for label, match in violations[:8])
    more = f"\n  … and {len(violations) - 8} more" if len(violations) > 8 else ""
    return (
        "Blocked: this outbound text contains references only your machine can "
        f"resolve.\n\n{found}{more}\n\n"
        "Nobody else can open a vault path, a /Users/ path, a ~/ path, or a "
        "[[wikilink]]. Instead:\n"
        "  • Inline the actual content — the checklist items, the finding, the list.\n"
        "  • Or link something resolvable: a Linear issue key, a PR/commit URL.\n"
        "  • Repo-relative paths (apps/foo/bar.yaml) are fine — teammates can open those.\n"
        "Then retry."
    )


def deny(violations):
    """Emit a PreToolUse deny decision on stdout."""
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": format_reason(violations),
    }}, sys.stdout)
    sys.stdout.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Block local-only path references in outbound tool calls.")
    parser.add_argument("--text", help="scan this string instead of reading stdin")
    parser.add_argument("--list-patterns", action="store_true",
                        help="print the patterns enforced, then exit")
    args = parser.parse_args()

    if args.list_patterns:
        for label, rx in build_patterns():
            print(f"{label:24} {rx.pattern}")
        return 0

    if args.text is not None:
        violations = find_violations(args.text)
        if violations:
            print(format_reason(violations))
            return 1
        print("clean")
        return 0

    payload = json.load(sys.stdin)
    violations = scan_payload(payload)
    if violations:
        deny(violations)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:  # fail open — never wedge outbound work on a guard bug
        sys.exit(0)
