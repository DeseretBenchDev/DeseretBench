# Statistical choices, and why

Every statistic DeseretBench reports comes out of two files:
[`deseretbench/stats.py`](../../deseretbench/stats.py) (the pure math, all of
it seeded) and [`deseretbench/analyze.py`](../../deseretbench/analyze.py) (the
pipeline that decides what the math is applied *to*). This document explains
the choices — what we use, what we rejected, and what we deliberately do not
do at v0.1 scale. For the mechanics of re-running the analysis, see
[../how-to/rerun-analysis.md](../how-to/rerun-analysis.md); for the output
schema, see [../reference/data-formats.md](../reference/data-formats.md). No
result numbers appear here — those live in the generated
[`reports/RESULTS.md`](../../reports/RESULTS.md).

## The unit of analysis: items, not records

A record is one model response: one item, one run. With repeat runs (five per
MC item, three per open item, per `configs/run_config.yaml`), each item
contributes several records — and those records are strongly correlated,
because they share the item. Treating records as independent observations is
pseudo-replication: it inflates the effective sample size by roughly the run
count and produces confidence intervals that are too narrow, i.e.
significance that isn't there.

So the analysis collapses to **per-item means first** — for MC, the fraction
of a model's runs that answered the item correctly; for open-ended, the mean
composite score across runs — and every bootstrap resamples *items*. The
uncertainty being quantified is item-sampling uncertainty: "how would this
score move if we had drawn a different set of questions from the same
domain?", which is the question a benchmark consumer actually has.
Run-to-run stochasticity is not discarded; it is reported separately as the
mean within-item standard deviation across runs (`run_variance`).

The bootstrap itself is the plain percentile bootstrap over the per-item
values $x_1,\dots,x_n$:

$$
\hat{\theta}^{*(b)} = \frac{1}{n}\sum_{i=1}^{n} x_{I_i^{(b)}},\qquad
I_i^{(b)} \sim \text{Uniform}\{1,\dots,n\},\qquad
\text{CI} = \left[\hat{\theta}^{*}_{(\alpha/2)},\; \hat{\theta}^{*}_{(1-\alpha/2)}\right]
$$

with $B$ = `stats.bootstrap_resamples` from
[`configs/run_config.yaml`](../../configs/run_config.yaml).

What enters the per-item map is already filtered: call failures and genuine
served-model fallbacks are treated as *missing data*, not as wrong answers
(see [measurement-integrity.md](measurement-integrity.md)). Scoring a
transport failure as 0 would penalize a model for the harness's problems.

## Smoothed Monte-Carlo p-values

Paired model comparisons use a paired bootstrap on the per-item differences
$d_i = a_i - b_i$ over the items both models answered. The two-sided p-value
uses add-one smoothing:

