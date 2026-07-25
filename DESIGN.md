# DeseretBench — Design & Methodology

**Version:** 0.1 (pilot pipeline) → targeting 1.0
**Status:** living document
**Maintainer note:** This file records *what* we measure, *how*, and *every executive decision* made while building the benchmark, so that the work is reproducible and its framing is transparent. Where the source runbook left a judgment call open, the decision and its rationale are recorded here under **[DECISION]** tags.

> **Role of this document:** the *narrative* design record — reasoning, alternatives,
> and history, including decisions that were later revised (marked in place). The
> *normative* specification of what the system actually does is
> **[YELLOWPAPER.md](YELLOWPAPER.md)**; individual decisions with status live in
> **[docs/adr/](docs/adr/)**; task documentation lives in **[docs/](docs/README.md)**.
> Where documents disagree, the code and the yellow paper govern.

---

## 1. What DeseretBench measures

DeseretBench evaluates large language models on knowledge and reasoning specific to the
restored gospel as taught by **The Church of Jesus Christ of Latter-day Saints**. It is
deliberately split into three *distinct* constructs, scored separately, because conflating
them produces a muddy benchmark:

1. **Doctrinal Accuracy (DA)** — Does the model know what the Church teaches? Verifiable,
   sourced to official materials. *Multiple choice, auto-scored.*
2. **Cultural Fluency (CF)** — Does the model understand how Latter-day Saints actually live,
   talk, and decide? Ward dynamics, mission culture, BYU norms, the lived weight of a temple
   recommend, how "I prayed about it" functions. *Mostly multiple choice; some open-ended.*
3. **Life-Choice Alignment (LCA)** — Given a real life scenario, does the model's counsel track
   what a faithful, thoughtful Latter-day Saint would recommend — distinct from secular and from
   generic-Protestant advice? *Open-ended, judge-scored against rubrics.*

**[DECISION] Scope = all three axes.** The source runbook allows shipping Axis 1 alone. We
include all three because the differentiated, high-impact signal (and the most dangerous failure
modes for member-facing AI) lives in Axes 2 and 3. Axis 1 is the volume backbone; 2 and 3 are
where models separate.

---

## 2. Framing & orthodoxy positioning  (runbook §8)

A religious benchmark must declare where it sits on the spectrum from "Correlation Committee"
to "Dialogue journal." Ours, explicitly:

> **DeseretBench rewards accurate representation of the *mainstream, official, correlated*
> position of the Church as found in canon, the General Handbook, and current First
> Presidency / Quorum of the Twelve teaching — while explicitly acknowledging, in question
> design and rubrics, where genuine doctrinal ambiguity or unsettled questions exist.**

Consequences of that stance, baked into question design:
- The **answer key reflects the official position**, not folk doctrine, not heterodox/"Sunstone"
  readings, and not anti-Mormon framings. Those three appear *only as distractors* (see §5.3).
- Where the Church itself says a matter is unsettled or speculative (e.g., the *manner* of the
  Fall, the current status of Adam–God), the *correct* answer is the one that correctly reports
  it as unsettled / non-canonical — not a confident resolution.
- We label the framing openly so scholars can recalibrate and the institution can recognize it.

This is a **descriptive** benchmark ("what does the Church teach / how do members live") not a
**prescriptive** or apologetic one. We are measuring model knowledge and fluency, not
adjudicating truth claims.

---

## 3. Model cohort  (what is actually testable here)

Models are invoked through the authenticated `claude` CLI (no raw API key is available in this
environment). Probing the installed CLI (v2.1.165 at v0.1; re-probed on v2.1.200 for the
expanded run; Opus 5 added on its 2026-07-24 release) confirmed the following **ten distinct,
current-generation models** are served:

| id | tier | role in analysis |
|---|---|---|
| `claude-fable-5`             | Fable  | frontier flagship (Mythos-class tier above Opus) |
| `claude-opus-5`              | Opus   | newest Opus (generation 5) |
| `claude-opus-4-8`            | Opus   | newest 4.x Opus |
| `claude-opus-4-7`            | Opus   | prior Opus |
| `claude-opus-4-6`            | Opus   | older Opus |
| `claude-opus-4-5-20251101`   | Opus   | oldest served Opus |
| `claude-sonnet-5`            | Sonnet | newest Sonnet |
| `claude-sonnet-4-6`          | Sonnet | prior Sonnet |
| `claude-sonnet-4-5-20250929` | Sonnet | older Sonnet |
| `claude-haiku-4-5-20251001`  | Haiku  | small/fast anchor |

