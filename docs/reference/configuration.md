# Configuration reference

This page describes every key in the two YAML config files and the essentials of
`pyproject.toml`. For *how to change* a configuration (add a model, change repeat
counts), see the how-to guides ([add a model](../how-to/add-a-model.md),
[re-run analysis](../how-to/rerun-analysis.md)). For *why* the values are what they
are, see the explanation pages ([judge design](../explanation/judge-design.md),
[statistics](../explanation/statistics.md)).

Two files define a benchmark run:

| File | Role | Read by |
|---|---|---|
| `configs/models.yaml` | Who is measured (the cohort) and who judges | `deseretbench/run_benchmark.py` |
| `configs/run_config.yaml` | The controlled experimental constants — held identical across all models so comparisons are valid | `run_benchmark.py`, `analyze.py`, `author.py`, `validate_questions.py` |

Both are snapshotted into `runs/<version>/config_snapshot.json` at run time by
`run_benchmark.py` (`write_config_snapshot`), so a run directory records the exact
configuration that produced it.

---

## configs/models.yaml

### `cohort`

A list of model entries. Each entry has four required keys plus one optional:

| Key | Type | Meaning |
|---|---|---|
| `id` | string | Model id passed verbatim to the backend (`claude --model <id>`, the Messages API, or the Ollama server). May be an alias (`claude-opus-4-8`) or a dated snapshot (`claude-opus-4-5-20251101`); the runner tolerates alias↔dated-snapshot resolution but rejects any other served-model mismatch (see [cache.md](cache.md)). |
| `tier` | string | Capability tier, used for within-tier generational comparisons in the reports. Claude tiers: `fable`, `opus`, `sonnet`, `haiku`. Local open-weights tiers are one per model family (e.g. `qwen3`, `gemma`, `phi`, `smollm`, `deepseek`). |
| `label` | string | Human-readable name used in tables and figure legends (e.g. `"Opus 4.8"`). |
| `generation` | number | Model generation (e.g. `4.6`, `5.0`), used to order models within a tier. For local families this is the parameter count in billions, so per-tier report lines read as scaling curves. |
| `backend` *(optional)* | string | Pins this entry to a specific backend (e.g. `ollama`). Entries without it use `runner.backend` from `run_config.yaml`. The effective backend is part of the cache key ([ADR-0011](../adr/0011-local-open-weights-backend.md)). |

The current cohort is twenty-three models over two serving paths.

Ten are Claude models reached through the authenticated `claude` CLI: one `fable`,
five `opus`, three `sonnet`, one `haiku`, spanning generations 4.5–5.0. Per the
file's header comment, that set is whatever the CLI genuinely serves in this
environment (probed 2026-06-05, expanded 2026-07-03 under CLI v2.1.200, then
again 2026-07-25 to add Opus 5); `claude-mythos-5` is unavailable here, and
legacy 3.5/3.7 models are excluded because they error under the current
reasoning-mode configuration.

Thirteen are local open-weights models (0.6B–4B) pinned with `backend: ollama` and
served by a user-space Ollama (CPU for the original cohort; a single consumer GPU for the
2026 families, per ADR-0013): tiers `qwen3` (0.6B/1.7B/4B), `gemma`
(1B/4B), `smollm` (1.7B), `phi` (3.8B), `deepseek` (1.5B), `granite` (3B),
`qwen3.5` (4B), `ministral` (3B), `nemotron` (4B), and `gemma4` (E2B). For these, `tier`
is the model family and `generation` is the parameter count in billions, so each
per-tier report line reads as a within-family scaling curve
([ADR-0011](../adr/0011-local-open-weights-backend.md)).

`run_benchmark.py` runs the whole cohort by default; its `--models` flag takes a
comma-separated subset of ids, and an unknown id is a hard error
(`select_cohort`, `run_benchmark.py:74-87`) rather than a silently empty run.

### `judges`

Configuration for open-ended scoring. Note carefully: the judge "panel" is **one**
judge model prompted as three personas, not three independent judge models.

| Key | Current value | Meaning |
|---|---|---|
| `primary_model` | `claude-sonnet-4-6` | The single judge model. Every open-ended response is scored three times by this model, once per persona. |
| `crosscheck_model` | `claude-opus-4-8` | A second judge model used only when `run_benchmark.py open --judge-crosscheck` is passed: it re-judges a seeded subset to measure judge-model sensitivity. Implemented but not yet run for v0.1. Required (hard error) if `--judge-crosscheck` is set and the key is absent. |
| `personas` | `[seminary_teacher, byu_religion_professor, bishop]` | The three judging personas the primary model is prompted as. |
| `crosscheck_fraction` | `0.25` | Fraction of (model, item, run) triples the crosscheck model re-judges. Default if absent: `0.25` (`run_benchmark.py:334`). The subset is selected with the seed from `stats.rng_seed` (default `0` if absent on that path). |

---

## configs/run_config.yaml

Everything in this file is held identical across all models. Keys are listed with
their current value, the default used when the key is absent, and the code that
reads them. "Required" means the reading code indexes the key directly and will
raise `KeyError` if it is missing.

### `runner`

Read by `Runner.__init__` (`deseretbench/runner.py:320-333`), which receives the
`runner` mapping from `run_benchmark.py`, `author.py`, and
`validate_questions.py` (all three load this file).

