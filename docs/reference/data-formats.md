# Data formats

Record-format reference for every JSON/JSONL artifact DeseretBench reads or
writes: dataset items, pipeline intermediates, run outputs, and analysis
summaries. Field lists below are taken from the code that writes each format
(cited per section), not from prose descriptions elsewhere.

Conventions used throughout:

- All JSONL files are UTF-8, one JSON object per line, written with
  `ensure_ascii=False`. Blank lines are tolerated on read
  (`schema.load_jsonl`) and never written.
- "Required" means the schema validator rejects the record without it, or the
  writer always emits it. "Optional" means the validator only checks it when
  present. "Newer" marks fields the current code writes that may be absent in
  older shipped files (readers treat them as missing data).
- Example records are real records from the published files, with long free
  text truncated (`…`) for readability.

Related pages: [configuration reference](configuration.md) ·
[CLI reference](cli.md) · [cache reference](cache.md) ·
[glossary](glossary.md) · [why typed distractors](../explanation/why-typed-distractors.md) ·
[judge design](../explanation/judge-design.md)

---

## 1. Controlled vocabularies (`deseretbench/schema.py`)

These sets define the legal values for item metadata. Validators reject
anything outside them.

### Axes

| Axis | Meaning |
|---|---|
| `doctrinal_accuracy` | Knows what the Church teaches |
| `cultural_fluency` | Understands how Latter-day Saints live and decide |
| `life_choice_alignment` | Counsel tracks a faithful, thoughtful member's |

### Dimensions and their fixed axis (`AXIS_FOR_DIMENSION`)

Every dimension belongs to exactly one axis; validators reject an item whose
`axis` disagrees with its `dimension` (a mismatch would silently pollute
per-axis scoring).

| Dimension | Format | Axis |
|---|---|---|
| `doctrine_scripture` | MC | `doctrinal_accuracy` |
| `ordinances_covenants` | MC | `doctrinal_accuracy` |
| `church_organization` | MC | `doctrinal_accuracy` |
| `eternal_family` | MC | `doctrinal_accuracy` |
| `restoration_history` | MC | `doctrinal_accuracy` |
| `living_gospel` | MC | `doctrinal_accuracy` |
| `cultural_fluency` | MC | `cultural_fluency` |
| `cultural_open` | open | `cultural_fluency` |
| `life_choice` | open | `life_choice_alignment` |

### Difficulties

`basic` · `intermediate` · `advanced` · `expert`

### Distractor types (`DISTRACTOR_TYPES`)

| Value | Meaning |
|---|---|
| `correct` | The keyed answer (exactly one per item; see invariant below) |
| `protestant_trap` | Plausible if you assume mainstream-Protestant theology |
| `folk_doctrine_trap` | Popular but non-official LDS folklore |
| `anti_mormon_trap` | Critical-literature framing presented as fact |
| `progressive_trap` | Heterodox/progressive reinterpretation |
| `correlation_oversimplification` | True-ish but flattened past accuracy |
| `plausible_near_miss` | Wrong in a subtle, informed way |

### Letters

`LETTERS = "ABCDEFGH"`. The valid letters for an item are
`LETTERS[:len(choices)]`.

---

## 2. Question item records

Items live one per line in `data/questions_mc.jsonl` (213 items) and
`data/questions_open.jsonl` (40 items). The same schemas apply to the
candidate pools (`data/candidates_*.jsonl`, 267 MC / 57 open) and the untracked
`data/private_holdout/{mc,open}.jsonl`. Validators:
`schema.validate_mc_item` / `schema.validate_open_item`
(dispatched by `schema.validate_item` on `format`).

### 2.1 MC item (`format: "mc"`)

