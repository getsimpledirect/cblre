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

**Install:**

```bash
# From PyPI-style git source (recommended):
pip install git+https://github.com/getsimpledirect/cblre.git

# Local development checkout:
git clone https://github.com/getsimpledirect/cblre.git && cd cblre
pip install -e .
```

If you are using the **Vertex AI judge path** (GCP ADC auth), add the `vertex` extra:

```bash
pip install "cblre[vertex] @ git+https://github.com/getsimpledirect/cblre.git"
# or, in a local checkout:
pip install -e ".[vertex]"
```

If you are using a **local HuggingFace checkpoint** as the model (`kind: hf_local`), add the `local` extra:

```bash
pip install "cblre[local] @ git+https://github.com/getsimpledirect/cblre.git"
# or, in a local checkout:
pip install -e ".[local]"
```

**Programmatic tracks only (no judge required):**

```bash
cblre-eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --run-id your-model-v1 \
  --out-dir ./results
```

**With an LLM judge for rubric/open items:**

```bash
cblre-eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --judge '{"kind":"openai_compat","model_name":"gpt-4o","base_url":"https://api.openai.com/v1","api_key_env":"OPENAI_API_KEY"}' \
  --run-id your-model-v1 \
  --out-dir ./results
```

**With the canonical judge (Claude Sonnet 4.6 — recommended):**

```bash
export ANTHROPIC_API_KEY=sk-ant-...

cblre-eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --judge '{"kind":"anthropic","model_name":"claude-sonnet-4-6","api_key_env":"ANTHROPIC_API_KEY"}' \
  --run-id your-model-v1 \
  --out-dir ./results
```

Teams already on GCP can reach the same judge model through Vertex AI instead — scores remain comparable because the model is identical:

```bash
  --judge '{"kind":"vertex_anthropic","model_name":"claude-sonnet-4-6","region":"us-east5","project":"your-gcp-project"}'
```

**Supported `--model` / `--judge` client kinds:**

| `kind` | When to use |
|---|---|
| `openai_compat` | Any `/v1/chat/completions` server (vLLM, Together, OpenAI, Groq, etc.) |
| `hf_local` | Local HuggingFace checkpoint (requires the `[local]` extra) |
| `anthropic` | Claude via native Anthropic API — canonical judge; set `ANTHROPIC_API_KEY` |
| `vertex_anthropic` | Same Claude models via Google Vertex AI — for teams on GCP (ADC auth) |

Run `cblre-eval --help` (or `python -m harness.run_eval --help`) for all CLI options.

---

## Reasoning / thinking models

Models that emit chain-of-thought before their final answer fall into two categories. Handle each differently.

### Qwen3 family — toggleable thinking (recommended: disable for eval)

Qwen3 models served via vLLM default to thinking mode on. When active, the model routes its answer through a `reasoning_content` field and leaves `message.content` null — the harness would score an empty answer for every item.

Fix: add `"chat_template_kwargs": {"enable_thinking": false}` to your `--model` spec:

```bash
cblre-eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"Qwen/Qwen3.5-9B",
            "base_url":"http://localhost:8000/v1",
            "chat_template_kwargs":{"enable_thinking":false}}' \
  --run-id qwen35-9b \
  --out-dir ./results
```

`chat_template_kwargs` is injected at the top level of the raw request body — this is the correct placement for vLLM's API when using direct HTTP requests (not the OpenAI Python SDK's `extra_body`).

### DeepSeek-R1 / QwQ — always-on reasoning (no toggle)

These models always produce a reasoning trace before the final answer; the `enable_thinking` kwarg has no effect. The harness handles them correctly without any spec change:

- `mcq_exact` uses a **final-committed-answer** strategy — it scans for the last commitment pattern in the full response, so chain-of-thought output scores correctly.
- Rubric-scored items: the judge evaluates `message.content` only; ensure your vLLM `--reasoning-parser` is configured to populate `message.content` with the final answer (not only `reasoning_content`).

```bash
cblre-eval \
  --items your_items.jsonl \
  --model '{"kind":"openai_compat","model_name":"deepseek-ai/DeepSeek-R1",
            "base_url":"http://localhost:8000/v1"}' \
  --run-id r1-baseline \
  --out-dir ./results
```

### Standard / non-thinking models

Leave `chat_template_kwargs` unset (the default is `null`). Do not set it for hosted APIs (OpenAI, Together, Groq, Fireworks, OpenRouter) — it is a vLLM-specific field and strict endpoints will reject unknown body fields.

### How the harness warns you

If `message.content` is null but a reasoning field is present, the harness prints a warning to stderr for every affected item:

```
[cblre] WARNING: message.content is null/empty but 'reasoning_content' is present.
  Qwen3 family: add "chat_template_kwargs": {"enable_thinking": false} to your --model spec.
  DeepSeek-R1 / QwQ: check that vLLM's --reasoning-parser is routing the final answer into message.content.
  Scoring this item as empty answer.
```

If you see this in a run, fix the spec or serving config and re-run — resumable eval means only unscored items are retried.

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

**To request access:** open an [Evaluation Set Access Request](https://github.com/getsimpledirect/cblre/issues/new?template=access-request.yml) on this repository's issue tracker.

See [docs/data_access.md](docs/data_access.md) for the full access and official scoring protocol.

---

## Vendor neutrality

CBLRE is a vendor-neutral instrument designed to evaluate any instruction-following LLM regardless of provider or architecture. SimpleDirect® publishes the [flash-1-mini](https://huggingface.co/simpledirect/flash-1-mini) model; CBLRE is not designed to favour it or any other specific model. The scoring harness applies identical prompts and decoding conditions to every evaluated model.

The canonical LLM judge (Claude Sonnet 4.6) shares no lineage with flash-1-mini, which is a Qwen fine-tune — so the benchmark author's own model receives no self-preference advantage from the judge. When Claude-family models are evaluated as competitors, a judge ensemble including a non-Claude judge is required to control for self-preference bias (see [docs/methodology.md](docs/methodology.md) §5.2).

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
