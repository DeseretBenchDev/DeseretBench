# DeseretBench

**A reproducible benchmark for Latter-day Saint doctrinal accuracy, cultural fluency,
and life-choice alignment in large language models.**

AI tools are already advising members of The Church of Jesus Christ of Latter-day Saints
on doctrinal and life questions, yet there has been no way to measure whether those
answers are good. DeseretBench is a quality-control instrument for the Church's emerging
AI surface area — and, for the AI-research community, a test case in an underexplored axis
of evaluation: a theology that is highly specific, well-documented, and distinct enough
from mainstream Christianity that models cannot coast on generic religious training data.

> **Vision in one line:** make within-tradition religious competence *measurable* —
> reproducibly, honestly, and in the open. The principles that govern this project,
> and its explicit non-goals, live in **[VISION.md](VISION.md)**.

## What it measures (three distinct axes)

1. **Doctrinal Accuracy** — does the model know what the Church teaches? *(multiple choice, auto-scored)*
2. **Cultural Fluency** — does it understand how Latter-day Saints actually live and decide? *(MC + open-ended)*
3. **Life-Choice Alignment** — does its counsel track a faithful, thoughtful Latter-day Saint's? *(open-ended, judge-panel scored)*

Each axis is scored separately. See **[DESIGN.md](DESIGN.md)** for the full methodology,
the explicit **framing stance** (mainstream / official / correlated — §2), the dimension
and difficulty taxonomy, the distractor palette that gives the items their discriminative
power, and the limitations.

## What's distinctive

- **Discriminative distractors.** Every wrong option is typed — `protestant_trap`,
  `folk_doctrine_trap`, `anti_mormon_trap`, `progressive_trap`,
  `correlation_oversimplification`, `plausible_near_miss` — so the benchmark separates
  models that *understand* LDS thought from those pattern-matching Christian keywords.
- **Currency probes.** A subset tests training-data currency against 2018–2026 changes
  (e.g., the 2025 succession of President Dallin H. Oaks, the 2019 Word of Wisdom
  clarifications, the 2018 ministering change). See `data/grounding_brief.md`.