| Field | Type | Required | Meaning | Example |
|---|---|---|---|---|
| `format` | string | yes | Must be `"mc"` | `"mc"` |
| `axis` | string | yes | One of the three axes; must equal `AXIS_FOR_DIMENSION[dimension]` | `"doctrinal_accuracy"` |
| `dimension` | string | yes | One of the seven MC dimensions | `"church_organization"` |
| `difficulty` | string | yes | One of the four difficulties | `"advanced"` |
| `question` | string | yes | Stem; stripped length ≥ 10 | `"On the death of the President of the Church, why…"` |
| `choices` | list of string | yes | 3–6 non-empty options, case-insensitively unique | `["Because the keys pass…", …]` |
| `answer_index` | int | yes | 0-based index of the keyed answer; `0 <= answer_index < len(choices)` | `1` |
| `distractor_types` | list of string | optional | One type per choice, values from `DISTRACTOR_TYPES` (see invariant) | `["plausible_near_miss","correct",…]` |
| `source` | string | yes | Non-empty citation for the key | `"D&C 107; …"` |
| `notes` | string | optional (not validated) | Author's rationale; present on published items | `"Tests the subtle teaching that…"` |
| `question_id` | string | assigned by pipeline | `{dimension}_{difficulty}_{sha256[:10]}` (see §2.3) | `"church_organization_advanced_bceefdc3c6"` |

**Exactly-one-correct invariant.** When `distractor_types` is present it must
(a) have the same length as `choices`, (b) contain **exactly one** `"correct"`
entry, and (c) have that entry at `answer_index`. `balance_positions` and
per-trap analysis both assume this; the validator enforces all three.

Example (verbatim from `data/questions_mc.jsonl`, choices/notes truncated):

```json
{"format": "mc", "axis": "doctrinal_accuracy", "dimension": "church_organization",
 "difficulty": "advanced",
 "question": "On the death of the President of the Church, why is it doctrinally accurate to say the new President 'receives no priesthood keys he did not already hold,' even though there is a setting apart?",
 "choices": ["Because the keys pass from the deceased President to his first counselor by right of seniority…",
             "Because every Apostle, at his ordination, already receives all the keys of the kingdom, but those keys can be exercised in their fullness only by the senior living Apostle…",
             "Because the setting apart restores keys that had lapsed at the previous President's death…",
             "Because the Quorum of the Twelve votes to confer the full keys…"],
 "answer_index": 1,
 "distractor_types": ["plausible_near_miss", "correct", "plausible_near_miss", "folk_doctrine_trap"],
 "source": "Boyd K. Packer, 'The Twelve Apostles' (Nov 1996 Ensign); D&C 107; churchofjesuschrist.org/learn/first-presidency",
 "notes": "Tests the subtle teaching that all Twelve hold all keys latently…",
 "question_id": "church_organization_advanced_bceefdc3c6"}
```

### 2.2 Open item (`format: "open"`)

| Field | Type | Required | Meaning | Example |
|---|---|---|---|---|
| `format` | string | yes | Must be `"open"` | `"open"` |
| `axis` | string | yes | Must equal `AXIS_FOR_DIMENSION[dimension]` | `"cultural_fluency"` |
| `dimension` | string | yes | `life_choice` or `cultural_open` | `"cultural_open"` |
| `difficulty` | string | yes | One of the four difficulties | `"intermediate"` |
| `prompt` | string | yes | Scenario text; stripped length ≥ 20 | `"A ward member returns to church after a long absence…"` |
| `rubric` | object | yes | Judge rubric (three required keys, below) | — |
| `rubric.must_include` | list of string | yes, non-empty | Points a good answer must cover | `["Intervene to redirect…", …]` |
| `rubric.should_not` | list of string | yes, non-empty | Failure modes to avoid | `["Join or silently permit the speculation…", …]` |
| `rubric.ideal_reasoning_pattern` | string | yes, non-empty | One-paragraph sketch of ideal reasoning | `"Worthiness and sacrament-taking are private…"` |
| `question_id` | string | assigned by pipeline | Same scheme as MC (hash basis is `prompt`) | `"cultural_open_intermediate_9c5b86e6a4"` |

Open items do **not** require a `source` field (MC items do).

Example (verbatim, rubric lists truncated):

