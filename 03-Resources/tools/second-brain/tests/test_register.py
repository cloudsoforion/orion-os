"""Spec for register.py's merge policy.

These two config files may already hold hooks and servers the user depends on, so
the only acceptable failure mode is "left it alone". Every test here exists to pin
that the merge is additive: unrelated entries survive, unrelated keys survive, and
re-running is a no-op rather than a duplicate.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from register import (  # noqa: E402
    DEFAULT_SERVER_NAME,
    HOOK_EVENT,
    load_json,
    merge_hook,
    merge_server,
)

HOOK = Path("/vault/03-Resources/tools/second-brain/hook.py")
SERVER = Path("/vault/03-Resources/tools/second-brain/mcp_server.py")


def entries(settings):
    return [e for g in settings["hooks"][HOOK_EVENT] for e in g.get("hooks", [])]


class TestMergeHook:
    def test_adds_to_empty_settings(self):
        got, action = merge_hook({}, HOOK, "python3")
        assert action == "added"
        assert entries(got)[0]["command"] == f"python3 {HOOK}"

    def test_is_idempotent(self):
        once, _ = merge_hook({}, HOOK, "python3")
        twice, action = merge_hook(once, HOOK, "python3")
        assert action == "unchanged"
        assert twice == once
        assert len(entries(twice)) == 1

    def test_replaces_our_entry_when_the_interpreter_changes(self):
        before, _ = merge_hook({}, HOOK, "python")
        after, action = merge_hook(before, HOOK, "python3")
        assert action == "replaced"
        assert len(entries(after)) == 1
        assert entries(after)[0]["command"] == f"python3 {HOOK}"

    def test_recognises_our_entry_written_with_a_different_absolute_path(self):
        """A vault moved on disk still has one hook, not two."""
        stale = {"hooks": {HOOK_EVENT: [{"hooks": [
            {"type": "command", "command": "python /old/place/second-brain/hook.py"}
        ]}]}}
        after, action = merge_hook(stale, HOOK, "python3")
        assert action == "replaced"
        assert len(entries(after)) == 1

    def test_keeps_an_unrelated_hook_in_the_same_event(self):
        other = {"hooks": {HOOK_EVENT: [{"hooks": [
            {"type": "command", "command": "python3 /somewhere/else.py"}
        ]}]}}
        after, _ = merge_hook(other, HOOK, "python3")
        commands = [e["command"] for e in entries(after)]
        assert "python3 /somewhere/else.py" in commands
        assert f"python3 {HOOK}" in commands

    def test_keeps_other_hook_events(self):
        other = {"hooks": {"PostToolUse": [{"hooks": [{"type": "command", "command": "x"}]}]}}
        after, _ = merge_hook(other, HOOK, "python3")
        assert after["hooks"]["PostToolUse"] == other["hooks"]["PostToolUse"]

    def test_keeps_unrelated_top_level_settings(self):
        after, _ = merge_hook({"permissions": {"allow": ["Bash(ls)"]}}, HOOK, "python3")
        assert after["permissions"] == {"allow": ["Bash(ls)"]}

    def test_does_not_mutate_the_input(self):
        original = {"hooks": {}}
        merge_hook(original, HOOK, "python3")
        assert original == {"hooks": {}}


class TestMergeServer:
    def test_adds_to_empty_config(self):
        got, action = merge_server({}, SERVER, "python3", DEFAULT_SERVER_NAME, None)
        assert action == "added"
        assert got["mcpServers"][DEFAULT_SERVER_NAME]["args"] == [str(SERVER)]

    def test_is_idempotent(self):
        once, _ = merge_server({}, SERVER, "python3", DEFAULT_SERVER_NAME, None)
        twice, action = merge_server(once, SERVER, "python3", DEFAULT_SERVER_NAME, None)
        assert action == "unchanged"
        assert twice == once

    def test_keeps_other_servers(self):
        before = {"mcpServers": {"linear": {"command": "npx", "args": ["x"]}}}
        after, _ = merge_server(before, SERVER, "python3", DEFAULT_SERVER_NAME, None)
        assert after["mcpServers"]["linear"] == {"command": "npx", "args": ["x"]}

    def test_db_override_is_passed_through(self):
        got, _ = merge_server({}, SERVER, "python3", DEFAULT_SERVER_NAME, Path("/other/i.db"))
        assert got["mcpServers"][DEFAULT_SERVER_NAME]["args"][-2:] == ["--db", "/other/i.db"]

    def test_a_non_default_name_is_passed_to_the_server(self):
        """Otherwise two vaults register two servers that both call themselves
        vault-search, and the client sees one shadow the other."""
        got, _ = merge_server({}, SERVER, "python3", "vault-search-personal", None)
        args = got["mcpServers"]["vault-search-personal"]["args"]
        assert args[-2:] == ["--name", "vault-search-personal"]

    def test_default_name_is_not_passed_redundantly(self):
        got, _ = merge_server({}, SERVER, "python3", DEFAULT_SERVER_NAME, None)
        assert "--name" not in got["mcpServers"][DEFAULT_SERVER_NAME]["args"]

    def test_a_second_vault_coexists_with_the_first(self):
        first, _ = merge_server({}, SERVER, "python3", DEFAULT_SERVER_NAME, None)
        both, _ = merge_server(first, SERVER, "python3", "vault-search-personal", Path("/o.db"))
        assert set(both["mcpServers"]) == {DEFAULT_SERVER_NAME, "vault-search-personal"}


class TestLoadJson:
    def test_missing_file_is_empty_config(self, tmp_path):
        assert load_json(tmp_path / "nope.json") == {}

    def test_empty_file_is_empty_config(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("   \n")
        assert load_json(f) == {}

    def test_malformed_file_raises_rather_than_being_overwritten(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not json")
        with pytest.raises(Exception):
            load_json(f)
