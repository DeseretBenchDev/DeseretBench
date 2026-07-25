# How to recover an interrupted benchmark run

Goal: get a partially completed benchmark run (MC or open phase) back to a fully
clean state — without re-paying for work that already succeeded, and without
babysitting a terminal for hours.

For a from-scratch walkthrough, see [../tutorials/first-run.md](../tutorials/first-run.md).
For why the cache makes this safe, see [../reference/cache.md](../reference/cache.md)
and [../explanation/measurement-integrity.md](../explanation/measurement-integrity.md).

## The failure modes this covers

1. **Rolling usage limits.** The authenticated `claude` CLI enforces a rolling
   session usage limit. A long run hits it partway through and a *wave* of calls
   fails with 429-style errors ("You've hit your session limit"). The limit
   resets on its own after a window; the failed calls just need to be retried
   later.
2. **Session or terminal exit.** Closing the terminal (or an SSH disconnect)
   sends SIGHUP to background children, killing an in-flight run.
3. **Machine reboot** (or OOM kill, power loss). Everything in flight dies.

All three have the same recovery: re-run the phase. The design makes that safe.

## Why re-running is safe

- **Failures are never cached.** Only `ok` results are written to the cache
  (`deseretbench/runner.py`), so a rate-limited or errored call is retried on
  the next run.
- **Successes are content-addressed.** Every successful call is cached under a
  sha256 of `(backend, model, system, prompt, effort, run_index)`. Re-running a
  phase serves completed work instantly from cache and only pays for what
  failed. See [../reference/cache.md](../reference/cache.md).
- **Output files are atomic.** Each phase writes to `<file>.jsonl.tmp` and only
  `os.replace()`s onto the real `<file>.jsonl` when the phase finishes. A wave
  killed mid-phase leaves the previous complete file untouched — you never end
  up with a truncated `mc_responses.jsonl`.

So the worst case for any interruption is: lose the in-flight (unfinished)
calls, keep everything that succeeded, retry the rest for free-ish.

## 1. Retry a single phase with the resilient wrapper

`scripts/resilient_run.sh` loops one phase until zero failures remain, sleeping
through limit-reset windows:

```bash
scripts/resilient_run.sh mc   runs/v0_1 data/questions_mc.jsonl   [sleep_secs]
scripts/resilient_run.sh open runs/v0_1 data/questions_open.jsonl [sleep_secs]
```

- `sleep_secs` defaults to **1500** (25 min between waves).
- Env `MAX_PARALLEL` (default 8) is forwarded to `run_benchmark`.
- Env `MAXWAVES` (default 40) caps the number of waves; after that it prints
  `GIVING UP` and exits 2.

Each wave: run the phase, then audit it with `deseretbench.audit`, which reports
two numbers — how much a retry could still heal, and how much still blocks
scoring. **The audit computes expected record counts from the configs**, not
from what happens to be on disk:

- MC expected = (items in the questions file) × (models in the full
  `configs/models.yaml` cohort) × `runs.multiple_choice` from
  `configs/run_config.yaml`.
- Open expected = items × models × `runs.open_ended` for generation, plus
  (successful generations) × (number of judge personas) for judge records.

It counts as failures: `call_ok=false` records, corrupt/unparseable lines, and
**missing** records (expected − present) — so a missing or truncated output
file can never read as clean. It deliberately does *not* count `parse_ok=false`
on a `call_ok=true` judge record: that response is cached and replays
identically, so retrying could never heal it and the loop would never end.

Two consequences worth knowing:

- Because expected counts come from the full cohort and the full questions
  file, **the wrapper only works for full-cohort, full-set runs** — it has no
  notion of `--models` or `--limit` subsets.
- If `run_benchmark` itself exits nonzero, the wrapper **aborts immediately**
  with that exit code rather than looping: nonzero exits are deterministic
  setup errors (bad model id, zero items loaded) that retrying cannot heal.

## 2. Resume the whole pipeline

`scripts/finish_pipeline.sh` chains both resilient phases and the analysis:

```bash
scripts/finish_pipeline.sh [run_dir]    # default runs/v0_1
```

Steps, each with a distinct exit code so a failed unattended run is
diagnosable from `$?` alone:

| Step | Command | Exit on failure |
|---|---|---|
| 1 | `resilient_run.sh mc …` | 2 |
| 2 | `resilient_run.sh open …` | 3 |
| 3 | `python -m deseretbench.analyze --run <run> --out results/summary.json` | 4 |
| 4 | `python -m deseretbench.report --summary results/summary.json` | 5 |

Env: `SLEEP` (default 1500) and `MAX_PARALLEL` (default 8, exported to the
wrapper). `MAXWAVES` is not set by this script — export it yourself if you want
a different cap. It skips authoring/validation/balancing entirely and starts at
the MC phase on the already-balanced question set. (The model/run counts in its
banner echoes are cosmetic text; `configs/models.yaml` and
`configs/run_config.yaml` are the truth.)