```json
{"format": "open", "axis": "cultural_fluency", "dimension": "cultural_open",
 "difficulty": "intermediate",
 "prompt": "A ward member returns to church after a long absence and a public divorce. In the foyer you overhear two well-meaning sisters speculating about 'what really happened' and whether the person 'should be taking the sacrament yet.' The returning member is within earshot and visibly deflates. What do you do in the moment and afterward?",
 "rubric": {"must_include": ["Intervene to redirect or gently shut down the speculation…", "…"],
            "should_not": ["Join or silently permit the speculation…", "…"],
            "ideal_reasoning_pattern": "Worthiness and sacrament-taking are private, bishop-stewarded matters…"},
 "question_id": "cultural_open_intermediate_9c5b86e6a4"}
```

### 2.3 `question_id` derivation

`schema.content_hash_id(item)` builds
`f"{dimension}_{difficulty}_{sha256(basis)[:10]}"` where the basis is
`question + "||" + "|".join(choices)` for MC and `prompt` for open items.

**Caveat:** position balancing (§3.2) reorders `choices` while keeping the
original `question_id`, so IDs on the shipped balanced MC set do **not**
recompute from current content. They are provenance IDs, not checksums.

---

## 3. Pipeline files under `data/`

| Path | Role | Tracked in git |
|---|---|---|
| `data/raw/*.jsonl` (51 shards) | Raw authoring output, one file per (dimension, difficulty, batch) cell: `mc_<dim>_<diff>_b<N>.jsonl`, `open_<dim>_b<N>.jsonl`. Written by `deseretbench.author`. | yes |
| `data/candidates_mc.jsonl`, `data/candidates_open.jsonl` | Assembled, schema-valid, deduplicated candidate pools with `question_id` assigned. Written by `deseretbench.assemble`. | yes |
| `data/reviews_mc.jsonl`, `data/reviews_open.jsonl` | Raw 5-persona review records (§3.1). Written by `deseretbench.validate_questions`. | yes |
| `data/questions_mc.jsonl`, `data/questions_open.jsonl` | The published benchmark sets (review-passing items minus the holdout split). `_review` metadata is stripped before writing. | yes |
| `data/questions_mc.jsonl.balance_meta.json` | Balance marker + position map (§3.2) | yes |
| `data/questions_mc.prebalance.jsonl` | Pre-balance backup (§3.2) | no (`*.prebalance.jsonl` is gitignored) |
| `data/private_holdout/{mc,open}.jsonl` | Stratified 20% split, same item schemas as the public sets. Untracked, but for v0.1 the holdout is *nominal*: the candidate pool and reviews are published, so its contents are derivable. See [holdout stance](../explanation/holdout-stance.md). | no |
| `data/validation_report.json` | Validation summary (§3.3) | yes |
| `data/grounding_brief.md` | Currency brief embedded in authoring prompts | yes |

### 3.1 Review records (`reviews_mc.jsonl`, `reviews_open.jsonl`)

One record per (item × reviewer persona) pass, written by
`validate_questions._review`. Reviewer personas: `orthodox_member`,
`byu_religion_instructor`, `church_historian`, `adult_convert`,
`international_returned_missionary`.

| Field | Type | Meaning |
|---|---|---|
| `question_id` | string | Item under review |
| `persona` | string | Reviewer persona key |
| `parse_ok` | bool | Whether a JSON review was extracted from the reviewer output |
| `resolicited` | bool (**newer**) | `false` for the first pass, `true` for the one-step-higher-effort retry; a retried persona produces two records. Absent in the shipped v0.1 review files, which predate the re-solicit flow. |
| `review` | object or `null` | Parsed review JSON; `null` when unparseable (37 of 285 lines in the shipped `reviews_open.jsonl` are `null`) |

MC `review` object (blind review — the reviewer never sees the key):
`best_answer` (letter), `n_defensible_options` (int), `clarity` (1–5),
`tests_understanding` (bool), `flags` (list from `{ambiguous,
multiple_correct, unfair, trivia, anglocentric, factually_wrong, none}`),
`comment` (string).

Open `review` object: `realistic` (1–5), `rubric_fair` (1–5), `clarity` (1–5),
`flags` (list from `{rubric_too_rigid, rubric_heterodox, unrealistic,
anglocentric, factually_wrong, none}`), `comment` (string).

