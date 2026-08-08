"""Spec for common.py — the primitives shared by second-brain's four entry points.

Before this module each of embed.py, search.py, hook.py, and mcp_server.py carried
its own copy of the Ollama endpoint, the model name, and `cosine_similarity`, plus
its own retrieval threshold. They were equal only by accident; changing the model
meant four edits, and missing one silently mixed vector spaces.

No network: `embed()` is never called here. Scoring is fed vectors directly.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import (  # noqa: E402
    DB_NAME,
    cosine_similarity,
    default_db_path,
    format_hits,
    score_rows,
)


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0

    def test_orthogonal_vectors_score_zero(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_opposite_vectors_score_minus_one(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0

    def test_magnitude_does_not_affect_score(self):
        assert cosine_similarity([1.0, 1.0], [5.0, 5.0]) == pytest.approx(1.0)

    def test_zero_vector_scores_zero_instead_of_dividing_by_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def row(path, vector, extracted=None):
    if extracted is None:
        return (path, json.dumps(vector))
    return (path, json.dumps(vector), json.dumps(extracted))


class TestScoreRows:
    def test_two_column_rows_yield_path_and_score_only(self):
        got = score_rows([row("a.md", [1.0, 0.0])], [1.0, 0.0])
        assert got == [{"path": "a.md", "score": 1.0}]

    def test_three_column_rows_add_title_and_h2_headings(self):
        extracted = {"title": "A Note", "headings": [
            {"level": 1, "text": "H1"},
            {"level": 2, "text": "First"},
            {"level": 3, "text": "H3"},
            {"level": 2, "text": "Second"},
        ]}
        got = score_rows([row("a.md", [1.0, 0.0], extracted)], [1.0, 0.0])
        assert got[0]["title"] == "A Note"
        assert got[0]["headings"] == ["First", "Second"]

    def test_title_falls_back_to_the_filename_stem(self):
        got = score_rows([row("dir/a.md", [1.0, 0.0], {})], [1.0, 0.0])
        assert got[0]["title"] == "a"

    def test_headings_are_capped_at_four(self):
        extracted = {"headings": [{"level": 2, "text": f"H{i}"} for i in range(10)]}
        got = score_rows([row("a.md", [1.0, 0.0], extracted)], [1.0, 0.0])
        assert len(got[0]["headings"]) == 4

    def test_results_are_ordered_best_first(self):
        rows = [row("weak.md", [0.0, 1.0]), row("strong.md", [1.0, 0.0])]
        assert [r["path"] for r in score_rows(rows, [1.0, 0.0])] == ["strong.md", "weak.md"]

    def test_min_score_filters_out_weak_matches(self):
        rows = [row("weak.md", [0.0, 1.0]), row("strong.md", [1.0, 0.0])]
        got = score_rows(rows, [1.0, 0.0], min_score=0.5)
        assert [r["path"] for r in got] == ["strong.md"]

    def test_default_min_score_keeps_everything(self):
        rows = [row("weak.md", [0.0, 1.0])]
        assert len(score_rows(rows, [1.0, 0.0])) == 1

    def test_no_rows_yields_no_results(self):
        assert score_rows([], [1.0, 0.0]) == []


class TestFormatHits:
    def test_drops_the_md_suffix_so_the_wikilink_resolves(self):
        assert format_hits([{"path": "02-Projects/a.md", "score": 0.9}]) == [
            "- [[02-Projects/a]] (0.90)"
        ]

    def test_appends_headings_when_present(self):
        line = format_hits([{"path": "a.md", "score": 0.9, "headings": ["One", "Two"]}])[0]
        assert line == "- [[a]] (0.90) — One · Two"

    def test_empty_headings_add_nothing(self):
        assert format_hits([{"path": "a.md", "score": 0.5, "headings": []}]) == ["- [[a]] (0.50)"]


class TestDefaultDbPath:
    def test_points_at_the_vault_indexer_db_by_default(self, monkeypatch):
        monkeypatch.delenv("SECOND_BRAIN_DB", raising=False)
        path = default_db_path()
        assert path.name == DB_NAME
        assert path.parent.name == "vault-indexer"

    def test_env_var_overrides_it(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SECOND_BRAIN_DB", str(tmp_path / "other.db"))
        assert default_db_path() == tmp_path / "other.db"
