# ADR-0002: Measure through the claude CLI, with prompts over stdin

Status: Accepted

Date: 2026-06

## Context

The evaluation environment has no Anthropic API key. What it does have is an
authenticated `claude` CLI — the same command-line surface a developer or a
tool builder actually uses. For DeseretBench that constraint is also a feature:
if we want to know what advice a member gets from AI, the honest thing to
measure is the surface real users hit, harness and all, not an idealized bare
API call.

Two decisions follow: *which* backend is canonical, and *how* prompts reach it.
On the transport question, the obvious path — passing the question text as a
command-line argument — is quietly dangerous. Item text starting with `-` can
be parsed as an option (option injection); long prompts can exceed the argv size
limit (`E2BIG`); and anything on the command line is visible to any user who
runs `ps`.

## Decision

Make the `claude` CLI the default runner backend and deliver every prompt over
**stdin**, never argv.

- The runner registers two backends (`deseretbench/runner.py`): `claude_cli`
  (default) and `anthropic_api`. `backend` is selected by
  `configs/run_config.yaml`; `claude_cli` is the v0.1 measurement path.
- The CLI argv is exactly:
  `claude -p --model <model> --tools <tools> --system-prompt <system> --output-format json --effort <effort>`,
  plus `--no-session-persistence` when requested (default on). The prompt is
  passed as `subprocess.run(cmd, input=prompt, ...)` — stdin, not argv.
- `--output-format json` gives a machine-parseable envelope; the runner reads
  `is_error`, `api_error_status`, `usage`, `modelUsage`, `result`,
  `total_cost_usd`, `duration_ms`, and `stop_reason` from it.
- `--no-session-persistence` keeps each call stateless, so no prior turn can
  leak into a later item's context.
- The `anthropic_api` backend is retained as the canonical, provider-neutral
  path for anyone who *does* have a key and wants a bare-API comparison; it
  shares the same cache and `CallResult` schema.

## Consequences

- **Absolute scores are harness-coupled.** A number produced through the CLI is
  not directly comparable to a bare-API run: the CLI may wrap the model in
  system scaffolding, and `modelUsage` sometimes reports auxiliary sub-model
  calls (e.g. a small helper) alongside the primary model. This is disclosed as
  a first-class limitation, not a footnote.
- To keep that coupling honest, the runner does **served-model verification**:
  if the model the CLI actually served does not match the one requested (allowing
  only a dated-snapshot suffix alias), the call is failed as `served_mismatch`
  rather than silently laundered. `_dominant_model` records which model carried
  the usage when several appear.
- `total_cost_usd` (hence spend accounting) is populated only on the CLI path;
  the API backend leaves cost at zero.
- The environment can never expose a secret it does not hold — but it also means
  v0.1 cannot report a bare-API baseline for the same cohort.

## Links

- Transport and backend code: `deseretbench/runner.py`.
- Why the harness coupling is acceptable: [docs/explanation/measurement-integrity.md](../explanation/measurement-integrity.md).
- Cohort discovery on this same CLI: [ADR-0010](0010-cohort-selection-by-cli-probe.md).
- Caching of these calls: [ADR-0003](0003-content-addressed-response-cache.md).
