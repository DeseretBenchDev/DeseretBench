# ADR-0015: A framed prompt condition, kept apart from the standings

Status: Accepted

Date: 2026-11-01

## Context

Every score so far comes from one neutral system prompt. The prompt does not tell the
model which tradition to answer from beyond what each question states (DESIGN §4.1).
That measures what a model says by default. It cannot tell two different failures
apart: a model that does not know the teaching, and a model that knows it and answers
from another frame unless told.

The original plan for the benchmark named a second condition for this: run each model
again with one added sentence telling it to answer according to the Church's teachings,
and report the gap. A model that scores 85 framed and 55 neutral knows the doctrine and
defaults elsewhere. A model that scores 55 both ways does not know it.

The framed condition changes the instrument. Mixing its scores with the neutral ones
would change published numbers.

## Decision

Add `framed` as a second **condition** beside `neutral`.

- The sentence belongs to the tradition, so it lives in the pack as
  `framed_instruction`. A pack without one has no framed edition.
- `run_benchmark {mc|open} --condition framed` appends the sentence to the configured
  system prompt. Nothing else changes: same items, templates, effort and judge. The
  judge prompt is the same in both conditions, so a framed answer is scored against the
  same rubric.
- `--condition neutral` is the default and returns the configured prompt untouched, so
  no existing cache key changes.
- Framed records carry `"condition": "framed"`. Neutral records carry no `condition`
  key, and a missing key means neutral, so every shipped record file stays valid.
- The two conditions never share a place:
  - the system prompt is part of the cache key, so the calls cannot collide;
  - a run directory holds one condition, and the run phases refuse to write another
    beside it;
  - `merge_runs` refuses framed records;
  - `analyze` stops if the run it is given holds any non-neutral record.
- `python -m deseretbench.framing --neutral DIR --framed DIR` compares the two. For each
  model and track it reports the neutral mean, the framed mean and the paired gap over
  the items both runs scored, with a seeded bootstrap interval and a Holm-adjusted *p*
  across the models of that track. It writes `framing.json` and `FRAMING.md` and reads
  nothing from, and writes nothing to, `summary.json`.

## Consequences

- The standings stay the neutral condition, by construction and by test.
- A framed run buys every call again. For the hosted and Claude models that is real
  usage; for the local models it is card time. The open-ended track also needs the
  judge panel again.
- The gap is a paired difference on the same items, so it is tighter than a comparison
  of two separate scores. Where repeats differ between the runs, per-item means are
  compared, as everywhere else.
- Multiple choice is at the ceiling for the strongest models, so their gap there is
  zero by arithmetic. The open-ended track is where the framed edition can say
  something about them.
- No framed run has been made yet. This ADR records the mechanism, not a result.

## Alternatives considered

- **A second system prompt in `run_config.yaml`.** Rejected: the sentence names the
  tradition, and the config is shared by every pack.
- **A `condition` field on every record, neutral included.** Rejected: it would rewrite
  every shipped record file to say what a missing key already says.
- **Folding the gap into `summary.json`.** Rejected: the summary is the standings, and
  one file with two instruments in it is how a framed number ends up in a leaderboard.