Example (from `data/reviews_mc.jsonl`, comment omitted):

```json
{"question_id": "church_organization_advanced_bceefdc3c6", "persona": "orthodox_member",
 "parse_ok": true,
 "review": {"best_answer": "A", "n_defensible_options": 1, "clarity": 5,
            "tests_understanding": true, "flags": ["none"]}}
```

(Reviewer letters refer to the **pre-balance** choice order; use the position
map in §3.2 to reconcile them with the shipped set.)

### 3.2 Balance marker and backup (`balance_positions`)

`python -m deseretbench.balance_positions --in X --out Y [--seed 19470417]`
permutes each MC item's choices (and parallel `distractor_types`), drawing the
correct slot uniformly at random per item, keeping `question_id` stable. It
writes two artifacts next to the output file:

**`<out>.balance_meta.json`** — the balance marker:

| Field | Type | Meaning |
|---|---|---|
| `seed` | int | RNG seed used for the permutation |
| `n_items` | int | Items balanced |
| `position_map` | object | `question_id → {order, answer_from, answer_to}` where `order[k]` is the **old** index of the choice now at new slot `k`; lets pre-balance artifacts (e.g. reviewer letters) be reconciled with the shipped order |

Example entry from `data/questions_mc.jsonl.balance_meta.json`:

```json
{"seed": 19470417, "n_items": 213,
 "position_map": {"church_organization_advanced_bceefdc3c6":
                  {"order": [1, 0, 3, 2], "answer_from": 0, "answer_to": 1}}}
```

**`<out-stem>.prebalance.jsonl`** — a byte-for-byte backup of the input items
before balancing (`Path(out).with_suffix(".prebalance.jsonl")`). Gitignored.

Without `--force`, the tool refuses to run if *either* file exists: the
permutation is not idempotent, so re-balancing would silently diverge from the
published run. With `--force`, an existing backup is rotated aside once
(`os.replace`) before the new one is written. After balancing, every output
item is re-validated with `validate_mc_item`; any schema-invalid result aborts
before writing.

### 3.3 `data/validation_report.json`

Written by `validate_questions.main` (current code):

| Field | Type | Meaning |
|---|---|---|
| `mc_candidates`, `open_candidates` | int | Candidate pool sizes |
| `mc_kept`, `open_kept` | int | Items passing review thresholds |
| `mc_rejected`, `open_rejected` | int | Quality rejections |
| `mc_unreviewed`, `open_unreviewed` | int | Items dropped because review quorum (< 3 valid reviews) was never reached — an infrastructure outcome, not a quality verdict |
| `mc_fleiss_kappa_answers` | float or null | Fleiss' κ over reviewers' blind `best_answer` letters |
| `mc_public`, `mc_holdout`, `open_public`, `open_holdout` | int | Post-split counts |
| `drop_reasons_mc`, `drop_reasons_open` | list (≤ 50) | `{id, …_review detail}` per dropped item |
| `unreviewed_mc`, `unreviewed_open` | list of string | Question IDs that never reached quorum |
| `live_spend_usd` | float | Live (non-cached) review spend |

**Legacy note:** the shipped `data/validation_report.json` predates the
rejected/unreviewed split and instead has `mc_dropped` / `open_dropped`
counts, without the `*_rejected` / `*_unreviewed` / `unreviewed_*` fields.
A fresh validation run produces the shape above.

---

## 4. Run artifacts under `runs/<run>/`

All four JSONL files are written by `deseretbench.run_benchmark` through an
atomic sink (records accumulate in `<path>.tmp`, which replaces `<path>` only
on successful close — a crash leaves the previous complete file intact).

Several fields are pass-throughs from the runner's per-call result and appear
in both response formats:

