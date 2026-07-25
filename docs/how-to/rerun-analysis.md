# How to re-run the analysis without re-running the models

Goal: recompute `results/summary.json` — every statistic, CI, and pairwise test —
from an existing run directory, without a single model call.

This works because analysis is a pure read of the run's JSONL files. The expensive
part (model responses, judge verdicts) already lives in `runs/<run>/`; the statistics
are deterministic given the seed in `configs/run_config.yaml`.

For what the statistics mean, see [../explanation/statistics.md](../explanation/statistics.md).
To turn the refreshed summary into reports, see [regenerate-reports.md](regenerate-reports.md).

## Prerequisites

- A completed (or partially completed) run directory, e.g. `runs/v0_1`, containing
  some of: `mc_responses.jsonl`, `open_responses.jsonl`, `open_judge_raw.jsonl`,
  `open_scores.jsonl`, `config_snapshot.json`.
- The environment from [../tutorials/first-run.md](../tutorials/first-run.md)
  (`uv venv --python 3.12 .venv; uv pip install --python .venv/bin/python -e .`).

## 1. Run analyze

```bash
.venv/bin/python -m deseretbench.analyze --run runs/v0_1 --out results/summary.json
```

- `--run` is required: the run directory, relative to where you invoke it.
- `--out` defaults to `results/summary.json` and is resolved relative to the
  **repo root** (not your cwd), so the flag above is redundant but explicit.

This is exactly what the pipeline scripts do at their final step, with one cosmetic
difference:

| Script | analyze invocation | report invocation |
|---|---|---|
| `scripts/run_all.sh` (step 7) | `analyze --run "$RUN"` (default `--out`) | `report` (default `--summary`) |
| `scripts/finish_pipeline.sh` (steps 3–4) | `analyze --run "$RUN" --out results/summary.json` | `report --summary results/summary.json` |

Both end up at the same paths, because the defaults *are* `results/summary.json`
on both sides. Running analyze by hand is equivalent.

## 2. What analyze reads and writes

Inputs, all under the run directory:

- `mc_responses.jsonl` — MC section is computed only if this file exists.
- `open_scores.jsonl` — open-ended section; if missing, `summary["open"]` is `null`.
- `open_judge_raw.jsonl` — judge inter-rater reliability (primary-judge rows only).
- `config_snapshot.json` — provenance. Analyze prefers the snapshot the run wrote
  over the live config files; if it is missing or corrupt it falls back to the
  current `configs/*.yaml` with a printed WARNING, and records which path it took
  in `summary["config"]["provenance"]`.

Output: `results/summary.json`, plus MC and open leaderboards printed to the terminal.

Analyze never writes into the run directory and never calls a model.

## 3. When a re-analyze suffices

Re-running analyze (this page) is enough when the raw records are still valid and
only the downstream computation changed:

- `deseretbench/analyze.py` or `deseretbench/stats.py` changed (bootstrap, Holm,
  McNemar, item analysis, IRR, exclusion rules).
- `configs/run_config.yaml` `stats:` values changed (`bootstrap_resamples`,
  `rng_seed`, `ci_level`).
- A model was added to or removed from `configs/models.yaml` and you want the
  summary restricted/extended accordingly (records from models no longer in the
  cohort are excluded with a WARNING; a newly added model needs its responses
  generated first — see [add-a-model.md](add-a-model.md)).

## 4. When you must re-run a benchmark phase (but the cache makes it cheap)

Some numbers are baked into the run files at benchmark time, not analyze time:

- MC correctness (`correct`, `parsed_letter`) is scored inline by
  `run_benchmark mc` when it writes `mc_responses.jsonl`.
- The open-ended composite (`composite_100` etc. in `open_scores.jsonl`) is
  aggregated from judge verdicts by `run_benchmark open`.

If the MC answer parser, the judge-JSON parser, or the panel aggregation changed,
re-run the phase against the same run directory:

```bash
.venv/bin/python -m deseretbench.run_benchmark mc   --questions data/questions_mc.jsonl   --out runs/v0_1
.venv/bin/python -m deseretbench.run_benchmark open --questions data/questions_open.jsonl --out runs/v0_1
```

With a warm cache this costs almost nothing: every successful model and judge call
replays from the content-addressed cache (see [../reference/cache.md](../reference/cache.md)),
and only the scoring/aggregation code runs fresh. Then re-run analyze.

## 5. When responses genuinely must be regenerated

The cache key is a sha256 over exactly six fields (`_cache_key` in
`deseretbench/runner.py`): **backend, model id, system prompt, prompt text,
effort, run_index**. Changing any of them makes every affected call a cache miss —
real API spend:

- Question text or choices (the prompt embeds them).
- `mc_prompt_template`, `open_prompt_template`, or `system_prompt` in
  `configs/run_config.yaml`.
- `effort.*` values, or the runner `backend`.
- Adding runs (`runs.multiple_choice` / `runs.open_ended` upward — new
  `run_index` values; existing indices stay cached).
- A new model id in the cohort (only that model's calls are new).

Changing `timeout_seconds`, `max_retries`, `retry_backoff_seconds`, or
`max_parallel` does **not** invalidate the cache — they are deliberately outside
the key. For long regeneration runs under CLI session limits, see
[recover-interrupted-run.md](recover-interrupted-run.md).
