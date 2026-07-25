# How to add or regenerate questions

Goal: extend or refresh the question set — either by re-running the model-assisted
authoring pipeline or by hand-writing items — and end with a validated,
position-balanced public set.

A caution up front: any change to the public question set produces a **new
benchmark version**. Scores on the new set are not comparable to scores on the old
one; treat the result as v-next, not a patch to v0.1.

Record formats are specified in
[../reference/data-formats.md](../reference/data-formats.md); the reasoning behind
the distractor taxonomy is in
[../explanation/why-typed-distractors.md](../explanation/why-typed-distractors.md).

## The authoring pipeline

Four stages, each a module with its own CLI. `scripts/run_all.sh` chains all of
them (steps 1–4) before running the benchmark, if you want the one-command
version.

### 1. Author candidate items

```bash
.venv/bin/python -m deseretbench.author --max-parallel 8 \
  --model claude-opus-4-8 --effort high
```

Flags (defaults shown): `--max-parallel 8`, `--model claude-opus-4-8`,
`--effort high`, `--force`.

One high-effort completion is made per (dimension, difficulty, batch) cell; each
cell writes `data/raw/mc_<dimension>_<difficulty>_b<N>.jsonl` or
`data/raw/open_<dimension>_b<N>.jsonl`. A cell is **skipped** if its raw file
already contains at least 70% of the expected item count as schema-valid lines —
pass `--force` to re-author everything (each cell file is overwritten whole). The
authoring prompts over-generate ~1.3× the target counts, since validation will
reject some items.

**`data/grounding_brief.md` and currency items.** The authoring prompt embeds this
file verbatim — it is the dated, source-cited fact sheet that anchors answer keys,
especially for currency-sensitive items (leadership succession, recent policy and
organizational changes). `author.py` reads it at import time and crashes if it is
missing. If you are authoring new currency items, **update the brief first** (it
is stamped "as of June 2026"); an outdated brief silently authors items keyed to
stale facts.

### 2. Assemble candidates

```bash
.venv/bin/python -m deseretbench.assemble
```

No flags. Reads every `data/raw/*.jsonl` tolerantly (code fences and
pretty-printed blocks are handled), drops schema-invalid items, assigns
`question_id` from a content hash, dedupes by both content hash and normalized
question stem, and writes `data/candidates_mc.jsonl` and
`data/candidates_open.jsonl`.

### 3. Validate with the reviewer panel

```bash
.venv/bin/python -m deseretbench.validate_questions --max-parallel 8 --effort medium
```

Flags (defaults shown): `--max-parallel 8`, `--effort medium`, `--limit 0`
(0 = all candidates), `--no-holdout` (skip the 20% holdout split).

Reads the two candidate files; writes `data/reviews_mc.jsonl`,
`data/reviews_open.jsonl`, the public sets `data/questions_mc.jsonl` and
`data/questions_open.jsonl`, `data/private_holdout/{mc,open}.jsonl` (untracked;
see [../explanation/holdout-stance.md](../explanation/holdout-stance.md) — for
v0.1 this split is a structural placeholder, not a secret set), and
`data/validation_report.json`.

**Quorum and re-solicitation, in one paragraph.** Every item is reviewed by five
fixed reviewer personas, always on the same review model regardless of flags; MC
review is blind (reviewers are not shown the key). A review that fails or returns
unparseable JSON is re-solicited exactly once at the next effort level up with a
fresh cache key — a same-effort retry would replay the identical cached bytes, and
skipping "difficult" items would let item content decide what gets reviewed. If a
persona's retry also fails, it simply contributes nothing. An item with fewer than
three usable reviews is marked **unreviewed and dropped as an infrastructure
outcome, not a quality verdict** (its id is listed in `validation_report.json`).
Items with quorum are kept or rejected by fixed thresholds on key agreement,
clarity, defensible-option count, and bad-flag counts (see
`deseretbench/validate_questions.py` for the exact rules).

### 4. Balance key positions (MC only)

Authoring skews which letter holds the correct answer, so the MC set is
permuted with a seeded shuffle before it is ever run:

```bash
.venv/bin/python -m deseretbench.balance_positions \
  --in data/questions_mc.jsonl --out data/questions_mc.jsonl
```

Flags: `--in` and `--out` are required (in-place, `--in` == `--out`, is the
normal usage); `--seed 19470417` (default); `--force`.

**The balance-marker rule.** Balancing is not idempotent — re-balancing an
already-balanced file silently diverges from any published run. So the tool
refuses to run if either the marker `data/questions_mc.jsonl.balance_meta.json`
or the backup `data/questions_mc.prebalance.jsonl` exists. After re-running
validation on a refreshed set, those files are stale; remove them first, exactly
as `scripts/run_all.sh` step 4 does:

```bash
rm -f data/questions_mc.jsonl.balance_meta.json data/questions_mc.prebalance.jsonl
.venv/bin/python -m deseretbench.balance_positions \
  --in data/questions_mc.jsonl --out data/questions_mc.jsonl
```

Alternatively pass `--force` (intended for re-authored sets only). `--force`
rotates a stale backup aside rather than deleting it — to
`data/questions_mc.prebalance.prebalance.1.jsonl` (yes, the doubled `prebalance`
segment is the actual filename; `with_suffix` replaces only the final `.jsonl`).
Only one rotated generation is kept: a second `--force` run overwrites it.

The tool writes the marker (seed, item count, and a position map that lets
pre-balance artifacts like reviewer letters stay interpretable), re-validates
every output item against the schema, and prints the before/after key-letter
distributions — check that "AFTER" is roughly uniform.

## Hand-writing items

You can write items by hand instead of (or in addition to) step 1. The full field
requirements are in [../reference/data-formats.md](../reference/data-formats.md);
the validators are `validate_mc_item` / `validate_open_item` in
`deseretbench/schema.py`. In brief:

- **MC**: `format: "mc"`, a valid `axis`/`dimension`/`difficulty` combination
  (axis must match the dimension's fixed axis), a question of ≥ 10 characters,
  3–6 unique choices, an in-range `answer_index`, and a non-empty `source`.
  `distractor_types` is optional, but if present it must parallel `choices` with
  exactly one `correct` entry sitting at `answer_index`.
- **Open**: `format: "open"`, valid axis/dimension/difficulty, a prompt of ≥ 20
  characters, and a `rubric` with non-empty `must_include` and `should_not` lists
  and an `ideal_reasoning_pattern` string. No `source` field is required.

Put hand-written items in a `data/raw/*.jsonl` file (one JSON object per line)
and run the pipeline from step 2. That way `assemble` assigns the content-hash
`question_id` and dedupes for you, and your items pass through the same reviewer
panel and thresholds as authored ones — hand-written does not mean
hand-waved-through. Appending directly to the public `questions_*.jsonl` files
skips validation and (for MC) position balancing, and is not supported.

## After the set changes

Re-run both benchmark phases on the new set (see
[../tutorials/first-run.md](../tutorials/first-run.md) and
[recover-interrupted-run.md](recover-interrupted-run.md)). The response cache is
keyed by prompt content, so unchanged items still hit cache; only new or edited
items trigger fresh model calls.
