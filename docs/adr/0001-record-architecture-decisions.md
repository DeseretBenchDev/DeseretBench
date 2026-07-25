# ADR-0001: Record architecture decisions

Status: Accepted

Date: 2026-06

## Context

DeseretBench makes a handful of load-bearing choices — how models are called,
how responses are cached, how distractors are typed, how open-ended answers are
judged — that shape every number the benchmark produces. Those choices are not
obvious, and several of them trade something away (see the honest limitations in
[VISION.md](../../VISION.md) and [DESIGN.md](../../DESIGN.md)). If the reasoning
lives only in commit messages and a maintainer's memory, a future contributor
(human or AI) will either relitigate a settled question or, worse, quietly undo
a decision without knowing what it was protecting.

The project's own working agreement ([VISION.md](../../VISION.md), principle 5)
says to treat code and comments as *what currently exists*, not as
self-evidently correct. Decisions need a record that outranks a comment and
sits next to the code without being buried in it.

## Decision

Adopt Architecture Decision Records, in the lightweight Nygard style, under
`docs/adr/`.

- **One decision per file.** Each ADR is numbered (`NNNN`), titled, and captures
  a single choice with its context and consequences. Files are append-only in
  spirit: the historical record is not edited to look smarter after the fact.
- **Fixed sections.** Every ADR carries `Status`, `Date`, `Context`,
  `Decision`, `Consequences` (cons included, not just pros), and `Links`.
- **Superseding, not deletion.** A decision that changes is not rewritten. A new
  ADR is written, its `Status` is `Accepted`, and it names the ADR it
  supersedes; the old ADR's status is flipped to `Superseded by ADR-NNNN`. The
  losing option stays on the record so the reversal is legible.
- **Status vocabulary:** `Proposed`, `Accepted`, `Superseded by ADR-NNNN`,
  `Deprecated`. v0.1 ships everything as `Accepted`.

ADRs are the *why*; they do not duplicate the *how*. Reference material lives in
[docs/reference/](../reference/), task recipes in [docs/how-to/](../how-to/),
and longer-form rationale in [docs/explanation/](../explanation/). ADRs
cross-link to those rather than restating them.

## Consequences

- There is a small standing cost: a genuine architectural choice now means
  writing a file, not just merging a diff.
- The line between "architectural decision" and "ordinary implementation
  detail" is a judgment call; not every choice warrants an ADR, and reasonable
  contributors will disagree about the threshold.
- ADRs record intent at a moment in time. They go stale the instant the code
  moves without the record following. A reader must treat an ADR as history, and
  verify current behavior against the code — the same discipline the whole
  project runs on.

## Links

- Style: Michael Nygard, "Documenting Architecture Decisions" (2011).
- The v0.1 decisions this practice records: [ADR-0002](0002-claude-cli-backend-stdin-transport.md),
  [ADR-0003](0003-content-addressed-response-cache.md),
  [ADR-0004](0004-typed-distractors-and-position-balancing.md),
  [ADR-0005](0005-judge-panel-three-personas.md),
  [ADR-0010](0010-cohort-selection-by-cli-probe.md).
- Governing intent: [VISION.md](../../VISION.md).
