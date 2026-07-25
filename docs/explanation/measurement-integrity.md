# Measurement integrity: running a benchmark over a consumer CLI

DeseretBench's default transport is not a raw API — it is the authenticated
`claude` CLI, a consumer tool built for interactive coding sessions, not for
evaluation harnesses. That choice is pragmatic (the environment this project
runs in has no API key), but it changes the threat model. A benchmark's job is
to attribute every recorded answer to the model that actually produced it, at a
known cost, exactly once, with no silent substitutions. A consumer CLI
guarantees none of that on its own.

This document lays out the threats we designed against and the specific
mechanism that answers each one. The mechanisms live mostly in
[`deseretbench/runner.py`](../../deseretbench/runner.py) and
[`deseretbench/run_benchmark.py`](../../deseretbench/run_benchmark.py); the
reference details are in [../reference/cache.md](../reference/cache.md) and
[../reference/cli.md](../reference/cli.md).

## The threat model

| Threat | What goes wrong if ignored | Mechanism |
|---|---|---|
| Silent model fallback | The CLI serves a different model than requested; its answers are scored under the wrong name | Served-model verification (`_served_matches`), `served_all` bookkeeping, fail-fast `served_mismatch` |
| Prompt-as-argv hazards | Item text parsed as a CLI option, argv size limits, prompt text visible in `ps` | Prompt delivered over stdin, never argv; no shell is ever invoked |
| Partial-write corruption | A crash mid-phase leaves a half-written results file that later tooling reads as truth | Atomic sinks: write to `<path>.tmp`, `os.replace` on close |
| Double-spend blindness | Retries cost real money that a per-call counter never sees | Spend accumulated per *attempt*, under a lock |
| Cache laundering | A bad result (failure, or a fallback-served answer) gets cached once and replays forever as a clean hit | Success-only cache writes; read guard re-checks `ok` and served-model match |
| Provenance drift | Config changes after a run, and analysis stamps the run with values it never used | Per-phase config snapshots written only after the phase's outputs land |

## Silent model fallback

The CLI can and does serve a model other than the one requested — during
capacity fallbacks, alias repoints, or when it quietly enlists a helper model.
An answer produced by the wrong model is not a noisy data point; it is another
model's data point, and scoring it under the requested model's name corrupts
the comparison the whole benchmark exists to make.

The defense has three parts:

1. **Identify what was actually served.** The CLI's JSON output includes a
   `modelUsage` map. `_dominant_model` picks the primary serving model — with
   one key, that key; with several, the key with the most output tokens (cost
   as tiebreak) — and records *all* keys, comma-joined, in
   `CallResult.served_all`. The `served_all` field exists because the CLI
   sometimes reports auxiliary sub-model calls (e.g. a small helper model)
   alongside the primary one, and that evidence matters later (see
   "Honest edges").

2. **Compare with a deliberately narrow tolerance.** `_served_matches`
   accepts exactly three cases: served is unknown (`None` — not provably
   mismatched), served equals requested, or one string extends the other by a
   dated suffix matching `-\d{8}$` (alias ↔ dated snapshot, either direction,
   e.g. `claude-opus-4-8` vs `claude-opus-4-8-YYYYMMDD`). Any other suffix —
   a `-fast` tier, a different generation sharing a prefix — is a mismatch.
   Those are exactly the silent fallbacks the guard exists for.

3. **Fail fast, don't retry into it.** When a live call comes back `ok` but
   mismatched, the runner flips it to `ok=False` with error
   `served_mismatch: requested X, served Y`. That string is on the
   permanent-error marker list, so the call is *not* retried: while a
   fallback or repoint persists, retrying just burns quota producing more
   wrong-model output. Every live attempt also records `called_at` (UTC), so
   mismatches can later be audited against known alias-repoint windows.

Downstream, `analyze.py` applies the same `_served_matches` predicate to the
recorded `model_served` on every response record, and classifies any surviving
mismatches into extraction artifacts (kept) versus genuine fallbacks (excluded
from scoring) — see [statistics.md](statistics.md) for where exclusions enter
the analysis.

## Prompt delivery: stdin, never argv

Benchmark items are arbitrary text. Passed as an argv element, an item that
happens to start with `-` could be parsed as a CLI option, a long item could
hit the argv size limit, and every prompt would be visible to any user on the
machine via `ps`. So the runner passes the prompt via
`subprocess.run(cmd, input=prompt, ...)` — stdin, always — and never invokes a
shell, so there is no quoting or interpolation surface at all. The fixed
arguments (`--model`, `--system-prompt`, `--effort`, `--output-format json`,
`--tools`, `--no-session-persistence`) come from config, not from item
content.

## Partial-write corruption

A benchmark phase can run for hours; the process can die at any point. If the
output file were appended in place, a crash would leave a file that is
plausible but incomplete — and "plausible but incomplete" is the worst failure
mode for a results file, because nothing downstream notices.

`JsonlSink` in `run_benchmark.py` writes every record to `<path>.tmp`
(flushing after each line, thread-safe via a lock) and only renames it onto
`<path>` with `os.replace()` when the phase closes. `os.replace` is atomic on
POSIX: at every instant, `<path>` is either the previous complete file or the
new complete file, never a torn hybrid. A crash mid-phase costs the
in-progress phase (whose successful calls are all cached and replay instantly
on resume — see [../how-to/recover-interrupted-run.md](../how-to/recover-interrupted-run.md))
but never corrupts what was already on disk.

## Double-spend on retries

