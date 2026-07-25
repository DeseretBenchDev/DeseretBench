---
license: cc-by-nc-sa-4.0
language: [en]
tags: [evaluation, benchmark, religion, latter-day-saints, lds, theology, culture]
pretty_name: DeseretBench
task_categories: [multiple-choice, question-answering, text-generation]
size_categories: [n<1K]
---

# DeseretBench (v0.1)

A benchmark for evaluating large language models on **Latter-day Saint doctrinal
accuracy, cultural fluency, and life-choice alignment**. Built for *model evaluation,
not model training.*

## Dataset summary

DeseretBench has two configurations:

- **`multiple_choice`** — auto-scored items across seven dimensions (doctrine & scripture,
  ordinances & covenants, church organization, eternal family, restoration history,
  living the gospel, cultural fluency), four difficulty tiers (basic → expert), with
  per-choice **distractor-type labels** that give the items their discriminative power.
- **`open_ended`** — judge-scored life-choice and cultural scenarios, each with a rubric
  (`must_include`, `should_not`, `ideal_reasoning_pattern`).

**Post-validation counts (v0.1).** From 324 authored candidates, a blind review by five
reviewer personas — one model (`claude-opus-4-8`) under five system prompts, so κ = 1.00 on
answers reflects item clarity, not independent raters — retained **266 / 267 MC** and **50 / 57
open** items. Of the 7 dropped open items, all 7 were dropped because their reviews failed to
parse (a review-infrastructure failure on sensitive topics, not a quality judgment); the
harness now re-solicits failed reviews and reports no-quorum items separately. A stratified **20% holdout is withheld** (not published) for
contamination-resistant scoring (DESIGN.md §6.3):

| split | multiple_choice | open_ended |
|---|---|---|
| **public** (this dataset) | 213 | 40 |
| private holdout (withheld) | 53 | 10 |
| **kept total** | 266 | 50 |

Exact details are in `data/validation_report.json` and `reports/RESULTS.md`.

**Holdout status (v0.1: nominal).** The full candidate pool (`data/candidates_*.jsonl`),
raw authored cells (`data/raw/`), and per-persona review records ship openly with the repo,
and the 20% "holdout" split is deterministically derivable from them — so v0.1's holdout is a
*structural placeholder*, not a contamination-proof set. True contamination management is
deferred: when the project is big enough, a fresh batch of never-published questions will
serve as the real holdout. The shipped MC file is position-balanced, with the seeded
permutation recorded in `data/questions_mc.jsonl.balance_meta.json`.

## Fields

**multiple_choice**
| field | type | description |
|---|---|---|
| `question_id` | str | deterministic content hash id |
| `axis` | str | `doctrinal_accuracy` / `cultural_fluency` / `life_choice_alignment` |
| `dimension` | str | one of seven MC dimensions |
| `difficulty` | str | `basic` / `intermediate` / `advanced` / `expert` |
| `question` | str | the stem |
| `choices` | list[str] | 3–6 options |
| `answer_index` | int | index of the correct option |
| `distractor_types` | list[str] | per-choice trap type (`correct` for the key) |
| `source` | str | authoritative citation |
| `notes` | str | trap logic / why it tests understanding |

**open_ended**
| field | type | description |
|---|---|---|
| `question_id`, `axis`, `dimension`, `difficulty` | | as above |
| `prompt` | str | the scenario |
| `rubric.must_include` | list[str] | points a faithful answer must engage |
| `rubric.should_not` | list[str] | failure modes |
| `rubric.ideal_reasoning_pattern` | str | the LDS reasoning arc |

## Framing (important)

DeseretBench keys answers to the **mainstream, official, correlated** position of the
Church (canon, the General Handbook, current First Presidency / Quorum of the Twelve
teaching), while acknowledging genuine ambiguity where the Church itself leaves matters
unsettled. Folk doctrine, heterodox ("Sunstone"), and anti-Mormon framings appear **only
as distractors**. This is a *descriptive* benchmark ("what does the Church teach / how do
members live"), not a prescriptive or apologetic one. See DESIGN.md §2.

## How it was built

- **Authoring:** items drafted by Claude models against a cited factual grounding brief
  (`data/grounding_brief.md`), with a controlled distractor palette and source-priority list.
- **Validation:** five independent reviewer personas (orthodox member, BYU religion
  instructor, church historian, adult convert, international returned missionary) reviewed
  each item *blind*; items were kept only on high key-agreement, clarity, and low ambiguity.
  Reviewer agreement (Fleiss' κ) is reported.

## Intended use & out-of-scope

- **Use:** evaluating LLM knowledge/fluency/alignment on LDS topics; comparing models.
- **Out of scope:** training data; adjudicating the truth of religious claims; representing
  every Latter-day Saint's personal views.

## Limitations

English-only; US-Anglo-centric cultural assumptions; orthodox/correlated framing by design;
**v0.1 validation is by automated personas, not a credentialed human panel**; questions
authored by models in the same family as (some) evaluated models (mitigated by
source-anchoring + independent validation). See DESIGN.md §9.

## Citation

```
@misc{deseretbench2026,
  title  = {DeseretBench: Evaluating Latter-day Saint Doctrinal Accuracy, Cultural
            Fluency, and Life-Choice Alignment in Large Language Models},
  author = {DeseretBench contributors},
  year   = {2026},
  note   = {v0.1, CC BY-NC-SA 4.0}
}
```
