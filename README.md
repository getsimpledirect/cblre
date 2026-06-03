# CBLRE — Canadian Bilingual Legal & Regulatory Evaluation

**Status: In active development.** The scoring harness and item schema are published here. The item bank is gated — see [Requesting the evaluation set](#requesting-the-evaluation-set).

CBLRE is a benchmark for evaluating large language models on Canadian legal and regulatory tasks, in both official languages. It is developed and maintained by **Alpine Pacific Trading Inc. (operating as SimpleDirect®)**.

---

## Why public harness, gated items?

The item bank, gold answers, and held-out scoring split are not published here. Evaluators can inspect the full scoring logic, run the harness against their own items, and understand the methodology — while the private split prevents models from being trained on test content before evaluation. This is the standard contamination-resistance design used by credible benchmarks.

---

## Tracks

| # | Track | What it measures |
|---|---|---|
| 1 | `bilingual_parity` | Accuracy drop between matched EN and FR items |
| 2 | `quebec_civil_law` | Québec civil law doctrine (C.c.Q., extracontractual liability) |
| 3 | `common_law` | Canadian common law doctrine (negligence, contract) |
| 4 | `constitutional_charter` | Charter rights, Oakes test, division of powers |
| 5 | `privacy_compliance` | PIPEDA, Québec Law 25, provincial privacy statutes |
| 6 | `citation_integrity` | Legal citation hallucination detection |
| 7 | `safety_calibration` | Appropriate refusal vs. compliance |
| 8 | `grounded_rag` | Answer faithfulness to supplied legal context |
| 9 | `function_calling` | Structured tool use for legal search tasks |
| 10 | `capability_retention` | Instruction-following under legal framing |

---

## Scoring methods

| Method | Used by | Programmatic? |
|---|---|---|
| `mcq_exact` | Multiple-choice items | Yes — final-committed-answer extraction |
| `language_adherence` | Bilingual parity track | Yes — heuristic, fastText recommended for release |
| `citation_validity` | Citation integrity track | Yes — optional CanLII verifier |
| `keyword_coverage` | Compliance tracks (gate) | Yes — gate only; judge sets quality score |
| `rubric` | Open legal reasoning | No — requires an LLM judge |
| `refusal` | Safety calibration | Yes — binary correctness |
| `tool_call` | Function calling | Partial — judge scores argument quality |

`mcq_exact` implements a **final-committed-answer** strategy: for reasoning models that produce chain-of-thought before committing, it scans for the LAST commitment pattern rather than the first letter. See [docs/methodology.md](docs/methodology.md) for detail.

---

## Running the harness on your own items

You supply a JSONL file where each line is an item conforming to [`schema/eval_item.schema.json`](schema/eval_item.schema.json). The harness calls your model, scores each item, and writes a per-item JSONL and a `summary.json`.

```bash
pip install -r requirements.txt
```

**Programmatic tracks only (no judge required):**

```bash
python -m harness.run_eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --run-id your-model-v1 \
  --out-dir ./results
```

**With an LLM judge for rubric/open items:**

```bash
python -m harness.run_eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --judge '{"kind":"openai_compat","model_name":"gpt-4o","base_url":"https://api.openai.com/v1","api_key_env":"OPENAI_API_KEY"}' \
  --run-id your-model-v1 \
  --out-dir ./results
```

**With a Vertex AI Claude judge (recommended):**

```bash
python -m harness.run_eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --judge '{"kind":"vertex_anthropic","model_name":"claude-sonnet-4-6@YYYYMMDD","region":"us-east5","project":"your-gcp-project"}' \
  --run-id your-model-v1 \
  --out-dir ./results
```

**Supported `--model` / `--judge` client kinds:**

| `kind` | When to use |
|---|---|
| `openai_compat` | Any `/v1/chat/completions` server (vLLM, Together, OpenAI, Groq, etc.) |
| `hf_local` | Local HuggingFace checkpoint (requires `torch`, `transformers`) |
| `vertex_anthropic` | Claude on Google Vertex AI — recommended judge |

Run `python -m harness.run_eval --help` for all CLI options.

---

## Output format

Results are written to `--out-dir/<run-id>/`:

- `items.jsonl` — one row per item: response, latency, programmatic score, judge score, final score
- `summary.json` — per-track means with 95% bootstrap CIs, bilingual parity ratios, difficulty breakdowns

Results from seed runs carry the note: *"Items require SME validation before these numbers are publishable."* Do not cite seed-run numbers as finalized benchmark results.

---

## Synthetic sample

`data/sample/` contains a small set of illustrative synthetic items demonstrating the item format. These are **not part of the scoring set** and have no bearing on model evaluation. See [data/sample/README.md](data/sample/README.md).

---

## Requesting the evaluation set

The full item bank (~129 expert-reviewed items in the current validation set; SME validation ongoing) is available to qualified evaluators on request. Official scoring against the held-out split is coordinated with SimpleDirect® to prevent contamination.

**To request access:** *[contact form / email placeholder — fill before publishing]*

See [docs/data_access.md](docs/data_access.md) for the full access and official scoring protocol.

---

## Vendor neutrality

CBLRE is a vendor-neutral instrument designed to evaluate any instruction-following LLM regardless of provider or architecture. SimpleDirect® publishes the [flash-1-mini](https://huggingface.co/simpledirect/flash-1-mini) model; CBLRE is not designed to favour it or any other specific model. The scoring harness applies identical prompts and decoding conditions to every evaluated model.

---

## Limitations & current status

CBLRE is at an early development stage. We state its current limitations plainly so that no result is over-interpreted:

- **Sample size.** The current validation set is ~129 items across 10 tracks (~13 per track). Per-track confidence intervals are correspondingly wide, and most per-track differences between models will not be statistically distinguishable at this size. Track-level numbers should be read as directional, not definitive.
- **Validity evidence is in progress.** SME (subject-matter expert) validation is ongoing. Inter-annotator agreement (Cohen's / weighted κ) and judge-vs-human calibration are planned but not yet published. No baseline model leaderboard is published; the instrument's discrimination has not yet been demonstrated empirically.
- **Two scorers are not yet release-grade.** `language_adherence` uses a lightweight heuristic (fastText `lid.176` is the intended replacement), and `citation_validity` cannot confirm hallucinated citations without an external verifier (e.g. a CanLII lookup) wired in; without one it flags citation-shaped text for review rather than confirming.
- **Contamination defense.** Items carry canary strings for leak detection, but corpus-overlap analysis (n-gram / embedding) against training data is not yet part of the protocol.
- **Single-entity authorship.** CBLRE is built by the entity that also ships a model. We mitigate this with vendor-neutral conditions, a third-party judge model, gated items, and by not publishing self-run leaderboards — but independent governance is the stronger long-term fix, and external SME authorship is a goal.

### Roadmap

Active development is focused on:

- **Expanding the item bank** — substantially increasing the number of expert-reviewed items per track to narrow confidence intervals and support stable per-track comparisons.
- **Broadening domain coverage** — adding further Canadian legal and regulatory domains beyond the current 10 tracks.
- Publishing SME inter-annotator agreement (κ) and judge-vs-human calibration figures.
- Upgrading `language_adherence` to a published language-ID model and integrating a citation verifier.
- Independent, third-party-run baselines before any comparative claim is published.

Until these are in place, CBLRE should be described as a development-stage instrument, not a finalized standard.

---

## License

**Code** (this repository): Apache License 2.0. See [LICENSE](LICENSE).

**Evaluation data** (item bank, gold answers): separately licensed and gated. See [DATA_LICENSE.md](DATA_LICENSE.md).

---

## Citation

*Citation entry will be added once a technical report is published.*
