# CBLRE Scoring Methodology

> **Scoring protocol status: stable.** The harness-level scoring rules described here — scorers, rubrics, aggregation, and judge protocol — are fixed and will not change without a versioned update. What is still in progress is the *extended methodology*: SME inter-annotator agreement (Cohen's κ), judge-vs-human calibration figures, and corpus-overlap contamination analysis. These will be published alongside the first formal data release and do not affect the reproducibility of runs made against the current harness.

---

## §0. Pre-publication gate

The current validation set (~129 items) is undergoing expert review. Runs against the private item bank produce a `summary.json` that carries the following note until SME validation is complete:

```
"note": "Seed run. Items require SME validation before these numbers are publishable (see docs/methodology.md §0)."
```

Do not publish or cite numbers from seed runs as finalized benchmark results.

---

## §1. Per-track scoring overview

| Track | Primary scorer | Judge required? |
|---|---|---|
| `bilingual_parity` | `language_adherence` + track-specific scorer | No |
| `quebec_civil_law` | `rubric` (`qc-civil-liability-v1`) | Yes |
| `common_law` | `rubric` (`common-law-doctrine-v1`) | Yes |
| `constitutional_charter` | `rubric` (`charter-oakes-v1` / `charter-division-powers-v1`) | Yes |
| `privacy_compliance` | `keyword_coverage` (gate) + `rubric` | Yes |
| `citation_integrity` | `citation_validity` | Optional (CanLII verifier) |
| `safety_calibration` | `refusal` | Optional (quality annotation only) |
| `grounded_rag` | `rubric` (`rag-faithfulness-v1`) | Yes |
| `function_calling` | `tool_call` (partial) + judge | Yes (arg quality) |
| `capability_retention` | `keyword_coverage` (gate) + `rubric` | Yes |

All scoring code is in `harness/scorers.py` (programmatic) and `harness/judge.py` (LLM judge). No gold answers are embedded in these files.

---

## §2. Final-committed-answer extraction (MCQ)

Reasoning models frequently produce long chain-of-thought before committing to a final answer, then continue with caveats or restatements. Taking the first letter-match would mis-score many correct responses.

`scorers.mcq_exact` applies a four-stage cascade, taking the LAST commitment found:

1. **Bare response** — the entire response is a single letter, optionally wrapped in parens/period
2. **Last explicit commitment** — scan the full response for patterns like `"The answer is B"`, `"**C**"`, `"So, D"`, `"Choose E"`. The LAST match position wins.
3. **Final-line letter** — the last non-empty line of the response contains only a letter
4. **Content match** — match response text against option bodies; requires ≥3 content-word hits and a 2-word margin over the runner-up to avoid degenerate matches on short options
5. **Last letter fallback** — the last standalone A–E anywhere in the response

This cascade is applied identically to every model. The extraction path (`how`) is recorded in `programmatic.detail.extraction` for post-hoc inspection.

---

## §3. Citation validity

`scorers.citation_validity` detects hallucinated Canadian legal citations using three regex patterns:

- **Neutral citations**: `2001 SCC 79`, `2019 ONCA 123`
- **Reported citations**: `[1986] 1 SCR 103`, `1986, 1 S.C.R. 103`
- **CCQ articles**: `art. 1457 C.c.Q.`, `1457 CCQ`

Known-good citations from `item.scoring.valid_citations` are matched punctuation-insensitively (alphanumeric collapse). An optional `verifier` callable can check real existence via CanLII or another authority. Without a verifier, citation-shaped strings that do not match gold are flagged as `unverified_format_ok` and escalated to the judge.

---

## §4. Bilingual parity

The Track 1 headline metric is the **parity ratio**: FR accuracy ÷ EN accuracy, computed across matched `parity_group` item pairs. A ratio of 1.0 indicates no accuracy drop between languages. Ratios below ~0.90 indicate material bilingual performance degradation.

Parity is also computed for any other track with items in both languages.

---

## §5. LLM judge

Open-ended legal reasoning items (method `rubric`) and some programmatic tracks with quality escalation (tool-call argument quality, citation ambiguity) require an LLM judge.

### §5.1 Available rubrics

| Rubric ID | Used for |
|---|---|
| `common-law-doctrine-v1` | Tracks 3, 4 (common law reasoning) |
| `qc-civil-liability-v1` | Track 2 (Québec civil law) |
| `charter-oakes-v1` | Track 4 (section 1 Oakes analysis) |
| `charter-division-powers-v1` | Track 4 (division of powers) |
| `privacy-compliance-v1` | Track 5 (PIPEDA / Law 25) |
| `rag-faithfulness-v1` | Track 8 (grounded RAG faithfulness) |
| `instruction-following-v1` | Track 10 (capability retention) |

### §5.2 Judge design rules

- **Canonical judge**: the official primary judge is **Claude Sonnet 4.6** (`claude-sonnet-4-6`), accessed through the native Anthropic API (client kind `anthropic`, requires only `ANTHROPIC_API_KEY`) or equivalently through Google Vertex AI (client kind `vertex_anthropic`, same dateless ID) — the model is identical on both paths, so scores are comparable regardless of access route. `claude-sonnet-4-6` is a pinned snapshot, not an evergreen alias: from the Claude 4.6 generation onward, dateless model IDs are fixed releases, satisfying the fixed-judge-version rule below. Official scoring is anchored on this judge; self-evaluation during development may use any judge, but only canonical-judge scores are admissible for leaderboard comparison. The judge spec is recorded in `summary.json` (`judge_specs`), and the API-resolved judge model ID is recorded per vote (`judge_model`) in each item's judge result.
- **Blind grading**: the judge prompt never identifies which model produced the answer
- **Ensemble**: ≥2 judge clients of different lineage, anchored on the canonical judge; mean score is reported and spread > 1 point is flagged `divergent_flag_for_human` for manual review. For official scoring the full ensemble composition (every member's model + version) is fixed and recorded, exactly as for the primary judge.
- **Self-preference guard**: LLM judges measurably favour outputs from their own model family. When an evaluated model shares lineage with the canonical judge (i.e. any Claude model entered as a competitor), the different-lineage ensemble is mandatory rather than recommended, and published results for that model must disclose the judge-lineage overlap.
- **Anchored 0–4 scale**: explicit per-level descriptions in `judge.SCALE_ANCHORS`; rescaled to [0, 1] for aggregation
- **Fabrication cap**: a fabricated or misattributed citation flagged by any judge caps the item at 0 regardless of other quality
- **Fixed judge version**: the judge model + version must be recorded and held constant across a leaderboard refresh; changing the judge invalidates comparisons
- **Human calibration**: before publication, judge agreement must be validated against a human-scored calibration set; Cohen's κ (or weighted κ) reported alongside results

---

## §6. Scoring combination rules

| Method | Programmatic score | Judge role | Final score |
|---|---|---|---|
| `mcq_exact` | Exact match → 0 or 1 | Not used | Programmatic |
| `language_adherence` | Heuristic match → 0 or 1 | Not used | Programmatic |
| `citation_validity` | Gold match / hallucination | Escalated if ambiguous | Judge (if escalated) |
| `keyword_coverage` | Gate pass/fail | Sets quality score for open items | 0 if gate fails; otherwise judge |
| `rubric` | Not scored | Sets full score on 0–4 scale | Judge / 4 |
| `refusal` | Binary correct/incorrect | Quality annotation only | Programmatic |
| `tool_call` | 0.5 if correct tool name | Scores argument quality (other 0.5) | prog + 0.5 × judge |

---

## §7. Statistics

All reported numbers include:
- Item count (n) per track
- Mean accuracy (%)
- 95% bootstrap CI (10,000 resamples, percentile method, seed=0)
- Difficulty breakdown: `core` / `applied` / `expert`

For any "A is better than B" claim: two-sample bootstrap significance test (`stats.bootstrap_diff_test`). Differences inside overlapping CIs are reported as `"not_distinguishable"` — never as a directional ranking.

---

## §8. RAG random baseline

Track 8 (`grounded_rag`) items supply a context passage. The faithfulness scorer grades grounding quality, not independent factual accuracy. Results are reported alongside the random-baseline for closed-book MCQ (25% for 4-option, 20% for 5-option) so performance is not presented as impressive where it merely exceeds chance.

---

## §9. Leak-proofing

- Item bank is gated; only illustrative synthetic items are published in `data/sample/`
- Each item carries a `provenance.canary` field; canary strings are tracked to detect leakage via model outputs
- The held-out scoring split is never distributed to evaluators
- `run_eval.py` accepts items only via `--items` CLI arg; no items are embedded in the harness
- `.gitignore` blocks `*.jsonl` and all non-sample data paths
