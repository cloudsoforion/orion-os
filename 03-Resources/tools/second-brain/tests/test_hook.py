"""Spec for hook.py's prompt parsing.

The hook sits in front of a human pressing enter, so its contract is *never
block the prompt*. Every malformed input must degrade to "no prompt" rather than
raising — a traceback here would surface as a broken Claude Code session.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hook import format_context, read_prompt  # noqa: E402


class TestReadPrompt:
    def test_extracts_the_prompt_field(self):
        assert read_prompt(json.dumps({"prompt": "hello"})) == "hello"

    def test_ignores_other_fields(self):
        assert read_prompt(json.dumps({"prompt": "hi", "cwd": "/tmp"})) == "hi"

    def test_bare_json_string_is_the_prompt(self):
        assert read_prompt(json.dumps("hello")) == "hello"

    def test_missing_prompt_key_yields_empty(self):
        assert read_prompt(json.dumps({"cwd": "/tmp"})) == ""

    def test_null_prompt_yields_empty_not_none(self):
        assert read_prompt(json.dumps({"prompt": None})) == ""

    def test_malformed_json_yields_empty_rather_than_raising(self):
        assert read_prompt("{not json") == ""

    def test_empty_input_yields_empty(self):
        assert read_prompt("") == ""

    def test_unexpected_json_type_yields_empty(self):
        assert read_prompt(json.dumps([1, 2, 3])) == ""


class TestFormatContext:
    def test_no_results_produces_no_context_block(self):
        assert format_context([]) == ""

    def test_wraps_hits_in_a_vault_context_block(self):
        out = format_context([{"path": "a.md", "score": 0.9, "headings": []}])
        assert out.startswith("<vault-context>")
        assert out.endswith("</vault-context>")
        assert "- [[a]] (0.90)" in out