- **Statistical rigor.** Repeat runs per model, bootstrap 95% CIs, pairwise significance
  (paired bootstrap + McNemar), classical item analysis (difficulty + discrimination),
  run-to-run variance, and judge inter-rater reliability (Krippendorff's α).
- **Reproducible & provider-agnostic.** Seeded, content-addressed cache, pinned configs,
  a canonical Anthropic-API path, and an lm-evaluation-harness task config.

## Cohort evaluated (v0.1)

Twenty-three models across nine vendors and two serving paths.

**Ten current-generation Claude models** served by the local `claude` CLI (probed
2026-06-05, expanded 2026-07-03 and 2026-07-24): `claude-fable-5`, `claude-opus-5`, `claude-opus-4-8`,
`claude-opus-4-7`, `claude-opus-4-6`, `claude-opus-4-5-20251101`, `claude-sonnet-5`,
`claude-sonnet-4-6`, `claude-sonnet-4-5-20250929`, `claude-haiku-4-5-20251001` —
within-tier generational progressions (Opus 4.5→5, Sonnet 4.5→5) plus the Fable
tier above Opus, and a cross-tier spread. The cohort is *whatever the authenticated
CLI actually serves*, discovered by probe — see
[ADR-0010](docs/adr/0010-cohort-selection-by-cli-probe.md).

**Thirteen local open-weights models** (0.6B–4B) served by a user-space Ollama:
Qwen3 0.6B/1.7B/4B, Gemma 3 1B/4B, SmolLM2 1.7B, Phi-4 Mini 3.8B,
DeepSeek-R1-Distill 1.5B, plus five 2026 families — Granite 4.1 3B, Qwen3.5 4B,
Ministral 3 3B, Nemotron 3 Nano 4B, and Gemma 4 E2B — under the identical
measurement configuration, spanning eight open-weights vendors (Alibaba, Google,
Microsoft, IBM, Mistral, NVIDIA, DeepSeek, HuggingFace). See
[ADR-0011](docs/adr/0011-local-open-weights-backend.md) and
[ADR-0013](docs/adr/0013-2026-cohort-expansion-and-gpu-inference.md).

The two halves answer different questions. The Claude cohort measures how frontier
models differ from each other. The local cohort measures the benchmark against models
well below the frontier, which is what makes the item set's discriminative power
visible.

## Quickstart

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e .
.venv/bin/python -m deseretbench.author             # author candidate items
.venv/bin/python -m deseretbench.assemble           # dedupe + validate schema
.venv/bin/python -m deseretbench.validate_questions # 5-persona review + holdout split
rm -f data/questions_mc.jsonl.balance_meta.json data/questions_mc.prebalance.jsonl  # fresh authoring invalidates the shipped balance marker
.venv/bin/python -m deseretbench.balance_positions --in data/questions_mc.jsonl --out data/questions_mc.jsonl
.venv/bin/python -m deseretbench.run_benchmark mc   --questions data/questions_mc.jsonl   --out runs/v0_1
.venv/bin/python -m deseretbench.run_benchmark open --questions data/questions_open.jsonl --out runs/v0_1
.venv/bin/python -m deseretbench.analyze --run runs/v0_1
.venv/bin/python -m deseretbench.report
```

For an unattended, rate-limit-resilient end-to-end run (the `claude` CLI enforces a rolling
session usage limit), use `scripts/finish_pipeline.sh` — it re-runs each phase until zero
failed calls remain, resuming from the content-addressed cache across reset windows.

Tests: `uv pip install --python .venv/bin/python --group dev && .venv/bin/python -m pytest tests/ -q`.
Full details: **[REPRODUCE.md](REPRODUCE.md)**. Results live in `reports/leaderboard.html`
and `reports/RESULTS.md`.

## Headline results (v0.1)

Twenty-three models, balanced MC + judge-panel open-ended, 5/3 repeat runs, seed
19470417. Numbers regenerated from `reports/RESULTS.md` — never hand-typed.

- **Multiple choice saturates at the frontier and discriminates below it.** All 45
  Claude-vs-Claude MC comparisons are non-significant after correction. Across the full
  cohort, 186 of 253 are significant. Accuracy runs from 0.521 (R1-Distill 1.5B) through
  0.703 (SmolLM2 1.7B) and 0.811–0.813 (Phi-4 Mini, Qwen3 1.7B, Gemma 3 4B) to 0.922
  (Qwen3 4B) and 0.932 (Qwen3.5 4B), then 0.986–1.000 across the Claude cohort. The items
  discriminate; the ten-model cohort was too narrow to show it.
- **The MC-to-open collapse.** Qwen3 4B scores 0.922 on MC, close to Claude's range, and
  **21.8** on open-ended, under half of Haiku 4.5 (48.5), the weakest Claude. MC asks a
  model to recognize an answer among four options; the open track asks it to write counsel
  with no options in view.
- **Open-ended discriminates sharply** (judge Krippendorff's α = 0.9929, 2,760 scored
  units; 228 of 253 pairwise comparisons significant), composite 0–100:

  | Model | Composite (95% CI) | MC accuracy |
  |---|---|---|
  | Opus 4.7 | **98.2** [96.8, 99.3] | 1.000 |
  | Fable 5 | **97.9** [96.6, 99.0] | 0.999 |
  | Opus 5 | **97.6** [96.2, 98.8] | 1.000 |
  | Opus 4.6 | **95.0** [92.6, 97.0] | 1.000 |
  | Opus 4.8 | **91.4** [87.9, 94.5] | 1.000 |
  | Sonnet 4.6 | **89.6** [86.0, 92.8] | 1.000 |
  | Sonnet 5 | **86.6** [82.1, 90.6] | 0.986 |
  | Opus 4.5 | **83.5** [79.7, 87.0] | 1.000 |
  | Sonnet 4.5 | **69.7** [64.9, 74.2] | 1.000 |
  | Haiku 4.5 | **48.5** [44.2, 52.7] | 0.994 |
  | Qwen3 4B | **21.8** [18.8, 24.5] | 0.922 |
  | Gemma 4 E2B | **18.7** [15.9, 21.4] | 0.813 |
  | Granite 4.1 3B | **18.4** [16.2, 20.6] | 0.905 |
  | Ministral 3 3B | **17.7** [15.2, 20.1] | 0.892 |
  | Gemma 3 4B | **17.7** [14.8, 20.5] | 0.813 |
  | Qwen3.5 4B | **17.6** [15.5, 19.5] | 0.932 |
  | SmolLM2 1.7B | **11.7** [10.0, 13.3] | 0.703 |
  | Qwen3 1.7B | **9.9** [8.3, 11.5] | 0.811 |
  | Nemotron 3 Nano 4B | **8.4** [6.5, 10.4] | 0.820 |
  | Phi-4 Mini | **7.6** [5.9, 9.3] | 0.811 |
  | Gemma 3 1B | **4.5** [3.2, 5.9] | 0.548 |
  | Qwen3 0.6B | **2.0** [1.2, 2.9] | 0.536 |
  | R1-Distill 1.5B | **0.3** [0.1, 0.6] | 0.521 |

- **Parameter count does not predict open score in the mid band.** Phi-4 Mini (3.8B)
  matches Qwen3 1.7B on MC (0.811 each) at more than twice the size, but scores lower on
  open (7.6 vs 9.9). And the best local MC model is not the best on open: Qwen3.5 4B tops
  the local cohort on MC (0.932) yet lands mid-pack on open (17.6), below Qwen3 4B (0.922
  MC, 21.8 open) — heavy reasoning that does not transfer to open-ended counsel. Plotted
  in `reports/figures/scaling_by_size.png`.
- **Within-family open scaling is clean.** Qwen3 0.6B, 1.7B and 4B score 2.0, 9.9 and 21.8;
  Gemma 1B and 4B score 4.5 and 17.7. Across families at the same size, scores diverge.
- **Reasoning training did not transfer.** R1-Distill 1.5B is last on both tracks (0.521 MC,
  0.3 open), and is the only reasoning-distilled model in the cohort. Its answers are not
  truncated or empty: all 120 terminate normally at a median of ~1,100 characters, and they
  score 0.02 on rubric coverage.
- **Fable 5 debuts at the top,** statistically tied with Opus 4.7 for first (Δ = −0.3, not
  significant), and significantly ahead of Opus 4.8.
- **Newer is not automatically more faithful.** Within Anthropic's Opus line the ordering
  zig-zags rather than climbing. Opus 4.8 scores significantly below Opus 4.7 (Δ = −6.8,
  Holm-corrected over 253 pairwise comparisons), and then the newest model, Opus 5, recovers:
  significantly above 4.8 (Δ = +6.2) and statistically tied with 4.7 at the top. Sonnet 5, for
  its part, does not improve on Sonnet 4.6, and Fable 5 reaches the top of the board. A model's
  generation number does not predict its within-tradition fidelity.
- **A wider cohort costs statistical power.** The Opus 4.8 vs 4.6 gap (Δ = −3.6) was
  significant when Holm-corrected over the nine-model family's 36 comparisons
  (*p* = 0.041) and is not over the 23-model family's 253 (*p* = 0.184, raw *p* = 0.008).
  The estimate is unchanged; only the size of the correction family grew.

## Repository layout

```
deseretbench/        # library: runner, schema, score_mc, judge, stats,
                     #          author, assemble, validate_questions, run_benchmark,
                     #          analyze, report
configs/             # models.yaml (cohort + judges), run_config.yaml (constants)
data/                # grounding_brief.md, questions_* (public set), candidates_*,
                     #   raw/ authoring cells, reviews_*, balance_meta (position map),
                     #   validation_report.json — the full pool is published;
                     #   private_holdout/ stays untracked but its contents are
                     #   derivable (nominal holdout — see
                     #   docs/explanation/holdout-stance.md)
lm_eval/             # lm-evaluation-harness portability task
runs/                # per-run raw responses + scores
reports/             # leaderboard.html, RESULTS.md, figures/
docs/                # Diátaxis docs (tutorials/how-to/reference/explanation) + ADRs
VISION.md            # why this exists; principles and non-goals
YELLOWPAPER.md       # normative technical spec (the "yellow paper")
DESIGN.md            # narrative design history, framing, limitations
PAPER.md             # white paper: motivation, method, results
DATASET_CARD.md      # Hugging Face style dataset card
AGENTS.md            # working agreement for contributors, AI and human
```

## Documentation

| I want to… | Read |
|---|---|
| Understand why this exists | [VISION.md](VISION.md) |
| See motivation, method, and results | [PAPER.md](PAPER.md) — the white paper |
| Know exactly how the machinery works | [YELLOWPAPER.md](YELLOWPAPER.md) — the technical spec |
| Run it for the first time | [docs/tutorials/first-run.md](docs/tutorials/first-run.md) |
| Do one task (add a model, add questions, recover a run…) | [docs/how-to/](docs/how-to/) |
| Look up a flag, config key, or record format | [docs/reference/](docs/reference/) |
| Understand a design choice | [docs/explanation/](docs/explanation/) · [docs/adr/](docs/adr/) |
| Place this among other faith-AI work | [RELATED_WORK.md](RELATED_WORK.md) |
| Contribute — fix questions, add a model, or benchmark another tradition | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Build the internals (map for humans and AI agents) | [AGENTS.md](AGENTS.md) |

## Status & licensing

- **v0.1** — pilot pipeline; questions authored by Claude models and validated by an
  automated reviewer-persona panel (a stand-in for a human expert panel — see DESIGN.md §6.1).
- Code: **MIT**. Dataset: **CC BY-NC-SA 4.0**. Intended for **model evaluation, not training.**
- This is a *living* benchmark; doctrine changes rarely but policy, emphasis, and culture do.

## Honest limitations (short form; full list in DESIGN.md §9)

English-only, US-Anglo-centric; orthodox/correlated framing by design; automated (not
human) validation in v0.1; questions authored by models in the same family as those
evaluated (mitigated by source-anchoring + independent validation); measured through the
Claude Code CLI harness, so absolute scores are not directly comparable to a bare-API run.
