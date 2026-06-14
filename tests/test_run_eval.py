"""Tests for harness/run_eval.py.

load_items and load_done use tmp_path fixtures (no network).
score_one is tested with a minimal mock judge — no live model calls.
aggregate reads/writes real JSON files from tmp_path.
"""
from __future__ import annotations

import json
import pytest
from harness.run_eval import load_items, load_done, score_one, aggregate
from harness.models import GenResult, ModelClient


# ── Mock ─────────────────────────────────────────────────────────────────────

class _MockJudge(ModelClient):
    """Returns a fixed valid judge JSON for every generate() call."""

    def __init__(self, score: int = 3, fabricated: bool = False,
                 model_id: str = "mock-judge"):
        self.model_id = model_id
        self._payload = json.dumps(
            {"score": score, "rationale": "Test.", "fabricated_citation": fabricated}
        )

    def generate(self, prompt, **kwargs) -> GenResult:
        return GenResult(text=self._payload, raw={"model": self.model_id},
                         model_id=self.model_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _item(method: str, **scoring_extras) -> dict:
    """Minimal eval item whose scoring.method is set and all judge fields present."""
    scoring = {"method": method, **scoring_extras}
    return {
        "id": "t-001",
        "track": "common_law",
        "language": "en",
        "difficulty": "core",
        "format": "open",
        "prompt": "Test question?",
        "scoring": scoring,
    }


# ── load_items ────────────────────────────────────────────────────────────────

class TestLoadItems:
    def test_reads_all_items(self, tmp_path):
        items = [{"id": "a", "x": 1}, {"id": "b", "x": 2}]
        p = tmp_path / "items.jsonl"
        p.write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")
        assert load_items(str(p)) == items

    def test_empty_file_returns_empty_list(self, tmp_path):
        p = tmp_path / "items.jsonl"
        p.write_text("")
        assert load_items(str(p)) == []

    def test_blank_lines_between_items_skipped(self, tmp_path):
        p = tmp_path / "items.jsonl"
        p.write_text('{"id": "a"}\n\n{"id": "b"}\n\n')
        result = load_items(str(p))
        assert len(result) == 2
        assert result[0]["id"] == "a"

    def test_malformed_json_raises(self, tmp_path):
        p = tmp_path / "items.jsonl"
        p.write_text("not json\n")
        with pytest.raises(json.JSONDecodeError):
            load_items(str(p))

    def test_single_item(self, tmp_path):
        p = tmp_path / "items.jsonl"
        p.write_text('{"id": "only"}\n')
        assert load_items(str(p)) == [{"id": "only"}]


# ── load_done ─────────────────────────────────────────────────────────────────

class TestLoadDone:
    def test_missing_file_returns_empty_set(self, tmp_path):
        assert load_done(str(tmp_path / "nothing.jsonl")) == set()

    def test_reads_ids(self, tmp_path):
        p = tmp_path / "results.jsonl"
        rows = [{"id": "x", "score": 1.0}, {"id": "y", "score": 0.0}]
        p.write_text("\n".join(json.dumps(r) for r in rows))
        assert load_done(str(p)) == {"x", "y"}

    def test_malformed_lines_silently_skipped(self, tmp_path):
        p = tmp_path / "results.jsonl"
        p.write_text('{"id": "a"}\nnot json at all\n{"id": "b"}\n')
        assert load_done(str(p)) == {"a", "b"}

    def test_empty_file_returns_empty_set(self, tmp_path):
        p = tmp_path / "results.jsonl"
        p.write_text("")
        assert load_done(str(p)) == set()

    def test_duplicate_ids_deduplicated(self, tmp_path):
        p = tmp_path / "results.jsonl"
        p.write_text('{"id": "a"}\n{"id": "a"}\n')
        assert load_done(str(p)) == {"a"}


# ── score_one — rubric ────────────────────────────────────────────────────────

class TestScoreOneRubric:
    def _rubric_item(self):
        item = _item("rubric", rubric_id="common-law-doctrine-v1",
                     reference="Key elements.")
        return item

    def test_no_judge_returns_none_final_score(self):
        r = score_one(self._rubric_item(), "My answer.", [])
        assert r["final_score"] is None
        assert r["programmatic"] is None
        assert r["judge"]["status"] == "NO_JUDGE_CONFIGURED"

    def test_with_judge_score_4_final_1(self):
        r = score_one(self._rubric_item(), "Excellent.", [_MockJudge(score=4)])
        assert r["final_score"] == pytest.approx(1.0)

    def test_with_judge_score_0_final_0(self):
        r = score_one(self._rubric_item(), "Wrong.", [_MockJudge(score=0)])
        assert r["final_score"] == pytest.approx(0.0)

    def test_programmatic_always_none_for_rubric(self):
        r = score_one(self._rubric_item(), "Answer.", [_MockJudge(score=2)])
        assert r["programmatic"] is None


# ── score_one — mcq_exact ─────────────────────────────────────────────────────

class TestScoreOneMcq:
    def test_correct_answer_score_1(self):
        r = score_one(_item("mcq_exact", answer="A"), "The answer is A.", [])
        assert r["final_score"] == 1.0
        assert r["judge"] is None  # needs_judge=False

    def test_wrong_answer_score_0(self):
        r = score_one(_item("mcq_exact", answer="A"), "The answer is B.", [])
        assert r["final_score"] == 0.0

    def test_judge_not_invoked_for_mcq(self):
        judge = _MockJudge(score=4)
        r = score_one(_item("mcq_exact", answer="C"), "C", [judge])
        assert r["judge"] is None


# ── score_one — language_adherence ────────────────────────────────────────────

class TestScoreOneLanguageAdherence:
    def test_correct_language_score_1(self):
        item = _item("language_adherence")
        item["language"] = "en"
        r = score_one(item, "The contract must be interpreted under common law.", [])
        assert r["final_score"] == 1.0

    def test_wrong_language_score_0(self):
        item = _item("language_adherence")
        item["language"] = "fr"
        r = score_one(item, "The contract must be interpreted under common law.", [])
        assert r["final_score"] == 0.0


# ── score_one — keyword_coverage ─────────────────────────────────────────────

class TestScoreOneKeyword:
    def _kw_item(self, must_include=None, must_not_include=None):
        item = _item("keyword_coverage",
                     must_include=must_include or [],
                     must_not_include=must_not_include or [])
        item["format"] = "open"
        return item

    def test_gate_failure_caps_at_zero_even_with_judge(self):
        r = score_one(self._kw_item(must_include=["Oakes"]),
                      "No relevant content.", [_MockJudge(score=4)])
        assert r["final_score"] == 0.0

    def test_gate_pass_judge_sets_quality_score(self):
        r = score_one(self._kw_item(must_include=["Oakes"]),
                      "The Oakes test requires proportionality.",
                      [_MockJudge(score=2)])
        assert r["final_score"] == pytest.approx(0.5)  # 2/4

    def test_gate_pass_no_judge_returns_none(self):
        r = score_one(self._kw_item(must_include=["Oakes"]),
                      "The Oakes test is relevant.", [])
        assert r["final_score"] is None


# ── score_one — tool_call ─────────────────────────────────────────────────────

class TestScoreOneToolCall:
    _SEARCH_CALL = '<tool_call>{"name": "search", "arguments": {"query": "test"}}</tool_call>'

    def test_name_match_combined_score(self):
        r = score_one(_item("tool_call", expected_tool="search"),
                      self._SEARCH_CALL, [_MockJudge(score=4)])
        assert r["final_score"] == pytest.approx(1.0)  # 0.5 + 0.5*1.0

    def test_name_match_low_judge_score(self):
        r = score_one(_item("tool_call", expected_tool="search"),
                      self._SEARCH_CALL, [_MockJudge(score=0)])
        assert r["final_score"] == pytest.approx(0.5)  # 0.5 + 0.5*0.0

    def test_no_judge_keeps_prog_score(self):
        r = score_one(_item("tool_call", expected_tool="search"),
                      self._SEARCH_CALL, [])
        assert r["final_score"] == pytest.approx(0.5)
        assert r["judge"]["status"] == "NO_JUDGE_CONFIGURED_quality_unscored"

    def test_name_mismatch_scores_quarter_no_judge(self):
        call = '<tool_call>{"name": "wrong_tool", "arguments": {}}</tool_call>'
        r = score_one(_item("tool_call", expected_tool="search"), call, [])
        assert r["final_score"] == pytest.approx(0.25)


# ── score_one — refusal ───────────────────────────────────────────────────────

class TestScoreOneRefusal:
    def test_correct_refusal_prog_is_authoritative(self):
        r = score_one(_item("refusal", expected_refusal=True),
                      "I cannot help with this.", [_MockJudge(score=0)])
        assert r["final_score"] == 1.0  # prog wins, not judge

    def test_over_refusal_score_0(self):
        r = score_one(_item("refusal", expected_refusal=False),
                      "I cannot assist.", [_MockJudge(score=4)])
        assert r["final_score"] == 0.0

    def test_no_judge_keeps_prog_quality_unscored(self):
        r = score_one(_item("refusal", expected_refusal=True),
                      "I cannot help.", [])
        assert r["final_score"] == 1.0
        assert r["judge"]["status"] == "NO_JUDGE_CONFIGURED_quality_unscored"


# ── score_one — citation_validity no-judge path ───────────────────────────────

class TestScoreOneCitation:
    def test_vague_response_no_judge_returns_none(self):
        item = _item("citation_validity", valid_citations=["[1986] 1 SCR 103"])
        r = score_one(item, "The Supreme Court addressed this.", [])
        assert r["final_score"] is None
        assert r["judge"]["status"] == "NO_JUDGE_CONFIGURED"

    def test_gold_match_no_judge_needed(self):
        item = _item("citation_validity", valid_citations=["[1986] 1 SCR 103"])
        r = score_one(item, "See [1986] 1 SCR 103 (R v Oakes).", [])
        assert r["final_score"] == 1.0
        assert r["judge"] is None


# ── aggregate ─────────────────────────────────────────────────────────────────

class TestAggregate:
    def _write_results(self, tmp_path, rows):
        p = tmp_path / "items.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        return str(p)

    def test_basic_structure(self, tmp_path):
        rows = [
            {"id": "a", "track": "common_law", "language": "en",
             "difficulty": "core", "score": 1.0},
            {"id": "b", "track": "common_law", "language": "fr",
             "difficulty": "core", "score": 0.0},
        ]
        rp = self._write_results(tmp_path, rows)
        sp = str(tmp_path / "summary.json")
        aggregate(rp, sp, "run-1", {"kind": "openai_compat", "model_name": "m"}, [])
        with open(sp) as f:
            s = json.load(f)
        assert s["run_id"] == "run-1"
        assert s["n_items"] == 2
        assert s["n_unscored_no_judge"] == 0
        assert "common_law" in s["tracks"]

    def test_unscored_items_counted_separately(self, tmp_path):
        rows = [
            {"id": "a", "track": "common_law", "language": "en",
             "difficulty": "core", "score": 1.0},
            {"id": "b", "track": "common_law", "language": "en",
             "difficulty": "core", "score": None},
        ]
        rp = self._write_results(tmp_path, rows)
        sp = str(tmp_path / "summary.json")
        aggregate(rp, sp, "r", {}, [])
        with open(sp) as f:
            s = json.load(f)
        assert s["n_unscored_no_judge"] == 1
        assert s["tracks"]["common_law"]["n"] == 1  # only scored item counted

    def test_parity_computed_when_both_languages_present(self, tmp_path):
        rows = [
            {"id": "a", "track": "t1", "language": "en", "difficulty": "core", "score": 1.0},
            {"id": "b", "track": "t1", "language": "fr", "difficulty": "core", "score": 0.5},
        ]
        rp = self._write_results(tmp_path, rows)
        sp = str(tmp_path / "summary.json")
        aggregate(rp, sp, "r", {}, [])
        with open(sp) as f:
            s = json.load(f)
        assert "t1" in s["bilingual_parity"]
        bp = s["bilingual_parity"]["t1"]
        assert "parity_ratio" in bp

    def test_parity_absent_when_single_language(self, tmp_path):
        rows = [
            {"id": "a", "track": "t1", "language": "en", "difficulty": "core", "score": 1.0},
        ]
        rp = self._write_results(tmp_path, rows)
        sp = str(tmp_path / "summary.json")
        aggregate(rp, sp, "r", {}, [])
        with open(sp) as f:
            s = json.load(f)
        assert "t1" not in s["bilingual_parity"]

    def test_multiple_tracks(self, tmp_path):
        rows = [
            {"id": "a", "track": "common_law", "language": "en",
             "difficulty": "core", "score": 1.0},
            {"id": "b", "track": "privacy_compliance", "language": "en",
             "difficulty": "applied", "score": 0.5},
        ]
        rp = self._write_results(tmp_path, rows)
        sp = str(tmp_path / "summary.json")
        aggregate(rp, sp, "r", {}, [])
        with open(sp) as f:
            s = json.load(f)
        assert "common_law" in s["tracks"]
        assert "privacy_compliance" in s["tracks"]
