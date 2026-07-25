# ADR-0011: Local open-weights backend (ollama) for a non-Anthropic cohort

Status: Accepted

Date: 2026-07-08

## Context

Through v0.1 the cohort was Claude-only — the models the authenticated `claude`
CLI serves ([ADR-0010](0010-cohort-selection-by-cli-probe.md)). That leaves the
benchmark's central premise untested from below: if Latter-day Saint competence
really requires tradition-specific knowledge rather than generic Christian
pattern-matching, small open-weights models should fail it in measurable,
type-diagnosable ways. A frontier-only leaderboard also can't say where the
capability *emerges*.

The bench host is modest (4-core i5-7300HQ, 15 GB RAM, no CUDA — the GTX 1060
runs nouveau), so anything local must be small, quantized, CPU-served, and
strictly one-model-at-a-time to avoid OOM.

## Decision

Add an `ollama` backend to the runner and let **cohort entries pin a backend**
(`backend: ollama` in `configs/models.yaml`; entries without the key keep the
configured default, `claude_cli`).

- **Serving.** A user-space Ollama install (no root, no HF token; models pulled
  from the Ollama library, which hosts official vendor uploads) with
  `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_NUM_PARALLEL=1`: at most one model
  resident, requests queued serially — OOM-safe by construction on a 15 GB host.
- **Transport.** `POST /api/chat` on localhost via stdlib `urllib` (no new
  dependencies), `stream: false`, system + user messages, pinned generation
  caps (`num_predict: 4096`, `num_ctx: 8192`).
- **Effort mapping.** The benchmark's pinned effort knob (MC = `low`,
  open = `high`) maps onto native think modes where they exist — Qwen3 and
  DeepSeek-R1 families get `think: false` at `low` and `think: true`
  otherwise; models without a think mode never receive the key. This mirrors
  how effort modulates reasoning for the Claude cohort.
- **Comparable measured surface.** Only `message.content` is scored; a native
  `thinking` field is ignored, and reasoning leaked inline as a `<think>` block
  by some GGUF chat templates is stripped — the Claude CLI likewise returns
  only final answer text.
- **Same integrity rails.** The effective backend is part of the cache key
  (`{b,m,s,p,e,r}`), so Claude entries are untouched and cross-backend
  laundering is impossible; served-model verification applies unchanged (the
  server must echo the requested model id); "model not found, try pulling" and
  "does not support think" join the permanent-error markers (fail fast, no
  retry burn); `cost_usd` is recorded as 0.0 — local inference has no marginal
  cost, and spend accounting keeps tracking the Claude-side judge.
- **Judging is unchanged.** Open-ended answers from local models are scored by
  the same judge configuration as the Claude cohort (same judge model, same
  personas, same rubrics), so composites stay on one scale.

## Consequences

- The leaderboard becomes cross-vendor, and per-distractor-type item analysis
  can show *which* traps catch small models — the discriminative-power claim
  becomes testable rather than asserted.
- Local scores are CPU-latency-bound, not quality-bound; latency and token
  counts are recorded but absolute speed is not comparable across backends.
- The judge shares a vendor with only part of the cohort now — same-family
  bias ([ADR-0005](0005-judge-panel-three-personas.md)) cuts differently for
  local models; the cross-check judge remains the designed mitigation.
- `timeout_seconds` rose to 1200 for CPU-bound thinking turns (deliberately
  outside the cache key, so nothing re-buys).
- A local Ollama server becomes part of the reproduction environment for the
  non-Anthropic slice; the Claude-only slice reproduces without it.

### What running it actually cost (recorded 2026-07-15)

Three traps surfaced in the first full local run. None changed a number; all
three would have cost the next person a day.

- **The qwen3 thinking-tag trap.** The bare `qwen3:4b` tag maps to a thinking
  build that *ignores* `think: false` — it spends ~3k reasoning tokens on a
  multiple-choice answer (~200× slower) and returns content with a dangling
  `</think>` and no opener, because its chat template auto-opens reasoning. The
  cohort therefore pins `qwen3:4b-instruct`, the non-thinking sibling, which is
  consistent with how the 0.6b/1.7b tags behave at low effort. The strip logic
  handles an opener-less closer regardless (`tests/test_ollama.py`), because a
  silent half-strip would have scored reasoning text as the answer.
- **The runner leaks memory, and not in the way you would guess.** Ollama
  0.31.1's `llama-server` child accumulates resident memory across sequential
  requests at **2.5–10 GB/h**. The rate is model-dependent and does **not**
  track thinking mode — the fastest leak measured was SmolLM2, a non-thinking
  model, which falsified the obvious hypothesis. It self-clears when the model
  idle-unloads, but a long generation leg exhausts a 15 GB host first. A
  supervisor outside this repo bounces the server on `MemAvailable` (the
  primary trigger, checked independently of any process match — a safety net
  that disables itself when it cannot find a process name is worse than none)
  with RES as a secondary trigger. Over the full run it fired **eight times in
  production — three on `MemAvailable`, five on RES** — plus twice more when the
  bounce path was deliberately forced to test it. All ten restarts succeeded on
  the first attempt; none failed; the run completed with **zero OOM kills**. The
  split matters: the three `MemAvailable` fires happened while RES was still
  under its cap, so a watchdog gated on the process read alone would have missed
  exactly the cases that were closest to the OOM killer. Bouncing mid-leg is safe
  precisely because of [ADR-0003](0003-content-addressed-response-cache.md): a
  refused connection is a transient error, and every completed call is already
  cached.
- **The nouveau boot-clock trap.** The host's GPU path was unusable, so the
  entire local cohort ran on CPU. This is why local latency is not comparable
  to anything and is reported only as provenance.

The general lesson is the one worth carrying: a local backend moves the
benchmark's failure modes from *the API's* problems to *the operator's* — OOM
kills, tag aliases, driver state. The cache is what makes those failures
recoverable rather than fatal.

## Links

- [ADR-0002](0002-claude-cli-backend-stdin-transport.md) — backend architecture
- [ADR-0003](0003-content-addressed-response-cache.md) — cache-key discipline
- [ADR-0010](0010-cohort-selection-by-cli-probe.md) — cohort selection
- `deseretbench/runner.py` (`_call_ollama`), `tests/test_ollama.py`
