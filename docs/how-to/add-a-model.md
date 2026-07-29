# How to add a model to the cohort

Goal: add one model to the evaluated cohort, run it on both phases, and regenerate
the analysis — without re-paying for the models you already ran.

For what the config keys mean, see [../reference/configuration.md](../reference/configuration.md).
For a first end-to-end walkthrough, see [../tutorials/first-run.md](../tutorials/first-run.md).

## Prerequisites

- The repo set up per [../tutorials/first-run.md](../tutorials/first-run.md)
  (`uv venv --python 3.12 .venv; uv pip install --python .venv/bin/python -e .`).
- The model must be servable by the **authenticated `claude` CLI** on this machine
  (the default backend is `claude_cli`; there is no API key in the reference
  environment). A model id that the CLI cannot serve fails every call.

## 1. Probe the model cheaply

The runner invokes the CLI as `claude -p --model <id> --tools "" --system-prompt
<system> --output-format json --effort <effort> --no-session-persistence`, with the
prompt on stdin (see `_call_cli` in `deseretbench/runner.py`). Reproduce that shape
with a one-token question before committing to a full run:

```bash
echo "What is 7+5? Reply with only the number." | \
  claude -p --model <model-id> --tools "" \
    --system-prompt "You are answering a knowledge assessment." \
    --output-format json --effort low --no-session-persistence
```

Or use the runner's built-in smoke test, which exercises the exact code path
(including the cache and the served-model guard):

```bash
.venv/bin/python -m deseretbench.runner --model <model-id>
```

Check the JSON output for two things:

- No error / `is_error`. A 404-style "model not found" is a permanent error — the
  runner fails it fast without retries (`_PERMANENT_ERROR_MARKERS` in
  `deseretbench/runner.py`).
- The served model matches. The runner marks a call failed with `served_mismatch`
  if the CLI silently serves a different model; only alias ↔ dated-snapshot
  resolution (e.g. `claude-opus-4-8` ↔ `claude-opus-4-8-YYYYMMDD`) is tolerated
  (`_served_matches` in `deseretbench/runner.py`). Pick the id form you probed.

## 2. Add the model to `configs/models.yaml`

Append an entry to the `cohort:` list. Each entry has exactly four keys:

```yaml
cohort:
  # ... existing entries ...
  - id: claude-example-9          # the id the CLI serves (step 1)
    tier: sonnet                  # tier grouping used in reports (fable/opus/sonnet/haiku so far)
    label: "Example 9"            # human-readable name for tables and figures
    generation: 9.0               # numeric generation for progression plots
```

Leave the `judges:` block alone — it selects the judge model and personas, not the
evaluated cohort, and changing it invalidates comparability of judge scores across
runs.

There is no need to touch `configs/run_config.yaml`: effort levels, run counts,
prompts, and the system prompt are deliberately held identical across all models.

## 3. Check effort handling for new model families

How the "effort" setting reaches the model depends on the backend:

- **`claude_cli` backend (default):** effort is passed verbatim as `--effort` for
  every model. Nothing to do.
- **`openai_compat` backend:** for any OpenAI-compatible provider (OpenAI, Grok,
  DeepSeek, GLM, Kimi, OpenRouter, a local proxy). The abstract effort is *not*
  sent as `reasoning_effort` unless `openai_map_effort: true`, since many
  providers 400 on an unknown field. Full setup — base URL, key env var, cohort
  entry — is in [run-any-model.md](run-any-model.md).
- **`anthropic_api` backend:** `deseretbench/runner.py` decides per family between
  adaptive thinking + `output_config.effort` and the legacy
  `thinking.budget_tokens` path. The family lists are the module-level tuples
  `_ADAPTIVE_FAMILIES` and `_XHIGH_FAMILIES` in `deseretbench/runner.py`
  (`_api_reasoning_params`). A model family newer than those lists will fall
  through to the `budget_tokens` path, which newer families may reject with a 400
  — in that case add the family substring to `_ADAPTIVE_FAMILIES` (and to
  `_XHIGH_FAMILIES` if it supports `xhigh`). That is the one place a new model can
  require a code change.

## 4. Run both phases

The cheapest correct move is to re-run the full pipeline: every call is
content-addressed and cached in `./cache`, so all calls for the existing cohort
return instantly from cache at zero cost — **only the new model's calls (and the
judge calls on its open-ended responses) cost anything**.

Unattended, rate-limit-safe (recommended — question set must already be balanced):

```bash
bash scripts/finish_pipeline.sh runs/v0_1
```

Or run the phases by hand:

```bash
.venv/bin/python -m deseretbench.run_benchmark mc \
  --questions data/questions_mc.jsonl --out runs/v0_1
.venv/bin/python -m deseretbench.run_benchmark open \
  --questions data/questions_open.jsonl --out runs/v0_1
```

Notes:

- With no `--models` flag, the full `models.yaml` cohort runs. You *can* pass
  `--models <new-id>` to run only the new model, but the output file for the phase
  is rewritten from that run's jobs — a single-model run produces a single-model
  `mc_responses.jsonl`. To keep a complete run directory, run the full cohort and
  let the cache do the saving.
- A typo'd id in `--models` is a hard error (`SystemExit` listing the valid
  cohort), never silently ignored.
- If the run is interrupted or hits rate limits, see
  [recover-interrupted-run.md](recover-interrupted-run.md). Note that the
  resilient wrapper's completeness check assumes a full-cohort, full-set run.

## 5. Regenerate analysis and reports

`finish_pipeline.sh` already does this. If you ran the phases by hand:

```bash
.venv/bin/python -m deseretbench.analyze --run runs/v0_1 --out results/summary.json
.venv/bin/python -m deseretbench.report --summary results/summary.json
```

Results land in `reports/RESULTS.md`, `reports/leaderboard.html`, and
`reports/figures/`. Read numbers from there; do not copy them into other documents
by hand (see [regenerate-reports.md](regenerate-reports.md)).
