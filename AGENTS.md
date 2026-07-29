# AGENTS.md — how to work in this repo

*For AI agents and human contributors alike. Opinionated on purpose. Each layer goes
one level deeper — read until you have what you need, then follow the links.*

## Layer 0 — what this is

DeseretBench is a reproducible benchmark measuring Latter-day Saint doctrinal
accuracy, cultural fluency, and life-choice alignment in large language models.
The intent lives in [VISION.md](VISION.md). The normative technical spec is
[YELLOWPAPER.md](YELLOWPAPER.md). If those two disagree with anything else
(including this file), they win — VISION for *why*, YELLOWPAPER + code for *what*.

## Layer 1 — prime rules

1. **uv only.** `uv venv --python 3.12 .venv`, `uv pip install --python
   .venv/bin/python -e .`; dev tools via `uv pip install --python .venv/bin/python
   --group dev`. No pip-outside-uv, no poetry, no conda, no requirements.txt
   ([ADR-0008](docs/adr/0008-uv-only-python-toolchain.md)).
2. **The `claude` CLI is the default measurement backend.** No API key is assumed
   to exist. Cohort entries may pin `backend: ollama` for local open-weights
   models served one-at-a-time by a local Ollama
   ([ADR-0011](docs/adr/0011-local-open-weights-backend.md)). Every model call is
   content-addressed-cached in `./cache/` keyed on
   `{backend, model, system, prompt, effort, run_index}` — timeout and parallelism
   are deliberately *not* in the key. Changing any keyed input re-buys those calls
   for real money (or hours of CPU); think before you touch prompts or configs
   ([ADR-0003](docs/adr/0003-content-addressed-response-cache.md)).
3. **Every published number is generated.** Leaderboard scores, CIs, p-values,
   counts in README/PAPER/DATASET_CARD all come from `analyze` → `report` →
   `build_onepager`. Never hand-edit a result; regenerate it. If a doc number can't
   be traced to a generated artifact, that's a bug.
4. **All code and comments here were written by AI** (Claude models, human-directed).
   Treat them as *current state*, not contract. Trust order: tests > generated
   outputs > code > comments. When a comment and the code disagree, the code is what
   happens — fix whichever is wrong, loudly, and add a test.
5. **Check for a live run before changing anything.** Benchmark runs take hours and
   ride rolling usage-limit windows. `pgrep -af "[f]inish_pipeline|[r]esilient_run"`
   (the brackets stop pgrep matching itself) — if it's live, don't edit `scripts/`,
   `configs/`, or `data/questions_*`, and don't run a second pipeline on top
   ([how-to](docs/how-to/recover-interrupted-run.md)).
6. **This repo is built to be publishable.** No personal paths, emails, or real
   names in committed files. Before committing, leak-check the diff for
   home-directory paths and identity strings; keep the committer identity the
   project already uses (see `git log`).
7. **Tests pass before commit.** `.venv/bin/python -m pytest tests/ -q`. New
   behavior gets a test pinning it.

## Layer 2 — task router

| If you want to… | Start at | Check against |
|---|---|---|
| Change MC scoring/extraction | `deseretbench/score_mc.py` | `tests/test_pipeline.py`, [YELLOWPAPER §Scoring](YELLOWPAPER.md) |
| Change judging | `deseretbench/judge.py`, judge phase in `run_benchmark.py` | [judge-design](docs/explanation/judge-design.md) |
| Change statistics | `deseretbench/stats.py`, `analyze.py` | `tests/test_stats.py`, [ADR-0006](docs/adr/0006-statistical-testing-protocol.md) |
| Add a model | `configs/models.yaml` | [how-to](docs/how-to/add-a-model.md), [ADR-0010](docs/adr/0010-cohort-selection-by-cli-probe.md) |
| Run a hosted model (OpenAI/Grok/DeepSeek/GLM/Kimi/…) | `backend: openai_compat` in `configs/models.yaml` | [run-any-model](docs/how-to/run-any-model.md) |
| Add a new tradition (Catholic, Orthodox, …) | `python -m deseretbench.newpack <key>` → `deseretbench/packs/<key>/pack.py` | [add-a-faith-pack](docs/how-to/add-a-faith-pack.md) |
| Add/revise questions | `author` → `assemble` → `validate_questions` → `balance_positions` | [how-to](docs/how-to/add-questions.md) — mind the balance marker |
| Run the whole benchmark | `scripts/finish_pipeline.sh` | [recover-interrupted-run](docs/how-to/recover-interrupted-run.md) |
| Re-analyze without re-running models | `analyze` / `report` | [how-to](docs/how-to/rerun-analysis.md) |
| Understand a past decision | [docs/adr/](docs/adr/) | `DESIGN.md` |
| Cut a release / push | — | [release-checklist](docs/how-to/release-checklist.md) |