| Field | Type | Meaning |
|---|---|---|
| `call_ok` | bool | Transport-level success; `false` records carry no usable text |
| `model_served` | string or null | Model ID the backend reports actually serving |
| `served_all` | string or null | Comma-joined list of all served-model IDs observed across the call (null when only one) |
| `stop_reason` | string or null | e.g. `"end_turn"` |
| `called_at` | string | UTC timestamp `YYYY-MM-DDTHH:MM:SSZ` |
| `error` | string or null | Transport error message on failure |
| `attempts` | int | Attempts used (retries are linear-backoff) |
| `cache_hit` | bool | Whether the response came from the content-addressed [cache](cache.md) |
| `cost_usd` | float or null | Reported live cost (0/absent on cache hits varies by backend) |
| `input_tokens`, `output_tokens` | int or null | Token usage as reported |

### 4.1 `mc_responses.jsonl`

One record per (model × item × run). Written by `run_mc`.

| Field | Type | Meaning |
|---|---|---|
| `format` | string | Always `"mc"` |
| `model`, `tier`, `label` | string | Cohort entry: ID, tier (`fable`/`opus`/`sonnet`/`haiku`), display label |
| `question_id`, `dimension`, `difficulty`, `axis` | string | Item metadata copied from the question record |
| `run_index` | int | 0-based repeat index (5 MC runs per model by config) |
| `answer_index` | int | The item's keyed answer index (copied in for self-contained scoring) |
| `parsed_letter` | string or null | Letter extracted by `score_mc.parse_answer`; null = parse failure |
| `correct` | bool | `parsed_letter` matches `answer_index` |
| `parse_ok` | bool | `parsed_letter is not None` |
| `duration_ms` | int | Wall-clock call duration |
| `text` | string | Full model response text |
| *(runner pass-throughs)* | | `model_served`, `served_all`, `call_ok`, `stop_reason`, `called_at`, `cost_usd`, `input_tokens`, `output_tokens`, `attempts`, `cache_hit`, `error` |

Example (text truncated):

```json
{"format": "mc", "model": "claude-fable-5", "tier": "fable", "label": "Fable 5",
 "question_id": "church_organization_basic_beeafd11b2", "dimension": "church_organization",
 "difficulty": "basic", "axis": "doctrinal_accuracy", "run_index": 2,
 "model_served": "claude-fable-5", "served_all": null, "call_ok": true,
 "stop_reason": "end_turn", "called_at": "2026-07-03T17:40:17Z",
 "answer_index": 1, "parsed_letter": "B", "correct": true, "parse_ok": true,
 "cost_usd": 0.04851, "input_tokens": 1248, "output_tokens": 9, "duration_ms": 5142,
 "attempts": 1, "cache_hit": true, "error": null, "text": "ANSWER: B"}
```

### 4.2 `open_responses.jsonl`

One record per (model × item × run) generation. Written by `run_open` phase 1.

| Field | Type | Meaning |
|---|---|---|
| `model`, `tier`, `label` | string | Cohort entry |
| `question_id`, `dimension`, `difficulty` | string | Item metadata (no `axis` field, unlike MC records) |
| `run_index` | int | 0-based repeat index (3 open runs per model by config) |
| `text` | string | Response text; empty string when `call_ok` is false |
| *(runner pass-throughs)* | | `call_ok`, `model_served`, `served_all`, `stop_reason`, `called_at`, `error`, `attempts`, `cache_hit`, `cost_usd`, `input_tokens`, `output_tokens` |

Example (text truncated):

```json
{"model": "claude-fable-5", "tier": "fable", "label": "Fable 5",
 "question_id": "cultural_open_intermediate_9c5b86e6a4", "dimension": "cultural_open",
 "difficulty": "intermediate", "run_index": 0, "call_ok": true,
 "model_served": "claude-fable-5", "served_all": null, "stop_reason": "end_turn",
 "called_at": "2026-07-03T21:10:13Z", "error": null, "attempts": 1, "cache_hit": true,
 "text": "**In the moment:**\n\nI'd interrupt the conversation gently bu…",
 "cost_usd": 0.09406, "input_tokens": 1248, "output_tokens": 954}
```

### 4.3 `open_judge_raw.jsonl`

One record per (model × item × run × judge persona) — the raw panel verdicts.
The panel is **one judge model** (`configs/models.yaml` →
`judges.primary_model`) prompted under three personas (`seminary_teacher`,
`byu_religion_professor`, `bishop`), not three independent judge models.

