# Project philosophy: FLOSS, reproducibility, and AI authorship

This page explains the values that shaped DeseretBench and the tradeoffs each one
carries. It is an *explanation* — the "why" behind decisions documented mechanically
elsewhere. For the project's guiding intent and non-goals, see
[VISION.md](../../VISION.md); for the licenses themselves, see
[`LICENSE`](../../LICENSE) and [`LICENSE-DATA`](../../LICENSE-DATA).

## Open by default, with a deliberate asymmetry

DeseretBench is two artifacts under two licenses, and the split is intentional:

- **The code is MIT.** The harness, the authoring and validation pipeline, the
  statistics, the reporting — all of it is permissively licensed. A benchmark whose
  methods are secret is an advertisement; this one is meant to be forked, rerun, and
  adapted to other traditions, so the machinery carries the least restrictive terms
  we can offer.
- **The dataset is CC BY-NC-SA 4.0.** The questions, answer keys, typed distractors,
  rubrics, and recorded model responses under `data/`, `runs/`, and `results/` are
  licensed for *evaluation, not training*. The `NonCommercial` and `ShareAlike`
  clauses are not reflexive open-source habit; they answer a specific hazard.

### Why NonCommercial-ShareAlike for the data

A benchmark loses its meaning the moment a model is trained on it. Once the items
are in a training set, a high score measures memorization rather than within-tradition
competence — the exact failure the [holdout stance](holdout-stance.md) discusses at
length. That makes the dataset unusually *gameable if trained on*, and the license is
chosen to push against that:

- **NonCommercial** signals that the questions are an evaluation instrument, not a
  free corpus to fold into a commercial training run. It does not make contamination
  impossible — a license is not a technical control — but it removes the "it was
  openly licensed for any use" defense and states the intended use in legal terms
  (`LICENSE-DATA`: "This is a research and evaluation artifact").
- **ShareAlike** keeps derivatives open: anyone who extends, corrects, or translates
  the set must share their version under the same terms, so improvements flow back to
  the commons instead of disappearing into closed forks.

The asymmetry — permissive code, protective data — is the point. We want the *recipe*
copied freely and the *test items* kept in the open but out of training pipelines.

## Local-first, no accounts

DeseretBench inherits the portfolio's local-first, privacy-by-default posture. Nothing
about running the benchmark requires an account with this project, a hosted service, or
a telemetry endpoint. Evaluation happens on the maintainer's machine through the local
`claude` CLI; model responses are stored on disk in a content-addressed cache
(`cache/`, configured by `cache_dir` in
[`configs/run_config.yaml`](../../configs/run_config.yaml)); results are files you can
read, diff, and regenerate. There is no leaderboard server to submit to and no login to
see the numbers — the numbers live in [`reports/RESULTS.md`](../../reports/RESULTS.md)
and `reports/leaderboard.html` in the repo.

This is partly principle and partly hygiene: a benchmark with no network dependencies
and no accounts is easier to reproduce, harder to silently change, and safe to run
offline once the responses are cached.

## Reproducibility as an ethic

The project's first principle is that *every number in the docs is generated, never
typed in by hand from memory*. Seeded runs, a content-addressed cache, pinned configs,
and published statistical methods exist so that anyone with the tooling can regenerate
each figure from the same inputs — see [REPRODUCE.md](../../REPRODUCE.md) for the
end-to-end path and [the statistics explanation](statistics.md) for the methods.

The ethical weight is this: a hand-copied number cannot be checked, drifts silently as
the underlying data changes, and invites the author to round in a flattering direction.
A generated number is falsifiable. So the docs point at the generated artifacts rather
than embedding scores — the authoritative results are always
[`reports/RESULTS.md`](../../reports/RESULTS.md), regenerated from `runs/`, not a table
frozen into prose. When you find a specific score in this documentation set, treat it as
a pointer to be re-derived, not a fact to be trusted on the page.

## AI authorship, disclosed

All of DeseretBench's code — and every comment in it — was written by Claude models
under human direction. This is stated up front rather than buried, because it changes
how the artifacts should be read.

A comment describes *what the code currently does*, as understood by the model that
wrote it at the time. It is not a contract, not a specification, and not
self-evidently correct. When a comment and the code disagree, the code is the fact;
when the code and a test disagree, the test is the fact; when a generated output and a
comment disagree, the output wins. Comments outrank nothing. The ordering matters most
during maintenance: it is tempting to trust a confident-sounding comment, and that
temptation is exactly what the disclosure is meant to defuse.

The right posture toward all of it is *gratitude and a grain of salt*. Gratitude,
because the pipeline exists and works; a grain of salt, because it was written by a
system that can be fluently wrong, and so nothing here is beyond checking. That is why
the audit trail exists: the project assumes its
own code is wrong until adversarially reviewed, and it publishes the corrections rather
than the illusion of a clean first draft. (See [VISION.md](../../VISION.md) principle 5
for the canonical statement this section glosses.)

## A living benchmark

DeseretBench is built to be revised, not frozen, because its subject moves at two
different speeds:

- **Doctrine changes rarely.** The core teachings the benchmark tests are stable over
  years and decades, which is what makes within-tradition competence measurable at all.
- **Policy, emphasis, and culture drift.** Handbook policy, institutional emphasis,
  leadership succession, and lived practice shift on the scale of months to a few
  years — the 2018 ministering change, the 2019 Word of Wisdom clarifications, the 2025
  succession of President Dallin H. Oaks.

The benchmark holds both facts at once. A subset of items are **currency probes** that
deliberately test whether a model's training data has kept up with recent changes (see
`data/grounding_brief.md` and the framing in [README.md](../../README.md)), and the item
set as a whole *expects revision*: as practice evolves and as the pilot's known
weaknesses get their planned successors ([VISION.md](../../VISION.md) — human expert
validation, a genuinely private holdout, judge diversification), the questions will be
updated, retired, and added to. Version numbers exist because the set is meant to grow;
a score is always a score *against a stated version of the benchmark*, not against a
timeless answer key.

## Related

- [VISION.md](../../VISION.md) — the principles and non-goals this page explains.
- [The holdout stance](holdout-stance.md) — the contamination reasoning behind the
  eval-not-training data license.
- [Measurement integrity](measurement-integrity.md) — the reproducibility and
  provenance machinery in practice.
- [`LICENSE`](../../LICENSE) / [`LICENSE-DATA`](../../LICENSE-DATA) — the MIT and
  CC BY-NC-SA 4.0 terms.
