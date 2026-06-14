# Quickstart — run your first CBLRE evaluation in 5 minutes

This guide walks through installing the harness, running it against the synthetic sample items with a local or hosted model, and reading the output. No item bank access is required.

---

## 1. Install

```bash
pip install git+https://github.com/getsimpledirect/cblre.git
```

If you are using the **Vertex AI judge path** (GCP ADC auth):

```bash
pip install "cblre[vertex] @ git+https://github.com/getsimpledirect/cblre.git"
```

If you are evaluating a **local HuggingFace checkpoint**:

```bash
pip install "cblre[local] @ git+https://github.com/getsimpledirect/cblre.git"
```

Verify the install:

```bash
cblre-eval --help
```

---

## 2. Get the sample items

Clone the repository to access the synthetic sample items (these are not part of the scoring set):

```bash
git clone https://github.com/getsimpledirect/cblre.git
cd cblre
```

The sample items live at `data/sample/sample.jsonl`. Copy it to a working path:

```bash
cp data/sample/sample.jsonl /tmp/sample.jsonl
```

If you have written your own items as individual `.json` files, combine them into a JSONL first:

```bash
for f in your_items/*.json; do cat "$f"; echo; done > /tmp/sample.jsonl
```

---

## 3. Run evaluation — programmatic tracks only (no judge needed)

Point the harness at any OpenAI-compatible endpoint:

```bash
cblre-eval \
  --items /tmp/sample.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --run-id quickstart-test \
  --out-dir ./results
```

For a **hosted model** (e.g. GPT-4o via OpenAI):

```bash
export OPENAI_API_KEY=sk-...

cblre-eval \
  --items /tmp/sample.jsonl \
  --model '{"kind":"openai_compat","model_name":"gpt-4o","base_url":"https://api.openai.com/v1","api_key_env":"OPENAI_API_KEY"}' \
  --run-id gpt4o-quickstart \
  --out-dir ./results
```

---

## 4. Add the canonical judge for rubric-scored items

Open-ended (`format: open`) items require an LLM judge. The canonical judge is Claude Sonnet 4.6:

```bash
export ANTHROPIC_API_KEY=sk-ant-...

cblre-eval \
  --items /tmp/sample.jsonl \
  --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
  --judge '{"kind":"anthropic","model_name":"claude-sonnet-4-6","api_key_env":"ANTHROPIC_API_KEY"}' \
  --run-id quickstart-with-judge \
  --out-dir ./results
```

---

## 5. Reasoning / thinking models

**Qwen3 family** served via vLLM — disable thinking mode so `message.content` is populated:

```bash
--model '{"kind":"openai_compat","model_name":"Qwen/Qwen3.5-9B",
          "base_url":"http://localhost:8000/v1",
          "chat_template_kwargs":{"enable_thinking":false}}'
```

**DeepSeek-R1 / QwQ** — no spec change needed; `mcq_exact` handles chain-of-thought via its final-committed-answer strategy. Ensure vLLM's `--reasoning-parser` routes the final answer into `message.content`.

**Standard / hosted models** (GPT-4o, Llama, Mistral, etc.) — leave `chat_template_kwargs` unset.

---

## 6. Read the results

Results are written to `./results/<run-id>/`:

```
results/quickstart-test/
  items.jsonl    # one row per item: response, latency, scores
  summary.json   # per-track means with 95% bootstrap CIs
```

Inspect the summary:

```bash
python -c "import json; s=json.load(open('results/quickstart-test/summary.json')); print(json.dumps(s['tracks'], indent=2))"
```

The run is **resumable**: if it is interrupted, re-running the same command skips already-scored items and continues from where it left off.

---

## 7. Bring your own items

Items must conform to [`schema/eval_item.schema.json`](../schema/eval_item.schema.json). See [`data/sample/README.md`](../data/sample/README.md) for the format and a validation snippet. The [Evaluation Set Access Request](https://github.com/getsimpledirect/cblre/issues/new?template=access-request.yml) issue template explains how to request the full gated item bank.

---

## Next steps

- [README.md](../README.md) — full track and scorer reference
- [docs/methodology.md](methodology.md) — scoring protocol and design decisions
- [CONTRIBUTING.md](../CONTRIBUTING.md) — how to contribute and commit conventions
