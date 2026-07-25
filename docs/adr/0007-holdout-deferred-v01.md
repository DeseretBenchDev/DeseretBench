# ADR-0007: The private holdout is deferred for v0.1

Status: Accepted — supersedes the earlier "seal the private holdout" intent

Date: 2026-07-02

## Context

An earlier working stance (git commit `022e30c`, "audit WS8: seal the private
holdout for real") aimed to keep a genuinely secret 20% split — items no
adversary could see — so that a model trained on the public set could still be
caught out on unseen questions. That intent was reversed the same audit cycle.

The reversal is honest about a structural fact: even with
`data/private_holdout/` untracked in git, the holdout items are **derivable**.
DeseretBench publishes the full candidate pool (`data/candidates_*.jsonl`), the
raw authoring cells (`data/raw/`), and the review records. The public/holdout
split is a deterministic, seeded partition of that published pool. Anyone with
the repo can reconstruct the withheld items exactly. A holdout that is
recomputable from published inputs is not private; calling it "sealed" would be
a claim we cannot back.

## Decision

Publish the pool, raw cells, and reviews openly, and treat v0.1's holdout as
**nominal** — a structural placeholder, not a contamination barrier.

- The candidate pool, raw authoring shards, and reviews **ship in the repo**.
- The `data/private_holdout/` files stay untracked, but we state plainly that
  their contents are derivable from the published pool and the seeded partition
  (`stratified_holdout` in `validate_questions.py`, seeded from `stats.rng_seed`
  = `19470417` for MC and `+1` = `19470418` for open). The withheld items are then
  position-balanced separately with `balance_positions.py` seed `20250101`.
- We do **not** describe the holdout as secret, sealed, or contamination-proof
  anywhere in the docs. It is labeled "v0.1: nominal."
- The rationale is **transparency over contamination management at pilot scale.**
  A benchmark that hides its items is harder to audit, harder to reproduce, and
  harder to trust; at 213 MC / 40 open public items, open review is worth more
  than a holdout we cannot actually keep private.

## Consequences

- **We cannot detect training-on-the-set.** With every item derivable, a model
  that memorized the pool is indistinguishable from one that reasons well. v0.1
  absolute scores must be read with that caveat; the leaderboard is a snapshot,
  not a contamination-proof measurement.
- **Full auditability.** Every published claim traces to a published item and its
  reviews. The audit confirmed all 63
  withheld items ship verbatim through the pool and raw cells.
- **Detection is deferred, not abandoned.** Content-hashed item IDs still let a
  future run flag memorization spikes on specific items.
- **Revisit trigger.** A genuinely private holdout — a fresh, never-published
  batch of items — is deferred until the project is larger and a real
  contamination signal is worth the cost. When the dataset grows enough that a
  meaningful never-seen split can be built and kept off every public channel,
  this decision is revisited.

## Links

- Rationale and history: [docs/explanation/holdout-stance.md](../explanation/holdout-stance.md).
- Design record: [DESIGN.md](../../DESIGN.md) §6.3 `[DECISION REVISED 2026-07]`.
- Dataset card: [DATASET_CARD.md](../../DATASET_CARD.md) "Holdout status (v0.1: nominal)".
- Charter horizon: [VISION.md](../../VISION.md) (a real private holdout is a planned successor).