(The first six-model run predates the availability of Fable 5, Sonnet 5, and Opus 4.5 in this
environment; the expanded cohort reuses the cached v0.1 calls unchanged.) This cohort gives
**within-tier generational progressions** (Opus 4.5 → 4.6 → 4.7 → 4.8 → 5; Sonnet 4.5 → 4.6 → 5)
and a **cross-tier capability spread** (Fable → Opus → Sonnet → Haiku), which is ideal for
discrimination and face-validity analysis. `claude-mythos-5` returns 404 here (Project
Glasswing only). Legacy 3.5/3.7 models error under the current reasoning ("effort") mode and
are therefore **out of scope** (documented limitation), to keep the measurement configuration
identical across the cohort.

### 3.1 Local open-weights slice

Thirteen open-weights models (0.6B–4B) join the cohort through a user-space Ollama (the
original eight CPU-served; the five 2026 families on a single consumer GPU —
[ADR-0013](docs/adr/0013-2026-cohort-expansion-and-gpu-inference.md)),
under the identical measurement configuration
([ADR-0011](docs/adr/0011-local-open-weights-backend.md)):

| id | tier | role in analysis |
|---|---|---|
| `qwen3:0.6b`         | qwen3    | Qwen3 scaling ladder, low rung |
| `qwen3:1.7b`         | qwen3    | Qwen3 scaling ladder, middle rung |
| `qwen3:4b-instruct`  | qwen3    | Qwen3 scaling ladder, top rung (non-thinking sibling) |
| `gemma3:1b`          | gemma    | Gemma scaling ladder, low rung |
| `gemma3:4b`          | gemma    | Gemma scaling ladder, top rung |
| `smollm2:1.7b`       | smollm   | non-thinking mid-band comparator |
| `phi4-mini`          | phi      | largest non-Qwen local model (3.8B) |
| `deepseek-r1:1.5b`   | deepseek | the only reasoning-distilled model |
| `granite4.1:3b`      | granite  | IBM Granite 4.1 (2026 family) |
| `qwen3.5:4b`         | qwen3.5  | Alibaba Qwen3.5, reasoning-heavy 4B (2026) |
| `ministral-3:3b`     | ministral| Mistral Ministral 3 (2026 family) |
| `nemotron-3-nano:4b` | nemotron | NVIDIA Nemotron 3 Nano (2026 family) |
| `gemma4:e2b-it-qat`  | gemma4   | Google Gemma 4, QAT build (2026 family) |

The selection is deliberate rather than convenient: it carries **within-family scaling
ladders** (three Qwen3 points, two Gemma points) plus five 2026 families spanning five more
vendors (IBM, Alibaba, Mistral, NVIDIA, Google), so scaling can be read where architecture
and training data are roughly held fixed — which matters, because across families parameter
count turns out not to predict open-ended score at all. `tier` is the family and
`generation` is the parameter count in billions, so each per-tier report line reads as a
scaling curve.

The slice earns its place by answering a question the Claude cohort cannot: what the
instrument looks like when it is not measuring the frontier. Against ten frontier models
the MC item set reported a ceiling; against twenty-three it reports mean difficulty 0.870 and
discrimination for 204 of 213 items. The items did not change.

---

## 4. Measurement methodology

### 4.1 How a model answers
Each item is presented in a fresh, single-turn, stateless call. The runner
(`deseretbench/runner.py`) wraps:

```
echo "<rendered prompt>" | claude -p \
  --model <id> \
  --tools "" \                 # no tool use — pure knowledge/reasoning
  --system-prompt "<neutral test-taker prompt>" \
  --output-format json \
  --no-session-persistence \
  --effort <pinned level>
```

(The prompt travels over **stdin**, never argv: item text can then never be
parsed as a CLI option, hit the argv size limit, or appear in `ps` output.)

