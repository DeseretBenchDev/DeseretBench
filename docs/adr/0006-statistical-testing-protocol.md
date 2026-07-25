# ADR-0006: Statistical testing protocol

Status: Accepted

Date: 2026-06 (refined 2026-07-02: the audit added Holm correction and p-value
smoothing)

## Context

A benchmark that reports one number per model invites over-reading. We run each
item several times (MC 5, open 3) across a cohort of Claude models, and readers
will want to know two things the raw means cannot answer: how wide is the
uncertainty, and which model-to-model gaps are real rather than sampling noise.
Getting this wrong is easy in two specific ways.

First, **pseudo-replication** — treating every (item, run) response as
independent would count the correlated repeats of one item as separate evidence
and collapse the intervals to fiction. Second, **multiplicity** — a 9-model
cohort produces 36 pairwise comparisons per phase, and testing each at α = 0.05
independently would manufacture "significant" gaps by chance.

## Decision

Adopt a fixed, seeded protocol in [`deseretbench/stats.py`](../../deseretbench/stats.py),
driven by [`deseretbench/analyze.py`](../../deseretbench/analyze.py):

- **Per-item means are the resampling unit.** `analyze.py` first collapses each
  model's repeat runs of an item into a single per-item score, then bootstraps
  over those per-item values (`bootstrap_mean_ci`, `paired_bootstrap_diff`). The
  item, not the individual response, is the independent unit — this is what
  `stats.py`'s "clustered by item" docstring means in effect. Default 10,000
  resamples, seed from `run_config.yaml stats.rng_seed`.
- **Smoothed bootstrap p-values.** Paired differences use a two-sided
  add-one-smoothed p: `p = 2 * (min(#≤0, #≥0) + 1) / (B + 1)`, capped at 1.0.
  The `+1` gives a resolution floor of `1/(B+1)` per side, so a Monte-Carlo p can
  never be reported as exactly 0 (floor ≈ 0.0002 at 10k resamples).
- **Holm-Bonferroni family-wise control.** `_attach_holm` adjusts the whole set
  of pairwise comparisons within a phase (all MC pairs, all open pairs) via
  step-down Holm, adding `p_holm` and `significant_holm` to each pair. Holm is
  uniformly more powerful than plain Bonferroni at the same family-wise error.
- **Clopper-Pearson at the ceiling.** When MC accuracy saturates, the bootstrap
  CI collapses to zero width and lies. Each model also carries an exact
  Clopper-Pearson interval over item-majority correctness, the honest interval
  at the accuracy ceiling.
- **McNemar for paired MC.** Alongside the bootstrap, MC pairs get McNemar's test
  on per-item majority correctness (exact for small discordant counts), with an
  Edwards-corrected chi-square fallback when statsmodels is unavailable.
- **Krippendorff's α for panel agreement.** Inter-persona reliability uses the
  interval-metric α, computed on the composite and per dimension; it returns
  `None` (not 1.0) when all ratings are identical, because constant ratings are
  not evidence of reliability.
- **Deterministic draws.** `derive_seed(base, *parts)` hashes a stable call-site
  label into a child seed so every bootstrap gets a decorrelated but fully
  reproducible index stream from one master seed.

## Consequences

- **Significance calls are conservative by construction.** Holm over the full
  pairwise family plus add-one smoothing makes it *harder*, not easier, to claim
  a difference. A gap that survives is a gap we stand behind.
- **Every draw is replayable.** Given the run directory and the pinned seed, the
  intervals and p-values regenerate bit-for-bit; there is no hidden randomness.
- **Ceiling honesty over cosmetic precision.** At MC saturation we report a wide
  exact interval instead of a tight-but-false bootstrap band. Within-item run
  stochasticity, discarded by the per-item collapse, is reported separately as
  run-to-run SD.

## Links

- Method rationale: [docs/explanation/statistics.md](../explanation/statistics.md).
- Measurement integrity: [docs/explanation/measurement-integrity.md](../explanation/measurement-integrity.md).
- Code: `deseretbench/stats.py`, `deseretbench/analyze.py`.
