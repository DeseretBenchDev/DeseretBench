# Glossary

Short definitions of DeseretBench terms, alphabetized. Each entry links to the document
that treats the concept fully.

**axis** — One of the three things the benchmark measures: `doctrinal_accuracy`,
`cultural_fluency`, or `life_choice_alignment`. Each axis is scored separately and never
collapsed into a single number. See [DESIGN.md](../../DESIGN.md).

**balance marker** — The `questions_mc.jsonl.balance_meta.json` file written by
`balance_positions`, recording that the MC key positions have been shuffled (with a fixed
seed) plus the resulting position map; its presence signals "already balanced," which is
why `run_all.sh` deletes it after re-validation. See
[measurement integrity](../explanation/measurement-integrity.md).

**cache key** — The sha256 hash of `{backend, model, system prompt, prompt, effort,
run_index}` that names a cached call result; timeout, tools, retries, and parallelism are
deliberately excluded so operational tuning never invalidates the cache. See the
[cache reference](cache.md).

**candidate pool** — The full set of authored items before validation filtering: 267 MC
and 57 open candidates, published in `data/candidates_*.jsonl` alongside their reviews.
The public question sets are the survivors. See the
[holdout stance](../explanation/holdout-stance.md).

**Clopper–Pearson** — An exact (conservative) binomial confidence interval, used for
majority-correct accuracy counts where a normal approximation would be dubious. See
[statistics](../explanation/statistics.md).

**composite score** — The open-ended headline number: the unweighted mean of the four
judge-dimension means (1–5 scale), rescaled to 0–100 as `(mean − 1) / 4 × 100`. Missing
dimensions are treated as missing data, never as zeros. See
[judge design](../explanation/judge-design.md).

**config snapshot** — `<run_dir>/config_snapshot.json`, written after each phase's output
files land, recording the cohort, the full run config, and per-phase extras — the
provenance record for what settings actually produced a run. See
[measurement integrity](../explanation/measurement-integrity.md).

**content-addressed cache** — The flat directory of `<sha256>.json` files (repo-root
`./cache`) holding one successful call result per cache key; failures are never cached,
which is what makes re-running a phase retry only failed work. See the
[cache reference](cache.md).

**crosscheck judge** — A second judge model (`judges.crosscheck_model`, Opus family)
that re-judges a seeded 25% subset of responses with all personas, to test sensitivity to
the choice of judge model. Its verdicts are recorded raw-only and never feed panel
scores; it is implemented but has not yet been run. See
[run the judge crosscheck](../how-to/run-judge-crosscheck.md).

**currency probe** — An item keyed to a 2018–2026 change (e.g. the 2025 succession, the
2019 Word of Wisdom clarifications) that tests whether a model's knowledge is current
rather than frozen at an older training cut. See [DESIGN.md](../../DESIGN.md).

**dated-suffix rule** — The served-model tolerance rule: a requested alias and a served
id match if one extends the other by exactly a `-YYYYMMDD` suffix (regex `-\d{8}$`);
any other suffix difference is a mismatch. See
[measurement integrity](../explanation/measurement-integrity.md).

**difficulty ladder** — The four MC difficulty tiers: *basic* (seminary level),
*intermediate* (institute/mission), *advanced* (BYU Religion faculty), *expert*
(Roberts/Nibley/Givens-level synthesis). See [DESIGN.md](../../DESIGN.md).

**dimension** — A content area within an axis, e.g. `doctrine_scripture`,
`restoration_history`, `cultural_fluency` for MC, or `life_choice` and `cultural_open`
for open items. (The judge rubric also scores four *judge dimensions*, which are a
different thing — see **judge panel**.) See [DESIGN.md](../../DESIGN.md).

**distractor type** — The label attached to every MC choice explaining what kind of
wrong it is; the correct choice is labeled `correct`. The six trap types
(see [why typed distractors](../explanation/why-typed-distractors.md)):

- **protestant_trap** — correct in mainstream Christianity, wrong in LDS theology.
- **folk_doctrine_trap** — commonly believed by members but not official teaching.
- **anti_mormon_trap** — factual-sounding hostile framing; tests training-data poisoning.
- **progressive_trap** — a heterodox/"Sunstone" reading, not the mainstream position.
- **correlation_oversimplification** — the too-simple Sunday-School answer versus the
  real nuance.
