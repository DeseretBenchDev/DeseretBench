"""Statistics correctness tests — fixtures with known answers."""

import json
import math

import pytest

import deseretbench.stats as stx


# --------------------------------------------------------------------------- #
# paired bootstrap
# --------------------------------------------------------------------------- #

def test_paired_bootstrap_empty_inputs_no_nan():
    d = stx.paired_bootstrap_diff([], [], n_resamples=100, seed=1)
    assert d["n"] == 0
    assert d["diff"] is None and d["p"] is None
    json.dumps(d)  # must be strict-JSON serializable (no NaN)


def test_paired_bootstrap_p_never_zero():
    a, b = [1.0] * 30, [0.0] * 30
    d = stx.paired_bootstrap_diff(a, b, n_resamples=1000, seed=2)
    assert d["p"] > 0.0                    # (r+1)/(B+1) smoothing
    assert d["p"] <= 2 / 1001 + 1e-12
    assert d["diff"] == pytest.approx(1.0)


def test_paired_bootstrap_null_case_p_large():
    a = [0.4, 0.6, 0.5, 0.55, 0.45] * 6
    d = stx.paired_bootstrap_diff(a, list(a), n_resamples=500, seed=3)
    assert d["diff"] == 0.0 and d["p"] == 1.0


# --------------------------------------------------------------------------- #
# mcnemar fallback continuity clamp
# --------------------------------------------------------------------------- #

def test_mcnemar_fallback_clamped():
    # b == c: no evidence of difference; unclamped Edwards gives a spurious
    # positive statistic ((0-1)^2/2 = 0.5)
    stat, p = stx._mcnemar_chi2_fallback(1, 1)
    assert stat == 0.0 and p == 1.0
    stat0, p0 = stx._mcnemar_chi2_fallback(0, 0)
    assert stat0 == 0.0 and p0 == 1.0


# --------------------------------------------------------------------------- #
# krippendorff / fleiss
# --------------------------------------------------------------------------- #

def test_krippendorff_zero_variance_is_undefined():
    # every rater gives the same constant everywhere: no evidence of
    # reliability — must NOT report a perfect 1.0
    m = [[3.0, 3.0, 3.0], [3.0, 3.0, 3.0], [3.0, 3.0, 3.0]]
    assert stx.krippendorff_alpha_interval(m) is None


def test_krippendorff_perfect_and_imperfect():
    perfect = [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
    assert stx.krippendorff_alpha_interval(perfect) == pytest.approx(1.0)
    noisy = [[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]]
    a = stx.krippendorff_alpha_interval(noisy)
    assert a is not None and a < 1.0


def test_fleiss_kappa_rejects_bad_input():
    with pytest.raises(ValueError):
        stx.fleiss_kappa([[0, 1], [0, 1, 2]], n_categories=3)   # ragged
    with pytest.raises(ValueError):
        stx.fleiss_kappa([[0, 5], [0, 1]], n_categories=3)      # out of range


# --------------------------------------------------------------------------- #
# new helpers: holm, seed derivation, exact binomial CI
# --------------------------------------------------------------------------- #

def test_holm_bonferroni():
    adj = stx.holm_bonferroni([0.01, 0.04, 0.03])
    assert adj == pytest.approx([0.03, 0.06, 0.06])
    assert stx.holm_bonferroni([]) == []
    assert max(stx.holm_bonferroni([0.9, 0.8])) <= 1.0


def test_derive_seed_stable_and_distinct():
    s1 = stx.derive_seed(19470417, "mc", "overall", "claude-opus-4-8")
    s2 = stx.derive_seed(19470417, "mc", "overall", "claude-opus-4-8")
    s3 = stx.derive_seed(19470417, "mc", "overall", "claude-opus-4-7")
    assert s1 == s2 != s3
    assert isinstance(s1, int) and s1 >= 0


def test_clopper_pearson_at_ceiling():
    lo, hi = stx.clopper_pearson(213, 213, ci=0.95)
    assert hi == 1.0
    assert lo == pytest.approx(0.025 ** (1 / 213), abs=1e-6)
    lo2, hi2 = stx.clopper_pearson(0, 10, ci=0.95)
    assert lo2 == 0.0 and 0 < hi2 < 0.5
