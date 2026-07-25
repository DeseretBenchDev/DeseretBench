# Why typed distractors

*Explanation — the reasoning behind a design choice. For the schema itself, see
[data formats](../reference/data-formats.md); for authoring workflow, see
[how to add questions](../how-to/add-questions.md).*

## The discrimination problem

Latter-day Saint doctrine sits close enough to mainstream Christianity that a model
can answer many naively-written questions about it without knowing the tradition at
all. Ask "What does baptism accomplish?" with three absurd options and one reasonable
one, and any model trained on the general internet picks the reasonable one — by
pattern-matching *Christian* keywords, not by knowing anything distinctively LDS.
[VISION.md](../../VISION.md) calls this coasting on "generic religious training data,"
and it is the failure mode a within-tradition benchmark exists to catch.

So a wrong option in DeseretBench is never just wrong. Each distractor is written to
be the answer a model *would* give if it were reasoning from a specific wrong
framework — and that framework is recorded, per choice, in the item's
`distractor_types` field. The correct option is tagged `correct`; every other option
carries one of six trap types. The schema enforces the bookkeeping: when
`distractor_types` is present it must be exactly as long as `choices`, contain
exactly one `correct`, and place it at `answer_index`
(`deseretbench/schema.py`). All 213 public MC items carry the field.

The design bet: if the wrong answers are each *right in some adjacent worldview*,
then a correct answer is evidence of actually knowing the tradition, and a wrong
answer is a diagnosis, not just a demerit.

## The six trap types

Counts below are distractor slots across the 213 public MC items (derived from
`data/questions_mc.jsonl`). Definitions are canonical in
[DESIGN.md §5.3](../../DESIGN.md). Each type is illustrated with a real published
item, quoted verbatim.

### `protestant_trap` (63 slots)

Correct in mainstream Christianity, wrong in LDS theology. This is the direct probe
for the coasting failure: a model substituting mainline-Protestant instincts picks
this option confidently.

> *In Ether 3 the brother of Jared sees the finger, then the full body, of the
> premortal Lord. What does this episode teach about the nature of Christ's premortal
> spirit and His identity...?*
>
> Trap: "The being who appeared was God the Father, Elohim, showing that the Father
> and the Son are the same personage under different names" — a modalist/trinitarian
> reading that a generically-Christian prior finds natural, and that LDS theology
> specifically rejects.

### `folk_doctrine_trap` (127 slots)

Commonly believed by members but not official teaching. This catches a model that
learned the tradition from casual member discourse rather than correlated sources —
arguably a *deeper* form of familiarity than the Protestant trap tests, and still
wrong.

> *On the death of the President of the Church, why is it doctrinally accurate to say
> the new President 'receives no priesthood keys he did not already hold'...?*
>
> Trap: "Because the Quorum of the Twelve votes to confer the full keys upon
> whichever member they elect as President" — a plausible-sounding folk mechanism;
> the correct answer is that every Apostle already holds all keys, exercisable in
> fullness only by the senior living Apostle.

### `anti_mormon_trap` (68 slots)

Factual-sounding but carrying hostile editorial spin — the framing found in critical
literature such as the CES Letter. This tests whether adversarial framings in
training data leak into the model's account of the tradition's own self-understanding.

> *What best describes the primary purpose of the Correlation movement consolidated
> under President McKay and Elder Harold B. Lee in the 1960s?*
>
> Trap: "To screen and suppress controversial elements of Church history so that
> members would encounter only faith-promoting accounts" — a critical gloss presented
> as a neutral description.

### `progressive_trap` (93 slots)

A heterodox or "Sunstone"-adjacent answer that does not reflect the mainstream
correlated position. The benchmark's framing is deliberately orthodox/correlated
(see [DESIGN.md §2](../../DESIGN.md)); this type checks whether a model can
distinguish the institution's actual position from reformist readings of it. It
matters most on cultural and life-choice-adjacent items.

> *At BYU, a returned-missionary student tells his roommate he's anxious about 'ring
> by spring'... Which framing is most accurate to the actual culture and to Church
> teaching on marriage?*
>
> Trap: "'Ring by spring' is anti-Mormon mockery with no basis in actual BYU student
> culture" — a defensive over-correction that misreads a real, self-aware cultural
> quip.

### `correlation_oversimplification` (97 slots)

The too-simple Sunday-School answer where the actual doctrine carries a qualifier or
structure the simple version loses. This separates surface fluency from doctrinal
literacy among models that are already "inside" the tradition.

