# How to run the judge cross-check

Goal: re-judge a deterministic 25% subset of the open-ended responses with a
second judge model, so judge-model sensitivity can be checked by hand.

Honest status first: **the cross-check is implemented but has not been run for
v0.1.** `runs/v0_1/open_judge_raw.jsonl` contains zero `crosscheck` records. The
machinery below is real and validated at setup time, but unexercised at scale —
treat this page as the recipe, not a description of published results.

Background on why the judge is designed this way:
[../explanation/judge-design.md](../explanation/judge-design.md).

## What `--judge-crosscheck` does

The primary "panel" is one judge model (`judges.primary_model` in
`configs/models.yaml`, currently `claude-sonnet-4-6`) prompted as three personas
(`seminary_teacher`, `byu_religion_professor`, `bishop`) — not three independent
judges. The cross-check probes the single biggest fragility of that design: does
a *different* judge model score the same responses the same way?

With the flag set, `run_benchmark open` additionally:

1. Takes all successfully generated `(model, question_id, run_index)` triples and
   samples `judges.crosscheck_fraction` of them (default 0.25) with a seeded RNG
   (`stats.rng_seed` from `configs/run_config.yaml`, currently `19470417`) — the
   subset is deterministic across invocations.
2. Re-judges each sampled response with `judges.crosscheck_model` (currently
   `claude-opus-4-8`), using the **same** three personas, the same judge prompt,
   and the same `effort.judge` budget.
3. Appends the verdicts to the same `runs/<run>/open_judge_raw.jsonl`, tagged
   `judge_model: <crosscheck model>` and `judge_role: "crosscheck"` (primary
   rows carry `judge_role: "primary"`).

Cross-check verdicts are raw data only. They never feed `open_scores.jsonl` or
the leaderboard — the panel scores are aggregated from primary-judge rows before
the cross-check even runs.

## 1. Run it against an existing run directory

```bash
.venv/bin/python -m deseretbench.run_benchmark open \
  --questions data/questions_open.jsonl \
  --out runs/v0_1 \
  --judge-crosscheck
```

This re-runs the whole open phase, but against a warm cache the generation and
primary-judging steps replay from disk at no API cost; only the cross-check
calls are new spend. The flag is validated before anything is spent: if
`models.yaml` has no `judges.crosscheck_model`, the command exits immediately.

Do **not** add `--limit` or `--models` when pointing at a real run directory:
the output files are rewritten wholesale, so a truncated invocation would
replace the full run's `open_*.jsonl` with a subset. Use a scratch `--out` for
trial runs.

## 2. Cost and quota considerations

Cross-check call count = round(triples × fraction) × personas. With the current
defaults (23 models × 40 open items × 3 runs = 2,760 triples, fraction 0.25,
3 personas) that is **2,070 fresh judge calls** on the cross-check model at
`effort: medium` — on the `claude_cli` backend this is a substantial bite out of
a session window. Two properties help:

- Failed calls are not cached, successful ones are, so re-running the same
  command after a rate-limit reset retries only the failures.
- The subset is seeded, so every retry targets the same triples.

One caveat: `scripts/resilient_run.sh` counts expected records without any
knowledge of cross-check rows, so do not drive a cross-check run through the
resilient wrapper or `finish_pipeline.sh` — run the command above by hand and
re-issue it if calls fail. Note also that `open_judge_raw.jsonl` is committed
atomically only after *both* primary and cross-check judging finish; an
interruption mid-crosscheck leaves the previous complete file in place and the
new one unwritten, so simply re-run (cached primary verdicts replay instantly).

## 3. What analyze does with cross-check records

Currently: nothing quantitative. `deseretbench.analyze` explicitly filters
`open_judge_raw.jsonl` to `judge_role == "primary"` rows before computing judge
IRR (Krippendorff's alpha), so cross-check verdicts can never contaminate — or
appear in — `results/summary.json`. No cross-judge agreement statistic is
computed anywhere in the codebase yet; the records exist so the comparison can
be done manually, e.g.:

```bash
jq -c 'select(.judge_role == "crosscheck")' runs/v0_1/open_judge_raw.jsonl
```

pairs with the primary rows on `(model, question_id, run_index, persona)` for a
side-by-side of the `scores` dicts. Building this comparison into analyze is
future work.

## Related

- [rerun-analysis.md](rerun-analysis.md) — recompute the summary (unaffected by
  cross-check rows, per above).
- [../reference/configuration.md](../reference/configuration.md) — the
  `judges:` block and `stats.rng_seed`.
- [../reference/data-formats.md](../reference/data-formats.md) — the
  `open_judge_raw.jsonl` record schema.
