# ADR-0010: Cohort selection by CLI probe

Status: Accepted

Date: 2026-06-05 (amended 2026-07-03: re-probe expanded the cohort to nine models)

## Context

DeseretBench evaluates the Claude models an operator can actually reach through
the authenticated `claude` CLI in this environment. That set is not a marketing
list — it is whatever the CLI genuinely serves, under the exact measurement
configuration we hold constant. A model that 404s, or that errors under the
pinned reasoning mode, cannot be measured on identical terms and must not be in
the cohort. So the cohort is defined empirically, by probing, rather than by
listing every model that nominally exists.

## Decision

Define the cohort as **the current-generation Claude models the authenticated
CLI actually serves, discovered by probe**, recorded in
[`configs/models.yaml`](../../configs/models.yaml).

- **Probe, then include.** Only models that respond under the identical
  measurement configuration (pinned effort, no tools, neutral system prompt) are
  admitted, so `run_config.yaml` stays literally constant across the cohort.
- **Documented exclusions.** `claude-mythos-5` returns 404 in this environment
  ("Project Glasswing only"). Legacy 3.5/3.7 models **error under the current
  reasoning mode** and are excluded — not because they are old, but because
  admitting them would force a different measurement config and break the
  identical-conditions guarantee.
- **The 2026-07-03 re-probe** (CLI v2.1.200) added `claude-fable-5`,
  `claude-sonnet-5`, and `claude-opus-4-5-20251101`, bringing the cohort to
  **nine** models (1 fable, 4 opus, 3 sonnet, 1 haiku; generations 4.5-5.0). The
  models.yaml header comment records the probe dates and the exclusion reasons.

## Consequences

- **The cohort is environment-dependent by design.** Re-running elsewhere, or
  later, may yield a different served set. This is a feature — we measure what is
  reachable under identical terms — but it means the cohort is a property of the
  probe, not a fixed universal list, and each run records its own snapshot.
- **Mixed dated and alias ids.** The cohort mixes dated snapshots
  (`opus-4-5-20251101`, `sonnet-4-5-20250929`, `haiku-4-5-20251001`) with
  undated aliases (`opus-4-8`, `sonnet-5`, etc.). An alias can silently move.
  This is mitigated by a **dated-suffix rule** where the CLI exposes one and by
  per-run **config snapshots** that stamp the served model into the run record,
  so provenance survives even when an alias later shifts.
- **Cohort changes mid-project must be explicit.** The Jun→Jul expansion means
  artifacts predating the re-probe reflect the earlier set; docs must not quote a
  fixed model count without noting the probe date. Never hand-embed per-model
  scores — point readers at the generated `reports/RESULTS.md`.

## Links

- Cohort config: [configs/models.yaml](../../configs/models.yaml) (header comment records probes).
- Backend transport: [ADR-0002](0002-claude-cli-backend-stdin-transport.md).
- Adding a model: [docs/how-to/add-a-model.md](../how-to/add-a-model.md).
- Design record: [DESIGN.md](../../DESIGN.md) §3 Model cohort.
