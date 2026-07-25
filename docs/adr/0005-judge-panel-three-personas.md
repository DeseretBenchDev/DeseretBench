# ADR-0005: A one-model, three-persona judge panel

Status: Accepted

Date: 2026-06

## Context

The open-ended axes — cultural fluency and life-choice alignment — cannot be
auto-scored against a key. They need a judge that can read a paragraph of counsel
and rate its doctrinal accuracy, cultural authenticity, practical wisdom, and
distinctiveness. A human expert panel is the eventual goal
([VISION.md](../../VISION.md) horizon), but it is not feasible for a v0.1 pilot at
the volume of repeat runs the statistics require.

A single flat "rate this 1-5" judge is thin: it collapses the different lenses a
real Latter-day Saint evaluator would bring — a seminary teacher's plainness, a
scholar's awareness of where doctrine is genuinely unsettled, a bishop's pastoral
read — into one voice. And any LLM judge drawn from the same model family as the
cohort risks scoring its own relatives generously.

## Decision

Use **one judge model prompted as three personas** as a cost-feasible proxy for a
panel, and report agreement across the personas.

- **One judge model.** `configs/models.yaml` sets `judges.primary_model`
  (v0.1: `claude-sonnet-4-6`). The "panel" is that single model run three times,
  once per persona — not three independent judge models.
- **Three personas** (`deseretbench/judge.py`, `JUDGE_PERSONAS`):
  `seminary_teacher`, `byu_religion_professor`, `bishop`. Each gets the same
  rubric-embedding prompt and the same fixed system prompt, differing only in the
  persona sentence, and returns strict JSON scoring four dimensions (1-5) plus
  rubric must-include hit counts and should-not violations.
- **Aggregation and reliability.** `aggregate_panel` averages valid per-dimension
  scores across personas (missing/malformed values are treated as missing data,
  never as zero), maps the 1-5 composite to 0-100, and pools rubric coverage.
  Inter-persona agreement is reported as Krippendorff's α alongside the scores, so
  the panel's internal consistency is visible rather than assumed.
- **A crosscheck judge is designed but not yet run.** `judges.crosscheck_model`
  (an Opus-family model, `claude-opus-4-8`) over a `crosscheck_fraction` (0.25)
  subset exists to probe judge-model sensitivity. It is implemented but was
  **not run in v0.1**; its results are not part of the published numbers.

## Consequences

- **Same-family bias risk, disclosed.** The judge model shares a family with the
  evaluated cohort, so it may systematically favor relatives. We disclose this as
  a first-class limitation and treat absolute open-ended scores accordingly; the
  crosscheck judge exists precisely to measure the effect once run.
- **Three personas ≠ three independent judges.** The α we report is *inter-persona*
  agreement within one model, which is a weaker guarantee than agreement across
  genuinely independent raters. It should not be read as inter-model reliability.
- **Prompt-shaped scoring.** The judge scores against the item's rubric
  (`must_include`, `should_not`, `ideal_reasoning_pattern`); a weak rubric yields
  a weak judgment, and `must_include_total` is taken from the judge's own count,
  so a miscounting judge can skew coverage.
- The persona framing is cheap and reproducible, and it does surface lens-level
  differences a flat judge would miss — but it is a stand-in for a human panel,
  labeled as such, not a substitute for one.

## Links

- Judge code: `deseretbench/judge.py`; judge config: `configs/models.yaml`.
- Design rationale: [docs/explanation/judge-design.md](../explanation/judge-design.md).
- Running the crosscheck: [docs/how-to/run-judge-crosscheck.md](../how-to/run-judge-crosscheck.md).
- Reliability method: [docs/explanation/statistics.md](../explanation/statistics.md).