> *Book of Mormon prophets (2 Nephi 9, Alma 12, Helaman 14) teach that the Fall
> brought TWO deaths and that the Atonement and Resurrection answer each
> differently...*
>
> Trap: "There is only one death — the separation of body and spirit — and the
> Resurrection unconditionally overcomes it, after which all are judged solely by
> works" — recognizably churchy, and missing the conditional/unconditional structure
> the passage actually teaches.

### `plausible_near_miss` (207 slots)

Close-but-wrong on a technical detail — a date, name, sequence, or mechanism. This is
the workhorse type (most items carry at least one) and the standard difficulty
control found in any well-built MC exam.

> *After the October 2019 revision of the temple recommend questions, a member
> worries the standard for worthiness has become stricter...*
>
> Trap: "The revision removed the questions about tithing and the Word of Wisdom,
> leaving belief in God and Christ as the only remaining requirements" — specific,
> confident, and false.

## How typing feeds item analysis

Because the trap type of every choice is recorded, and every scored MC response
records which letter the model picked (`parsed_letter` in
`runs/<run>/mc_responses.jsonl`, written by `deseretbench/run_benchmark.py`), a wrong
answer can be resolved to the framework that produced it. Joining the two tells you
not just *that* a model missed an item but *which adjacent worldview it defaulted
to* — whether a given model's errors skew Protestant, folk, critical, heterodox, or
merely imprecise.

Two honesty notes on the current state:

- The shipped analysis (`deseretbench/analyze.py`) computes classical item analysis —
  per-item difficulty *p* and corrected point-biserial discrimination via
  `stats.item_analysis` — but does **not** itself emit a per-trap-type error
  breakdown in v0.1. The join is a few lines over published artifacts
  (`data/questions_mc.jsonl` × `runs/v0_1/mc_responses.jsonl`), not a shipped table.
- Position balancing permutes `distractor_types` in parallel with `choices`
  (`deseretbench/balance_positions.py`), so the published files stay aligned; the
  join is safe on the shipped set.

Typing also disciplines authoring. The authoring prompt requires at least two
distinct trap types per item (`deseretbench/author.py`), which forces every item to
attack from multiple directions rather than one trap plus filler. This is a
~98%-compliance authoring requirement — four public items violate it — not a schema
invariant.

## Position balancing: the companion control

Typed distractors control *what the wrong options mean*; position balancing controls
*where the right option sits*. The v0.1 authoring pass left the key heavily skewed
(correct answer at "B" roughly 51% of the time), which would let a
position-prior — in a model or a trivial baseline — collect points for free.

`deseretbench/balance_positions.py` re-slots every item's correct answer uniformly at
random (seed 19470417 for the public set), shuffles the distractors so their original
order carries no information, and permutes `distractor_types` in lockstep. On the
shipped balanced set the best fixed-position strategy pays about 29%, near the
uniform floor for mostly-4-choice items. The permutation is recorded in
`data/questions_mc.jsonl.balance_meta.json` and deliberately non-idempotent — see
[REPRODUCE.md](../../REPRODUCE.md) before ever re-running it.

The two controls are complementary: balancing removes the cheap positional shortcut,
and typing ensures that once a model must actually read the options, the wrong ones
are individually seductive to identifiable wrong priors.

## Limits

**Typing is authorial intent, not guaranteed perception.** A choice tagged
`protestant_trap` is one the (model) author believed a Protestant-primed reasoner
would find attractive. Nothing verifies that models experience it that way; a model
might reject it for unrelated reasons or fall for it via a different path. Per-trap
error analysis therefore characterizes items at least as much as it characterizes
models, and should be read as descriptive, not causal. The validation pass (five
blind reviewer personas — themselves one model under five system prompts, see
[DESIGN.md §6](../../DESIGN.md)) checks that items are clear, keyed correctly, and
have one defensible answer; it does not audit trap-type assignments.

**MC saturates at the frontier.** Typed distractors make items harder to
pattern-match, but v0.1's empirical result is that current frontier models clear the
public MC set at or near ceiling, so the MC track has largely stopped discriminating
among them — see [PAPER.md §4.1](../../PAPER.md) for the finding and
[judge-design](judge-design.md) for the consequence: the discriminative load shifts
to the judged open-ended track. Typed distractors remain valuable at the frontier
mostly for *smaller* models and as a diagnostic vocabulary; making MC discriminative
again would take harder items, not merely better-typed ones.

**Coverage is uneven by construction.** `plausible_near_miss` appears far more often
than `protestant_trap`; some trap types simply fit some dimensions better. Per-trap
comparisons across models are therefore built on very different slot counts, and the
rarer types support only coarse conclusions.
