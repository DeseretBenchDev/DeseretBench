# Reproducing DeseretBench

DeseretBench is built to be reproduced end-to-end. All randomness is seeded
(`configs/run_config.yaml: stats.rng_seed`), every model call is content-addressed
and cached, and the exact cohort / effort / prompt constants live in `configs/`.

## 0. Environment

```bash
# Python via uv (pinned to 3.12 for wheel availability)
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .          # installs deps from pyproject
```

You need a way to call the models. Two backends are supported:

| backend | how it authenticates | notes |
|---|---|---|
| `claude_cli` (default) | the authenticated `claude` CLI (OAuth/subscription) | what this study used; carries a fixed Claude Code context overhead (~3.9k input tokens) applied identically to all models — see DESIGN.md §4.1 |
| `anthropic_api` | `export ANTHROPIC_API_KEY=...` | **canonical** path: bare Messages API, neutral system prompt, no harness overhead; closest to "raw model knowledge" |

Set `runner.backend` in `configs/run_config.yaml` accordingly (`pip install -e '.[api]'`
for the API backend).

> **Scoring the shipped set vs. regenerating the dataset.** To reproduce the
> *measurement* (steps 3–4), use the shipped `data/questions_{mc,open}.jsonl`
> as-is — they are already validated and position-balanced. Steps 1–2b
> *regenerate the dataset from scratch*: they require live authoring calls and
> will OVERWRITE the shipped question files with newly authored ones.

## 1. Author the question set  (≈ 250–330 candidate items) — regeneration only

Pure-Python, parallel, resumable (skips cells already written):

```bash
.venv/bin/python -m deseretbench.author --max-parallel 8
```

(Historical note: the initial run also used a multi-agent workflow,
`scripts/author_questions.wf.js`, for a subset of cells. Either path writes
`data/raw/*.jsonl`; the assembler merges them.)

## 2. Assemble → validate → finalize — regeneration only

```bash
.venv/bin/python -m deseretbench.assemble            # raw -> deduped candidate pool
.venv/bin/python -m deseretbench.validate_questions  # 5-persona blind review -> keep/drop + holdout
```

`validate_questions` writes the public set (`data/questions_{mc,open}.jsonl`), the
20% holdout split (`data/private_holdout/`, kept out of the shipped question
files), per-item reviews, and `data/validation_report.json`
(includes reviewer Fleiss' κ). Failed reviews are re-solicited once at higher
effort; items that never reach a 3-review quorum are reported as *unreviewed*,
not silently dropped.

## 2b. Balance MC answer positions (seeded) — regeneration only

**Do not run this on the shipped set** — it is already balanced, the permutation
is not idempotent, and the balance marker (`data/questions_mc.jsonl.balance_meta.json`)
makes a second run refuse by default. After re-authoring (which removes the marker
via `scripts/run_all.sh`, or remove it yourself alongside the regenerated file):

```bash
.venv/bin/python -m deseretbench.balance_positions --in data/questions_mc.jsonl --out data/questions_mc.jsonl --seed 19470417
.venv/bin/python -m deseretbench.balance_positions --in data/private_holdout/mc.jsonl --out data/private_holdout/mc.jsonl --seed 20250101
```

Permutes each item's choices (and `distractor_types`) and redraws the correct slot
uniformly at random, preserving `question_id`. It writes the balance marker plus a
position map (per item, `order[k]` = the pre-balance index of the choice now at slot k) and keeps a local `*.prebalance.jsonl` backup
(not distributed). This removes a key-position bias (authoring left correct == `B`
~51% of the time); on the shipped balanced set the largest key share is ~29%.

## 3. Run the benchmark  (cohort × repeat runs)

```bash
.venv/bin/python -m deseretbench.run_benchmark mc   --questions data/questions_mc.jsonl   --out runs/v0_1
.venv/bin/python -m deseretbench.run_benchmark open --questions data/questions_open.jsonl --out runs/v0_1
```

Resumable: re-running fills only gaps (the runner cache is content-addressed).
Restrict with `--models claude-opus-4-8,claude-haiku-4-5-20251001`, `--runs N`,
`--limit K`, `--max-parallel P`. The `claude` CLI enforces a rolling session usage limit;
for long unattended runs use `scripts/finish_pipeline.sh`, which re-runs each phase until zero
failed calls remain (cache makes progress monotonic across reset windows).

## 4. Analyze + report

```bash
.venv/bin/python -m deseretbench.analyze --run runs/v0_1 --out results/summary.json
.venv/bin/python -m deseretbench.report  --summary results/summary.json
open reports/leaderboard.html
```

## 5. Run the test suite

```bash
uv pip install --python .venv/bin/python --group dev   # pytest
.venv/bin/python -m pytest tests/ -q
```

## 6. (Optional) lm-evaluation-harness cross-check

```bash
pip install lm-eval anthropic
# run from the repo root — the task's data path resolves against your CWD
lm_eval --model anthropic-chat --model_args model=claude-opus-4-8 \
        --tasks deseretbench_mc --include_path ./lm_eval
```

Note: the harness's `ANSWER:` regex filter is stricter than the in-repo parser
(`score_mc.parse_answer`), so cross-framework scores are a lower bound relative
to the primary path.

## Determinism & honesty notes
- Models run at default sampling with reasoning enabled; run-to-run variance is
  real and captured by repeat runs, not hidden. CIs are bootstrap over items.
- The `claude_cli` backend's absolute scores are **not** directly comparable to a
  bare-API run; within a run, all comparisons are internally valid (identical
  config across models). Report which backend you used.
