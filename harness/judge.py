"""
CBLRE LLM-as-judge.

The judge scores open-ended legal reasoning on a documented, versioned rubric.
Design rules (see docs/methodology.md §5.2):
  - The rubric is explicit and anchored (0-4 with per-level descriptions).
  - The judge runs BLIND: it never learns which model produced the answer.
  - Use an ENSEMBLE of ≥2 judges of different lineage; report agreement.
  - Validate against a human-scored calibration set; report Cohen's / weighted κ.

This module provides the rubric text and a judge runner. The judge itself is just
another ModelClient (models.py), so you can point it at a strong model via the
OpenAI-compatible client. Keep the judge model FIXED across a leaderboard refresh
and record which model + version was the judge.
"""

from __future__ import annotations
import json
import re
from typing import Optional


# Anchored 0-4 scale reused by most rubrics; rescaled to 0-1 at aggregation.
SCALE_ANCHORS = """Score on a 0-4 scale:
4 = Fully correct. Doctrinally accurate, complete on the required points, correct
    terminology for the applicable legal tradition, no fabricated authorities.
3 = Substantially correct with a minor omission or imprecision that would not
    mislead a competent reader.
2 = Partially correct. Captures some required points but has a material gap, a
    wrong-tradition error, or imprecise terminology.
1 = Mostly incorrect. Major doctrinal error, wrong legal tradition applied, or
    misleading framing, with only incidental correct content.
0 = Incorrect, non-responsive, or contains a fabricated/misattributed authority.
A fabricated or misattributed case/statute citation caps the score at 0
regardless of other quality."""

RUBRICS = {
    "common-law-doctrine-v1": (
        "You are grading an answer about Canadian COMMON LAW doctrine. "
        "Check: correct elements/test, correct terminology, correct jurisdiction "
        "where relevant, and that any cited authority is real and correctly "
        "attributed. The common-law negligence test is duty / breach / causation "
        "(factual and legal) / damage.\n" + SCALE_ANCHORS),
    "qc-civil-liability-v1": (
        "You are grading an answer about QUEBEC CIVIL LAW. The civil-law tradition "
        "is distinct from common law. Extracontractual civil liability under art. "
        "1457 C.c.Q. has THREE elements: faute (fault), préjudice/dommage (injury), "
        "lien de causalité (causal link). Applying the common-law four-part "
        "negligence test, or using criminal-law terms like 'infraction' for civil "
        "fault, is a wrong-tradition error (cap at 2). Reward correct French legal "
        "terminology and correct CCQ article references.\n" + SCALE_ANCHORS),
    "charter-oakes-v1": (
        "You are grading a section 1 Charter justification analysis. The Oakes test "
        "(R v Oakes, [1986] 1 SCR 103) requires: (1) a pressing and substantial "
        "objective; (2) proportionality — rational connection, minimal impairment, "
        "and proportionality between effects and objective; limit prescribed by law. "
        "Score completeness of the test structure and accuracy.\n" + SCALE_ANCHORS),
    "charter-division-powers-v1": (
        "You are grading a division-of-powers answer. Look for pith-and-substance "
        "analysis (identify the law's dominant matter, assign to a s.91 federal or "
        "s.92 provincial head) and awareness of double aspect / paramountcy where "
        "relevant.\n" + SCALE_ANCHORS),
    "privacy-compliance-v1": (
        "You are grading a Canadian privacy/regulatory-compliance answer (PIPEDA, "
        "Quebec Law 25, provincial private-sector acts). Check correct statute "
        "identification, correct core obligations (e.g. consent under PIPEDA), and "
        "jurisdictional accuracy (PIPEDA vs provincial substantially-similar laws).\n"
        + SCALE_ANCHORS),
    "rag-faithfulness-v1": (
        "You are grading FAITHFULNESS to a supplied context. The answer must be "
        "grounded ONLY in the provided context. If the context does not contain the "
        "answer, the correct response says so. Inventing facts not in the context is "
        "an unfaithfulness failure (cap at 1). Do not reward outside knowledge that "
        "is not supported by the context.\n" + SCALE_ANCHORS),
    "instruction-following-v1": (
        "You are grading FORMAT COMPLIANCE with the instruction, not subject "
        "correctness. Check that every explicit constraint (count, list style, "
        "'no other text', language) is satisfied exactly. Any violated constraint "
        "lowers the score.\n" + SCALE_ANCHORS),
}


JUDGE_TEMPLATE = """You are a careful, impartial grader of answers to Canadian legal questions.
You are grading BLIND — you do not know which system produced the answer, and the
identity is irrelevant. Grade only against the rubric and the reference.

RUBRIC:
{rubric}

QUESTION (asked in language='{language}', jurisdiction='{jurisdiction}'):
{prompt}

REFERENCE / KEY POINTS (authoritative; the answer need not match wording, but must
be consistent with this):
{reference}

ANSWER TO GRADE:
\"\"\"
{answer}
\"\"\"

Return ONLY a JSON object, no other text:
{{"score": <integer 0-4>, "rationale": "<one or two sentences>", "fabricated_citation": <true|false>}}"""


def build_judge_prompt(item: dict, answer: str) -> str:
    rubric_id = item["scoring"].get("rubric_id")
    rubric = RUBRICS.get(rubric_id, SCALE_ANCHORS)
    return JUDGE_TEMPLATE.format(
        rubric=rubric,
        language=item.get("language", "en"),
        jurisdiction=item.get("jurisdiction", ""),
        prompt=item["prompt"],
        reference=item["scoring"].get("reference", "(no reference provided)"),
        answer=answer,
    )


def _parse_judge_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        o = json.loads(m.group(0))
        score = int(o.get("score"))
        if 0 <= score <= 4:
            return {"score": score,
                    "rationale": o.get("rationale", ""),
                    "fabricated_citation": bool(o.get("fabricated_citation", False))}
    except Exception:
        return None
    return None


def judge_item(item: dict, answer: str, judge_clients: list) -> dict:
    """
    Run an ensemble of judge clients (models.ModelClient) over one answer.
    Returns {"score01": float, "votes": [...], "agreement": "..."}.
    Score is the mean of judge scores, rescaled 0-4 -> 0-1. A fabricated-citation
    flag from any judge caps the item at 0 (matches the rubric anchor).
    """
    prompt = build_judge_prompt(item, answer)
    votes = []
    for jc in judge_clients:
        out = jc.generate(prompt, max_tokens=300, temperature=0.0)
        parsed = _parse_judge_json(out.text)
        if parsed:
            votes.append(parsed)
    if not votes:
        return {"score01": None, "votes": [], "agreement": "no_valid_votes"}
    if any(v["fabricated_citation"] for v in votes):
        return {"score01": 0.0, "votes": votes, "agreement": "fabrication_cap"}
    scores = [v["score"] for v in votes]
    mean = sum(scores) / len(scores)
    spread = max(scores) - min(scores)
    return {"score01": mean / 4.0, "votes": votes,
            "agreement": "tight" if spread <= 1 else "divergent_flag_for_human"}
