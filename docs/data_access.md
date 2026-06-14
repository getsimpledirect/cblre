# Requesting the CBLRE Evaluation Set

## What is gated

The following are not published in this repository:

- The full item bank (currently ~129 expert-reviewed items in the validation set; SME validation ongoing)
- Gold answers and scoring keys
- The held-out scoring split used for official evaluation

Only a small set of **synthetic illustrative items** in `data/sample/` is published here, clearly labeled as non-scoring.

## Why gated

Benchmark contamination — models trained on test items before evaluation — is a documented and growing problem in LLM evaluation. Publishing only the harness and methodology while gating the item bank means:

1. Evaluators can inspect and audit the full scoring logic
2. Models cannot be trained on items prior to evaluation
3. Official scoring on the held-out split preserves the instrument's integrity over multiple leaderboard refreshes

## How to request access

Open an [Evaluation Set Access Request](https://github.com/getsimpledirect/cblre/issues/new?template=access-request.yml) on this repository's issue tracker. The request form asks for:

- Organization name and your role
- Intended use (self-evaluation, research, regulatory compliance assessment, other)
- Agreement to the data use terms (see [DATA_LICENSE.md](../DATA_LICENSE.md))

**Access requests are public.** Do not include private contact details in the issue — once a request is approved, a maintainer responds on the issue to arrange delivery through a private channel.

Requests are reviewed by SimpleDirect® on a rolling basis.

## Official scoring on the held-out split

If you want results on the held-out split — the basis for any leaderboard entry or published comparative claim — scoring is coordinated with SimpleDirect® rather than run independently:

1. Submit your model for evaluation via an inference API endpoint or packaged weights
2. SimpleDirect® runs the harness against the private held-out split on controlled infrastructure
3. A `summary.json` in the standard output format is returned to you
4. Results may be published in the forthcoming CBLRE leaderboard with your consent

This process ensures that no evaluator handles the held-out items directly. It also ensures that all published numbers are produced under the same conditions (identical prompts, temperature 0, specified judge model), which makes cross-model comparisons valid.

## Self-evaluation with your own items

If you want to test the harness before requesting official evaluation, you can:

1. Install the harness: `pip install git+https://github.com/getsimpledirect/cblre.git`
2. Write items conforming to [`schema/eval_item.schema.json`](../schema/eval_item.schema.json)
3. Run `cblre-eval --items your_items.jsonl ...` (or `python -m harness.run_eval --items your_items.jsonl ...`)
4. Inspect the per-item output and summary

Results from self-evaluation on your own items are not comparable to official CBLRE numbers and should not be cited as CBLRE scores.

## Timeframe and contact

Access requests and data license questions are handled through the [repository issue tracker](https://github.com/getsimpledirect/cblre/issues).

**Response time target:** We aim to acknowledge access requests within **5 business days** and to complete review within **15 business days**. The open/closed state of your access-request issue reflects its current status; a maintainer will comment on the issue if additional information is needed or when access is approved.

If you have not received a response within 15 business days, please add a comment to your open issue to prompt a follow-up. For urgent research timelines, note your deadline in the original request.
