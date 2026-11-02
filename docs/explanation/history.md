# How the benchmark idea grew

This page tells how DeseretBench took its shape, which plans the project did not follow, and what is still open. It is history. For what the project is today, read [VISION](../../VISION.md), [DESIGN](../../DESIGN.md) and the [yellow paper](../../YELLOWPAPER.md). Where this page and the repo disagree, the repo is right.

## The starting plan

The project began as a written plan for a benchmark of how well language models track current, official Latter-day Saint positions. The plan made four points that still hold.

1. **The questions are the product.** A benchmark is a dataset plus a scoring method. The harness is packaging. Tooling that grows faster than the question set is a way to avoid the hard work.
2. **Three kinds of knowledge.** Doctrinal accuracy is the easiest to verify. Cultural fluency and life-choice alignment are where a benchmark stops being a seminary quiz. All three are scored apart ([DESIGN §1](../../DESIGN.md)).
3. **Ground truth is the official position.** The plan ranked its sources: canon and the General Handbook settle a question, conference talks and Gospel Topics essays come next, scholarship gives context. Critical and revisionist material is never ground truth. The repo keeps this as the source priority and tier table in [DESIGN §5.4](../../DESIGN.md).
4. **Wrong answers carry information.** The plan wanted each wrong option to be a real position from another tradition or from folk belief, so that a model's mistake shows which way it failed. This became the typed distractors ([why typed distractors](why-typed-distractors.md), [ADR-0004](../adr/0004-typed-distractors-and-position-balancing.md)).

The plan also set a scoring stance for history: be honest about history and faithful about doctrine. Hedging that treats prophetic authority as optional fails. So does defensiveness that denies the Church's own published account. [DESIGN §2](../../DESIGN.md) records the stance.

## Where the project went a different way

| The plan | What the repo does | Where to read |
|---|---|---|
| Build a small JSON dataset and a short script first. Add an evaluation framework only for open-weight models. | A full pipeline with its own runner and a content-addressed cache. An `lm-evaluation-harness` task config also ships. | [measurement integrity](measurement-integrity.md), [REPRODUCE](../../REPRODUCE.md) |
| Start with 50 to 100 reviewed questions. Grow toward 700. | 213 multiple-choice and 40 open-ended items. The target is about 250. | [DESIGN §5.1](../../DESIGN.md) |
| Ship the first axis alone, then add the others. | All three axes in one release. | [DESIGN §1](../../DESIGN.md) |
| Run two prompt conditions, one neutral and one that names the tradition. The gap would separate default stance from knowledge. | One neutral prompt for every model. The benchmark measures latent knowledge, not steerability. | [DESIGN §4.1](../../DESIGN.md) |
| Review by university experts in doctrine, scholarship and methods, then a wider panel. | Five reviewer personas on one model. The human panel is still to come. | [DESIGN §6.1](../../DESIGN.md), [ADR-0005](../adr/0005-judge-panel-three-personas.md) |
| Judges from at least two model families, calibrated against human scores. | A three-persona panel on one judge model. A cross-check judge exists in code and has not run. | [judge design](judge-design.md) |
| A private test set of 20 to 30 percent. A canary string in the published files. | A 20 percent split that the repo calls nominal, because the candidate pool ships openly. No canary string ships. | [holdout stance](holdout-stance.md), [ADR-0007](../adr/0007-holdout-deferred-v01.md) |
| Report each model's wrong answers as a share per distractor type. | Items and responses carry the data. The join is a few lines over published files, and no shipped table reports it. | [why typed distractors](why-typed-distractors.md) |
| Run a handful of hosted models. | Thirty models across thirteen vendors and three serving paths, including a local open-weights slice. | [README](../../README.md), [ADR-0010](../adr/0010-cohort-selection-by-cli-probe.md), [ADR-0011](../adr/0011-local-open-weights-backend.md), [ADR-0013](../adr/0013-2026-cohort-expansion-and-gpu-inference.md) |

The plan's statistics section made one point the repo kept: with a small item set, a gap of a few points between two models means nothing. The repo reports bootstrap intervals everywhere and compares models on the same items with paired tests ([statistics](statistics.md), [ADR-0006](../adr/0006-statistical-testing-protocol.md)).

## What the results changed

The first release found that multiple-choice recall saturates among frontier models. The open-ended track carries the discriminating power. The local open-weights slice showed that the same items still separate smaller models. [PAPER §4](../../PAPER.md) has the numbers. Typed distractors were built to make multiple choice discriminate. They help most below the frontier, as the [typed-distractor page](why-typed-distractors.md#limits) explains.

## A pluggable tradition

An early idea was an umbrella project that would help any community define a source hierarchy and measure how models represent it. The project did not build the umbrella. It built the part that generalizes: a faith-pack layer that holds the taxonomy, judge personas, and report labels. DeseretBench itself stays Latter-day Saint only. A benchmark for another tradition belongs to people inside that tradition ([VISION, the horizon](../../VISION.md), [add a faith pack](../how-to/add-a-faith-pack.md)).

## Order of work

The plan said to publish results before asking anyone for support, and to ask in terms of defensive cultural infrastructure: models describe the Church to many people, and this is a way to measure how well. The repo follows the first half. It holds a full run, a paper, and the data. Related evaluation work from other groups is in [RELATED_WORK](../../RELATED_WORK.md).

## Open questions

Each question names what would answer it.

1. **Do real reviewers agree with the keys?** The persona panel shares one model, so its agreement shows clarity and not independent validation. A panel of the kind in [DESIGN §6.1](../../DESIGN.md), with the κ targets stated there, would answer it.
2. **Does the judge track human judgment?** A human calibration set of 30 to 50 responses, scored against the rubrics, would give a judge-to-human agreement figure. The bar is in [judge design](judge-design.md).
3. **Does a model know the tradition but default to another stance?** The second prompt condition would show it. It needs a new edition, because it changes the instrument.
4. **Can a held-out set resist contamination?** A fresh batch of never-published questions would answer it. See the [holdout stance](holdout-stance.md).
5. **Does a hedge tag add information?** A separate distractor type for answers that treat authority as optional would let reports separate hedging from Protestant collapse. See [why typed distractors](why-typed-distractors.md#the-hedge-shape).
6. **Which items rest on no Tier 1 or Tier 2 source?** A pass over the item set to mark contested items would count them. The rule is in [DESIGN §5.4](../../DESIGN.md).

## The name

The name and its meaning are in [VISION](../../VISION.md#the-name).
