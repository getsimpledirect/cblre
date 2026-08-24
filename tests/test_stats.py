# Copyright 2026 Alpine Pacific Trading Inc. (operating as SimpleDirect®)
# SPDX-License-Identifier: Apache-2.0
"""Tests for harness/stats.py.

All five functions are pure math with no external deps: bootstrap_ci,
bootstrap_diff_test, parity_ratio, paired_bootstrap_diff, mcnemar_test.
"""
from __future__ import annotations

import pytest

from harness.stats import (
    bootstrap_ci,
    bootstrap_diff_test,
    mcnemar_test,
    paired_bootstrap_diff,
    parity_ratio,
)


class TestBootstrapCI:
    def test_empty_returns_none_sentinel(self):
        r = bootstrap_ci([])
        assert r == {"n": 0, "mean_pct": None, "ci_low_pct": None, "ci_high_pct": None}

    def test_single_item_all_correct(self):
        r = bootstrap_ci([1.0])
        assert r["n"] == 1
        assert r["mean_pct"] == 100.0
        assert r["ci_low_pct"] is not None
        assert r["ci_high_pct"] is not None

    def test_single_item_all_wrong(self):
        r = bootstrap_ci([0.0])
        assert r["mean_pct"] == 0.0

    def test_all_identical_ci_is_exact(self):
        r = bootstrap_ci([0.5] * 20)
        assert r["mean_pct"] == 50.0
        assert r["ci_low_pct"] == 50.0
        assert r["ci_high_pct"] == 50.0

    def test_mean_pct_correct(self):
        r = bootstrap_ci([1.0, 0.0])
        assert r["mean_pct"] == 50.0
        assert r["n"] == 2

    def test_ci_bounds_straddle_mean(self):
        scores = [1.0] * 5 + [0.0] * 5
        r = bootstrap_ci(scores)
        assert r["ci_low_pct"] <= r["mean_pct"]
        assert r["ci_high_pct"] >= r["mean_pct"]

    def test_seed_produces_same_result(self):
        scores = [float(i % 2) for i in range(20)]
        assert bootstrap_ci(scores, seed=0) == bootstrap_ci(scores, seed=0)

    def test_all_correct_mean_100(self):
        r = bootstrap_ci([1.0] * 10)
        assert r["mean_pct"] == 100.0

    def test_n_matches_input_length(self):
        scores = [0.5] * 7
        assert bootstrap_ci(scores)["n"] == 7


class TestBootstrapDiffTest:
    def test_empty_a_insufficient_data(self):
        r = bootstrap_diff_test([], [1.0, 0.0])
        assert r["verdict"] == "insufficient_data"
        assert r["diff_pct"] is None
        assert r["p_value"] is None

    def test_empty_b_insufficient_data(self):
        r = bootstrap_diff_test([1.0], [])
        assert r["verdict"] == "insufficient_data"

    def test_both_empty_insufficient_data(self):
        r = bootstrap_diff_test([], [])
        assert r["verdict"] == "insufficient_data"

    def test_identical_samples_not_distinguishable(self):
        scores = [1.0, 0.0, 1.0, 0.0, 1.0]
        r = bootstrap_diff_test(scores, scores, seed=0)
        assert r["diff_pct"] == 0.0
        assert r["verdict"] == "not_distinguishable"

    def test_a_clearly_better(self):
        r = bootstrap_diff_test([1.0] * 50, [0.0] * 50, seed=0)
        assert r["verdict"] == "A_better"
        assert r["diff_pct"] > 0
        assert r["p_value"] < 0.05

    def test_b_clearly_better(self):
        r = bootstrap_diff_test([0.0] * 50, [1.0] * 50, seed=0)
        assert r["verdict"] == "B_better"
        assert r["diff_pct"] < 0

    def test_seed_reproducible(self):
        a = [float(i % 2) for i in range(20)]
        b = [float((i + 1) % 2) for i in range(20)]
        assert bootstrap_diff_test(a, b, seed=0) == bootstrap_diff_test(a, b, seed=0)

    def test_diff_pct_sign_matches_direction(self):
        r = bootstrap_diff_test([0.8], [0.2])
        assert r["diff_pct"] > 0


