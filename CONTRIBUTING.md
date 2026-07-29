# Contributing to DeseretBench

Thanks for being here. **DeseretBench** is a reproducible benchmark for how well
language models understand one tradition in depth — the Church of Jesus Christ of
Latter-day Saints. Under it sits a small, tradition-agnostic **framework**, so the
same machinery can measure *any* tradition. That framework is the part most open
to contribution.

You don't need to be a developer to help, and you don't need permission to start.

## The quickest way to help

- **Found a wrong answer key, an ambiguous question, or a typo?** Open an issue or
  a pull request. Doctrine questions are hard to get exactly right; careful eyes
  are the most valuable thing you can bring.
- **Know a tradition well?** Build a benchmark for it — see *"Add your own
  tradition"* below. This is the contribution we most hope to see.
- **Want to test a model we haven't?** See
  [docs/how-to/add-a-model.md](docs/how-to/add-a-model.md) (local + Claude) and
  [docs/how-to/run-any-model.md](docs/how-to/run-any-model.md) (OpenAI, Grok,
  DeepSeek, OpenRouter, Nous, any OpenAI-compatible endpoint).
- **Improve the docs, the stats, the site.** All fair game.

## Add your own tradition (a faith pack)

DeseretBench is **LDS-only** on purpose. A benchmark for another tradition is a
*separate* thing — its own doctrine, its own experts, its own name — unified with
DeseretBench only by the shared framework. So a new tradition is not a change to
DeseretBench; it's a **pack** that lives outside the package and plugs into the
same rails.

```bash
python -m deseretbench.newpack catholic --name "the Catholic tradition"
```

That scaffolds `packs/catholic/` (outside the code, gitignored — it's yours), with
the reusable structure pre-filled and the tradition-specific content marked
`TODO`. Fill it in, write its grounding brief, and run author → validate → score.
The full recipe is [docs/how-to/add-a-faith-pack.md](docs/how-to/add-a-faith-pack.md);
`deseretbench/packs/lds/pack.py` is a complete worked example to copy from.

The one rule that makes these benchmarks trustworthy: **key every answer to the
mainstream, official position of the tradition, and represent minority or outside
views only as distractors** — accurately, never as strawmen. The goal is to
measure understanding, not to grade orthodoxy of belief.

## Setting up to hack on the code

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .
.venv/bin/python -m pytest        # the test suite is the contract
```

That's it — no services, no accounts, no API key needed for the default path.

## Conventions

- **Tests first.** New behavior comes with a test that failed before it and passes
  after. The suite is fast; keep it green.
- **Never hand-type a statistic.** Every number in the docs and reports is
  generated from `results/summary.json`. Change the data or the code, then
  regenerate — don't edit numbers by hand.
- **Small, focused commits** that say *why* in the message.
- **The LDS set is load-bearing.** Every non-LDS pack namespaces its own
  `data/<key>/`, `results/<key>/`, `reports/<key>/`, so your work can never
  overwrite the reference set. If a change touches shared code, confirm the LDS
  numbers are unchanged (`reports/RESULTS.md` should regenerate byte-identical).
- **License.** Code is MIT; the question data is CC BY-NC-SA 4.0 (see `LICENSE`
  and `LICENSE-DATA`). By contributing you agree your contribution ships under the
  same terms.

## Where to look

`AGENTS.md` is the map of the repo — read it first. `README.md` → `VISION.md` →
`DESIGN.md` explain what this is and why it's built the way it is, and
`docs/README.md` is the documentation hub. Questions are welcome as issues.
