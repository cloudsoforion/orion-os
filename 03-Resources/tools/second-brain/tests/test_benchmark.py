#!/usr/bin/env python3
"""
test_benchmark.py — the benchmark contract from benchmark.py.

Specification enforced here:

| Function        | Behaviour                                                          |
| --------------- | ------------------------------------------------------------------ |
| `load_probes`   | Requires an object with a non-empty `probes` list                   |
|                 | Every probe needs `label`, `query`, `kind`                          |
|                 | `kind` must be `signal` or `noise`; empty queries rejected          |
|                 | **At least one `noise` probe** — it is the control, so its absence  |
|                 | is an error, not a warning                                          |
| `summarise`     | best/mean/hits from a score list; empty list is 0.0, not a crash    |
| `separation`    | mean best signal − mean best noise; `None` if either class is absent |
| `compare`       | Joins on label; unmatched labels survive with `delta: None`          |
| `verdict`       | Flags separation ≤ 0 as the structure-not-meaning failure           |
| `format_table`  | Renders without raising, including on an empty run                  |

`benchmark.py` itself hits Ollama; nothing here does. Only the pure functions are
covered, which is exactly the split CONTRIBUTING § Tests asks for.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from benchmark import (  # noqa: E402
    compare,
    format_comparison,
    format_table,
    load_probes,
    separation,
    summarise,
    verdict,
)

GOOD = {"probes": [
    {"label": "a", "query": "real question", "kind": "signal"},
    {"label": "b", "query": "asdfgh", "kind": "noise"},
]}


class TestLoadProbes:
    def test_accepts_a_valid_document(self):
        assert len(load_probes(GOOD)) == 2

    def test_rejects_missing_probes_key(self):
        with pytest.raises(ValueError, match="probes"):
            load_probes({"queries": []})

    def test_rejects_empty_list(self):
        with pytest.raises(ValueError, match="non-empty"):
            load_probes({"probes": []})

    def test_rejects_missing_field(self):
        with pytest.raises(ValueError, match="missing 'kind'"):
            load_probes({"probes": [{"label": "a", "query": "q"}]})

    def test_rejects_unknown_kind(self):
        with pytest.raises(ValueError, match="kind must be"):
            load_probes({"probes": [{"label": "a", "query": "q", "kind": "control"}]})

    def test_rejects_empty_query(self):
        with pytest.raises(ValueError, match="empty query"):
            load_probes({"probes": [
                {"label": "a", "query": "   ", "kind": "signal"},
                {"label": "b", "query": "x", "kind": "noise"}]})

    def test_requires_at_least_one_noise_probe(self):
        # Without a control there is no separation, which is the point of the tool.
        with pytest.raises(ValueError, match="noise"):
            load_probes({"probes": [{"label": "a", "query": "q", "kind": "signal"}]})


class TestSummarise:
    def test_computes_best_mean_and_hits(self):
        r = summarise("p", "signal", [0.5, 0.9, 0.7])
        assert r["best"] == 0.9
        assert r["hits"] == 3
        assert r["mean"] == 0.7

    def test_empty_scores_are_zero_not_an_error(self):
        r = summarise("p", "noise", [])
        assert r["best"] == 0.0 and r["hits"] == 0 and r["scores"] == []

    def test_rounds_to_three_places(self):
        assert summarise("p", "signal", [0.123456])["best"] == 0.123


class TestSeparation:
    def test_signal_above_noise_is_positive(self):
        rows = [summarise("a", "signal", [0.8]), summarise("b", "noise", [0.4])]
        assert separation(rows) == pytest.approx(0.4)

    def test_noise_above_signal_is_negative(self):
        rows = [summarise("a", "signal", [0.4]), summarise("b", "noise", [0.8])]
        assert separation(rows) < 0

    def test_averages_across_multiple_probes(self):
        rows = [summarise("a", "signal", [0.8]), summarise("b", "signal", [0.6]),
                summarise("c", "noise", [0.5])]
        assert separation(rows) == pytest.approx(0.2)

    def test_none_when_noise_missing(self):
        assert separation([summarise("a", "signal", [0.8])]) is None

    def test_none_when_signal_missing(self):
        assert separation([summarise("a", "noise", [0.3])]) is None


class TestCompare:
    def test_computes_delta_on_matching_labels(self):
        cur = [summarise("a", "signal", [0.8])]
        base = [summarise("a", "signal", [0.6])]
        assert compare(cur, base)[0]["delta"] == pytest.approx(0.2)

    def test_new_probe_has_null_baseline_and_delta(self):
        row = compare([summarise("new", "signal", [0.8])], [])[0]
        assert row["baseline"] is None and row["delta"] is None

    def test_negative_delta_is_preserved(self):
        cur = [summarise("a", "noise", [0.4])]
        base = [summarise("a", "noise", [0.6])]
        assert compare(cur, base)[0]["delta"] == pytest.approx(-0.2)


class TestVerdict:
    def test_flags_non_positive_separation(self):
        assert "🔴" in verdict(0.0)
        assert "🔴" in verdict(-0.1)

    def test_warns_on_weak_separation(self):
        assert "⚠️" in verdict(0.05)

    def test_passes_healthy_separation(self):
        assert "✅" in verdict(0.25)

    def test_handles_missing_separation(self):
        assert "n/a" in verdict(None)

    def test_includes_baseline_delta_when_given(self):
        assert "baseline" in verdict(0.25, 0.15)


class TestFormatting:
    def test_table_renders(self):
        out = format_table([summarise("a", "signal", [0.8, 0.7])])
        assert "probe" in out and "0.800" in out

    def test_table_survives_empty_run(self):
        assert isinstance(format_table([]), str)

    def test_comparison_renders_new_probes(self):
        out = format_comparison(compare([summarise("a", "signal", [0.8])], []))
        assert "new" in out