class TestParityRatio:
    def test_normal_ratio(self):
        assert parity_ratio(0.8, 1.0) == {"parity_ratio": 0.8}

    def test_equal_accuracy(self):
        assert parity_ratio(0.75, 0.75) == {"parity_ratio": 1.0}

    def test_acc_en_zero_returns_none(self):
        assert parity_ratio(0.8, 0.0) == {"parity_ratio": None}

    def test_both_zero_returns_none(self):
        assert parity_ratio(0.0, 0.0) == {"parity_ratio": None}

    def test_fr_zero_en_nonzero(self):
        assert parity_ratio(0.0, 1.0) == {"parity_ratio": 0.0}

    def test_rounded_to_three_decimals(self):
        r = parity_ratio(1.0, 3.0)
        assert r == {"parity_ratio": round(1.0 / 3.0, 3)}

    def test_fr_greater_than_en(self):
        r = parity_ratio(0.9, 0.6)
        assert r["parity_ratio"] == pytest.approx(1.5, rel=1e-2)


class TestPairedBootstrapDiff:
    def test_empty_returns_none_sentinel(self):
        r = paired_bootstrap_diff([], [])
        assert r["n"] == 0
        assert r["diff_pct"] is None
        assert r["verdict"] == "insufficient_data"

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError, match="equal-length arms"):
            paired_bootstrap_diff([1.0, 0.0], [1.0])

    def test_mismatched_lengths_name_the_alternative(self):
        with pytest.raises(ValueError, match="bootstrap_diff_test"):
            paired_bootstrap_diff([1.0], [1.0, 0.0])

    def test_identical_arms_zero_diff_not_distinguishable(self):
        s = [0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0]
        r = paired_bootstrap_diff(s, s, n_boot=500)
        assert r["diff_pct"] == 0.0
        assert r["excludes_zero"] is False
        assert r["verdict"] == "not_distinguishable"

    def test_constant_offset_recovered_exactly(self):
        a = [0.1, 0.4, 0.9, 0.3, 0.7, 0.5]
        b = [x - 0.2 for x in a]
        r = paired_bootstrap_diff(a, b, n_boot=500)
        assert r["diff_pct"] == 20.0
        # Every per-item delta is identical, so the resampled CI has no width.
        assert r["ci_low_pct"] == 20.0
        assert r["ci_high_pct"] == 20.0
        assert r["verdict"] == "A_better"

    def test_b_better_is_reported_as_b_better(self):
        a = [0.2, 0.3, 0.1, 0.25, 0.15, 0.2]
        b = [x + 0.3 for x in a]
        r = paired_bootstrap_diff(a, b, n_boot=500)
        assert r["diff_pct"] == -30.0
        assert r["verdict"] == "B_better"

    def test_detects_effect_the_unpaired_test_misses(self):
        # The reason this function exists. Both arms vary widely across items,
        # but A beats B on every single item by the same small margin. Paired
        # sees it; unpaired drowns it in the between-item variance.
        base = [0.05, 0.95, 0.15, 0.85, 0.25, 0.75, 0.35, 0.65, 0.45, 0.55] * 3
        a = [x + 0.04 for x in base]
        b = list(base)
        paired = paired_bootstrap_diff(a, b, n_boot=2000, seed=1)
        unpaired = bootstrap_diff_test(a, b, n_boot=2000, seed=1)
        assert paired["diff_pct"] == unpaired["diff_pct"]  # same point estimate
        assert paired["verdict"] == "A_better"
        assert unpaired["verdict"] == "not_distinguishable"

    def test_accepts_negative_values_for_difference_in_differences(self):
        # Arms are per-item pre/post deltas, so values fall outside [0,1].
        true_arm = [0.3, 0.2, 0.4, 0.25, 0.35, 0.3]
        control_arm = [-0.1, 0.0, 0.05, -0.05, 0.0, 0.1]
        r = paired_bootstrap_diff(true_arm, control_arm, n_boot=500)
        assert r["n"] == 6
        assert r["diff_pct"] > 0
        assert r["verdict"] == "A_better"

    def test_seed_reproducible(self):
        a = [0.0, 1.0, 0.5, 0.75, 0.25, 1.0, 0.0, 0.5]
        b = [1.0, 0.0, 0.5, 0.25, 0.75, 0.0, 1.0, 0.5]
        r1 = paired_bootstrap_diff(a, b, n_boot=500, seed=42)
        r2 = paired_bootstrap_diff(a, b, n_boot=500, seed=42)
        assert r1 == r2

    def test_ci_brackets_the_point_estimate(self):
        a = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3, 0.6, 0.4]
        b = [0.5, 0.4, 0.5, 0.3, 0.4, 0.4, 0.5, 0.3]
        r = paired_bootstrap_diff(a, b, n_boot=2000)
        assert r["ci_low_pct"] <= r["diff_pct"] <= r["ci_high_pct"]

    def test_n_is_pair_count_not_total(self):
        r = paired_bootstrap_diff([1.0] * 7, [0.0] * 7, n_boot=200)
        assert r["n"] == 7


