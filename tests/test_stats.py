# Copyright 2026 Alpine Pacific Trading Inc. (operating as SimpleDirect®)
# SPDX-License-Identifier: Apache-2.0
"""Tests for harness/stats.py.

All three functions are pure math with no external deps:
bootstrap_ci, bootstrap_diff_test, parity_ratio.
"""
from __future__ import annotations

import pytest
from harness.stats import bootstrap_ci, bootstrap_diff_test, parity_ratio


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