Transient failures are retried up to `max_retries` times with *linear*
backoff (`backoff * attempt`: 5 s, 10 s, 15 s at the defaults). Each of those
attempts is a real API call with a real cost, whether or not it succeeds. The
runner therefore accumulates `self._spend += r.cost_usd` on **every attempt**,
inside a `threading.Lock` (the runner is used from a thread pool), while
`n_live_calls` counts logical calls once. Progress lines during a run print
live spend from this counter, so a retry storm is visible as money, not just
as time.

The permanent-error list is the other half of spend discipline: errors that
will not heal on retry (`model not found`, `authentication`, `billing`,
`served_mismatch`, …) break out of the retry loop immediately instead of
burning `max_retries × timeout` on each one. The markers are deliberately
specific substrings so that timeouts, 429s, and 5xxs never match them.

## Cache laundering

The response cache (see [../reference/cache.md](../reference/cache.md)) is
what makes runs resumable: every call is content-addressed by
sha256 over `(backend, model, system, prompt, effort, run_index)`, and a
re-run skips completed work. A cache is also a laundering risk: a bad result
written once replays forever, looking exactly like a fresh clean call.

Two rules prevent that:

- **Success-only writes.** A result is written to cache only if `last.ok` is
  true. Failures — including served-mismatch results, which are flipped to
  `ok=False` before this point — are never cached, so every resume retries
  them for real.
- **Guarded reads.** A cached entry is served only if its stored `ok` is
  truthy *and* `_served_matches(model_requested, model_served)` holds on the
  stored fields. This re-check matters because entries can predate the guard:
  silent-fallback artifacts cached before the mismatch check existed are
  rejected on read and re-run, instead of laundered into the current run. A
  corrupt (unparseable) cache entry is treated the same way — swallowed and
  recomputed, never trusted.

## Provenance: snapshots after the phase closes

`analyze.py` stamps every summary with the configuration the run actually
used. It cannot trust the live `configs/run_config.yaml` for that — the config
may have changed since the run. So `run_benchmark.py` writes a per-phase entry
(`mc` / `open`) into `<out>/config_snapshot.json` containing the timestamp,
the cohort, and the full run config — and it writes that entry only **after**
the phase's sinks have closed. Ordering is the point: provenance never
describes a run whose outputs failed to land. Analysis then prefers the
snapshot over the live config, falling back (with a printed warning) only when
the snapshot is missing or corrupt.

## The guarded call path

```mermaid
sequenceDiagram
    participant O as run_benchmark
    participant R as Runner.call
    participant C as cache/<sha256>.json
    participant CLI as claude CLI

    O->>R: model, system, prompt, effort, run_index
    R->>C: read entry (if exists)
    alt entry ok AND served-model matches
        C-->>R: CallResult (cache_hit=true)
        R-->>O: result
    else missing / failed / mismatched / corrupt
        loop attempts 1..max_retries
            R->>CLI: argv (fixed flags) + prompt via stdin
            CLI-->>R: JSON (result, modelUsage, cost, ...)
            R->>R: spend += cost_usd  (every attempt)
            R->>R: dominant model from modelUsage; served_all if >1
            alt ok but served model mismatched
                R->>R: ok=false, error=served_mismatch (permanent: no retry)
            else ok
                R->>C: write entry (success only)
            else transient error
                R->>R: sleep backoff * attempt, retry
            end
        end
        R-->>O: result
    end
    O->>O: JsonlSink: append to <file>.tmp
    Note over O: phase close: os.replace(tmp, file),<br/>then write config_snapshot.json
```

## Honest edges

These mechanisms narrow the trust surface; they do not eliminate it.

- **The served-model check trusts the CLI's own report.** Dominant-model
  inference is built on the `modelUsage` map the CLI returns. If that report
  were wrong or absent, the guard has nothing better to check against — an
  absent report (`model_served=None`) is treated as "unknown, not provably
  mismatched" and accepted. There is no independent channel to verify which
  weights actually ran.
- **Fallback within a dated alias family is tolerated by design.** Requesting
  an alias and being served that alias's dated snapshot (or vice versa) passes
  the check. That is the intended semantics of an alias, but it does mean the
  benchmark measures "whatever the alias pointed at during the run window" —
  which is why `called_at` is recorded on every live call, so a run can be
  placed relative to known repoints after the fact.
- **Cache entry writes are a single `write_text`, not tmp+rename.** A crash
  during a cache write could leave a torn entry — but the read side treats any
  unparseable entry as a miss and recomputes, so the failure mode is a little
  wasted spend, never a wrong result. Older cache entries also predate some
  schema fields (`served_all`, `called_at`, cache-token counts); on a hit they
  are reconstructed with defaults, so those fields can read as absent/zero for
  old entries.
- **Nonzero CLI exit with output is still parsed.** The runner treats a
  nonzero exit code as an error only when stdout is empty; nonzero-with-stdout
  goes through JSON parsing and the normal `is_error` / `api_error_status`
  checks. This matches observed CLI behavior but is a judgment call, not a
  guarantee from the tool.

## Related

- [../reference/cache.md](../reference/cache.md) — cache key, layout, and lifecycle in full
- [../how-to/recover-interrupted-run.md](../how-to/recover-interrupted-run.md) — using resumability in practice
- [statistics.md](statistics.md) — how exclusions (call failures, genuine fallbacks) enter the analysis
- [judge-design.md](judge-design.md) — integrity questions specific to LLM-as-judge scoring
