# ADR-0003: Content-addressed response cache

Status: Accepted

Date: 2026-06

## Context

Every model call costs real money and real time, and the `claude` CLI enforces a
rolling session usage limit that stops a run mid-flight. A full benchmark pass is
thousands of calls; a crash, a rate-limit wave, or a rerun of the analysis stage
must not re-buy answers that are already known. At the same time, reproducibility
demands that a cached answer be *the* answer for its exact inputs — never a stale
result served for a subtly different request.

A content-addressed cache solves both, provided the key names exactly the inputs
that determine the response and nothing that is merely an operational knob.

## Decision

Cache every successful call by a SHA-256 content address.

- **Key.** `sha256` of the canonical JSON of
  `{backend, model, system, prompt, effort, run_index}`
  (`json.dumps(..., sort_keys=True, ensure_ascii=False)`). These six fields
  determine the response.
- **Deliberately excluded from the key:** `timeout`, `tools`, `max_retries`,
  `backoff`, and `max_parallel`. These are operational knobs — changing a
  timeout must not orphan a valid answer. `run_config.yaml` documents the
  timeout exclusion inline.
- **Layout.** A flat directory of `<sha256-hex>.json` files at the repo root
  `./cache`, one per keyed tuple. Content is `CallResult.to_json()`, which drops
  the raw CLI blob so entries stay compact.
- **Success-only writes.** Only `ok` results are written. Failures — timeouts,
  429s, 5xx, empty results — are *never* cached, so a resume retries exactly the
  calls that still need an answer.
- **Guarded reads.** A cached entry is served only if `ok` is truthy *and* the
  served model still matches the request. Pre-guard silent-fallback artifacts are
  re-run rather than laundered; a corrupt/unparseable entry is silently
  recomputed.

## Consequences

- **Free replays.** Resuming a model-calling stage (the benchmark and judge
  passes) across usage-limit windows and crashes is free for work already done —
  only the still-failing calls re-run. `scripts/finish_pipeline.sh` leans on this
  to grind a pass to zero failures across reset windows. (The `analyze` and
  `report` stages are cheap for a different reason: they read `runs/` artifacts
  and make no model calls at all.)
- **Changing any keyed field re-buys everything.** Edit a prompt template, a
  system prompt, the effort ladder, or the model id, and every affected call is a
  cache miss — by design, because the answer genuinely changed, but it is a real
  cost to keep in mind before touching those inputs.
- **Two cache-dir resolutions coexist.** `run_benchmark.py` honors the
  `cache_dir` config key; `author.py` and `validate_questions.py` hardcode
  `ROOT/'cache'`. Both currently resolve to the same `./cache`, so caches are
  shared today — but changing the config key would silently split them.
- **Legacy entries are heterogeneous.** Older `.json` files predate later schema
  fields (e.g. `served_all`, `called_at`, cache-token counts). Reads reconstruct
  by field-filtering, so old hits report defaults (zeros / `None`) for the
  missing fields. Any tooling that aggregates cache files must treat those fields
  as optional.

## Links

- Cache implementation: `deseretbench/runner.py`; config keys: `configs/run_config.yaml`.
- Field-by-field walkthrough: [docs/reference/cache.md](../reference/cache.md).
- What produces the cached calls: [ADR-0002](0002-claude-cli-backend-stdin-transport.md).
- Resume workflow: [docs/how-to/recover-interrupted-run.md](../how-to/recover-interrupted-run.md).
