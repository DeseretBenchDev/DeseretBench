# ADR-0012: Operator-settings isolation and the judge-quorum completion gate

Status: Accepted

Date: 2026-07-15

## Context

Finishing the 17-model run surfaced one judge call, of 6,120, that no retry
could clear. Its error was not a refusal or a rate limit:

```
served_mismatch: requested claude-sonnet-4-6, served claude-opus-4-8
```

The call had *succeeded*. It returned a well-formed verdict. The served-model
guard rejected it because the CLI answered with a model other than the one
asked for.

The mechanism, confirmed by controlled experiment: `claude -p` reads the
operator's `~/.claude/settings.json`, and that file set `advisorModel: opus`.
On a hard prompt the CLI consults an advisor, and the advisor's tokens land in
the same `modelUsage` map as the answer's. `_dominant_model` attributes a call
to whichever model produced the most output tokens, so when the advisor did
enough work, attribution flipped to Opus and the guard fired.

Pinning the setting removes it entirely — same prompt, same effort:

| Condition | Output tokens by model |
|---|---|
| Inherited settings, effort `high` | sonnet 2332 + **opus 4830** |
| `--settings '{"advisorModel":"claude-sonnet-4-6"}'`, effort `high` | sonnet 4577 only |
| Inherited settings, effort `medium` | sonnet 1474 only |

The finding: **a measurement harness that reads the operator's personal
settings is not reproducible.** Two operators running the same pinned config
can get different judge behaviour, for a reason that appears nowhere in the
config, the cache key, or the run snapshot.

Two properties bound how much this touched v0.1, and both are load-bearing:

- **The judge panel runs at `medium`** (`effort.judge`), not `high`. The
  probes above ran at `high` and therefore overstate how often the advisor
  fires in production. The honest production evidence is the handful of
  `served_mismatch` failures the resilient loop chewed through — at medium the
  advisor fires *rarely*, not routinely.
- **Every observed firing had the advisor dominant**, in the high-effort probes
  and the medium-effort production failures alike, and dominant means the guard
  rejects. A silent case (Sonnet dominant, Opus present as a minority) was never
  observed, but cannot be ruled out retroactively, because judge records do not
  persist `served_all`. That gap is why persisting it is part of this decision.

What *is* provable about v0.1:

- No wrong-model data ever entered the dataset. Across 34,210 cached calls,
  requested equals served in every one — the cache is success-only, so a
  rejected verdict is never stored.
- The response track is clean outright: 20,145 response records, zero
  multi-model calls (responses do persist `served_all`).
- `settings.json` changed 2026-07-14 21:37 MDT. By `called_at`, all 3,240
  Claude-cohort judge verdicts predate it. Exposure is bounded to 1,799
  local-model verdicts — and *exposure is not contamination*: those verdicts
  passed the guard, so Sonnet was dominant in each.

Separately, the incident exposed a real defect in the completion gate. The
resilient runner counted `call_ok=False` records as work remaining and retried
until the count hit zero. That conflates two different questions:

- Can a retry still *heal* this record?
- Is the dataset *complete enough to score*?

A guard rejection can heal — whether the advisor fires is a property of the
call, not of the prompt, and retries did clear four of five. But it is not
guaranteed to, and the gate had no way to ever say so. It would have retried
one call for 40 waves across ~16 hours and then exited non-zero, so `analyze`
and `report` would never have run. A complete dataset would have produced no
results.

## Decision

**Isolate the subprocess from operator settings.** The harness pins the
settings that affect measurement rather than inheriting whatever the operator
happens to have. A benchmark's behaviour must follow from its committed config.

Validated end to end against the call that started this: the verdict that was
rejected four times now returns `served=claude-sonnet-4-6`, `served_all=None`,
and parses — at `high` effort, the condition where the advisor fired most
reliably. (Run against a throwaway cache, so v0.1's dataset is untouched.)

**Persist `served_all` and `error` on judge records.** Judge records stored
neither, which is why diagnosing this required reproducing the call live
against a running pipeline. Attribution evidence belongs in the artifact.

**Gate completion on judge quorum, not on zero failures** (`deseretbench/audit.py`).
Two signals, computed separately:

- `strict_fail` — records a retry could heal. Drives retry.
- `accept_fail` — what must be zero before a phase may finish anyway.

Only judge calls are tolerable, and only while every panel still holds a
quorum (default 2 of 3), and only after retries have had `GRACE_WAVES` honest
chances. Generation gaps and corrupt lines are never tolerated.

**Tolerate means drop, never substitute.** A rejected verdict is discarded and
its panel scores over the judges it has; `aggregate_panel` already treats a
missing verdict as missing data rather than zero. Recording the Opus scores
under Sonnet's name would defeat the guard and contaminate the panel with a
second judge model.

## Consequences

- v0.1 completes on its own terms. One triple
  (`qwen3:4b-instruct` / `life_choice_advanced_ea4531edea` / run 0) scored on a
  2-judge panel; 2,039 of 2,040 carry the full three. Its composite is 31.25
  and Qwen3 4B's 21.7 is unaffected. Judge IRR is α=0.993.
- v0.1 stays internally consistent and is **not** re-run: every call ran under
  the same conditions, and the guard filtered what didn't belong. Re-running
  would also be a full cache bust — the cache key covers
  `{backend, model, system, prompt, effort, run_index}`, deliberately not
  settings.
- The residual caveat on the open track is stated, not hidden: 1,799
  local-model verdicts were produced under the changed settings; each was
  Sonnet-dominant; a Sonnet-dominant call with an Opus minority cannot be
  excluded retroactively for v0.1, and is excluded going forward by isolation
  plus `served_all` on judge records.
- The served-model guard is load-bearing, not defensive plumbing. It is why the
  dataset stayed clean and why the problem was detectable at all.
- A quorum gate can, in principle, accept a panel that a further retry would
  have completed. `GRACE_WAVES` bounds that: retries stay best-effort and only
  a persistent failure degrades a panel, so a transient blip still heals.

## Links

- [ADR-0003](0003-content-addressed-response-cache.md) — success-only caching;
  why a rejected call is never stored
- [ADR-0005](0005-judge-panel-three-personas.md) — the three-persona panel a
  quorum is drawn from
- [ADR-0011](0011-local-open-weights-backend.md) — the run this surfaced on
- `deseretbench/audit.py`, `tests/test_audit.py`, `scripts/resilient_run.sh`
- `deseretbench/runner.py` (`_dominant_model`, served-model guard)