- **plausible_near_miss** — a close-but-wrong technical detail (date, name, sequence).

**effort** — The reasoning-budget setting passed on every call, pinned per item class
(MC low, open-ended high, judge medium) and constant across models. On adaptive-thinking
model families it maps to the API effort parameter; on older families it maps to a fixed
thinking-token *budget* instead. See the
[configuration reference](configuration.md).

**holdout (nominal)** — `data/private_holdout/` (53 MC + 10 open items) is untracked in
git, but since v0.1 publishes the full candidate pool and reviews, its contents are
derivable from published data. It is a structural placeholder, not a secret; a genuinely
private holdout is deferred. See the [holdout stance](../explanation/holdout-stance.md).

**Holm correction** — Holm–Bonferroni step-down adjustment applied to the family of
pairwise model-comparison p-values, controlling the family-wise error rate. See
[statistics](../explanation/statistics.md).

**item discrimination** — Corrected item-total point-biserial correlation: how well an
item separates high-scoring from low-scoring models. Undefined for zero-variance
(ceiling/floor) items. See [statistics](../explanation/statistics.md).

**judge panel** — One judge model (`judges.primary_model` in `configs/models.yaml`)
prompted three times per response, once per persona; the "panel" is three prompted
perspectives of a single model, **not** three independent judge models. Each verdict
scores four judge dimensions (doctrinal accuracy, cultural authenticity, practical
wisdom, distinctiveness) plus rubric coverage. See
[judge design](../explanation/judge-design.md).

**Krippendorff alpha** — Inter-rater reliability (interval metric, missing-data-aware)
computed across the three persona verdicts, reported so readers can see how much the
"panel" actually agrees with itself. See [statistics](../explanation/statistics.md).

**per-item bootstrap** — Resampling items (not raw responses) with replacement to get
CIs and paired differences, so the unit of inference matches the unit of measurement.
Pairwise comparisons use only items both models answered. See
[statistics](../explanation/statistics.md).

**permanent error** — A call error matching a marker list (auth, billing, unknown model,
served mismatch, invalid request, …) that fails fast without retries, because retrying
cannot fix it. Timeouts and rate limits deliberately never match. See
[recover an interrupted run](../how-to/recover-interrupted-run.md).

**persona** — One of the three judge framings — `seminary_teacher`,
`byu_religion_professor`, `bishop` — each eliciting a different evaluative stance from
the single judge model. See [judge design](../explanation/judge-design.md).

**position map** — Part of the balance marker: a per-item record of where the correct
answer sat before and after key-position shuffling, so the shuffle is auditable and
reversible. See [measurement integrity](../explanation/measurement-integrity.md).

**quorum** — In question validation, the minimum number of successfully parsed reviews
an item needs before its keep/drop verdict counts; items whose reviews failed to parse
even after re-solicit are reported as unreviewed rather than silently judged. See
[add questions](../how-to/add-questions.md).

**re-solicit** — The validation retry pass that re-requests failed reviews at a higher
effort level, since a cached parse failure would replay identically at the same effort.
See [add questions](../how-to/add-questions.md).

**run_index** — The repeat counter (0-based) for a given (model, item) pair; it is part
of the cache key, which is how repeat runs get distinct cached results despite identical
prompts. See the [cache reference](cache.md).

**served-model verification** — The check that the model id the CLI reports serving
matches the model requested (up to the dated-suffix rule); a mismatch flips the result to
a permanent error rather than laundering a silent fallback into the data. See
[measurement integrity](../explanation/measurement-integrity.md).

**smoothed bootstrap p** — The two-sided Monte-Carlo p-value with add-one smoothing, so
a bootstrap p can never be exactly zero — the floor is set by the number of resamples.
See [statistics](../explanation/statistics.md).

**usage-limit window** — The rolling session usage limit the authenticated `claude` CLI
enforces; long runs hit 429s partway through and must wait out the reset window, which is
what the wave loop's sleep interval (default 1500 s) is for. See
[recover an interrupted run](../how-to/recover-interrupted-run.md).

**wave** — One full pass of a benchmark phase inside `resilient_run.sh`: run the phase,
count remaining failures, and either stop clean, give up (default cap 40 waves), or sleep
and go again. See the [scripts reference](scripts.md).