| Field | Type | Meaning |
|---|---|---|
| `model` | string | The *scored* model (not the judge) |
| `question_id` | string | Item |
| `run_index` | int | Repeat index of the scored response |
| `persona` | string | Judge persona key |
| `judge_model` | string (**newer**) | Model ID that produced this verdict |
| `judge_role` | string (**newer**) | `"primary"` or `"crosscheck"` (records from the optional `--judge-crosscheck` pass, which is implemented but has not been run). Analysis defaults absent values to `"primary"`. |
| `call_ok` | bool | Judge call transport success |
| `parse_ok` | bool | Whether a complete score JSON was extracted (`judge.parse_judge_json`) |
| `called_at` | string (**newer**) | UTC timestamp of the judge call |
| `scores` | object or null | Parsed judge JSON; null when the call failed or output was unparseable |

These fields are present on every record in the shipped
`runs/v0_1/open_judge_raw.jsonl` (7,920 lines = 22 models × 40 items × 3 runs ×
3 personas); the `(newer)` tag marks fields that older, pre-audit cache/run files
may lack, not the current v0.1 data.

`scores` object, as demanded by the judge prompt (`deseretbench/judge.py`):
`doctrinal_accuracy`, `cultural_authenticity`, `practical_wisdom`,
`distinctiveness` (each 1–5), `must_include_hits`, `must_include_total`,
`should_not_violations` (counts, self-reported by the judge),
`justification` (one sentence). Values are judge-emitted and unvalidated at
write time; aggregation clamps and sanitizes (see §4.4).

Example (justification truncated):

```json
{"model": "claude-opus-4-8", "question_id": "cultural_open_intermediate_9c5b86e6a4",
 "run_index": 0, "persona": "seminary_teacher", "call_ok": true, "parse_ok": true,
 "scores": {"doctrinal_accuracy": 5, "cultural_authenticity": 5, "practical_wisdom": 5,
            "distinctiveness": 4, "must_include_hits": 5, "must_include_total": 5,
            "should_not_violations": 0,
            "justification": "The response hits every required point with specificity and …"}}
```

### 4.4 `open_scores.jsonl`

One record per (model × item × run): the persona verdicts aggregated by
`judge.aggregate_panel`. Missing or malformed judge values are treated as
missing data, never coerced to zero; dimension scores are clamped to [1, 5]
before averaging.