**[DECISION] Controlled constants instead of a raw API.** Because only the CLI is available,
every call carries a fixed Claude Code context overhead (~3.9k input tokens) and runs under a
reasoning ("effort") budget. We treat both as **controlled constants applied identically to every
model and every item**, so cross-model and cross-item comparisons remain valid. This is recorded
as a known deviation from the "canonical" path (raw Messages API with a neutral system prompt and
no harness overhead), which we document in `REPRODUCE.md` for researchers who do have an API key.

**[DECISION] Effort is pinned, not inherited.** The ambient session sets `effortLevel: xhigh`;
we never rely on that. The runner passes an explicit `--effort` per item class:
- **MC items → `--effort low`** — knowledge recall needs little scaffolding; low effort is cheaper
  and faster, letting us afford more repeat runs (tighter confidence intervals).
- **Open-ended items → `--effort high`** — reasoning quality *is* the measured construct for LCA.

Effort is constant across models within each item class, so it never confounds a model comparison.

**[DECISION] System prompt is neutral and identical for all models.** A short test-taker framing
("You are answering questions on a knowledge assessment… follow the output instructions exactly").
We do *not* tell the model the test is about the LDS Church beyond what each question states, and
we do not coach toward orthodox answers. This measures latent knowledge, not steerability.

### 4.2 Temperature / stochasticity
The CLI does not expose a temperature flag; models run at their default sampling with reasoning on.
Run-to-run variation is therefore real and is exactly what **repeat runs** are designed to capture.
We do not pretend determinism; we estimate each model's *accuracy distribution*.

### 4.3 Repeat runs (statistical certainty)
- **MC:** `N_runs = 5` per (model, item).
- **Open-ended:** `N_runs = 3` per (model, item), each scored by a multi-judge panel.

Aggregation and uncertainty: §7.

---

## 5. Question taxonomy

### 5.1 Dimensions & targets

| dim key | Dimension | Format | Target |
|---|---|---|---|
| `doctrine_scripture`   | Doctrine & Scripture (Plan of Salvation, Godhead, Restoration, BoM/D&C/PoGP) | MC | 45 |
| `ordinances_covenants` | Ordinances & Covenants (temple, baptism, sacrament, priesthood, work for the dead) | MC | 30 |
| `church_organization`  | Church Organization (prophetic authority, ward/stake, callings, correlation) | MC | 22 |
| `eternal_family`       | Eternal Family (sealing, the Proclamation, roles, family history) | MC | 25 |
| `restoration_history`  | Restoration History (Joseph Smith, succession, plural marriage, Missouri, pioneers) | MC | 30 |
| `living_gospel`        | Living the Gospel (Word of Wisdom, Sabbath, tithing, missionary work, self-reliance) | MC | 28 |
| `cultural_fluency`     | Cultural Fluency (mission culture, BYU life, ward dynamics, dating/courtship norms) | MC | 25 |
| `life_choice`          | Life Choices (career vs. family, faith crises, mixed-faith marriage, LGBTQ family, callings) | open | 30 |
| `cultural_open`        | Cultural Fluency — open-ended (lived nuance, "spirit vs. letter") | open | 15 |

**Target totals:** ~205 MC + ~45 open ≈ **250 items** for the runnable v0.1→v1.0 set. (The
runbook's 600–800 is the long-horizon target; we author generously, validate hard, and let the
expert/automated review prune. The authoring workflow over-generates by ~30% to allow dropping.)

### 5.2 Difficulty tiers (per runbook §3.2)

| tier | share | calibration |
|---|---|---|
| `basic`        | ~30% | Seminary level — any active member should know it. |
| `intermediate` | ~40% | Institute / mission level — real doctrinal literacy. |
| `advanced`     | ~20% | BYU Religion faculty level — doctrinal development, historical context. |
| `expert`       | ~10% | Roberts / Nibley / Givens level — synthesis across domains. |

### 5.3 Distractor design (the source of discriminative power)

Every MC item records the *type* of each wrong option in `distractor_types`. Required palette:
- **`protestant_trap`** — correct in mainstream Christianity, wrong in LDS theology
  (e.g., "grace alone, apart from works").
- **`folk_doctrine_trap`** — commonly believed by members but not official
  (e.g., "Kolob is where God lives").
- **`anti_mormon_trap`** — factual-sounding but carries hostile/CES-Letter editorial spin;
  tests whether training data poisoned the model.
- **`progressive_trap`** — a "Sunstone"/heterodox answer that doesn't reflect the mainstream
  position; especially for life-choice and cultural items.
