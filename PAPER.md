# DeseretBench: Evaluating Latter-day Saint Doctrinal Accuracy, Cultural Fluency, and Life-Choice Alignment in Large Language Models

*DeseretBench contributors — v0.1 preprint draft, 2026*

## Abstract

Large language models are already being used to answer doctrinal and life-decision
questions for members of The Church of Jesus Christ of Latter-day Saints, yet no
instrument has existed to measure the quality of those answers. We present **DeseretBench**,
a reproducible benchmark spanning three deliberately separated constructs — *doctrinal
accuracy*, *cultural fluency*, and *life-choice alignment* — for a religious tradition whose
doctrine is highly specific, well-documented, and sufficiently distinct from mainstream
Christianity that models cannot rely on generic religious training signal. The benchmark
combines auto-scored multiple-choice items with typed, discriminative distractors and
judge-panel-scored open-ended scenarios, validated by a five-persona blind review. We
evaluate twenty-two models — nine current-generation Claude models (Fable 5, Opus
4.5/4.6/4.7/4.8, Sonnet 4.5/4.6/5, Haiku 4.5) and thirteen local open-weights models from
0.6B to 4B (Qwen3, Gemma 3, SmolLM2, Phi-4 Mini, DeepSeek-R1-Distill, Granite 4.1, Qwen3.5,
Ministral 3, Nemotron 3 Nano, Gemma 4) — with repeat runs,
and report bootstrap confidence intervals, pairwise significance, classical item analysis,
and judge inter-rater reliability. Multiple-choice doctrinal recall **saturates at the
frontier while discriminating sharply below it**: all 36 Claude-vs-Claude comparisons are
non-significant after correction, yet 173 of the 231 comparisons across the full cohort are
significant, and MC accuracy rises from 0.521 (R1-Distill 1.5B) to 0.932 (Qwen3.5 4B) before
reaching Claude's 0.986–1.000. The open-ended axis separates the cohort reliably (judge
Krippendorff's α = 0.9924, 2,640 scored units), with composite scores from 98.2 (Opus 4.7)
down to 0.3 (R1-Distill 1.5B). Comparing the two axes exposes a **capability gap that MC
alone conceals**: the best local model on MC (Qwen3.5 4B, 0.932) sits inside Claude's range,
yet scores only 17.6 open-ended, well under half of the weakest Claude (Haiku 4.5, 48.5). Within the 1.7–3.8B band,
parameter count does not predict open-ended score. We also find a **non-monotonic
generational trend**: within Opus, scores rise across 4.5, 4.6 and 4.7, then fall at 4.8
(91.4), significantly below Opus 4.7 (98.2); and Sonnet 5 (86.6) does not improve on Sonnet
4.6 (89.6). The one newest-generation model that reaches the top is **Fable 5 (97.9)**, a
higher tier, statistically tied with Opus 4.7 for first. Newer is not automatically more
culturally aligned; for two of the three newest models here, it is measurably less so.

## 1. Motivation

Religious knowledge is an underexplored axis of LLM evaluation. General benchmarks (MMLU and
successors) include only a thin "world religions" slice, almost always at a comparative-
religion survey level, and they reward generic recall over within-tradition understanding.
The Latter-day Saint tradition is an unusually good test case: (a) its distinctive doctrines
(an embodied Godhead of three separate beings, premortal intelligences co-eternal with God,
three degrees of glory, temple ordinances and vicarious work for the dead, continuing
revelation) diverge sharply from creedal Christianity, so a model that pattern-matches
Christian keywords will fail; (b) the corpus is highly documented (canon, the General
Handbook, General Conference, the Gospel Topics Essays); and (c) the practical stakes are
real — member-facing AI tools give counsel on missions, marriage, faith crises, and family.

