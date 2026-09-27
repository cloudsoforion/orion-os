"""Spec enforced by these tests.

The guard denies an outbound tool call when its payload contains a reference only
the local machine can resolve. The decision table it implements:

| Reference                              | Verdict | Why                                  |
|----------------------------------------|---------|--------------------------------------|
| `[[anything]]`                         | block   | wikilinks resolve in Obsidian only   |
| `02-Projects/…`, any numbered pillar   | block   | distinctive vault dirs               |
| `Log/…md`, `CHANGELOG/…md`, `templates/…md` | block | generic dir names, `.md` = vault |
| `Log/foo.yaml`, `templates/base.html`  | allow   | generic dir, not a vault doc         |
| `/Users/…`, `~/…`                      | block   | machine-local absolute paths         |
| `apps/api/dev/infra/queue.yaml`        | allow   | repo-relative; teammates can open it |

Scanning is gated on the call actually being outbound: MCP writes to Linear/Slack/
Notion/Gmail, and Bash only for publishing commands (`gh pr create`, curl at Slack).
A local `cat 02-Projects/foo.md` must never be blocked.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from outbound_path_guard import (  # noqa: E402
    build_patterns,
    find_violations,
    format_reason,
    is_outbound,
    iter_strings,
    scan_payload,
)

SCRIPT = Path(__file__).parent.parent / "outbound_path_guard.py"

CONFIG = {
    "pillars": {"inbox": "00-Inbox", "areas": "01-Areas", "projects": "02-Projects",
                "resources": "03-Resources", "archive": "04-Archive"},
    "log_dir": "Log",
    "changelog_dir": "CHANGELOG",
    "templates_dir": "templates",
}
PATTERNS = build_patterns(CONFIG)


class TestFindViolations:
    def test_the_pla_146_leak_is_caught(self):
        # The exact string that shipped, backticked rather than bracketed.
        text = ("Full itemized list in the vault: `02-Projects/2026-SOC-2/Resolving-CVEs/"
                "Remove-kube-prometheus-stack-from-NA-clusters/20260820-cleanup-checklist.md`")
        found = find_violations(text, PATTERNS)
        assert [label for label, _ in found] == ["vault path"]

    def test_wikilink_still_caught(self):
        found = find_violations("see [[03-Resources/tools/CONTRIBUTING]]", PATTERNS)
        assert any(label == "wikilink" for label, _ in found)

    def test_every_numbered_pillar(self):
        for pillar in CONFIG["pillars"].values():
            found = find_violations(f"in {pillar}/thing/note.md", PATTERNS)
            assert found, pillar

    def test_absolute_and_home_paths(self):
        labels = {l for l, _ in find_violations(
            "/Users/alice/notes/vault and ~/projects/deployment", PATTERNS)}
        assert labels == {"absolute local path", "home-relative path"}

    def test_generic_dir_blocked_only_for_markdown(self):
        assert find_violations("Log/20260817/priorities-week-of-20260817.md", PATTERNS)
        assert find_violations("CHANGELOG/20260616/notes.md", PATTERNS)
        # …but a repo that merely has these directory names is left alone.
        assert not find_violations("templates/base.html", PATTERNS)
        assert not find_violations("Log/output.json", PATTERNS)

    def test_repo_relative_paths_allowed(self):
        for ok in ("apps/api/dev/infra/queue.yaml",
                   "cluster-services/argocd/values.yaml",
                   "docs/runbook.md",
                   "mesh/environments/production/values.yaml"):
            assert not find_violations(ok, PATTERNS), ok

    def test_prose_and_urls_are_clean(self):
        text = ("Merged https://github.com/example/deployment/pull/1234 — see ENG-146. "
                "Watch `api-worker`, not the DLQ.")
        assert not find_violations(text, PATTERNS)

    def test_deduplicates_repeats(self):
        text = "02-Projects/a/b.md and again 02-Projects/a/b.md"
        assert len(find_violations(text, PATTERNS)) == 1

    def test_non_strings_and_empty(self):
        assert find_violations("", PATTERNS) == []
        assert find_violations(None, PATTERNS) == []
        assert find_violations(42, PATTERNS) == []


class TestIsOutbound:
    def test_linear_and_slack_writes_are_outbound(self):
        assert is_outbound("mcp__linear-server__save_issue", {})
        assert is_outbound("mcp__linear-server__save_comment", {})
        assert is_outbound("mcp__claude_ai_Slack__slack_send_message", {})
        assert is_outbound("mcp__notion__notion-create-pages", {})
        assert is_outbound("mcp__claude_ai_Gmail__send_message", {})

    def test_reads_are_not_outbound(self):
        for name in ("mcp__linear-server__get_issue",
                     "mcp__linear-server__list_issues",
                     "mcp__claude_ai_Slack__slack_search_public",
                     "mcp__notion__notion-fetch",
                     "mcp__vault-search__search_vault"):
            assert not is_outbound(name, {}), name

    def test_unrelated_tools_ignored(self):
        assert not is_outbound("Write", {"file_path": "02-Projects/x.md"})
        assert not is_outbound("Edit", {})
        assert not is_outbound("", {})

    def test_bash_only_when_publishing(self):
        assert is_outbound("Bash", {"command": "gh pr create --body 'x'"})
        assert is_outbound("Bash", {"command": "gh issue comment 5 --body y"})
        assert is_outbound("Bash", {"command": "curl -X POST https://hooks.slack.com/x"})
        # A local read of a vault file must stay allowed.
        assert not is_outbound("Bash", {"command": "cat 02-Projects/foo/bar.md"})
        assert not is_outbound("Bash", {"command": "gh pr view 102 --json title"})
        assert not is_outbound("Bash", {"command": "grep -r Log/ ."})

    def test_matches_after_a_shell_separator(self):
        assert is_outbound("Bash", {"command": "git push && gh pr create --body x"})
        assert is_outbound("Bash", {"command": "cd /tmp; gh issue comment 1 --body y"})

    def test_quoted_mention_is_not_a_command(self):
        # Regression: matching anywhere flagged these as outbound and blocked
        # purely local work. Caught on this guard's first real use, 2026-08-20.
        assert not is_outbound("Bash", {"command": 'echo "gh pr create --body 02-Projects/x.md"'})
        assert not is_outbound("Bash", {"command": "grep -rn 'gh pr create' ."})

    def test_heredoc_body_is_data_not_command(self):
        cmd = ("cat > doc.md <<'EOF'\n"
               "Docs say: gh pr create --body 'see 02-Projects/x.md'\n"
               "EOF")
        assert not is_outbound("Bash", {"command": cmd})

    def test_heredoc_strip_does_not_hide_a_real_command_after_it(self):
        cmd = ("cat > f <<'EOF'\nplain text\nEOF\ngh pr create --body z")
        assert is_outbound("Bash", {"command": cmd})


class TestScanPayload:
    def test_blocks_a_linear_write(self):
        payload = {"tool_name": "mcp__linear-server__save_issue",
                   "tool_input": {"title": "ENG-146",
                                  "description": "list: `Log/20260817/x.md`"}}
        assert scan_payload(payload, PATTERNS)

    def test_nested_strings_are_reached(self):
        payload = {"tool_name": "mcp__claude_ai_Slack__slack_send_message",
                   "tool_input": {"blocks": [{"text": {"body": "~/projects/deployment"}}]}}
        assert scan_payload(payload, PATTERNS)

    def test_clean_write_passes(self):
        payload = {"tool_name": "mcp__linear-server__save_issue",
                   "tool_input": {"description": "See ENG-144 and deployment#1234."}}
        assert scan_payload(payload, PATTERNS) == []

    def test_local_tool_never_scanned(self):
        payload = {"tool_name": "Write",
                   "tool_input": {"content": "[[02-Projects/x]] /Users/alice/y"}}
        assert scan_payload(payload, PATTERNS) == []

    def test_iter_strings_walks_everything(self):
        got = set(iter_strings({"a": "1", "b": ["2", {"c": "3"}], "d": 4, "e": None}))
        assert got == {"1", "2", "3"}


class TestReason:
    def test_reason_names_the_match_and_the_fix(self):
        reason = format_reason([("vault path", "02-Projects/a/b.md")])
        assert "02-Projects/a/b.md" in reason
        assert "Inline the actual content" in reason

    def test_reason_truncates_long_lists(self):
        reason = format_reason([("vault path", f"02-Projects/{i}.md") for i in range(12)])
        assert "and 4 more" in reason


class TestHookContract:
    """End-to-end through the real stdin/stdout contract."""

    def _run(self, payload):
        out = subprocess.run([sys.executable, str(SCRIPT)],
                             input=json.dumps(payload), capture_output=True,
                             text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return out.stdout.strip()

    def test_deny_shape_matches_pretooluse_schema(self):
        out = self._run({"tool_name": "mcp__linear-server__save_issue",
                         "tool_input": {"description": "see 02-Projects/a/b.md"}})
        decision = json.loads(out)["hookSpecificOutput"]
        assert decision["hookEventName"] == "PreToolUse"
        assert decision["permissionDecision"] == "deny"
        assert "02-Projects/a/b.md" in decision["permissionDecisionReason"]

    def test_clean_call_emits_nothing(self):
        assert self._run({"tool_name": "mcp__linear-server__save_issue",
                          "tool_input": {"description": "See ENG-146."}}) == ""

    def test_malformed_input_fails_open(self):
        out = subprocess.run([sys.executable, str(SCRIPT)], input="not json",
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0
        assert out.stdout.strip() == ""
