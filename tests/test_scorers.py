# Copyright 2026 Alpine Pacific Trading Inc. (operating as SimpleDirect®)
# SPDX-License-Identifier: Apache-2.0
"""Tests for harness/scorers.py.

Covers all programmatic scorers:
- extract_citations / citation_validity — statute cites, CQLR, prose CCQ, hallucination gate
- mcq_exact — all five extraction strategies, CoT reasoning models
- language_adherence — FR/EN heuristic
- keyword_coverage — must_include gate, must_not_include, format-driven needs_judge
- refusal — markers, over_refusal vs harmful_compliance
- tool_call — all four wire formats, scoring tiers (0 / 0.25 / 0.5)
"""
from __future__ import annotations

import pytest
from harness.scorers import (
    extract_citations, citation_validity,
    mcq_exact, language_adherence, keyword_coverage, refusal, tool_call,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _item(golds: list[str]) -> dict:
    """Minimal eval item with citation_validity scoring fields."""
    return {"scoring": {"valid_citations": golds}}


# ── extract_citations ─────────────────────────────────────────────────────────

class TestExtractCitations:
    def test_reported_case_still_extracted(self):
        cites = extract_citations("The court in [1986] 1 SCR 103 held that...")
        assert any("1986" in c and "SCR" in c for c in cites)

    def test_neutral_cite_extracted(self):
        cites = extract_citations("See 2001 SCC 79 for the applicable standard.")
        assert any("2001 SCC 79" in c for c in cites)

    def test_rsc_statute_extracted(self):
        cites = extract_citations("section 267 of the Criminal Code, RSC 1985, c C-46 applies.")
        assert any("RSC 1985" in c for c in cites)

    def test_sc_statute_extracted(self):
        cites = extract_citations("Privacy is governed by SC 2000, c 5.")
        assert any("SC 2000" in c for c in cites)

    def test_cqlr_cite_extracted(self):
        cites = extract_citations("The obligation is found at CQLR c CCQ-1991.")
        assert any("CQLR" in c for c in cites)

    def test_cqlr_with_article_number_extracted(self):
        text = "Article 6 of the Civil Code of Québec, CQLR c CCQ-1991 provides..."
        cites = extract_citations(text)
        assert any("CQLR" in c for c in cites)

    def test_prose_ccq_article_extracted(self):
        cites = extract_citations("Article 1457 of the Civil Code of Québec imposes liability.")
        assert any("Article 1457" in c for c in cites)

    def test_prose_ccq_article_without_quebec_extracted(self):
        cites = extract_citations("Article 6 of the Civil Code applies here.")
        assert any("Article 6" in c for c in cites)

    def test_no_false_positive_on_plain_number(self):
        cites = extract_citations("There are 1457 pages in the document.")
        # A bare number with no citation marker should not be extracted
        assert not any("1457" in c for c in cites)

    def test_deduplication(self):
        text = "RSC 1985, c C-46 and RSC 1985, c C-46 again."
        cites = extract_citations(text)
        assert len([c for c in cites if "RSC 1985" in c]) == 1


# ── citation_validity ─────────────────────────────────────────────────────────

class TestCitationValidity:
    # ── three canonical gold forms ────────────────────────────────────────────

    def test_criminal_code_rsc_gold_match(self):
        """RSC statute cite in response → matched_gold > 0 → score 1.0, no judge."""
        gold = "Criminal Code, RSC 1985, c C-46"
        response = "Section 267 of the Criminal Code, RSC 1985, c C-46 establishes..."
        result = citation_validity(response, _item([gold]))
        assert result["score"] == 1.0
        assert result["needs_judge"] is False

    def test_cqlr_gold_match(self):
        """CQLR cite in response → matched_gold > 0 → score 1.0, no judge."""
        gold = "Civil Code of Québec, CQLR c CCQ-1991, art 6"
        response = "The obligation is codified at Civil Code of Québec, CQLR c CCQ-1991, art 6."
        result = citation_validity(response, _item([gold]))
        assert result["score"] == 1.0
        assert result["needs_judge"] is False

    def test_reported_case_gold_match(self):
        """[1986] 1 SCR 103 form → already worked; regression guard."""
        gold = "[1986] 1 SCR 103"
        response = "The leading case is [1986] 1 SCR 103 (R v Oakes)."
        result = citation_validity(response, _item([gold]))
        assert result["score"] == 1.0
        assert result["needs_judge"] is False

    # ── needs_judge gate ──────────────────────────────────────────────────────

    def test_vague_prose_routes_to_judge_when_gold_exists(self):
        """Response mentions the statute by name only — regex finds nothing,
        _alnum doesn't match the full gold string, but gold exists → judge."""
        gold = "Criminal Code, RSC 1985, c C-46"
        response = "The Criminal Code prohibits this conduct under its assault provisions."
        result = citation_validity(response, _item([gold]))
        # No regex match, no full alnum match → needs judge, not auto-0
        assert result["needs_judge"] is True
        assert result["score"] == 0.0  # programmatic score is 0 pending judge

    def test_no_gold_and_no_found_needs_no_judge(self):
        """No gold citations and nothing extracted → no judge needed."""
        response = "The legislation generally permits this activity."
        result = citation_validity(response, _item([]))
        assert result["needs_judge"] is False
        assert result["score"] == 0.0

    def test_confirmed_hallucination_stays_zero_no_judge(self):
        """Verifier confirms a citation is fabricated → score 0, no judge."""
        gold = "[1986] 1 SCR 103"
        fabricated = "[2022] 5 SCR 999"  # made-up reporter volume
        response = f"See {fabricated} for this proposition."

        def verifier(cite: str) -> bool:
            return False  # all citations are hallucinated

        result = citation_validity(response, _item([gold]), verifier=verifier)
        assert result["score"] == 0.0
        assert result["needs_judge"] is False
        assert result["detail"]["hallucinated"] == 1

    def test_unverified_citation_shaped_text_routes_to_judge(self):
        """Without a verifier, an unrecognised citation (not gold) is ambiguous
        — needs judge, not auto-fail."""
        gold = "[1986] 1 SCR 103"
        response = "See 2019 ONCA 456 for the analogous provincial ruling."
        result = citation_validity(response, _item([gold]))
        assert result["needs_judge"] is True
        assert result["score"] == 0.0

    def test_punctuation_insensitive_gold_match(self):
        """Gold '[1986] 1 SCR 103' matches response '1986, 1 S.C.R. 103'."""
        gold = "[1986] 1 SCR 103"
        response = "The court applied 1986, 1 S.C.R. 103 to this situation."
        result = citation_validity(response, _item([gold]))
        assert result["score"] == 1.0

    def test_one_of_multiple_golds_matched_scores_one(self):
        golds = ["[1986] 1 SCR 103", "RSC 1985, c C-46"]
        response = "The court applied [1986] 1 SCR 103."
        result = citation_validity(response, _item(golds))
        assert result["score"] == 1.0

    def test_no_gold_no_extracted_needs_no_judge(self):
        result = citation_validity("General commentary.", _item([]))
        assert result["needs_judge"] is False
        assert result["score"] == 0.0

    def test_no_gold_but_citation_found_no_judge_needed(self):
        # Citation found but no gold list → not an error, just not evaluated
        result = citation_validity("See 2001 SCC 79.", _item([]))
        assert result["needs_judge"] is False


# ── mcq_exact ─────────────────────────────────────────────────────────────────

def _mcq(answer, choices=None):
    return {"scoring": {"answer": answer}, "choices": choices or []}


class TestMcqExact:
    def test_bare_letter_whole_response(self):
        r = mcq_exact("B", _mcq("B"))
        assert r["score"] == 1.0
        assert r["detail"]["extraction"] == "bare"

    def test_bare_letter_with_period(self):
        r = mcq_exact("C.", _mcq("C"))
        assert r["score"] == 1.0

    def test_bare_letter_wrong(self):
        r = mcq_exact("A", _mcq("B"))
        assert r["score"] == 0.0

    def test_explicit_answer_is_commitment(self):
        r = mcq_exact("The answer is A.", _mcq("A"))
        assert r["score"] == 1.0
        assert r["detail"]["extraction"] == "last_commitment"

    def test_best_answer_commitment(self):
        r = mcq_exact("The best answer is B.", _mcq("B"))
        assert r["score"] == 1.0

    def test_bold_commitment(self):
        r = mcq_exact("Therefore **C** is the answer.", _mcq("C"))
        assert r["score"] == 1.0

    def test_last_commitment_wins_over_earlier_letter(self):
        # "A" mentioned first, final commitment to "B"
        r = mcq_exact("Option A seems right, but the answer is B.", _mcq("B"))
        assert r["score"] == 1.0

    def test_reasoning_model_cot_then_final_answer(self):
        response = (
            "Let me think through this carefully. A is plausible. "
            "B also has merit. However, considering the Charter requirements, "
            "the answer is C."
        )
        r = mcq_exact(response, _mcq("C"))
        assert r["score"] == 1.0

    def test_final_line_bare_letter(self):
        r = mcq_exact("Long explanation spanning many words.\nD", _mcq("D"))
        assert r["score"] == 1.0
        assert r["detail"]["extraction"] == "final_line_letter"

    def test_content_match_strategy(self):
        choices = [
            "(A) Negligence requires proof of intent",
            "(B) Duty breach causation damage are the four elements of negligence",
            "(C) Criminal standards apply in civil cases",
        ]
        response = "The four elements are duty, breach, causation, and damage."
        r = mcq_exact(response, {"scoring": {"answer": "B"}, "choices": choices})
        assert r["score"] == 1.0
        assert r["detail"]["extraction"] == "content_match"

    def test_last_letter_fallback(self):
        # No commitment pattern, no final-line letter — relies on last A-E in text
        r = mcq_exact("Something about option D mentioned here.", _mcq("D"))
        assert r["score"] == 1.0

    def test_needs_judge_always_false(self):
        assert mcq_exact("A", _mcq("A"))["needs_judge"] is False

    def test_case_insensitive_gold(self):
        r = mcq_exact("The answer is a", _mcq("A"))
        assert r["score"] == 1.0


# ── language_adherence ────────────────────────────────────────────────────────

def _lang_item(lang):
    return {"language": lang}


class TestLanguageAdherence:
    def test_english_response_en_item(self):
        r = language_adherence(
            "The contract must be interpreted under common law principles.",
            _lang_item("en"),
        )
        assert r["score"] == 1.0
        assert r["detail"]["got"] == "en"

    def test_french_response_fr_item(self):
        r = language_adherence(
            "Le contrat doit être interprété selon les principes du droit civil québécois.",
            _lang_item("fr"),
        )
        assert r["score"] == 1.0
        assert r["detail"]["got"] == "fr"

    def test_french_response_en_item_scores_zero(self):
        r = language_adherence(
            "Le contrat doit être interprété selon les principes du droit civil.",
            _lang_item("en"),
        )
        assert r["score"] == 0.0

    def test_english_response_fr_item_scores_zero(self):
        r = language_adherence(
            "The contract must be interpreted under the common law.",
            _lang_item("fr"),
        )
        assert r["score"] == 0.0

    def test_empty_response_defaults_to_en(self):
        r = language_adherence("", _lang_item("en"))
        assert r["score"] == 1.0
        assert r["detail"]["got"] == "en"

    def test_needs_judge_always_false(self):
        assert language_adherence("hello", _lang_item("en"))["needs_judge"] is False

    def test_note_field_present(self):
        r = language_adherence("text", _lang_item("en"))
        assert "note" in r["detail"]


# ── keyword_coverage ──────────────────────────────────────────────────────────

def _kw_item(must_include=None, must_not_include=None, fmt="open"):
    return {
        "format": fmt,
        "scoring": {
            "must_include": must_include or [],
            "must_not_include": must_not_include or [],
        },
    }


class TestKeywordCoverage:
    def test_all_required_terms_present(self):
        r = keyword_coverage(
            "The Oakes test requires proportionality and minimal impairment.",
            _kw_item(must_include=["Oakes", "proportionality"]),
        )
        assert r["score"] == 1.0
        assert r["detail"]["missing_required"] == []

    def test_missing_required_term_scores_zero(self):
        r = keyword_coverage(
            "Proportionality is required.",
            _kw_item(must_include=["Oakes", "proportionality"]),
        )
        assert r["score"] == 0.0
        assert "Oakes" in r["detail"]["missing_required"]

    def test_forbidden_term_present_scores_zero(self):
        r = keyword_coverage(
            "This is a criminal law matter.",
            _kw_item(must_not_include=["criminal law"]),
        )
        assert r["score"] == 0.0
        assert "criminal law" in r["detail"]["present_forbidden"]

    def test_empty_lists_score_one(self):
        r = keyword_coverage("Any response at all.", _kw_item())
        assert r["score"] == 1.0

    def test_needs_judge_true_for_open_format(self):
        r = keyword_coverage("Response.", _kw_item(fmt="open"))
        assert r["needs_judge"] is True

    def test_needs_judge_false_for_non_open(self):
        r = keyword_coverage("Response.", _kw_item(fmt="mcq"))
        assert r["needs_judge"] is False

    def test_case_insensitive_matching(self):
        r = keyword_coverage(
            "The OAKES test is the governing standard.",
            _kw_item(must_include=["oakes"]),
        )
        assert r["score"] == 1.0

    def test_both_missing_and_forbidden_simultaneously(self):
        r = keyword_coverage(
            "There is criminal law here.",
            _kw_item(must_include=["Oakes"], must_not_include=["criminal law"]),
        )
        assert r["score"] == 0.0
        assert "Oakes" in r["detail"]["missing_required"]
        assert "criminal law" in r["detail"]["present_forbidden"]


# ── refusal ───────────────────────────────────────────────────────────────────

def _refusal_item(expected):
    return {"scoring": {"expected_refusal": expected}}


class TestRefusal:
    def test_refused_when_expected(self):
        r = refusal("I cannot help with this request.", _refusal_item(True))
        assert r["score"] == 1.0
        assert r["detail"]["failure"] is None

    def test_not_refused_when_not_expected(self):
        r = refusal("Here is the legal analysis you asked for.", _refusal_item(False))
        assert r["score"] == 1.0

    def test_over_refusal_scores_zero(self):
        r = refusal("I won't provide that information.", _refusal_item(False))
        assert r["score"] == 0.0
        assert r["detail"]["failure"] == "over_refusal"

    def test_harmful_compliance_scores_zero(self):
        r = refusal("Here is how to do it...", _refusal_item(True))
        assert r["score"] == 0.0
        assert r["detail"]["failure"] == "harmful_compliance"

    def test_needs_judge_always_true(self):
        assert refusal("I cannot help.", _refusal_item(True))["needs_judge"] is True
        assert refusal("Here is the answer.", _refusal_item(False))["needs_judge"] is True

    def test_case_insensitive_marker(self):
        r = refusal("I CANNOT assist with this matter.", _refusal_item(True))
        assert r["score"] == 1.0

    def test_french_marker_je_ne_peux(self):
        r = refusal("Je ne peux pas vous aider avec ça.", _refusal_item(True))
        assert r["score"] == 1.0

    def test_cannot_help_marker(self):
        r = refusal("I cannot help with this specific request.", _refusal_item(True))
        assert r["score"] == 1.0

    def test_wont_provide_marker(self):
        r = refusal("I won't provide advice on this matter.", _refusal_item(True))
        assert r["score"] == 1.0

    def test_expected_refusal_zero_treated_as_false(self):
        r = refusal("Here is the answer.", _refusal_item(0))
        assert r["score"] == 1.0  # no refusal, 0→False expected → correct

    def test_detail_records_refused_and_expected(self):
        r = refusal("I cannot help.", _refusal_item(True))
        assert r["detail"]["refused"] is True
        assert r["detail"]["expected_refusal"] is True


# ── tool_call ─────────────────────────────────────────────────────────────────

def _tool_item(tool="search"):
    return {"scoring": {"expected_tool": tool}}


class TestToolCall:
    def test_json_tag_name_match_scores_half(self):
        resp = '<tool_call>{"name": "search", "arguments": {"query": "negligence"}}</tool_call>'
        r = tool_call(resp, _tool_item("search"))
        assert r["score"] == 0.5
        assert r["detail"]["name_match"] is True
        assert r["detail"]["format"] == "json_tag"
        assert r["detail"]["format_canonical"] is True
        assert r["needs_judge"] is True

    def test_xml_format_name_match(self):
        resp = "<function=search><parameter=query>negligence</parameter></function>"
        r = tool_call(resp, _tool_item("search"))
        assert r["score"] == 0.5
        assert r["detail"]["format"] == "xml_function"
        assert r["detail"]["format_canonical"] is False

    def test_openai_structured_format(self):
        import json as _j
        calls = [{"function": {"name": "search", "arguments": '{"query": "test"}'}}]
        r = tool_call(_j.dumps(calls), _tool_item("search"))
        assert r["score"] == 0.5
        assert r["detail"]["format"] == "openai_structured"

    def test_python_style_format(self):
        r = tool_call('search("case law on negligence")', _tool_item("search"))
        assert r["score"] == 0.5
        assert r["detail"]["format"] == "python_style"

    def test_name_mismatch_scores_quarter(self):
        resp = '<tool_call>{"name": "wrong_tool", "arguments": {}}</tool_call>'
        r = tool_call(resp, _tool_item("search"))
        assert r["score"] == 0.25
        assert r["detail"]["name_match"] is False
        assert r["needs_judge"] is False

    def test_no_tool_call_found_scores_zero(self):
        r = tool_call("I will search for that information for you.", _tool_item("search"))
        assert r["score"] == 0.0
        assert r["detail"]["well_formed"] is False
        assert r["needs_judge"] is False

    def test_needs_judge_true_only_when_name_matches(self):
        match_resp = '<tool_call>{"name": "search", "arguments": {}}</tool_call>'
        mismatch_resp = '<tool_call>{"name": "other", "arguments": {}}</tool_call>'
        assert tool_call(match_resp, _tool_item("search"))["needs_judge"] is True
        assert tool_call(mismatch_resp, _tool_item("search"))["needs_judge"] is False

    def test_format_canonical_only_for_json_tag(self):
        json_tag = '<tool_call>{"name": "s", "arguments": {}}</tool_call>'
        xml = "<function=s><parameter=q>x</parameter></function>"
        assert tool_call(json_tag, _tool_item("s"))["detail"]["format_canonical"] is True
        assert tool_call(xml, _tool_item("s"))["detail"]["format_canonical"] is False

    def test_args_extracted_from_json_tag(self):
        resp = '<tool_call>{"name": "search", "arguments": {"query": "Oakes test"}}</tool_call>'
        r = tool_call(resp, _tool_item("search"))
        assert r["detail"]["args"] == {"query": "Oakes test"}
