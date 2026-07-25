# Release checklist

Goal: cut a release (or push a batch of changes) such that every published
number is machine-generated, provenance exists for every phase, and nothing
private leaves the machine. Work through the steps in order; each has a
concrete verification command.

Related: [regenerate-reports.md](regenerate-reports.md) for report details,
[../explanation/holdout-stance.md](../explanation/holdout-stance.md) for what
the holdout is (and is not), [../reference/data-formats.md](../reference/data-formats.md)
for the file schemas checked below.

## 1. Run the tests

```bash
uv pip install --python .venv/bin/python --group dev
.venv/bin/python -m pytest tests/ -q
```

All tests must pass. Do not release on a red suite, and do not skip this
because "only docs changed" — it takes about ten seconds.

## 2. Regenerate every published number

Never hand-edit a number in a report. Regenerate the full chain so that
everything published is the output of code on the commit being released:

```bash
.venv/bin/python -m deseretbench.analyze --run runs/v0_1 --out results/summary.json
.venv/bin/python -m deseretbench.report --summary results/summary.json
.venv/bin/python -m deseretbench.build_onepager --summary results/summary.json
```

This produces `reports/RESULTS.md`, `reports/leaderboard.html`,
`reports/figures/*.png`, and `reports/deseretbench_report.html`. Notes:

- `report.py` embeds only the figures it regenerated in this invocation — a
  stale PNG left on disk by an older run will not be silently referenced.
- `build_onepager.py` warns and omits a missing figure rather than failing, so
  read its output and open the HTML: a warning here means a hole in the
  published page.
- If `runs/` is mid-refresh (a re-run in flight), do not release — the
  generated reports would describe a moving target.

## 3. Verify provenance exists for each phase

`runs/<run>/config_snapshot.json` records, per phase, when it was written,
the exact cohort, and the full run config. It is written only *after* a
phase's outputs land, so its presence means the outputs it describes are real.

```bash
jq 'keys' runs/v0_1/config_snapshot.json          # expect ["mc","open"]
jq '.mc.written_at, .open.written_at, .mc.cohort' runs/v0_1/config_snapshot.json
```

Both phases must be present and the cohort must match `configs/models.yaml`.

## 4. Sweep the diff for private strings

Everything about to be pushed gets grepped for strings that identify the
machine or people: absolute home-directory paths, email addresses, and real
personal names. Check the full diff against the last released state, not just
staged files:

```bash
git diff <last-release-tag>..HEAD | grep -inE '/home/[a-z]|@[a-z0-9.-]+\.(com|net|org)'
git diff <last-release-tag>..HEAD --stat        # eyeball for unexpected files
```

Adapt the pattern to whatever is private in your environment (usernames,
hostnames, correspondents' names). Any hit is a release blocker: fix the
source, don't just amend the commit, so the string cannot recur.

## 5. Confirm the holdout directory stays untracked

`data/private_holdout/` must never be committed:

```bash
git check-ignore data/private_holdout && echo "ignored: OK"
git ls-files data/private_holdout/    # must print nothing
```

Keep the framing honest in any prose you touch: in v0.1 the holdout is
*nominal* — a structural placeholder whose contents are derivable from the
published candidate pool. Do not describe it as secret or sealed. See
[../explanation/holdout-stance.md](../explanation/holdout-stance.md).

## 6. Confirm the balance marker is consistent

The MC set is position-balanced, and re-balancing is not idempotent, so the
marker written by `balance_positions` must exist and agree with the set being
released:

```bash
jq '.n_items' data/questions_mc.jsonl.balance_meta.json
wc -l < data/questions_mc.jsonl
```

The two numbers must match. If the marker is missing, or the counts disagree,
the question set and the marker are from different balancing passes — stop and
re-run validation + balancing before releasing (`balance_positions` refuses to
re-balance a marked set without `--force` for exactly this reason).

## 7. Update dataset counts from generated outputs only

If item counts changed, update `DATASET_CARD.md` and `README.md` from the
files, never from memory:

```bash
wc -l data/questions_mc.jsonl data/questions_open.jsonl
```

Leaderboard numbers and per-model scores are **never** copied into prose docs
by hand — docs point readers at `reports/RESULTS.md`, which step 2 just
regenerated. The only numbers acceptable in hand-written docs are structural
ones (item counts, runs per model, persona count) sourced from the data files
and configs.

## 8. Commit

- Subject line: short, imperative, lowercase, saying what changed
  (matching the existing history, e.g. `publish the candidate pool openly; …`).
- Body: what changed and, for anything touching data or analysis, whether the
  published numbers changed and why. "Numbers unchanged" is a claim — only
  write it after step 2's regeneration diff confirms it.
- Never commit `CLAUDE.md`, `docs/superpowers/`, or local working artifacts
  (they are gitignored; do not force-add them).
- Commit the regenerated `reports/` and `results/summary.json` together with
  the code that produced them, so every published number is reproducible from
  its own commit.
