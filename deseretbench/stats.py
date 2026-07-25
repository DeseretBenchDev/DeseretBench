"""Statistics for DeseretBench: bootstrap confidence intervals (clustered by
item), paired model comparisons, McNemar, classical item analysis
(difficulty + discrimination), run-to-run variance, and Krippendorff's alpha
for judge inter-rater reliability. All randomness is seeded.
"""

from __future__ import annotations

import hashlib
import math
from typing import Optional

import numpy as np


def derive_seed(base: int, *parts: str) -> int:
    """Deterministic per-call-site seed. One shared seed would make every
    bootstrap in an analysis reuse the bit-identical resample index stream;
    deriving a child seed from a stable label decorrelates them while staying
    fully reproducible."""
    h = hashlib.sha256((str(base) + ":" + ":".join(parts)).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % (2 ** 63)


def holm_bonferroni(pvals: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in the input order."""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


def clopper_pearson(k: int, n: int, ci: float = 0.95) -> tuple[float, float]:
    """Exact binomial CI — the honest interval when the bootstrap degenerates
    to zero width at a 0% or 100% ceiling."""
    from scipy.stats import beta
    if n == 0:
        return 0.0, 1.0
    a = (1 - ci) / 2
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a, k + 1, n - k))
    return lo, hi


# --------------------------------------------------------------------------- #
# Bootstrap CIs (resample items -> reflects item-sampling uncertainty)
# --------------------------------------------------------------------------- #


def bootstrap_mean_ci(per_item: list[float], n_resamples: int = 10000,
                      seed: int = 0, ci: float = 0.95) -> dict:
    x = np.asarray([v for v in per_item if v is not None], dtype=float)
    n = len(x)
    if n == 0:
        return {"mean": None, "lo": None, "hi": None, "n": 0, "sem": None}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    means = x[idx].mean(axis=1)
    a = (1 - ci) / 2
    lo, hi = np.quantile(means, [a, 1 - a])
    return {"mean": float(x.mean()), "lo": float(lo), "hi": float(hi),
            "n": n, "sem": float(x.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0}


def paired_bootstrap_diff(a_per_item: list[float], b_per_item: list[float],
                          n_resamples: int = 10000, seed: int = 0,
                          ci: float = 0.95) -> dict:
    """Paired (same items) difference a - b with bootstrap CI and two-sided p."""
    a = np.asarray(a_per_item, dtype=float)
    b = np.asarray(b_per_item, dtype=float)
    assert a.shape == b.shape, "paired arrays must align by item"
    d = a - b
    n = len(d)
    if n == 0:
        # no shared items: undefined, not "significant with NaN diff"
        return {"diff": None, "lo": None, "hi": None, "p": None, "n": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    boot = d[idx].mean(axis=1)
    obs = float(d.mean())
    aa = (1 - ci) / 2
    lo, hi = np.quantile(boot, [aa, 1 - aa])
    # Two-sided p with add-one smoothing: a Monte-Carlo p-value can never be
    # exactly 0 — the resolution floor is 1/(B+1) per side.
    r_le = int(np.sum(boot <= 0))
    r_ge = int(np.sum(boot >= 0))
    p = 2 * (min(r_le, r_ge) + 1) / (n_resamples + 1)
    return {"diff": obs, "lo": float(lo), "hi": float(hi), "p": min(1.0, p), "n": n}


def _mcnemar_chi2_fallback(b01: int, c01: int) -> tuple[float, float]:
    """Edwards-corrected chi-square with the correction clamped at 0 (an
    uncorrected |b-c|-1 goes negative-then-squared and fabricates signal
    when b == c)."""
    n = b01 + c01
    if n == 0:
        return 0.0, 1.0
    stat = (max(0.0, abs(b01 - c01) - 1) ** 2) / n
    from scipy.stats import chi2
    return stat, float(1 - chi2.cdf(stat, 1))


def mcnemar_test(a_correct: list[bool], b_correct: list[bool]) -> dict:
    """McNemar on paired binary outcomes (e.g., majority-correct per item)."""
    a = np.asarray(a_correct, dtype=bool)
    b = np.asarray(b_correct, dtype=bool)
    b01 = int(np.sum(a & ~b))   # a right, b wrong
    c01 = int(np.sum(~a & b))   # a wrong, b right
    try:
        from statsmodels.stats.contingency_tables import mcnemar
        tbl = [[int(np.sum(a & b)), b01], [c01, int(np.sum(~a & ~b))]]
        res = mcnemar(tbl, exact=(b01 + c01) < 25)
        p = float(res.pvalue)
        stat = float(res.statistic)
    except Exception:
        stat, p = _mcnemar_chi2_fallback(b01, c01)
    return {"b": b01, "c": c01, "statistic": stat, "p": p}


# --------------------------------------------------------------------------- #
# Classical item analysis
# --------------------------------------------------------------------------- #


def item_analysis(resp_by_item: dict[str, list[int]]) -> dict[str, dict]:
    """resp_by_item: item_id -> list of 0/1 outcomes, one per respondent
    (a respondent = a model x run instance), aligned across items by position.

    Returns per-item difficulty (p) and corrected item-total point-biserial
    discrimination.
    """
    item_ids = list(resp_by_item.keys())
    if not item_ids:
        return {}
    M = np.array([resp_by_item[i] for i in item_ids], dtype=float)  # items x respondents
    n_items, n_resp = M.shape
    total = M.sum(axis=0)  # per respondent
    out = {}
    for k, iid in enumerate(item_ids):
        item_vec = M[k]
        rest = total - item_vec  # corrected (exclude this item)
        p = float(item_vec.mean())
        if item_vec.std() == 0 or rest.std() == 0:
            disc = None
        else:
            disc = float(np.corrcoef(item_vec, rest)[0, 1])
        out[iid] = {"difficulty_p": p, "discrimination": disc, "n_resp": int(n_resp)}
    return out


def run_variance(per_item_runs: list[list[int]]) -> dict:
    """per_item_runs: list over items of [0/1 per run]. Returns mean within-item
    SD across runs (a stochasticity measure)."""
    sds = []
    for runs in per_item_runs:
        a = np.asarray(runs, dtype=float)
        if len(a) > 1:
            sds.append(float(a.std(ddof=1)))
    return {"mean_within_item_sd": (float(np.mean(sds)) if sds else 0.0),
            "n_items": len(per_item_runs)}


# --------------------------------------------------------------------------- #
# Krippendorff's alpha (interval metric, handles missing data)
# --------------------------------------------------------------------------- #


def krippendorff_alpha_interval(reliability_data: list[list[Optional[float]]]) -> Optional[float]:
    """reliability_data: raters x units matrix; None == missing.

    Interval difference metric. Returns alpha or None if undefined.
    """
    data = reliability_data
    n_raters = len(data)
    if n_raters < 2:
        return None
    n_units = len(data[0])
    # Keep only units with >= 2 ratings (pairable).
    units = []
    all_vals: list[float] = []
    for u in range(n_units):
        vals = [float(data[r][u]) for r in range(n_raters) if data[r][u] is not None]
        if len(vals) >= 2:
            units.append(vals)
            all_vals.extend(vals)
    n_total = len(all_vals)
    if n_total < 2:
        return None

    # Observed disagreement (coincidence matrix counts ORDERED pairs -> factor 2).
    obs_sum = 0.0
    for vals in units:
        m = len(vals)
        pair = 0.0
        for i in range(m):
            for j in range(i + 1, m):
                pair += (vals[i] - vals[j]) ** 2
        obs_sum += 2.0 * pair / (m - 1)
    Do = obs_sum / n_total

    # Expected disagreement over all pairs of all values.
    exp_sum = 0.0
    for a in range(n_total):
        va = all_vals[a]
        for b in range(a + 1, n_total):
            exp_sum += (va - all_vals[b]) ** 2
    De = (2.0 * exp_sum) / (n_total * (n_total - 1))
    if De == 0:
        # zero expected disagreement = all ratings identical everywhere;
        # alpha is mathematically undefined there, and constant ratings are
        # no evidence of reliability — do not report a perfect 1.0
        return None
    return float(1 - Do / De)


def fleiss_kappa(rater_choices: list[list[int]], n_categories: int) -> Optional[float]:
    """rater_choices: units x raters matrix of category indices. Fleiss' kappa.

    Raises ValueError on ragged rows or out-of-range categories — silently
    dropping them would return a plausible-looking but wrong statistic.
    """
    N = len(rater_choices)
    if N == 0:
        return None
    n = len(rater_choices[0])
    if n < 2:
        return None
    counts = np.zeros((N, n_categories))
    for i, row in enumerate(rater_choices):
        if len(row) != n:
            raise ValueError(f"fleiss_kappa: row {i} has {len(row)} raters, expected {n}")
        for c in row:
            if not (0 <= c < n_categories):
                raise ValueError(f"fleiss_kappa: category {c} out of range "
                                 f"[0, {n_categories}) in row {i}")
            counts[i, c] += 1
    P_i = ((counts ** 2).sum(axis=1) - n) / (n * (n - 1))
    P_bar = P_i.mean()
    p_j = counts.sum(axis=0) / (N * n)
    P_e = (p_j ** 2).sum()
    if P_e == 1:
        return 1.0
    return float((P_bar - P_e) / (1 - P_e))