| Field | Type | Meaning |
|---|---|---|
| `model`, `tier`, `label` | string | Scored model |
| `question_id`, `dimension`, `difficulty` | string | Item metadata |
| `run_index` | int | Repeat index |
| `judge_model` | string | Primary judge model ID; present on all 2,640 shipped v0.1 records (`claude-sonnet-4-6`) |
| `composite_100` | float or null | `(composite_5 − 1) / 4 × 100`, where `composite_5` is the mean of the *present* per-dimension means; null if no dimension had a valid value |
| `dim_means` | object | Per-judge-dimension mean (1–5) across personas, or null per dimension |
| `must_include_coverage` | float or null | Pooled `sum(hits)/sum(totals)` across personas (hits capped at each judge's total); 0–1 |
| `mean_should_not_violations` | float or null | Mean self-reported violation count across personas reporting one |
| `n_judges` | int | Personas whose output parsed (0–3) |

Example:

```json
{"model": "claude-opus-4-8", "tier": "opus", "label": "Opus 4.8",
 "question_id": "cultural_open_intermediate_9c5b86e6a4", "dimension": "cultural_open",
 "difficulty": "intermediate", "run_index": 0, "composite_100": 93.75,
 "dim_means": {"doctrinal_accuracy": 5.0, "cultural_authenticity": 5.0,
               "practical_wisdom": 5.0, "distinctiveness": 4.0},
 "must_include_coverage": 1.0, "mean_should_not_violations": 0.0, "n_judges": 3}
```

### 4.5 `config_snapshot.json`

Written by `run_benchmark.write_config_snapshot` **after** a phase's outputs
commit, so provenance never describes an interrupted run. One top-level key
per completed phase (`"mc"`, `"open"`); running one phase preserves the
other's existing entry.

Per-phase object:

| Field | Type | Meaning |
|---|---|---|
| `written_at` | string | UTC timestamp the snapshot was written |
| `cohort` | list of string | Model IDs actually run |
| `run_config` | object | Full contents of `configs/run_config.yaml` at run time |
| `n_items` | int | Items in the phase |
| `n_runs` | int | Repeats per (model × item) |
| `judge_model` | string | Open phase only |
| `personas` | list of string | Open phase only |

`analyze` prefers this snapshot over the live config files when stamping
provenance into `summary.json` (§5); a missing or corrupt snapshot falls back
to the live config with a printed warning.

---

## 5. `results/summary.json` (`deseretbench.analyze`)

Written by `python -m deseretbench.analyze --run runs/<run>
[--out results/summary.json]`. This is the statistical summary that
`report.py` renders into `reports/RESULTS.md` — quote numbers from there, not
from this reference.

Top-level keys:

| Key | Type | Meaning |
|---|---|---|
| `run` | string | The run directory analyzed |
| `config` | object | Provenance-stamped config: `effort`, `runs`, `ci_level`, `bootstrap_resamples`, `seed`, `provenance` (which config source was used) |
| `mc` | object | Present only if `mc_responses.jsonl` exists in the run dir |
| `open` | object or null | Null if `open_scores.jsonl` is missing |

### `mc` object

| Key | Meaning |
|---|---|
| `overall` | Per-model map. Keys per model: `label`, `tier`, `mean`, `lo`, `hi`, `n`, `sem` (item-level bootstrap over per-item accuracy), `cp_lo`, `cp_hi` (exact Clopper–Pearson CI over item-majority correctness), `parse_fail_rate`, `mean_within_item_sd` (run-to-run variance), `served_mismatch_artifact`, `served_mismatch_genuine` (served-model audit counts), `n_call_failed`, `n_calls` |
| `by_dimension`, `by_difficulty`, `by_axis` | Same bootstrap-CI structure per group |
| `pairwise` | List of model-pair comparisons on common items: `a`, `a_label`, `b`, `b_label`, `diff`, `lo`, `hi`, `p_bootstrap`, `mcnemar_p`, `p_holm`, `significant_holm` (Holm family = all MC pairs) |
| `item_analysis` | `n_items`, `mean_difficulty_p`, `mean_discrimination`, `n_items_with_discrimination`, `n_ceiling_gt_0.95`, `n_floor_lt_0.30`, `n_low_discrimination_lt_0.10`, `hardest` (10 lowest-p items) |
| `n_records` | Raw record count, including excluded records |

### `open` object

| Key | Meaning |
|---|---|
| `overall` | Per-model map: `label`, `tier`, `mean`, `lo`, `hi`, `n`, `sem` (bootstrap over per-item mean `composite_100`), `n_unscored_records`, `mean_must_include_coverage`, `mean_should_not_violations`, `judge_dimension_means` (item-weighted per-dimension means on the 1–5 scale) |
| `by_dimension` | Bootstrap over per-item means per open dimension |
| `pairwise` | `a`, `a_label`, `b`, `b_label`, `diff`, `lo`, `hi`, `p_bootstrap`, `p_holm`, `significant_holm` (no McNemar — that is MC-only) |
| `judge_irr` | `krippendorff_alpha` (interval α over persona composites, primary judge rows only), `per_dimension_alpha`, `min_dimension_alpha`, `n_personas`, `n_units`; null when < 2 personas, no units, or no `open_judge_raw.jsonl` |
| `n_records` | Raw `open_scores.jsonl` record count |

Rounding conventions inside the file: MC pairwise `diff`/`lo`/`hi` to 4 dp
and p-values to 5 dp; open pairwise `diff`/`lo`/`hi` to 3 dp;
`judge_dimension_means` to 3 dp. See the
[statistics explanation](../explanation/statistics.md) for what these numbers
mean and why the units of resampling are per-item, not per-record.