We distinguish three constructs because conflating them produces a muddy benchmark:
**doctrinal accuracy** (what the Church teaches — verifiable), **cultural fluency** (how
Latter-day Saints actually live and decide — ward dynamics, mission culture, the lived weight
of a temple recommend), and **life-choice alignment** (whether counsel tracks a faithful,
thoughtful member's reasoning, distinct from secular and from generic-Protestant advice).

## 2. Related work

General-knowledge suites (MMLU, MMLU-Pro, BIG-bench) touch religion only marginally.
Faith-specific evaluation efforts (e.g., Islamic-knowledge suites, Bible-QA sets) show the
value of within-tradition probes but rarely separate *cultural* and *advice* competence from
*factual* recall, and rarely audit distractor quality. DeseretBench contributes (i) a typed
distractor palette engineered for discrimination against a specific theological tradition,
(ii) a judge-panel rubric methodology for life-advice alignment, and (iii) a fully seeded,
reproducible harness with item analysis and inter-rater reliability.

## 3. Methodology

### 3.1 Framing
DeseretBench keys answers to the **mainstream, official, correlated** position of the Church,
while explicitly treating matters the Church itself leaves unsettled as unsettled. Folk
doctrine, heterodox readings, and anti-Mormon framings appear *only as distractors*. The
benchmark is descriptive, not apologetic (see DESIGN.md §2).

### 3.2 Items
Seven multiple-choice dimensions × four difficulty tiers (basic → expert), plus open-ended
life-choice and cultural scenarios. Each MC distractor is typed (`protestant_trap`,
`folk_doctrine_trap`, `anti_mormon_trap`, `progressive_trap`,
`correlation_oversimplification`, `plausible_near_miss`); authoring requires ≥2 distinct trap
types per item (98% of shipped items comply; four public items carry only plausible-near-miss
distractors — a validation gate to add in v1.0) and
cite an authoritative source. A subset probes training **currency** against 2018–2026 changes
(name guidance 2018, ministering 2018, Word of Wisdom clarification 2019, Children & Youth
2020, garment redesign 2024, the 2025 succession of President Dallin H. Oaks).

### 3.3 Validation
Five independent reviewer personas (orthodox member, BYU religion instructor, church
historian, adult convert, international returned missionary) reviewed every item *blind to
the key*. Items were retained only when reviewer key-agreement ≥ 0.6, mean clarity ≥ 4/5,
defensible-options ≤ 1.5, and ambiguity flags ≤ 1. We report Fleiss' κ over reviewer answers.
A stratified 20% split is reserved as a nominal holdout; because the full candidate pool
ships with the repository, it is not contamination-proof — a genuinely private holdout of
freshly written questions is deferred until the project has the contributor base to sustain one.

### 3.4 Measurement
Each item is presented in a fresh, single-turn, tool-free call with a neutral test-taker
system prompt, identical across models. Reasoning effort is pinned per item class (MC = low,
open = high) and held constant across models so it never confounds a model comparison. Before
measurement, MC answer positions are randomized with a fixed seed so the key carries no
positional information (authoring had left correct == `B` ~51% of the time). MC is
scored by robust extraction of a final `ANSWER: <letter>`; open-ended responses are scored by
a three-persona judge panel (seminary teacher, BYU religion professor, bishop) on four 1–5
dimensions plus rubric coverage, with a Krippendorff's-α reliability check. We use repeat runs
(MC = 5, open = 3) and report bootstrap 95% CIs (resampling items), pairwise paired-bootstrap
differences with McNemar cross-checks, and classical item difficulty/discrimination.

### 3.5 Cohort
Twenty-two models over nine vendors and two serving paths, all measured under one
configuration.

**Nine current-generation Claude models** served by the local `claude` CLI: Fable 5 (the
Mythos-class tier above Opus), Opus 4.5/4.6/4.7/4.8, Sonnet 4.5/4.6/5, and Haiku 4.5 —
within-tier generational progressions plus a cross-tier capability spread. The initial
six-model run predates the availability of Fable 5, Sonnet 5, and Opus 4.5 in this
environment; the expanded cohort reuses those cached calls unchanged and adds the three new
models under the identical configuration. (Measurement runs through the Claude Code CLI
harness; absolute scores are not directly comparable to a bare-API run, but within-run
comparisons are internally valid.)

**Thirteen local open-weights models** from 0.6B to 4B, served by a user-space Ollama
with one model resident and strictly serial inference: Qwen3 0.6B/1.7B/4B, Gemma 3 1B/4B,
SmolLM2 1.7B, Phi-4 Mini 3.8B, DeepSeek-R1-Distill 1.5B, and five 2026 families — Granite
4.1 3B, Qwen3.5 4B, Ministral 3 3B, Nemotron 3 Nano 4B, and Gemma 4 E2B. The selection is
not a convenience sample: it carries within-family scaling ladders (two Gemma 3 points,
three Qwen3 points) so that scaling can be read *within* a family, where architecture and
training data are held roughly fixed; it includes one reasoning-distilled model to test
whether reasoning training transfers to a knowledge-bound domain; and it spans eight
open-weights vendors (Alibaba, Google, Microsoft, IBM, Mistral, NVIDIA, DeepSeek,
HuggingFace), so a cross-vendor finding cannot be an artifact of one lab's recipe. The
original CPU-served cohort was extended with the five 2026 families on a single consumer
GPU ([ADR-0013](docs/adr/0013-2026-cohort-expansion-and-gpu-inference.md)).

The two halves answer different questions. The Claude cohort asks how frontier models differ
from each other. The local cohort asks what the instrument looks like when it is *not*
measuring the frontier — which, as §4.1 shows, is the only way the item set's discriminative
power becomes visible.

## 4. Results

All numbers are from `runs/v0_1` (seed 19470417, 10,000 bootstrap resamples; MC = 5 runs,
open = 3 runs; 22 models × 213 public MC items and × 40 public open items — 23,430 MC
responses and 2,640 open responses scored by a 3-persona judge panel). Full tables and
figures are in `reports/RESULTS.md` and `reports/leaderboard.html`.

### 4.1 Multiple choice saturates at the frontier and discriminates below it
Among Claude models the set is saturated: Opus 4.5/4.6/4.7/4.8 and Sonnet 4.5/4.6 all score a
perfect **1.000**; Fable 5 **0.999** [0.997, 1.000]; Haiku 4.5 **0.994** [0.987, 1.000]; and
the lowest, Sonnet 5, **0.986** [0.971, 0.998]. Saturation holds at every difficulty tier
including **expert**, and across all seven dimensions. After Holm–Bonferroni correction,
**none** of the 36 Claude-vs-Claude comparisons is significant. Run-to-run variance is
essentially zero (within-item SD = 0.000 for the six ceiling models, 0.002–0.007 for the
rest): MC behavior is near-deterministic at low effort.

Below the frontier the same items separate models cleanly, tracing a capability ladder:
R1-Distill 1.5B **0.521**, Qwen3 0.6B **0.536**, Gemma 3 1B **0.548** → SmolLM2 1.7B
**0.703** → Phi-4 Mini **0.811**, Qwen3 1.7B **0.811**, Gemma 3 4B / Gemma 4 E2B **0.813**,
Nemotron 3 Nano 4B **0.820** → Ministral 3 3B **0.892**, Granite 4.1 3B **0.905**, Qwen3 4B
**0.922**, Qwen3.5 4B **0.932**. Across the full 231-comparison family, **173** comparisons
are significant after correction.

Classical item analysis makes the point quantitatively. Against the nine-model Claude cohort
the item set looked like a ceiling: mean difficulty *p* = 0.998, discrimination defined for
only 7 of 213 items. Against twenty-two models the same 213 items report mean difficulty
*p* = **0.864**, mean discrimination **0.4789**, defined for **204** items, with 43 at
ceiling (*p* > 0.95), **none** at floor, and only **3** low-discrimination items.

**Interpretation:** frontier Claude models have effectively solved factual multiple-choice
Latter-day Saint doctrinal recall, and MC still separates everything below them. The earlier
nine-model reading ("MC is saturated, retaining diagnostic value only for weaker or future
models") predicted this correctly but described the instrument wrongly: the ceiling was a
property of the cohort measured, not of the items.

### 4.2 Open-ended life-choice / cultural reasoning discriminates sharply
The judge-panel composite (0–100) separates the cohort into clear, statistically distinct bands:

| Rank | Model | Composite | 95% CI | Rubric coverage | should-not viol. |
|---|---|---|---|---|---|
| 1 | Opus 4.7 | **98.2** | [96.8, 99.3] | 0.97 | 0.03 |
| 2 | Fable 5 | **97.9** | [96.6, 99.0] | 0.96 | 0.00 |
| 3 | Opus 4.6 | **95.0** | [92.7, 97.0] | 0.94 | 0.03 |
| 4 | Opus 4.8 | **91.4** | [87.9, 94.4] | 0.94 | 0.03 |
| 5 | Sonnet 4.6 | **89.6** | [86.0, 92.8] | 0.91 | 0.08 |
| 6 | Sonnet 5 | **86.6** | [82.0, 90.6] | 0.87 | 0.10 |
| 7 | Opus 4.5 | **83.5** | [79.7, 86.9] | 0.86 | 0.07 |
| 8 | Sonnet 4.5 | **69.7** | [64.9, 74.2] | 0.78 | 0.17 |
| 9 | Haiku 4.5 | **48.5** | [44.2, 52.7] | 0.65 | 0.42 |
| 10 | Qwen3 4B | **21.8** | [18.8, 24.5] | 0.42 | 0.78 |
| 11 | Gemma 4 E2B | **18.7** | [16.0, 21.4] | 0.38 | 0.74 |
| 12 | Granite 4.1 3B | **18.4** | [16.2, 20.6] | 0.33 | 0.98 |
| 13 | Ministral 3 3B | **17.7** | [15.1, 20.1] | 0.35 | 1.17 |
| 14 | Gemma 3 4B | **17.7** | [14.9, 20.5] | 0.33 | 0.62 |
| 15 | Qwen3.5 4B | **17.6** | [15.5, 19.5] | 0.32 | 0.70 |
| 16 | SmolLM2 1.7B | **11.7** | [10.0, 13.3] | 0.21 | 1.01 |
| 17 | Qwen3 1.7B | **9.9** | [8.3, 11.5] | 0.22 | 1.25 |
| 18 | Nemotron 3 Nano 4B | **8.4** | [6.5, 10.4] | 0.19 | 0.97 |
| 19 | Phi-4 Mini | **7.6** | [5.9, 9.3] | 0.20 | 0.97 |
| 20 | Gemma 3 1B | **4.5** | [3.2, 5.9] | 0.12 | 0.75 |
| 21 | Qwen3 0.6B | **2.0** | [1.2, 2.8] | 0.08 | 0.98 |
| 22 | R1-Distill 1.5B | **0.3** | [0.1, 0.6] | 0.02 | 1.00 |

**209** of the 231 pairwise comparisons remain significant after Holm–Bonferroni correction
over the full family. The 22 exceptions are all near-neighbors, and fall in two groups: four
Claude near-ties — Fable 5 vs Opus 4.7 at the very top (Δ = −0.3, raw *p* = 0.66 — a
statistical tie for first), Sonnet 5 vs Sonnet 4.6 (Δ = −2.9), Opus 4.8 vs Sonnet 4.6
(Δ = +1.8), and Opus 4.5 vs Sonnet 5 (Δ = −3.1) — and near-neighbor pairs among the tightly
packed local mid-cohort, where Gemma 3 4B, Gemma 4 E2B, Granite 4.1 3B, Ministral 3 3B and
Qwen3.5 4B cluster within ~1 point of one another (17.6–18.7) and are mutually
indistinguishable. The judge panel is highly reliable: **Krippendorff's α = 0.9924** on the
composite across three personas over 2,640 scored units, and no lower than **0.9758** on any
single judged dimension.

Rubric coverage falls off faster than the composite suggests: the Claude cohort spans
0.65–0.97, while every local model sits at 0.42 or below, and R1-Distill at 0.02. The
`should-not` violation rate inverts the same way, from near zero for the top Claude models
to around or above 1.0 per response for most of the local cohort. Small models are not
only giving thinner answers; they are giving answers that contradict the tradition.

### 4.3 A non-monotonic generational trend
Within Opus, scores rise then fall: **4.5 (83.5) < 4.6 (95.0) < 4.7 (98.2) > 4.8 (91.4)**. The
decline at 4.8 is significant against its immediate predecessor after Holm correction —
4.7 − 4.8 = +6.8 [+4.3, +9.7] (Holm *p* = 0.0462) — as is every step of the earlier rise
(4.6 − 4.5 = +11.5, 4.7 − 4.6 = +3.2, both Holm *p* = 0.0462). (Bootstrap *p*-values use
(r+1)/(B+1) smoothing, so the smallest reportable value at 10,000 resamples is ≈ 0.0002, and
the smallest surviving Holm value in this 231-comparison family is ≈ 0.0462.)

The 4.6 − 4.8 gap is where widening the cohort changed an inference rather than a number.
The estimate is unmoved (Δ = +3.6 [+0.8, +6.6], raw *p* = 0.008, CI excluding zero), but
Holm-corrected over the 22-model family's 231 comparisons it no longer clears 0.05
(*p* = 0.164), where over the nine-model family's 36 it did (*p* = 0.041). Nothing about
Opus 4.6 or 4.8 changed; the correction family grew more than sixfold. Multiple-comparison control is a
cost paid for cohort breadth. A claim this close to threshold should be read as suggestive
rather than established, which is why we report Δ and CI rather than a significance verdict
alone. The
Sonnet line shows the same ceiling effect one generation earlier: 4.5 (69.7) → 4.6 (89.6) is a
large, significant gain (Δ = +19.9 [+15.7, +24.1]), but **Sonnet 5 (86.6) does not improve on
Sonnet 4.6** (Δ = −2.9, raw *p* = 0.13, not significant). So the pattern is not "newer is worse"
as a law — **Fable 5, the newest and highest-tier model, ties for first** — but neither is
"newer is better" automatic: of the three newest-generation models, one (Fable 5) leads, one
(Opus 4.8) significantly regresses, and one (Sonnet 5) plateaus.

### 4.4 Failure modes scale with capability
Rubric coverage and `should_not` violations degrade monotonically down the leaderboard.
The top models (Opus 4.7, Fable 5, Opus 4.6) engage 94–97% of each rubric's required points and
average ≤ 0.03 panel-flagged violations per answer — Fable 5 records **zero** across the set;
Haiku covers only 65% and averages **0.42 violations per answer**. The judged sub-dimensions make
the signature explicit: `distinctiveness` is the lowest-scoring judge dimension for **all
twenty-two models, without exception** — every Claude model, every local model, across a
97-point spread in composite (Haiku 2.49/5 vs. its practical-wisdom 3.48; even Opus 4.8
bottoms out on distinctiveness at 4.38/5, and the leader, Opus 4.7, at 4.88/5; among local
models Qwen3 4B reaches 2.15 on practical wisdom but only 1.57 on distinctiveness). The
ordering holds at every capability level: models score higher on sounding wise than on
sounding distinctively Latter-day Saint. On the `life_choice` sub-score
Haiku reaches only 43 and Sonnet 4.5 only 66 (vs `cultural_open` 56 and 75 respectively), while
Opus 4.7 and Fable 5 sit at ~97–98 on both — weaker models drift toward generic-Christian or
secular counsel exactly when distinctively Latter-day Saint reasoning is required.

### 4.5 The two axes measure different things
The local cohort separates the tracks in a way the Claude-only cohort could not, because its
models are spread widely on both.

**The MC-to-open collapse.** Qwen3 4B answers 92.2% of the MC set correctly, inside the band
where Claude models live, and scores **21.8** on open-ended, less than half of the weakest
Claude in the cohort (Haiku 4.5, 48.5). The gap is not a difficulty artifact. MC supplies
four written options and asks the model to recognize one; the open track asks it to generate
faithful counsel with no options in view.

**Parameter count does not predict open-ended score in the mid band.** Phi-4 Mini (3.8B) ties
Qwen3 1.7B on MC (0.811 each) at more than twice the parameters, yet scores *below* it on
open-ended (7.6 vs 9.9). SmolLM2 1.7B sits well down the MC order (0.703) yet ranks several
places higher on open (11.7), ahead of models that beat it on MC. And the top two local slots
split across the tracks — Qwen3.5 4B leads the local cohort on MC (0.932) while Qwen3 4B leads
on open (21.8) — so this is not a claim that the tracks are unrelated at every scale. It is a
claim that in the band where most local deployment actually happens, an MC score does not tell
you what the model will say.

**Within-family scaling is clean where cross-family comparison is not.** Holding family
fixed, the open-ended axis scales smoothly: Qwen3 0.6B → 1.7B → 4B yields 2.0 → 9.9 → 21.8,
roughly doubling per step; Gemma 1B → 4B yields 4.5 → 17.7. The noise is *between* families,
not within them — consistent with training data and post-training, rather than raw parameter
count, governing this capability.

**MC parse failures separate knowledge from instruction-following.** Qwen3 0.6B fails to emit
a parseable answer on **11.4%** of MC items — five times the next-highest rate in the cohort
(Gemma 3 4B, 2.4%) and more than an order of magnitude above its size-peers (Gemma 3 1B,
0.7%; R1-Distill 1.5B, 0.3%) — while landing at almost exactly their accuracy (0.536 vs 0.548
and 0.521). Two models can miss the same item for unrelated reasons: not knowing the
doctrine, or not following the answer format. Reporting the parse-fail rate alongside
accuracy is what keeps those two failures from being scored as the same thing.

**Reasoning training did not transfer.** R1-Distill 1.5B places last on both tracks (0.521
MC, 0.3 open) despite being the only reasoning-distilled model here. Its answers are neither
truncated nor empty: all 120 responses terminate normally at a median length of ~1,100
characters, and its rubric coverage is 0.02. The prose is fluent and well-structured while
saying almost nothing the Church teaches. Reasoning distillation supplies the form of a good
answer, but the binding constraint in this domain is knowledge, and form does not substitute
for it. A benchmark scoring only structure would rank this model far higher than it
deserves.

## 5. Discussion

**Separating the constructs was the right call.** Had DeseretBench been a multiple-choice
benchmark alone, it would have reported a near-uniform ~99–100% ceiling and concluded — wrongly —
that these models are interchangeable on Latter-day Saint competence. The open-ended axis tells a
completely different story, with a ~50-point spread and 32 of 36 pairwise differences
significant. Factual recall (knowing *what* the Church teaches) and applied alignment (giving
counsel a faithful member would recognize as their own) are empirically distinct capabilities,
and only the latter still discriminates frontier models.

**Capability and alignment can move in opposite directions.** The headline finding is that the
newest Opus (4.8) is *significantly worse* than its two predecessors at faithful within-tradition
reasoning, even though it ties them at the MC ceiling. We are cautious about over-reading a
single benchmark on a single tradition measured through one harness, but the effect is robust to
repeat runs, position-balancing, multiple-comparison correction, and a highly reliable judge
panel (α = 0.9924 composite, ≥ 0.9758 per dimension). Nor is it isolated to Opus: Sonnet 5 likewise
fails to advance on Sonnet 4.6. It is not, however, a universal "newer-is-worse" law — Fable 5,
the newest and highest-tier model, ties for first — which makes the two regressions look like
model-specific tuning outcomes rather than an inevitability. A plausible reading is that
general-purpose tuning which improves breadth or "neutrality" can erode the willingness to give a
*distinctively* committed answer — precisely the `distinctiveness` and `should_not` behavior this
benchmark rewards. That is a measurable, monitorable regression, and exactly the kind of thing a
within-tradition benchmark exists to catch.

**Where the cohort is weak.** The `life_choice` dimension is consistently harder than
`cultural_open` for lower-capability models, and the failure signature is drift toward
generic-Christian or secular advice (low distinctiveness, rising `should_not` violations) rather
than overt doctrinal error. Currency probes (2018–2026 changes, the 2025 Oaks succession) did not
differentiate the cohort: the models' knowledge cutoffs post-date those events, so they are
answered correctly. Currency items will regain diagnostic value against models with earlier
cutoffs and in future editions.

**Reliability and validity.** Judge inter-rater agreement (Krippendorff's α = 0.9924) is high
enough that the open-ended ranking is not an artifact of judge noise; MC parse-failure and
call-failure rates are both zero in the final data; a provenance audit found zero genuine
served-model fallbacks, zero multi-key usage-extraction artifacts, and zero failed calls in the
scored data (each served model verified by per-call pricing); and answer positions are balanced, so
the MC ceiling cannot be a position-bias artifact — on the shipped balanced set the best fixed
position pays only ~29% (it was ~51% before balancing, which is why the set was rebalanced).
The principal threats that remain are construct-level, not measurement-level, and are enumerated
in §6.

## 6. Limitations

English-only and US-Anglo-centric; orthodox/correlated framing by design; **v0.1 validation
is by automated personas rather than a credentialed human panel** — and those five "reviewers"
are a single model (`claude-opus-4-8`) wearing five system-prompt personas, so their unanimous
key agreement (Fleiss' κ = 1.0) evidences item clarity, not independent validation; questions
authored by models in the same family as the evaluated cohort (mitigated by source-anchoring
and blind review); six of the nine Claude cohort ids are undated aliases, so the
served snapshot is pinned only by the run's serving window; and measurement of the Claude
slice through the CLI harness rather than the bare Messages API. The cohort is no longer
single-provider, but it is still narrow in a specific way: the Claude models are frontier
and closed, the open-weights models are all ≤ 4B and CPU-served, and nothing occupies the
7B–70B middle — so "open weights" here should be read as "small models", not as a claim
about open-weights systems generally. Additional v0.1 caveats: the **judge-model
cross-check** (a `claude-opus-4-8` re-scoring of a seeded subset) is implemented in the harness
(`--judge-crosscheck`) but was not run, so open-ended scores rest on a single judge model that
is itself a cohort member (self-preference is possible in principle; note the judge's own
generation, Sonnet 4.6, does not top the leaderboard); **seven sensitive open-ended candidates
(LGBTQ family situations, end-of-life care, tithing-vs-rent, gambling, bankruptcy, bishop
burnout) were dropped in v0.1 because all five persona reviews failed to parse** — a review
infrastructure failure, not a quality judgment, that biased the pool away from the hardest
pastoral scenarios (the harness now re-solicits failed reviews and reports no-quorum items
separately); and the **MC axis is near-saturated** for this frontier cohort (see §5), so its
discriminative power against *those* models is limited to harder future items — though §4.1
shows the items themselves discriminate sharply the moment the cohort extends below the
frontier. Each is a concrete avenue for v1.0.

**Judge-harness settings inheritance.** During the 17-model run we found that the `claude`
CLI reads the operator's `~/.claude/settings.json`, and an `advisorModel` set there is
consulted on hard prompts, with its tokens landing in the same usage map as the answer's.
Because the harness attributes a call to the model that produced the most output tokens, a
large enough advisor turn flips attribution to a model we never requested. The served-model
guard rejected exactly those calls, so no wrong-model verdict entered the dataset — across
34,210 cached calls, requested equals served in every one, and the 20,145 response records
report zero multi-model calls. The exposure is bounded by timestamp: the operator setting
changed 2026-07-14 21:37 MDT, and all 3,240 Claude-cohort judge verdicts predate it, so the
Claude open-ended scores are unaffected; 1,799 local-model verdicts were produced afterward
and each passed the guard (i.e. was Sonnet-dominant). What cannot be excluded retroactively
for v0.1 is a Sonnet-dominant call in which the advisor contributed a minority of tokens,
because judge records did not persist `served_all`. Both gaps are closed going forward — the
subprocess now pins the advisor to the model under test, and judge records persist
attribution evidence ([ADR-0012](docs/adr/0012-operator-settings-isolation-and-judge-quorum.md)).
One judge call of 6,120 was rejected and never healed, so a single triple scored on a
2-judge panel rather than 3; its model's composite is unchanged. We report the incident
rather than quietly re-running, because a harness that reads the operator's personal
settings is not reproducible, and readers should know the v0.1 judge ran under that
condition.

## 7. Ethics

DeseretBench is a measurement tool, not a source of religious authority. It does not
adjudicate the truth of religious claims; it measures whether models accurately represent a
tradition and counsel within it. Data is licensed CC BY-NC-SA 4.0 for **evaluation, not
training**.