## Layer 3 — map of the repo

```
deseretbench/
  runner.py             model-call layer: claude_cli/anthropic_api/ollama/
                        openai_compat backends, cache, retries, served-model
                        verification (the integrity core)
  run_benchmark.py      mc/open/judge phases, atomic JSONL sinks, config snapshots
  score_mc.py           MC letter-extraction rule cascade
  judge.py              judge parsing/aggregation (personas + prompt from the pack)
  stats.py              bootstrap/Holm/Clopper-Pearson/Krippendorff/seeding
  analyze.py            scores + stats → <pack>/summary.json
  report.py             summary.json → <pack>/RESULTS.md, leaderboard, figures
  build_onepager.py     self-contained HTML one-pager (own aesthetic, own palette)
  schema.py             item validation (taxonomy comes from the active pack)
  packs/                the tradition surface, PLUGGABLE. packs/<key>/pack.py
                        exports a Pack (taxonomy, judge, report labels, authoring,
                        review, output routing); packs/lds is the reference,
                        packs/_template the scaffold. schema/judge/report/analyze/
                        author/validate_questions all read the active pack
                        (DESERETBENCH_PACK env → run_config `pack:` → "lds").
  newpack.py            scaffold a new faith pack from packs/_template
  author.py/assemble.py/validate_questions.py/balance_positions.py
                        question pipeline: draft → dedupe → persona review → balance
configs/                models.yaml (cohort + judges), run_config.yaml (constants + pack:)
data/                   published question pool, candidates, raw cells, reviews;
                        private_holdout/ stays untracked (nominal — see docs)
scripts/                run_all.sh, resilient_run.sh, finish_pipeline.sh (wave loops)
runs/ · cache/ · reports/   run outputs · content-addressed call cache · rendered results
docs/                   Diátaxis docs + ADRs (start at docs/README.md)
tests/                  pytest suite — the behavioral contract
```

## Layer 4 — going deeper

- [docs/README.md](docs/README.md) — the Diátaxis router (tutorials / how-to /
  reference / explanation).
- [YELLOWPAPER.md](YELLOWPAPER.md) — precise spec: cache-key tuple, served-model
  rules, extraction cascade, statistical formulas, record schemas.
- [PAPER.md](PAPER.md) — the white paper: motivation, method, results.
- [DESIGN.md](DESIGN.md) — narrative design history; superseded details are marked.
- [RELATED_WORK.md](RELATED_WORK.md) — the faith-AI evaluation landscape.

## Conventions

- Commits: imperative mood, small, scoped; explain *why* in the body when it isn't
  obvious. Data/licensing: code MIT, data CC BY-NC-SA 4.0 — keep the boundary clean
  ([ADR-0009](docs/adr/0009-dual-licensing-mit-cc-by-nc-sa.md)).
- New docs go in the right Diátaxis quadrant; decisions get an ADR, not a comment.
- Generated artifacts (`reports/`, `results/`, `runs/*`) are outputs — regenerate,
  don't hand-edit.
- This file (`AGENTS.md`) is the committed, vendor-neutral agent guide — edit it when
  the working agreement changes. A local `CLAUDE.md`, if you keep one, is git-ignored
  and personal: put machine-specific paths or private notes there, never here.