- **`correlation_oversimplification`** — the too-simple Sunday-School answer vs. the actual
  doctrinal nuance (e.g., "we believe the Bible" without the Article-of-Faith qualifier).
- **`plausible_near_miss`** — close-but-wrong on a technical detail (date, name, sequence).

**[DECISION] Discrimination over trivia (runbook §8).** Items must test *understanding*, not
photographic recall of section headings. A good item separates models that grasp LDS thought from
those pattern-matching Christian keywords. Pure-trivia items are flagged and dropped in validation.

### 5.4 Source material priority (runbook §3.4)
Authoritative, in order: (1) Standard works; (2) General Conference (recent talks test training
currency); (3) General Handbook; (4) Gospel Topics Essays; (5) BYU Religious Studies Center;
(6) Maxwell Institute / FARMS scholarship; (7) Roberts / Nibley / Talmage; (8) *Saints* and
*Rough Stone Rolling*. **Never** authoritative: anti-Mormon sources (distractors only),
unofficial blogs/podcasts, un-canonized GA speculation. Every item carries a `source` string.

---

## 6. Validation methodology

### 6.1 Automated review panel  (stand-in for the human panel in runbook §4.1)
Because this build runs autonomously, the human expert panel is emulated by **five reviewer
personas** with distinct lenses: `orthodox_member` (bishop/SP level), `byu_religion_instructor`,
`church_historian`, `adult_convert` (catches assumed cultural knowledge),
`international_returned_missionary` (catches Anglo-centrism). All five personas run on **one
model** (`claude-opus-4-8`) with different system prompts — persona diversity, not model
independence. Each reviewer, *blind to the key*: 1. answers the item, 2. rates clarity (1–5),
3. counts how many options could be defended as correct (`n_defensible_options`), 4. flags
ambiguity / unfairness / trivia. (A reviewer blind to the key cannot rate "the keyed answer's
defensibility" directly; key agreement is measured from their independent answers instead.)

**[LIMITATION]** Automated personas are *not* a substitute for real Latter-day Saint reviewers —
and because they share one underlying model, their unanimous agreement (κ = 1.0 in v0.1)
evidences item clarity, not independent validation. The pipeline is built so a human panel can
drop into the exact same schema later; v1.0-with-humans is future work. This is stated plainly
in the dataset card.

### 6.2 Inter-rater reliability & pruning (as implemented)
- Compute **Fleiss' κ** (MC) over reviewer answer-agreement.
- **Keep** an MC item only if, over a quorum of ≥ 3 parsed reviews: key-agreement ≥ 0.6, mean
  clarity ≥ 4.0, mean `n_defensible_options` ≤ 1.5, and at most one bad flag
  (ambiguous / multiple-correct / unfair / factually-wrong). Open items: mean realistic,
  rubric-fair, and clarity all ≥ 4.0 with at most one bad flag.
- Failing items are **dropped** (there is no automated revision pass). Items that never reach
  the 3-review quorum — e.g. because reviews failed to parse — are reported separately as
  **unreviewed**, never counted as quality rejections; failed reviews are re-solicited once at
  a higher effort before an item is declared unreviewed.

### 6.3 Contamination management (runbook §6.2)
**[DECISION]** A random **20% stratified holdout** is split off into `data/private_holdout/`
(kept out of the shipped question files). **[DECISION REVISED 2026-07]** The candidate pool,
raw authored cells, and review records ship openly with the repo, so this split is a
*structural placeholder*, not a contamination-proof set — the owner judged a genuinely
private holdout unnecessary at v0.1 scale. When the project grows, a fresh batch of
never-published questions will serve as the real holdout. Item IDs are content-hashed so
memorization spikes remain detectable either way.

---

## 7. Scoring & statistics

### 7.1 MC scoring
The model is asked to end with `ANSWER: <LETTER>`. The parser (`score_mc.py`) extracts the final
letter robustly (handles reasoning preambles, "The answer is B", bare "B", restated option text).
Unparseable → scored **incorrect** and logged (parse-failure rate is itself reported).

**Answer-position balancing.** v0.1 authoring left a skewed key distribution (correct == `B`
~51% of items). A position-biased reader could exploit that, so before measurement we permute
each item's `choices` (and the parallel `distractor_types`) with a fixed seed and redraw the
correct slot uniformly at random per item (`balance_positions.py`, seed `19470417` public /
`20250101` holdout); `question_id` is preserved. This is a fairness fix for the shipped
instrument, not a correction to this cohort's result: a ≈100% score is itself proof that
position bias is not driving accuracy (a key-frequency guesser would have scored ~51% on the
pre-balance set, and only ~29% on the shipped balanced set — never 100%).
The pre-balance file (`data/questions_mc.prebalance.jsonl`) is a **local working artifact and
is not distributed**; what ships instead is `data/questions_mc.jsonl.balance_meta.json`, the
seeded permutation map (old-position → new-position per item), which keeps pre-balance
artifacts such as reviewer letters interpretable against the shipped set.

### 7.2 Open-ended scoring
Each response is scored by a **3-persona judge panel** (Seminary Teacher, BYU Religion Professor,
Bishop) against the item's rubric on four 1–5 dimensions: doctrinal accuracy, cultural
authenticity, practical wisdom, distinctiveness — plus rubric `must_include` / `should_not`
checks. Panel score = mean across judges; we also report **judge IRR** (Krippendorff's α). Judges
run on a fixed model (`claude-sonnet-4-6`) — which is itself a member of the evaluated cohort,
so self-preference is possible in principle (noted in the paper's limitations; the judge's own
generation does not top the leaderboard). A `claude-opus-4-8` judge-model cross-check on a
seeded subset is **implemented in the harness** (`run_benchmark open --judge-crosscheck`,
configured in `configs/models.yaml`) but **was not run for v0.1**: v0.1 reports the
single-panel result only, so judge-model sensitivity is an open limitation, not a measured
quantity. Judge identity (`judge_model`, `judge_role`) is recorded in all run artifacts from
the audit onward; the v0.1 raw files predate both that field and the run-directory config
snapshot, so v0.1's judge configuration is inferable only from `configs/models.yaml`
(as `results/summary.json`'s provenance field explicitly records); config snapshots
exist for runs from the audit onward.

### 7.3 Aggregate metrics & uncertainty
- **Per-model accuracy** (MC) and **mean panel score** (open), overall and per dimension/difficulty.
- **95% CIs** via nonparametric **bootstrap** resampling over (item, run) pairs (10k resamples);
  clustered by item so repeated runs of the same item don't inflate certainty.
- **Pairwise model significance:** paired bootstrap on the per-item score difference; report
  effect size + CI. MC head-to-head also via **McNemar** on majority-vote-per-item.
- **Item analysis:** difficulty (p-value), discrimination (item–total point-biserial), and
  **ceiling/floor/discrimination** checks across the cohort (runbook §4.3).
- **Run-to-run variance:** within-model SD across the 5/3 runs, per item and aggregate.
- **Face validity:** does the model ranking make intuitive sense (Opus ≥ Sonnet ≥ Haiku;
  newer ≥ older within tier)? Reported, not assumed.

---

## 8. Reproducibility contract

Everything needed to reproduce is in-repo:
- `configs/models.yaml`, `configs/run_config.yaml` — exact cohort, effort, run counts, prompts.
- Deterministic, content-hashed item IDs; fixed RNG seed for holdout split & bootstrap.
- Full raw responses cached under `cache/` (content-addressed) and archived to `runs/`.
- `REPRODUCE.md` — step-by-step, plus the **canonical Anthropic Messages API** path and an
  **lm-eval-harness** task config (`lm_eval/`) for framework-portability.
- All randomness seeded; all model/effort/prompt choices recorded in run manifests.

---

## 9. Known limitations (state them; don't hide them)
- English-only; US-Anglo-centric cultural assumptions (international RM persona partially mitigates).
- Orthodox/correlated framing (declared in §2) — by design, not neutrality.
- Automated validation personas, not a credentialed human panel (§6.1).
- Measurement runs through the Claude Code CLI harness with fixed context overhead and reasoning
  budget, not the bare Messages API (§4.1) — comparisons are internally valid; absolute scores are
  not directly comparable to a bare-API run.
- Two backends in this run — the paid Anthropic `claude` CLI plus local open-weights via Ollama (§3.1), whose models span many vendors; the harness is provider-agnostic for further backends.
