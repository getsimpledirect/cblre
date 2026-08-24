# Copyright 2026 Alpine Pacific Trading Inc. (operating as SimpleDirect®)
# SPDX-License-Identifier: Apache-2.0
"""
CBLRE statistics.

Every reported number gets an n and a 95% bootstrap CI. Every "A beats B"
claim gets a significance test. Differences inside overlapping CIs are reported
as "not distinguishable", never as a ranking.

Pairing is not optional. When two arms are scored over the same items, the
paired estimator is the correct one and the unpaired one is not merely weaker,
it is wrong: it discards the item-level correlation and widens the interval
until a real effect disappears into it. Use paired_bootstrap_diff for graded
scores and mcnemar_test for pass/fail judgements whenever the task set is
shared; keep bootstrap_diff_test for genuinely independent samples.
"""

from __future__ import annotations

import random
from math import comb
from statistics import mean


def bootstrap_ci(scores: list[float], n_boot: int = 10000,
                 alpha: float = 0.05, seed: int = 0) -> dict:
    """95% bootstrap CI (percentile method) over a list of per-item scores in
    [0,1]. Returns mean and CI in percent."""
    if not scores:
        return {"n": 0, "mean_pct": None, "ci_low_pct": None, "ci_high_pct": None}
    rng = random.Random(seed)
    n = len(scores)
    boots = []
    for _ in range(n_boot):
        sample = [scores[rng.randrange(n)] for _ in range(n)]
        boots.append(mean(sample))
    boots.sort()
    lo = boots[int((alpha / 2) * n_boot)]
    hi = boots[int((1 - alpha / 2) * n_boot)]
    return {"n": n,
            "mean_pct": round(100 * mean(scores), 2),
            "ci_low_pct": round(100 * lo, 2),
            "ci_high_pct": round(100 * hi, 2)}


def bootstrap_diff_test(scores_a: list[float], scores_b: list[float],
                        n_boot: int = 10000, seed: int = 0) -> dict:
    """
    Two-sample bootstrap test of mean(A) - mean(B). Returns the observed
    difference (percentage points) and a two-sided p-value for H0: diff = 0.
    Use for any leaderboard claim that one model beats another on a track.
    """
    if not scores_a or not scores_b:
        return {"diff_pct": None, "p_value": None, "verdict": "insufficient_data"}
    rng = random.Random(seed)
    obs = mean(scores_a) - mean(scores_b)
    na, nb = len(scores_a), len(scores_b)
    # Center both samples on the pooled mean to simulate H0, then resample.
    pooled = mean(scores_a + scores_b)
    a_c = [x - mean(scores_a) + pooled for x in scores_a]
    b_c = [x - mean(scores_b) + pooled for x in scores_b]
    count_extreme = 0
    for _ in range(n_boot):
        da = mean([a_c[rng.randrange(na)] for _ in range(na)])
        db = mean([b_c[rng.randrange(nb)] for _ in range(nb)])
        if abs(da - db) >= abs(obs):
            count_extreme += 1
    p = count_extreme / n_boot
    verdict = ("A_better" if obs > 0 else "B_better") if p < 0.05 else "not_distinguishable"
    return {"diff_pct": round(100 * obs, 2), "p_value": round(p, 4), "verdict": verdict}


def parity_ratio(acc_fr: float, acc_en: float) -> dict:
    """Track-1 headline metric. Ratio of FR accuracy to EN accuracy."""
    if not acc_en:
        return {"parity_ratio": None}
    return {"parity_ratio": round(acc_fr / acc_en, 3)}


