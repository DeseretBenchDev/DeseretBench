# ADR-0014: Generation caps for local models, and one model's own window

Status: Accepted

Date: 2026-11-01

*`configs/run_config.yaml` has cited this ADR since July 2026, but the file was never
written. This records the decision as the config comment and the code state it, and
adds the November 2026 exception.*

## Context

The local backend sends two caps with every Ollama call: `num_predict`, the most tokens
a model may generate, and `num_ctx`, the context window that must hold the prompt and
the reply together. ADR-0011 set them to 4,096 and 8,192. Those values came from
serving on CPU, where a small window kept memory down.

The 2026 thinking models broke them. A model that reasons before it answers can spend
several thousand tokens first; Qwen3.5 needed about 5,600 tokens end to end on a real
open-ended item. At a 4,096-token cap its reasoning was cut off before any answer
appeared. The call returned empty content and was recorded as a failure. The Claude
models, meanwhile, answer through the CLI with no comparable cap. The cap was deciding
scores, and unevenly.

## Decision

1. **Shared caps: `ollama_num_predict: 16000`, `ollama_num_ctx: 20480`.** Large enough
   that the thinking models in the cohort finish naturally, still a backstop against a
   model that loops, and small enough that the models in the cohort stay on the test
   card. Every local model runs under these unless it meets point 3.
2. **The caps are not in the cache key.** They govern how a call is made, not what is
   asked (ADR-0003). Raising them re-buys nothing; calls that had failed under the old
   cap were never cached, so they simply ran again.
3. **A model may carry its own window, and its rows say so.** A cohort entry can set
   `backend_opts: {ollama_num_ctx: N}`. This is for a model whose weights fit the card
   and whose context memory at the shared window does not. It is allowed only on a
   track where every item fits the smaller window whole. The window travels with the
   model's summary record, and the results tables print it beside the name with a mark
   and a note. No other model's settings, cache keys or numbers change.
4. **A model that still does not fit is listed as not run**, with the reason, in the
   cohort file and the cohort note. It is not skipped silently and not run in a way
   that changes the measurement.

Phi-4 14B is the first use of point 3: a 2,048-token window, multiple choice only, where
the longest prompt is under 500 tokens. Even so, part of the model runs on CPU. That
changes speed and not the answers, so the row stays, marked, and no speed figure is
published for it.

## Consequences

- Local thinking models are no longer truncated into empty answers.
- A runaway generation can now cost up to 16,000 tokens before it stops.
- "Fits the card" is judged at the shared window, so some models that would load at a
  smaller one are listed as not run on the open-ended track, where a small window could
  clip a long answer.
- A marked row is a slightly different measurement from its neighbours in one respect,
  and the mark is the price of having the row at all. If an item ever fails to fit a
  model's own window, that model's row must be withdrawn, not footnoted.
- Whether the smaller window clipped anything is checkable after the fact: each record
  stores its input and output token counts.

## Alternatives considered

- **Keep 4,096 / 8,192.** Rejected: it silently failed a whole class of models.
- **No cap.** Rejected: a looping model would hold the card until the timeout.
- **A smaller shared window for everyone, so more models fit.** Rejected: it would buy
  two or three more rows at the cost of truncating thinking models again.
- **Put the window in the cache key.** Rejected: every local call would be bought again
  for a setting that does not change what is asked.