| Key | Current value | Default if absent | Notes |
|---|---|---|---|
| `backend` | `claude_cli` | `claude_cli` | `claude_cli` \| `anthropic_api` \| `ollama`. The default for cohort entries that don't pin their own `backend:`. The API backend requires `ANTHROPIC_API_KEY` and the `api` extra (`pip install -e '.[api]'`); `ollama` requires a local server ([ADR-0011](../adr/0011-local-open-weights-backend.md)). |
| `ollama_host` | `http://localhost:11434` | `http://localhost:11434` | Base URL of the local Ollama server (`ollama` backend only). |
| `ollama_num_predict` | `4096` | `4096` | Per-call generation cap (`ollama` backend only) — bounds runaway reasoning loops. |
| `ollama_num_ctx` | `8192` | `8192` | Per-call context window (`ollama` backend only), sized for one-model-at-a-time CPU serving. |
| `tools` | `""` | `""` | Passed to the CLI as `--tools ""` — no tool use on any call. |
| `no_session_persistence` | `true` | `true` | Appends `--no-session-persistence` to the CLI argv. |
| `max_retries` | `4` | `4` | Maximum attempts per call. Permanent errors (auth, unknown model, `served_mismatch`, …) fail fast without retrying. |
| `retry_backoff_seconds` | `5` | `5` | Sleep between attempts is **linear**: `backoff * attempt` (5 s, 10 s, 15 s with defaults) — not exponential (`runner.py:374`). |
| `timeout_seconds` | `1200` | `240` (Runner default) | Per-call subprocess/API/HTTP timeout. Sized as headroom for Fable 5 high-effort turns and CPU-bound local thinking models. **Explicitly excluded from the cache key** — changing it never invalidates cached responses. `author.py:257` additionally floors it at 300 s. |
| `max_parallel` | `8` | `8` | Thread-pool width for `Runner.map`. Overridden by `--max-parallel` in `run_benchmark.py` and `author.py`, and by the caller in `validate_questions.py`. |
| `cache_dir` | `cache` | `cache` | Response-cache directory, resolved relative to the repo root by `run_benchmark.py:131,223`. **Honored only by `run_benchmark.py`**: `author.py:258` and `validate_questions.py:101` hardcode `ROOT/'cache'` and ignore this key. Today the value is also `cache`, so all three share one cache — but changing this key would silently split the caches. See [cache.md](cache.md). |

### `effort`

Reasoning budget pinned per item class, constant across models. Read by
`run_benchmark.py` (lines 140, 232, 290).

| Key | Current value | Default if absent |
|---|---|---|
| `multiple_choice` | `low` | required |
| `open_ended` | `high` | required |
| `judge` | `medium` | `medium` (`run_benchmark.py:290` uses `.get`) |

Effort **is** part of the cache key: changing an effort value re-runs (and
re-bills) that item class.

### `runs`

Repeat counts per model per item, for run-to-run variance and bootstrap CIs. Read
by `run_benchmark.py:139,231`; the `--runs` CLI flag overrides either value.

| Key | Current value | Default if absent |
|---|---|---|
| `multiple_choice` | `5` | required |
| `open_ended` | `3` | required |

### `system_prompt`

A single neutral test-taker system prompt, identical for every model and item
("You are answering items on a written knowledge assessment…"). Required; read by
`run_benchmark.py:141,233`. Part of the cache key.

### `mc_prompt_template`

Jinja2 template for multiple-choice items. It renders `{{ question }}` and
iterates `lettered_choices`, and instructs the model to end its response with a
line in exactly the format `ANSWER: <letter>` (the MC parser keys on this).
Required; read by `run_benchmark.py:142`. Part of the cache key (via the rendered
prompt text).

### `open_prompt_template`

Jinja2 template for open-ended items; currently just `{{ prompt }}` (the item text
is passed through unchanged). Required; read by `run_benchmark.py:234`.

### `stats`

Read by `analyze.py:307-311` and `validate_questions.py:279-281`.

| Key | Current value | Default if absent | Read by |
|---|---|---|---|
| `bootstrap_resamples` | `100000` | required | `analyze.py:311` |
| `rng_seed` | `19470417` | required in `analyze.py`/`validate_questions.py`; `0` on the judge-crosscheck path (`run_benchmark.py:335` uses `.get`) | `analyze.py:311`, `validate_questions.py:280`, `run_benchmark.py:335` |
| `holdout_fraction` | `0.20` | required | `validate_questions.py:281` (public/holdout split of the validated pool; see [holdout stance](../explanation/holdout-stance.md)) |
| `ci_level` | `0.95` | required | `analyze.py:311` |

The seed is an arbitrary fixed value chosen once for reproducibility.

---

## pyproject.toml essentials

| Field | Value |
|---|---|
| `name` / `version` | `deseretbench` / `0.1.0` |
| `requires-python` | `>=3.12` |
| Runtime dependencies | `numpy>=1.26`, `scipy>=1.11`, `pandas>=2.1`, `matplotlib>=3.8`, `jinja2>=3.1`, `pyyaml>=6.0`, `tqdm>=4.66`, `statsmodels>=0.14` |
| Optional extras | `api` = `anthropic>=0.40` (Messages API backend); `hub` = `datasets>=2.18` + `huggingface_hub>=0.23` (Hugging Face publishing) |
| Dev dependencies | uv-style `[dependency-groups]` `dev` group: `pytest>=8`. Install with `uv pip install --python .venv/bin/python --group dev`. There is no pytest config file (no `[tool.pytest.ini_options]`, `pytest.ini`, or `conftest.py`); pytest runs on defaults against `tests/`. |
| Build system | hatchling; the wheel packages only the `deseretbench/` directory |
| License field | `license = { text = "CC-BY-NC-SA-4.0 (data) / MIT (code)" }`. **Caveat:** this is descriptive text, not a valid single SPDX license expression — it documents the dual-licensing intent (data vs. code) but will not parse as SPDX. |

## See also

- [cache.md](cache.md) — what the response cache stores and what invalidates it
- [cli.md](cli.md) — command-line flags that override config values
- [data-formats.md](data-formats.md) — record schemas of the files these configs produce