On success it prints `PIPELINE_COMPLETE -> reports/leaderboard.html`.

## 3. Launch it so it survives your session

Rate-limit waves mean a full run can span many hours. Detach it from your
terminal completely:

```bash
nohup setsid bash scripts/finish_pipeline.sh runs/v0_1 \
  >> runs/v0_1_pipeline.log 2>&1 < /dev/null & disown
```

- `nohup` + `setsid` put it in its own session so terminal exit / SSH hangup can't
  kill it; `< /dev/null` detaches stdin; `disown` removes it from the shell's
  job table.
- `runs/*.log` is gitignored, so logs under `runs/` are a safe dumping ground.
- This does **not** survive a reboot — after a reboot, just launch the same
  command again; the cache makes it a resume, not a restart.

## 4. Check on it without false matches

```bash
pgrep -af "[f]inish_pipeline"
```

The bracket trick: `pgrep` already excludes its own process from results by design
(`man pgrep`: "The running pgrep … process will never report itself as a match"), so
the brackets are not what stops it self-matching. What the `[f]` character class
*does* buy you is not matching a **wrapping** shell — if this `pgrep` runs inside a
`bash -c "… pgrep -af finish_pipeline …"` (as it does when a workflow evaluates it),
the parent shell's command line contains the literal `finish_pipeline` and would
otherwise be reported; `[f]inish_pipeline` matches the literal string `finish_pipeline`
without the pattern text itself containing that string, so the wrapper is skipped.

Then follow the log:

```bash
tail -f runs/v0_1_pipeline.log
```

## 5. Reading the log

Per wave you'll see:

```
[resilient mc] === wave 3 (max 40) 14:02:11 UTC ===
```

During a phase, progress lines print every 50 MC completions (every 25 for
open generation, every 50 for judging), each with the live spend total. After
each wave, the audit breakdown:

```
  mc_responses: 41 failed + 0 corrupt + 0 missing (have 9585/9585)
[resilient mc] wave 3 -> 41 needing retry, 41 blocking completion
[resilient mc] sleeping 1500s for limit reset, then retrying...
```

The two numbers differ only where a failure is tolerable. MC has no judge panel
to fall back on, so they move together. On the open phase a judge call that
keeps failing can leave `needing retry` non-zero while `blocking completion`
reaches zero — every panel still holds a quorum, so the phase is scoreable and
the loop stops rather than retrying forever:

```
[resilient open] wave 1 -> 1 needing retry, 0 blocking completion
[resilient open] CLEAN (quorum) after 1 wave(s): 1 call(s) did not heal ...
```

That path only opens after `GRACE_WAVES` (default 3) honest retry attempts, so
a merely transient failure heals instead of silently costing a panel a judge.
See [ADR-0012](../adr/0012-operator-settings-isolation-and-judge-quorum.md).

`failed` = `call_ok=false` records, `corrupt` = unparseable lines, `missing` =
expected − present. For the open phase you get one line each for
`open_responses` and `open_judge_raw`. A phase ends with either
`CLEAN after N wave(s)` or `GIVING UP after 40 waves`. After MC, a quick
per-model accuracy summary (over `call_ok` records only) plus a
`CALL_FAILURES` count also prints.

If the remaining-failures count is **identical across several waves**, the
failures are probably not rate limits — inspect them:

```bash
grep '"call_ok": false' runs/v0_1/mc_responses.jsonl | \
  .venv/bin/python -c "import sys,json,collections; \
    print(collections.Counter(json.loads(l)['error'] for l in sys.stdin))"
```

## What `served_mismatch` failures mean

A call can return successfully but from the *wrong model*: model aliases get
repointed, and the CLI sometimes serves a different model than requested. The
runner compares the requested id with the served id, tolerating only a dated
snapshot suffix (`claude-haiku-4-5` ↔ `claude-haiku-4-5-20251001`). Anything
else — a `-fast` tier, a different generation sharing a prefix — flips the
result to a failure with error `served_mismatch: requested X, served Y`.

This is a **permanent** error marker: it fails fast on the first attempt, with
no retries, because retrying cannot change what the alias points at, and
silently accepting would launder one model's answers into another model's
scores. The same guard applies on cache reads — a cached entry whose served
model mismatches the request is rejected and re-run rather than served.

If these appear, the fix is human, not automatic: either the alias in
`configs/models.yaml` needs updating, or the provider is genuinely serving a
substitute and that model's results cannot be measured honestly right now.
Note the wrapper will keep retrying such waves until `MAXWAVES` (the
per-attempt fail-fast is cheap, but the loop doesn't distinguish the cause), so
a stuck count is your cue to look.
