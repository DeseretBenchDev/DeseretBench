# The DeseretBench Vision

*Why this exists, what must remain true of it, and where it is going. This document
changes rarely; when it conflicts with code or other docs, this is the intent and the
rest is the current state.*

## The problem

AI assistants are already advising members of The Church of Jesus Christ of Latter-day
Saints — on doctrine, on family decisions, on missions, callings, covenants, and money.
Nobody measures whether that advice is any good. General-purpose benchmarks can't: a
model can score perfectly on "world religions" trivia while confusing exaltation with
generic salvation, missing why a bishop's counsel differs from a therapist's, or quietly
substituting mainline-Protestant instincts for Latter-day Saint ones.

DeseretBench exists to make that quality measurable — for one tradition, in depth,
with the rigor of a real evaluation instrument rather than a vibes leaderboard.

## The wager

Within-tradition competence is measurable if you take the tradition seriously as a
knowledge domain. Latter-day Saint thought is specific, well-documented, centrally
correlated, and distinct enough from mainstream Christianity that a model cannot coast
on generic religious training data. That makes it an unusually clean substrate for a
question the AI field has barely asked: *does this model actually know and reason within
a particular community, or does it pattern-match the nearest majority culture?*

Cross-tradition benchmarks (see [RELATED_WORK.md](RELATED_WORK.md)) ask whether models
treat faiths *evenly*. DeseretBench asks whether a model is *right, fluent, and aligned*
inside one faith. The two axes are complementary; a model can be perfectly even-handed
and doctrinally shallow everywhere.

## Principles — what must remain true

1. **Reproducible above impressive.** Seeded runs, content-addressed caching, pinned
   configs, published statistical methods. Anyone with the tooling should be able to
   regenerate every number, and every number in the docs is generated — never typed in
   by hand from memory.

2. **Honest above flattering.** Limitations are first-class content, not fine print.
   When a metric saturates, we say it stopped discriminating. When the judge shares a
   model family with the evaluated cohort, we disclose the bias risk. When validation is
   automated rather than human, the docs say so on the first page, not the last.

3. **Open above proprietary.** Code is MIT; the dataset is CC BY-NC-SA 4.0, intended
   for evaluation, not training. A benchmark whose methods are secret is an
   advertisement. This one is a recipe: fork it, rerun it, extend it to your own
   tradition.

4. **Within-tradition respect.** The framing is deliberately orthodox/correlated —
   current official teaching, as the institution presents it. That is a documented
   measurement stance, not a theological verdict; other lenses (progressive, scholarly,
   ex-member) are real, and modeling them is out of scope here, not denied.

5. **Built to be checked.** All of this code — and every comment in it — was written by
   AI (Claude), with a human directing. Treat implementations and comments as *what
   currently exists*, received with gratitude and a grain of salt, never as final or
   self-evidently correct. Tests and generated outputs outrank comments; comments
   outrank nothing. The project assumes its own code is wrong until adversarially
   reviewed.

## Non-goals

- **Not apologetics.** DeseretBench measures models, not the Church, and takes no
  position on religious truth-claims.
- **Not a marketing leaderboard.** Rankings exist to expose measurement signal
  (which capabilities separate models, which have saturated), not to sell a winner.
- **Not a theology oracle.** A high score means a model reflects correlated teaching
  accurately; it does not make the model a source of doctrine or a substitute for
  a bishop, a parent, or personal revelation.
- **Not a fairness meter.** Cross-faith symmetry is a different instrument's job.

## The horizon

v0.1 is a pilot: model-authored questions, automated persona validation, a single
judge family, a nominal holdout. Each of those is a known weakness with a planned
successor:

- **Human expert validation** of items (the persona panel is a stand-in, and labeled
  as such).
- **A genuinely private holdout** — freshly written questions, never published —
  once the project is big enough for contamination to matter more than transparency.
- **Judge diversification** beyond a single model family, with cross-judge agreement
  reported the way inter-rater reliability already is.
- **Siblings, not colonies.** The architecture (typed distractors, judge personas,
  the statistical harness) generalizes to other traditions — but a Catholic or Muslim
  or Jewish DeseretBench-alike should be built *by people within those traditions*,
  not by this project guessing at someone else's orthodoxy.

## The name

Deseret is the Book of Mormon word for *honeybee*, and the beehive is the tradition's
oldest symbol of cooperative industry — small contributions, carefully structured,
building something durable and sweet. That is the model for this project: open
craft, offered to the hive.