$$
p = \min\!\left(1,\; 2\cdot\frac{\min\big(\#\{\bar d^{*}\le 0\},\, \#\{\bar d^{*}\ge 0\}\big) + 1}{B + 1}\right)
$$

The `+1` in numerator and denominator is not decoration. A raw Monte-Carlo
proportion can be exactly zero whenever none of the $B$ resamples crosses
zero — reporting $p = 0$ from a finite simulation is a claim no finite
simulation can support. The smoothed estimator has a resolution floor of
$1/(B+1)$ per side: the smallest reportable p-value honestly reflects how many
resamples were drawn. (This is the standard permutation-test correction; see
Davison & Hinkley.)

## Holm, not Bonferroni

With a cohort of twenty-three models, one phase produces $\binom{23}{2} = 253$
pairwise comparisons — a genuine multiplicity problem, and one that grows
quadratically: the nine-model v0.1 cohort produced 36. We correct with the Holm
step-down procedure, applied over all pairwise comparisons within one phase
(MC and open are corrected as separate families):

$$
\tilde p_{(k)} = \max_{j \le k}\; \min\!\big(1,\; (m - j + 1)\, p_{(j)}\big)
$$

where $p_{(1)} \le \dots \le p_{(m)}$ are the sorted raw p-values. Holm
controls the family-wise error rate at the same level as Bonferroni, under the
same (i.e. no) independence assumptions — it is valid for arbitrary dependence
among the tests, which matters here because 253 comparisons among 23 models are
heavily entangled (every model appears in 22 of them). And it is uniformly more
powerful: every hypothesis Bonferroni rejects, Holm also rejects, and
sometimes more. Given that strict dominance, there is no reason to prefer
Bonferroni. Sharper procedures (Hochberg, Benjamini–Hochberg FDR) buy power by
adding assumptions or changing the error criterion; at this scale the
conservative FWER guarantee is worth keeping.

Each pairwise entry carries both the raw bootstrap p and the Holm-adjusted
`p_holm`, plus a `significant_holm` flag at $\alpha = 0.05$.

That resolution floor interacts with the correction, and it is why $B$ was
raised from 10,000 to 100,000. The two-sided smoothed p bottoms out at
$2/(B+1)$, so at $B = 10{,}000$ even a maximally separated pair can report no
p-value below $\approx 2\times10^{-4}$. Holm scales the smallest raw p by the
full family size ($m = 253$), and $2\times10^{-4}\times 253 \approx 0.0506 >
0.05$ — so *every* pair fails the $\alpha = 0.05$ flag for want of Monte-Carlo
resolution, not for want of separation. Raising $B$ to 100,000 drops the floor
to $\approx 2\times10^{-5}$ and restores ample headroom below the threshold.

## Clopper–Pearson at the ceiling

Frontier models sit near the MC accuracy ceiling, and near
$\hat p \approx 1$ interval estimates degenerate. The normal approximation
$\hat p \pm z\sqrt{\hat p(1-\hat p)/n}$ collapses to zero width at
$\hat p = 1$, and the percentile bootstrap does the same: if every per-item
value is 1, every resample mean is 1, and the "interval" is $[1, 1]$ — an
absurd claim of certainty from a finite item set.

So alongside the bootstrap CI, each model's MC overall carries an exact
Clopper–Pearson interval over item-majority correctness ($k$ items with
per-item accuracy $\ge 0.5$ out of $n$ items):

$$
\text{lo} = \text{Beta}^{-1}\!\left(\tfrac{\alpha}{2};\, k,\, n-k+1\right),\qquad
\text{hi} = \text{Beta}^{-1}\!\left(1-\tfrac{\alpha}{2};\, k+1,\, n-k\right)
$$

with $\text{lo}=0$ when $k=0$ and $\text{hi}=1$ when $k=n$. At $k=n$ the
lower bound stays properly below 1 — the exact interval keeps saying "you
only had $n$ items" when every approximation has stopped talking.
Clopper–Pearson is conservative (coverage at least, not exactly, the nominal
level); at a ceiling, conservative is the honest direction to err.

## McNemar for paired binary outcomes

The paired bootstrap compares means; for MC there is also a sharper paired
question — on which items do two models *disagree*? McNemar's test uses only
the discordant items ($b$ = A right & B wrong, $c$ = A wrong & B right, on
per-item majority correctness). The primary path is `statsmodels`' exact
binomial McNemar when $b + c < 25$, chi-square otherwise. If statsmodels is
unavailable, a self-contained fallback uses the Edwards continuity-corrected
statistic:

$$
\chi^2 = \frac{\big(\max(0,\, |b - c| - 1)\big)^2}{b + c}
$$

The clamp at 0 matters: the uncorrected $|b-c|-1$ goes negative when $b = c$,
and squaring a negative correction fabricates signal exactly where there is
none. $b + c = 0$ (no discordant items) returns $p = 1$.

## Judge agreement: Krippendorff's alpha

Open-ended responses are scored by a persona panel — one judge model prompted
as three personas (see [judge-design.md](judge-design.md)). How much the
personas agree is itself a reported result, measured with Krippendorff's
alpha under the interval difference metric $\delta^2(v_i, v_j) = (v_i - v_j)^2$:

$$
\alpha = 1 - \frac{D_o}{D_e}
$$

where $D_o$ is the observed disagreement within units and $D_e$ the
disagreement expected if ratings were exchanged at random across all units.

Why alpha and not a kappa? The persona scores are **interval-scaled** (1–5
per dimension; disagreeing by 1 point is not the same as disagreeing by 4,
and a categorical statistic would treat them identically), and the data has
**missing cells** (a persona whose output failed to parse contributes nothing
for that unit). Krippendorff's alpha handles both natively — units with fewer
than two ratings simply drop out of the pairable set.

Two implementation decisions are worth knowing:

- When $D_e = 0$ (all ratings identical everywhere) the function returns
  `None`, not $1.0$. Alpha is mathematically undefined there, and constant
  ratings are no *evidence* of reliability — a panel that always says "4" agrees
  perfectly and measures nothing.
- Alpha is computed on the composite **and per judge dimension separately**,
  with the minimum single-dimension alpha reported alongside. Averaging the
  dimensions before computing agreement smooths over per-dimension
  disagreement and inflates the headline number.

Only primary-judge rows enter the IRR; crosscheck-judge rows are sensitivity
data, kept separate (see
[../how-to/run-judge-crosscheck.md](../how-to/run-judge-crosscheck.md)).

## Fleiss' kappa, where the data is categorical

Where raters pick a *category* rather than a scale point, Fleiss' kappa is the
right instrument. It is used in question validation
([`deseretbench/validate_questions.py`](../../deseretbench/validate_questions.py)):
the validation personas each independently answer every candidate MC item, and
kappa over their chosen answer letters (six categories) measures whether the
answer key is something independent readers converge on. Fleiss' kappa
requires an equal number of raters per unit, so items are restricted to the
modal rater count before computing. The implementation raises `ValueError` on
ragged rows or out-of-range categories rather than silently dropping them —
a silently repaired input returns a plausible-looking but wrong statistic.

## Item analysis

Classical test theory rounds out the picture: per-item difficulty (proportion
correct across all model×run respondents) and *corrected* item–total
point-biserial discrimination — each item's 0/1 vector correlated against the
respondent totals **excluding that item**, since including it correlates the
item with itself. Items whose vector or rest-total has zero variance get
`discrimination = None` (undefined, not zero). The respondent matrix is built
from the same post-exclusion scoreable sets as the model scores, and items
missing any respondent are dropped so the matrix is complete. This is how the
benchmark audits itself: ceiling items, floor items, and low-discrimination
items are counted and listed in the summary.

## Deterministic seeding

Reproducibility is a project principle, so every random draw is replayable.
One shared seed would be a subtle bug: every bootstrap in the analysis would
reuse the bit-identical resample index stream, coupling statistics that
should be independent. Instead each call site derives a child seed from a
stable label:

```python
def derive_seed(base: int, *parts: str) -> int:
    h = sha256((str(base) + ":" + ":".join(parts)).encode()).digest()
    return int.from_bytes(h[:8], "big") % (2 ** 63)
```

`base` is `stats.rng_seed` from the run config; the labels name the call site
(e.g. `derive_seed(seed, "mc-overall", model_id)`,
`derive_seed(seed, "open-pair", model_a, model_b)`). Every stream is
decorrelated from every other, and every one is reproducible from the config
seed alone — change nothing, and `analyze` regenerates `summary.json`
bit-for-bit. The same discipline covers non-stats sampling, e.g. the judge
crosscheck subset (`pick_crosscheck_keys`) is a seeded `random.Random(seed)`
sample.

## What we deliberately do not do

**No Bayesian model.** A hierarchical Bayesian treatment (partial pooling
across items and models, posterior intervals) would be defensible, but it
adds a prior-specification argument and an inference stack (MCMC or
variational) to a pilot whose value is that anyone can re-derive every number
with numpy, scipy, and a seed. Percentile bootstraps and exact binomial
intervals are auditable by inspection.

**No mixed-effects models.** The "right" general machinery for
runs-nested-in-items-crossed-with-models is a mixed-effects (multilevel)
model with item and model random effects. We approximate its key insight —
that runs within an item are correlated — by aggregating to per-item means
before resampling, which removes the dominant pseudo-replication at the cost
of ignoring finer structure (e.g. differing run counts per item after
failures, item-by-model interaction variance). At v0.1 scale — a twenty-three-model
cohort over 213 MC and 40 open items, with five and three runs respectively —
the per-item aggregation captures nearly all of what a mixed model would, and
the simple estimator's behavior is easy to verify. This is fine for now, and
it is on the horizon: as the item bank and cohort grow, and especially if run
counts become uneven by design, a mixed-effects (or Bayesian hierarchical)
treatment is the natural successor, with the current bootstrap kept as a
cross-check.

**No one-number leaderboard fetishism.** Every mean ships with its interval,
its $n$, and its exclusion counts; pairwise claims ship with multiplicity
correction. Where the instrument stops discriminating (the MC ceiling), the
statistics are chosen to say so rather than to hide it.

## Related

- [measurement-integrity.md](measurement-integrity.md) — how records get excluded before any statistic runs
- [judge-design.md](judge-design.md) — what the persona panel is and is not
- [../reference/data-formats.md](../reference/data-formats.md) — `summary.json` field-by-field
- [../how-to/rerun-analysis.md](../how-to/rerun-analysis.md) — regenerate every number yourself
