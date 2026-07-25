# How the judge is designed (and its biases)

*Explanation — why the open-ended scoring works the way it does, and where it is
weakest. For the mechanics, see [data formats](../reference/data-formats.md) and the
[glossary](../reference/glossary.md); to actually run the cross-check, see
[how to run the judge cross-check](../how-to/run-judge-crosscheck.md).*

## Why judged open-ended at all

Two reasons, one empirical and one intrinsic.

The empirical one: multiple-choice saturates. v0.1's frontier cohort clears the
public MC set at or near ceiling ([PAPER.md §4.1](../../PAPER.md)), so among current
top models the MC track has stopped discriminating. Whatever signal separates them
has to come from somewhere else.

The intrinsic one: the benchmark's third axis — life-choice alignment — is not a
multiple-choice quantity even in principle. "Should I take this job offer that
requires working Sundays?" has no keyed letter. What can be assessed is the *quality*
of a written answer: whether it is doctrinally accurate, culturally real, practically
wise, and distinctively LDS rather than generic good advice. That is a rubric
judgment, and in v0.1 the rater is an LLM.

Each open item ships a rubric (`must_include` points, `should_not` failure modes, an
`ideal_reasoning_pattern`), authored alongside the item and reviewed in validation.
The judge scores against that rubric — not against its own free-floating opinion of
a good answer.

## The panel: one model, three personas

Every response is scored three times by **a single judge model**
(`judges.primary_model` in [configs/models.yaml](../../configs/models.yaml), currently
`claude-sonnet-4-6`), prompted under three different personas
(`deseretbench/judge.py`):

| Persona | Stance it encodes |
|---|---|
| `seminary_teacher` | "an experienced Latter-day Saint seminary teacher who knows the standard works and how to explain doctrine plainly to youth" — plain-doctrine correctness, accessibility |
| `byu_religion_professor` | "a BYU religion professor with deep knowledge of doctrinal development, Church history, the Gospel Topics Essays, and where genuine ambiguity exists" — scholarly nuance, tolerance for real ambiguity |
| `bishop` | "a serving bishop who counsels members through real life decisions with both doctrinal fidelity and pastoral compassion" — pastoral judgment, practical wisdom |

Each persona returns strict JSON: four 1–5 dimensions (`doctrinal_accuracy`,
`cultural_authenticity`, `practical_wisdom`, `distinctiveness`), rubric-coverage
counts (`must_include_hits` / `must_include_total`), a `should_not_violations`
count, and a one-sentence justification. `aggregate_panel` averages the panel and
maps the composite 1–5 mean to 0–100 via `(x − 1) / 4 × 100`.

**Why personas instead of three different judge models?** Cost and plumbing. v0.1
runs in a CLI-only environment (no API key), against one vendor's model lineup;
three genuinely independent judges from different vendors were not available, and
tripling judge spend on the same lineup would have bought correlated opinions at
three times the price. The personas are an attempt to get *perspective* diversity —
plain-doctrine vs. scholarly vs. pastoral — out of a single model.

**Be clear about what this is not.** Three personas on one model are **not three
independent raters**. They share every weight, every training bias, and every blind
spot of the underlying model. Agreement between them is much cheaper than agreement
between independent judges would be, and must be interpreted accordingly.

## What Krippendorff's alpha does and does not establish

`deseretbench/analyze.py` computes Krippendorff's alpha (interval metric,
missing-data tolerant — `stats.krippendorff_alpha_interval`) over the three
personas' scores, both on the composite and per dimension, and reports the minimum
single-dimension alpha alongside the headline so that a smooth composite cannot hide
per-dimension disagreement. Current values live in
[reports/RESULTS.md](../../reports/RESULTS.md); they are not repeated here.

What high alpha here establishes: **internal consistency**. The scoring procedure is
stable — the persona prompts do not send the same model to wildly different verdicts,
and the panel mean is not an average over noise.

What it does not establish: **external validity**. It says nothing about whether a
seminary teacher, a professor, or a bishop — the actual humans — would agree with
these scores. One model agreeing with itself under three hats is a reliability floor,
not a validity claim. The same caveat applies to the item-validation pipeline (five
reviewer personas, one model, Fleiss' κ), and the project applies it there too
([PAPER.md §6](../../PAPER.md)).

## The same-family bias problem

The judge is a Claude model scoring a cohort of Claude models — it is literally a
cohort member. LLM-as-judge self-preference and family-preference effects are
documented in the literature this project positions against (see
[RELATED_WORK.md](../../RELATED_WORK.md): the AllFaith benchmarks lean on
human-*verified* LLM judges, and the TGC benchmark uses seven named human graders
precisely where DeseretBench v0.1 uses an LLM panel). A judge that shares training
lineage with every contestant may systematically reward its family's house style —
and no within-family agreement statistic can detect that.

The designed mitigation is a **cross-check judge**: `run_benchmark open
--judge-crosscheck` re-scores a seeded 25% subset of (model, item, run) triples with
a second judge model from a different tier (`judges.crosscheck_model`, currently
`claude-opus-4-8`; fraction from `judges.crosscheck_fraction`). Raw cross-check
verdicts are written with `judge_role: "crosscheck"` alongside the primary panel's
records for sensitivity analysis. **This is implemented but has not been run** — the
mitigation exists as machinery, not yet as evidence. Note its limit even when run:
Opus and Sonnet are the same vendor family, so the cross-check probes judge-*model*
sensitivity, not judge-*vendor* independence.

## Parse-failure handling as bias avoidance

A judge that emits malformed output must not silently flatter the model being
scored. Several deliberate choices in `deseretbench/judge.py`:

- **Balanced-JSON scan, not regex.** Judge output is scanned for top-level balanced
  `{...}` spans with JSON string-state tracking, so a `}` inside a quoted
  justification cannot truncate the parse. The last span that parses as a dict *and*
  contains all four dimension keys wins; partial verdicts are rejected rather than
  half-used.
- **None, never zero.** Missing or malformed counts aggregate as *missing data*, not
  as zero. Defaulting `should_not_violations` to 0 on a parse failure would silently
  score bad data as a clean answer — the exact direction a lenient bug would bias
  the leaderboard. A persona whose output cannot be parsed simply contributes
  nothing (`n_judges` shrinks), which surfaces in the run output instead of hiding
  in the mean.
- **Clamping and capping.** Dimension scores are clamped to [1, 5] (a judge emitting
  7 counts as 5, not as an outlier bonus); non-numeric values become None;
  `must_include_hits` is capped at the judge's reported total so a miscounting judge
  cannot report more than full coverage; negative counts are dropped.

None of this makes the judge unbiased. It makes the *aggregation* refuse to convert
judge malfunction into free points.

## Where this goes

The v0.1 judge is a labeled stand-in, and [VISION.md](../../VISION.md) commits to its
successors:

- **Human raters** — the TGC-style path: real experts grading against the same
  rubrics, at least on a calibration subset, to anchor the LLM panel's external
  validity.
- **Cross-vendor judges** — diversification beyond a single model family, with
  cross-judge agreement reported the same way inter-persona reliability already is.
  The `--judge-crosscheck` machinery generalizes: the immediate step is running the
  existing Opus cross-check; the meaningful step is a judge that shares no training
  lineage with the cohort.

Until then, read every open-ended score as: *one capable model's rubric-anchored,
internally consistent opinion, rendered from three angles* — useful, reproducible,
and honestly short of ground truth.
