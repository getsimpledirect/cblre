"""Tests for harness/scorers.py.

Covers the citation_validity scorer and extract_citations helper:
- Statute chapter cites (RSC/SC)
- Quebec consolidated-law cites (CQLR)
- Prose CCQ article references
- needs_judge gate behaviour (confirmed hallucination stays 0; vague prose routes to judge)
- Existing reported-case format still works
"""
from __future__ import annotations

import pytest
from harness.scorers import extract_citations, citation_validity


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
