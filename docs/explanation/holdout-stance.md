# The holdout stance: why v0.1's "private" holdout is nominal

DeseretBench splits off 20% of its validated items into `data/private_holdout/`
(53 MC items, 10 open items) and keeps those files out of version control. Despite
that, **v0.1's holdout is not private in any meaningful sense**, and this document
explains why we say so out loud instead of pretending otherwise.

This is an explanation of a decision and its tradeoffs. For the mechanics of the
split itself, see [../reference/data-formats.md](../reference/data-formats.md) and
`deseretbench/validate_questions.py`; for the methodology context, see
[DESIGN.md §6.3](../../DESIGN.md).

## The contamination problem

A published benchmark is a target. Once question text is on the public internet,
three failure modes open up:

1. **Passive contamination.** The items end up in a future model's training data
   simply because crawlers found them. Scores on those items then measure
   memorization, not competence.
2. **Active gaming.** A lab that cares about the leaderboard fine-tunes on the
   published set, or on paraphrases of it.
3. **Silent saturation.** Contaminated scores rise, the benchmark stops
   discriminating, and nobody can tell whether models got better or the test leaked.

The standard defense is a **private holdout**: a subset of items that is never
published, served only at evaluation time, so that a suspicious gap between public
and holdout scores exposes contamination. DeseretBench's pipeline was built with
that structure — `validate_questions.py` performs a stratified 20% split (by
dimension × difficulty, seeded from `stats.rng_seed` in
[`configs/run_config.yaml`](../../configs/run_config.yaml)) into
`data/private_holdout/`, and `.gitignore` excludes that directory.

## The v0.1 decision (2026-07-02): publish everything, call the holdout nominal

During the 2026-07 audit, we found that the "withheld" items were not actually withheld. All 63 of them ship
verbatim through three published channels:

- `data/candidates_mc.jsonl` / `data/candidates_open.jsonl` — the full validated
  candidate pool (267 MC / 57 open), of which the holdout is a subset;
- `data/raw/` — the raw authoring cell outputs;
- `data/reviews_mc.jsonl` / `data/reviews_open.jsonl` — the per-persona review
  records.

Worse, the split is **deterministic**: the seed and holdout fraction are in the
published config, so anyone can rerun the split and reconstruct exactly which
candidates are "held out."

The initial audit reaction was to seal the leak — untrack those channels and scrub
history. The final decision (2026-07-02) went the other way: **publish the
candidate pool, raw authoring cells, and review records openly, keep
`data/private_holdout/` untracked as a matter of hygiene, and state plainly that
the holdout is nominal** — a structural placeholder whose contents are derivable
from what is published. It keeps the pipeline's split machinery
(`stratified_holdout`) and the reporting paths (the `mc_public`/`mc_holdout`
counts written to `data/validation_report.json`) exercised, so that a real
holdout can drop into an already-working slot later. It provides no contamination
protection.

### Reconciling older language

If you read git history or older revisions of the docs, you will find the opposite
stance: a commit titled "seal the private holdout for real," a history-scrub
script, and prose that treated `data/private_holdout/` as genuinely withheld.
**That stance changed.** The sealing work was done during the audit and then
deliberately reversed two days later; the scrub script was dropped. Current
documents — [DESIGN.md §6.3](../../DESIGN.md) (tagged `[DECISION REVISED
2026-07]`), [DATASET_CARD.md](../../DATASET_CARD.md) ("Holdout status (v0.1:
nominal)"), and this page — describe the holdout as nominal. Where older text
survives that calls it sealed, private, or contamination-proof, the newer text
wins.

## Why transparency won at this scale

The choice was between two imperfect states, and the deciding fact is that
DeseretBench v0.1 is a solo pilot, not an instrument labs currently optimize
against.

**What a sealed holdout would have cost here:**

- **Reproducibility.** The project's first principle
  ([VISION.md](../../VISION.md)) is that anyone can regenerate every number.
  A sealed holdout means part of the dataset pipeline — validation reviews,
  keep-rule decisions, the split itself — cannot be independently checked.
- **Auditability of the authoring pipeline.** The candidate pool and review
  records are the evidence that the keep rules did what the docs claim. Hiding
  them to protect 63 items would have hidden the receipts for all 324.
- **History surgery.** The items were already in git history. Genuinely sealing
  them meant rewriting history — destructive, error-prone, and still not
  trustworthy, since any pre-scrub clone keeps the data anyway.
- **Honesty.** A holdout that is "private" except for being derivable from three
  published files and a seeded RNG is worse than no holdout: it invites false
  confidence.

**What publishing costs:** contamination risk on a dataset that, today, few if
any training pipelines target. That risk is real (see below) but currently cheap;
the transparency is valuable now. Fresh, never-published items can be written
when the stakes justify it — writing new questions is cheaper than un-publishing
old ones.

## What would trigger a real private holdout, and what it takes

The trigger, per [VISION.md](../../VISION.md), is the project becoming big enough
for contamination to matter more than transparency — concretely, signs such as:
external labs or papers citing DeseretBench scores, the benchmark appearing in
model cards or marketing, public/holdout score divergence on the existing split,
or the public set visibly saturating in ways training-data timing could explain.

Operationally, a genuine holdout requires discipline the nominal one never had:

- **Fresh authorship.** New items written from scratch after the decision —
  never drawn from the published candidate pool, and not paraphrases of it.
- **No VCS history.** The items never touch the repository, not even in an
  early commit later reverted. Once text has been pushed, it cannot be recalled.
- **Separate serving.** Evaluation on holdout items runs from storage and
  infrastructure separate from the public repo, with results published as
  aggregates only — item text never appears in run logs, cached responses, or
  reports (the response cache and `runs/` files both store full item-bearing
  prompts and completions, so a holdout served through the public pipeline's
  default paths would leak on the first run).
- **A published protocol.** The one part that should be public is the procedure:
  how holdout items are sampled, scored, and compared against the public set, so
  the aggregate numbers remain checkable even when the items are not.

One mitigation survives regardless of stance: item IDs are content-hashed
(`deseretbench/schema.py`), so per-item accuracy is trackable across versions and
a memorization spike on published items stays detectable.

## The residual risk, stated plainly

A lab could train on the published DeseretBench set — deliberately or through
ordinary crawling — and **v0.1 cannot detect that**. There is no uncontaminated
reference set to compare against; the nominal holdout offers zero protection
because its contents are public. If a future model posts a surprising score on
DeseretBench v0.1, "it trained on the questions" is a live hypothesis that this
version of the benchmark has no instrument to rule out. Treat v0.1 scores
accordingly: strong evidence about models whose training predates the dataset's
publication, weaker evidence about models trained after it.

## Related

- [DESIGN.md §6.3](../../DESIGN.md) — the decision log entry.
- [DATASET_CARD.md](../../DATASET_CARD.md) — the dataset-level statement.
- [measurement-integrity.md](measurement-integrity.md) — provenance and caching
  design, which a future sealed holdout would have to route around.
- [../how-to/add-questions.md](../how-to/add-questions.md) — the authoring
  pipeline a fresh holdout batch would reuse.
