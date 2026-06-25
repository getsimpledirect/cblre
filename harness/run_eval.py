#!/usr/bin/env python3
# Copyright 2026 Alpine Pacific Trading Inc. (operating as SimpleDirect®)
# SPDX-License-Identifier: Apache-2.0
"""
CBLRE runner.

Run one model over a CBLRE item set, score every item, and write a
publication-shaped summary with per-track means + 95% bootstrap CIs.

Resumable: per-item results are appended to a JSONL as they complete, so a
re-run skips already-scored items.

Usage:
  python -m harness.run_eval \
    --items your_items.jsonl \
    --model '{"kind":"openai_compat","model_name":"your-model-name","base_url":"http://localhost:8000/v1"}' \
    --run-id your-model-v1 \
    --judge '{"kind":"anthropic","model_name":"claude-sonnet-4-6","api_key_env":"ANTHROPIC_API_KEY"}' \
    --out-dir ./results

Notes:
  * --model and --judge take a JSON client spec (see harness/models.py, build_client).
  * Greedy decoding (temperature 0) by default — the fairness protocol default.
  * The judge spec is optional; without it, rubric items are left unscored and
    flagged, and only programmatic tracks produce final numbers.
  * The canonical judge for comparable scores is claude-sonnet-4-6 (see
    docs/methodology.md §5.2); any judge may be used for self-evaluation.
  * Pass --judge twice (or a JSON list) to use a judge ENSEMBLE.
"""

from __future__ import annotations
import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from . import models as M
from . import scorers as S
from . import judge as J
from . import stats as ST


def load_items(path: str) -> list[dict]:
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_done(results_path: str) -> set:
    done = set()
    if os.path.exists(results_path):
        with open(results_path) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    return done