def paired_bootstrap_diff(scores_a: list[float], scores_b: list[float],
                          n_boot: int = 10000, alpha: float = 0.05,
                          seed: int = 0) -> dict:
    """
    Paired bootstrap of mean(A) - mean(B) for two arms scored over the *same*
    items, in the same order. Resamples item indices once per draw and applies
    that index to both arms, so the item-level correlation is preserved.

    Use this, not bootstrap_diff_test, whenever the arms share a task set.
    bootstrap_diff_test resamples the arms independently, which throws away the
    pairing and inflates the interval — often by enough to hide a real effect.

    For a difference-in-differences gate, pass the per-item pre/post deltas as
    the two arms: scores_a = [post_true_i - pre_true_i], scores_b =
    [post_control_i - pre_control_i]. The returned diff is then the paired
    effect and the interval is the one a gate should read.

    Inputs need not lie in [0,1]; deltas in [-1,1] are the expected case.

    Returns the observed difference and its CI in percentage points, plus a
    two-sided p-value from the same resampling. Mismatched lengths raise rather
    than returning a sentinel: an unequal pair is a caller error, and silently
    answering it would be the exact failure this function exists to prevent.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError(
            f"paired_bootstrap_diff needs equal-length arms scored over the same items, "
            f"in the same order; got {len(scores_a)} and {len(scores_b)}. If the arms were "
            f"scored over different task sets, the comparison is unpaired — use "
            f"bootstrap_diff_test instead."
        )
    if not scores_a:
        return {"n": 0, "diff_pct": None, "ci_low_pct": None, "ci_high_pct": None,
                "p_value": None, "verdict": "insufficient_data"}
    rng = random.Random(seed)
    deltas = [a - b for a, b in zip(scores_a, scores_b)]
    n = len(deltas)
    obs = mean(deltas)
    boots = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        boots.append(mean([deltas[i] for i in idx]))
    boots.sort()
    lo = boots[int((alpha / 2) * n_boot)]
    hi = boots[min(int((1 - alpha / 2) * n_boot), n_boot - 1)]
    # Two-sided p under H0: mean delta = 0, by shifting the resampled deltas.
    count_extreme = sum(1 for b in boots if abs(b - obs) >= abs(obs))
    p = count_extreme / n_boot
    excludes_zero = lo > 0 or hi < 0
    if not excludes_zero:
        verdict = "not_distinguishable"
    else:
        verdict = "A_better" if obs > 0 else "B_better"
    return {"n": n,
            "diff_pct": round(100 * obs, 2),
            "ci_low_pct": round(100 * lo, 2),
            "ci_high_pct": round(100 * hi, 2),
            "p_value": round(p, 4),
            "excludes_zero": excludes_zero,
            "verdict": verdict}


def mcnemar_test(correct_a: list[bool], correct_b: list[bool],
                 n_boot: int = 10000, alpha: float = 0.05,
                 seed: int = 0) -> dict:
    """
    Exact McNemar test for two arms judged pass/fail on the *same* items, in
    the same order. Only the discordant pairs carry information: items both
    arms got right, or both got wrong, say nothing about which is better.

    Returns the count of each discordant kind, the paired difference in pass
    rate with a bootstrap CI in percentage points, and an exact two-sided
    binomial p-value. Exact rather than the chi-square approximation, because
    the discordant count is usually small even when n is not.

    Mismatched lengths raise, for the reason given in paired_bootstrap_diff.
    """
    if len(correct_a) != len(correct_b):
        raise ValueError(
            f"mcnemar_test needs equal-length arms judged over the same items, in the same "
            f"order; got {len(correct_a)} and {len(correct_b)}."
        )
    if not correct_a:
        return {"n": 0, "n_discordant": 0, "a_only": 0, "b_only": 0,
                "diff_pct": None, "ci_low_pct": None, "ci_high_pct": None,
                "p_value": None, "verdict": "insufficient_data"}
    a_only = sum(1 for a, b in zip(correct_a, correct_b) if a and not b)
    b_only = sum(1 for a, b in zip(correct_a, correct_b) if b and not a)
    nd = a_only + b_only
    paired = paired_bootstrap_diff([1.0 if x else 0.0 for x in correct_a],
                                   [1.0 if x else 0.0 for x in correct_b],
                                   n_boot=n_boot, alpha=alpha, seed=seed)
    if nd == 0:
        p = 1.0
    else:
        k = min(a_only, b_only)
        tail = sum(comb(nd, i) for i in range(k + 1))
        p = min(1.0, 2 * tail / (2 ** nd))
    verdict = ("A_better" if a_only > b_only else "B_better") if p < alpha \
        else "not_distinguishable"
    return {"n": len(correct_a),
            "n_discordant": nd,
            "a_only": a_only,
            "b_only": b_only,
            "diff_pct": paired["diff_pct"],
            "ci_low_pct": paired["ci_low_pct"],
            "ci_high_pct": paired["ci_high_pct"],
            "p_value": round(p, 4),
            "verdict": verdict}
