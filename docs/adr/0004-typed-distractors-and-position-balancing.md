# ADR-0004: Typed distractors and seeded position balancing

Status: Accepted

Date: 2026-06

## Context

A multiple-choice item only measures what its wrong answers make it measure. If
the distractors are random or obviously silly, a model can score well by keyword
matching "religious-sounding" text without any Latter-day Saint understanding — a
generic-Christianity instinct passes. To separate models that *understand* the
tradition from those pattern-matching the nearest majority culture (the wager in
[VISION.md](../../VISION.md)), each wrong option has to represent a *specific*
way of being wrong.

A second, mechanical hazard: model-authored items left the correct answer
clustered on one letter (v0.1 authoring put the key at `B` roughly 51% of the
time). A model with a position prior could then score above its true knowledge.

## Decision

Type every distractor, and balance the correct-answer position with a seeded
permutation.

- **Six typed distractor classes** (plus `correct`) in
  `deseretbench/schema.py`: `protestant_trap`, `folk_doctrine_trap`,
  `anti_mormon_trap`, `progressive_trap`, `correlation_oversimplification`,
  `plausible_near_miss`. Authoring (`author.py`) requires at least two distinct
  trap types per item and exactly one defensibly-correct answer. When present,
  `distractor_types` must be a list the length of `choices`, contain exactly one
  `correct`, and place that `correct` at `answer_index` (schema-enforced).
- **Seeded position balancing** (`balance_positions.py`): the correct
  `(choice, dtype)` pair is separated out, the distractors are shuffled (their
  original order could itself carry signal), the correct answer's new slot is
  drawn uniformly at random with seed `19470417`, and `answer_index` is set to
  that slot. `distractor_types` is permuted in parallel so typing stays aligned
  with choices.
- **Provenance machinery.** Balancing writes a `.balance_meta.json` marker (seed,
  item count, and a position map where `order[k]` is the pre-balance index of the
  choice now at slot `k`) and a `.prebalance` backup. It refuses to re-run
  without `--force` because the permutation is not idempotent, and re-running
  would silently diverge from the published set. The position map keeps
  pre-balance artifacts — e.g. reviewer letters in `reviews_mc.jsonl` — readable
  against the shipped reordered items. `question_id` is held stable across the
  reorder.

## Consequences

- **Answer-slot bias is controlled.** The key is spread across letters by a
  reproducible draw, so a position prior no longer inflates scores, and the
  before/after key distribution is printed for inspection.
- **Typing is authorial intent, not a fact of nature.** A `protestant_trap` is a
  trap *as the author framed it*; the taxonomy encodes a stance
  (mainstream/official/correlated — see [DESIGN.md](../../DESIGN.md) §2) about
  what counts as the near-miss. `distractor_types` is validated but *optional* on
  MC items, so not every shipped item carries the labels, and the classification
  is only as good as the author's judgment.
- **IDs are provenance, not checksums.** Because `question_id` survives the
  reorder while `choices` move, IDs on the balanced set do not recompute from
  current content. They identify an item's lineage; they do not verify it.
  Re-authoring the pool invalidates the marker, so it and the `.prebalance`
  backup must be cleared before a fresh `--force` balance (the README does this).

## Links

- Distractor taxonomy and schema: `deseretbench/schema.py`; balancing:
  `deseretbench/balance_positions.py`; authoring: `deseretbench/author.py`.
- Rationale in depth: [docs/explanation/why-typed-distractors.md](../explanation/why-typed-distractors.md).
- Framing stance: [DESIGN.md](../../DESIGN.md) §2.