class TestMcNemarTest:
    def test_empty_returns_none_sentinel(self):
        r = mcnemar_test([], [])
        assert r["n"] == 0
        assert r["n_discordant"] == 0
        assert r["p_value"] is None
        assert r["verdict"] == "insufficient_data"

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError, match="equal-length arms"):
            mcnemar_test([True, False], [True])

    def test_identical_judgements_no_discordant_pairs(self):
        j = [True, False, True, True, False]
        r = mcnemar_test(j, j, n_boot=200)
        assert r["n_discordant"] == 0
        assert r["a_only"] == 0
        assert r["b_only"] == 0
        assert r["p_value"] == 1.0
        assert r["verdict"] == "not_distinguishable"

    def test_concordant_pairs_carry_no_information(self):
        # Adding items both arms get right must not change the discordant
        # counts or the p-value, only n.
        a = [True, False, True, False]
        b = [False, True, True, False]
        small = mcnemar_test(a, b, n_boot=200)
        big = mcnemar_test(a + [True] * 40, b + [True] * 40, n_boot=200)
        assert big["n"] == 44
        assert big["n_discordant"] == small["n_discordant"] == 2
        assert big["p_value"] == small["p_value"]

    def test_discordant_counts_are_directional(self):
        a = [True, True, True, False, False]
        b = [False, False, False, False, True]
        r = mcnemar_test(a, b, n_boot=200)
        assert r["a_only"] == 3
        assert r["b_only"] == 1
        assert r["n_discordant"] == 4

    def test_all_discordant_one_direction_is_significant(self):
        a = [True] * 10 + [False] * 5
        b = [False] * 10 + [False] * 5
        r = mcnemar_test(a, b, n_boot=500)
        assert r["a_only"] == 10
        assert r["b_only"] == 0
        # Exact two-sided binomial on 10 discordant pairs, all one way.
        assert r["p_value"] == round(2 / 2 ** 10, 4)
        assert r["verdict"] == "A_better"

    def test_b_better_is_reported_as_b_better(self):
        a = [False] * 10 + [True] * 3
        b = [True] * 10 + [True] * 3
        r = mcnemar_test(a, b, n_boot=500)
        assert r["b_only"] == 10
        assert r["diff_pct"] < 0
        assert r["verdict"] == "B_better"

    def test_even_split_is_not_distinguishable(self):
        a = [True] * 5 + [False] * 5
        b = [False] * 5 + [True] * 5
        r = mcnemar_test(a, b, n_boot=500)
        assert r["a_only"] == r["b_only"] == 5
        assert r["p_value"] == 1.0
        assert r["verdict"] == "not_distinguishable"

    def test_p_value_never_exceeds_one(self):
        # The doubling in the exact two-sided tail can overshoot; it is clamped.
        for nd in range(1, 12):
            half = nd // 2
            a = [True] * half + [False] * (nd - half)
            b = [False] * half + [True] * (nd - half)
            assert mcnemar_test(a, b, n_boot=100)["p_value"] <= 1.0

    def test_diff_pct_matches_paired_bootstrap_on_same_data(self):
        a = [True, True, False, True, False, False, True, True]
        b = [False, True, False, False, True, False, True, False]
        r = mcnemar_test(a, b, n_boot=500, seed=3)
        paired = paired_bootstrap_diff([1.0 if x else 0.0 for x in a],
                                       [1.0 if x else 0.0 for x in b],
                                       n_boot=500, seed=3)
        assert r["diff_pct"] == paired["diff_pct"]
        assert r["ci_low_pct"] == paired["ci_low_pct"]
        assert r["ci_high_pct"] == paired["ci_high_pct"]

    def test_seed_reproducible(self):
        a = [True, False, True, True, False, True, False, False]
        b = [False, False, True, False, True, True, True, False]
        assert mcnemar_test(a, b, n_boot=500, seed=9) == mcnemar_test(a, b, n_boot=500, seed=9)