def score_one(item: dict, response: str, judge_clients: list) -> dict:
    method = item["scoring"]["method"]

    # Rubric items are judge-only — there is no programmatic scorer named "rubric".
    if method == "rubric":
        if not judge_clients:
            return {"programmatic": None,
                    "judge": {"status": "NO_JUDGE_CONFIGURED"},
                    "final_score": None}
        jr = J.judge_item(item, response, judge_clients)
        return {"programmatic": None, "judge": jr, "final_score": jr["score01"]}

    prog = S.PROGRAMMATIC[method](response, item)
    result = {"programmatic": prog, "judge": None, "final_score": prog["score"]}
    if prog.get("needs_judge") and judge_clients:
        jr = J.judge_item(item, response, judge_clients)
        result["judge"] = jr
        if jr["score01"] is not None:
            # For open/rubric items the judge sets the final score. For gated
            # programmatic methods (keyword/tool) combine: a hard gate failure stays 0;
            # otherwise the judge score governs. For refusal, the programmatic check is a
            # pre-filter only — the judge is authoritative when present (it catches
            # phrasings the marker list misses and overrides false-negatives).
            if method in ("keyword_coverage",) and prog["score"] == 0.0:
                result["final_score"] = 0.0  # required-term gate failed
            elif method == "tool_call":
                # name match (prog 0.5) + judged arg quality (other 0.5)
                result["final_score"] = prog["score"] + 0.5 * jr["score01"]
            else:
                result["final_score"] = jr["score01"]
    elif prog.get("needs_judge") and not judge_clients:
        # No judge available. Refusal and tool_call programmatic scores are real
        # signals worth keeping; other methods cannot finalize without a judge.
        if method in ("refusal", "tool_call"):
            result["final_score"] = prog["score"]
            result["judge"] = {"status": "NO_JUDGE_CONFIGURED_quality_unscored"}
        else:
            result["final_score"] = None  # genuinely cannot finalize without a judge
            result["judge"] = {"status": "NO_JUDGE_CONFIGURED"}
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--model", required=True, help="JSON client spec")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--judge", action="append", default=[],
                    help="JSON client spec; repeat for an ensemble")
    ap.add_argument("--out-dir", default="./results")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    out_dir = os.path.join(args.out_dir, args.run_id)
    os.makedirs(out_dir, exist_ok=True)
    results_path = os.path.join(out_dir, "items.jsonl")
    summary_path = os.path.join(out_dir, "summary.json")

    items = load_items(args.items)
    done = load_done(results_path)
    print(f"[run] {len(items)} items, {len(done)} already done")

    client = M.build_client(json.loads(args.model))
    judge_clients = [M.build_client(json.loads(j)) for j in args.judge]
    if not judge_clients:
        print("[run] WARNING: no judge configured — rubric items will be unscored")

    with open(results_path, "a") as out:
        for it in items:
            if it["id"] in done:
                continue
            # MCQ items must present the options to the model and constrain the
            # answer to a letter — otherwise the model answers in prose and there
            # is no letter to score. Applied identically to every model (format
            # protocol, not a content change).
            prompt = it["prompt"]
            if it.get("format") == "mcq" and it.get("choices"):
                prompt = (prompt.rstrip() + "\n" + "\n".join(it["choices"])
                          + "\n\nAnswer with ONLY the letter of the correct option.")
            gen = client.generate(
                prompt, system=it.get("system"), context=it.get("context"),
                tools=it.get("tools"), max_tokens=args.max_tokens,
                temperature=args.temperature,
            )
            scored = score_one(it, gen.text, judge_clients)
            row = {
                "id": it["id"], "track": it["track"], "language": it["language"],
                "difficulty": it["difficulty"], "parity_group": it.get("parity_group"),
                "response": gen.text, "latency_s": round(gen.latency_s, 2),
                "score": scored["final_score"], "scoring_method": it["scoring"]["method"],
                "programmatic": scored["programmatic"], "judge": scored["judge"],
                "canary": it["provenance"]["canary"],
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            ss = "?" if scored["final_score"] is None else f"{scored['final_score']:.2f}"
            print(f"  [{it['id']:<28}] {it['track']:<22} score={ss}")

    aggregate(results_path, summary_path, args.run_id,
              json.loads(args.model), [json.loads(j) for j in args.judge])
    print(f"[run] summary -> {summary_path}")


def aggregate(results_path, summary_path, run_id, model_spec, judge_specs):
    rows = [json.loads(line) for line in open(results_path)]
    by_track = defaultdict(list)
    lang_acc = defaultdict(lambda: defaultdict(list))   # track -> lang -> scores
    diff_acc = defaultdict(lambda: defaultdict(list))   # track -> difficulty -> scores
    unscored = 0
    for r in rows:
        if r["score"] is None:
            unscored += 1
            continue
        by_track[r["track"]].append(r["score"])
        lang_acc[r["track"]][r["language"]].append(r["score"])
        diff_acc[r["track"]][r["difficulty"]].append(r["score"])

    tracks = {}
    for tr, scores in sorted(by_track.items()):
        entry = ST.bootstrap_ci(scores)
        # difficulty breakdown
        entry["by_difficulty"] = {
            d: ST.bootstrap_ci(v) for d, v in sorted(diff_acc[tr].items())
        }
        tracks[tr] = entry

    # Track-1 parity headline (and any track with both languages present)
    parity = {}
    for tr in by_track:
        en = lang_acc[tr].get("en", [])
        fr = lang_acc[tr].get("fr", [])
        if en and fr:
            from statistics import mean
            parity[tr] = {
                "en_acc_pct": round(100 * mean(en), 2),
                "fr_acc_pct": round(100 * mean(fr), 2),
                **ST.parity_ratio(mean(fr), mean(en)),
                "n_en": len(en), "n_fr": len(fr),
            }

    summary = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model_spec": model_spec,
        "judge_specs": judge_specs,
        "n_items": len(rows),
        "n_unscored_no_judge": unscored,
        "tracks": tracks,
        "bilingual_parity": parity,
        "note": "Seed run. Items require SME validation before these numbers are publishable (see docs/methodology.md §0).",
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
