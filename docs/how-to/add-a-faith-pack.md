# How to add a faith pack

Goal: stand up a benchmark for a new tradition — Catholic, Eastern Orthodox,
whatever you bring — by cloning the repo, scaffolding a pack, and filling in the
tradition's content. The runner, cache, scoring, statistics, and analysis are
tradition-agnostic and need no changes; you supply doctrine, not machinery.

Honest status: the pack system is implemented and tested, and the LDS pack
(`deseretbench/packs/lds`) is a complete worked example. No non-LDS pack has been
authored or run yet — you would be the first. This page is the recipe.

## What a pack is

A pack is the tradition-specific surface of the benchmark gathered into one
Python package under `packs/<key>/` — **outside** the deseretbench package.
DeseretBench itself is lds-only (the `lds` pack ships in-package); a contributed
tradition is *separate*, unified with DeseretBench only by the framework. The
loader finds external packs via `DESERETBENCH_PACK_PATH` (os-path-separated,
default `./packs`), searching it before the in-package location. A pack exports
a `PACK` object with the taxonomy the schema validates against, the judge
(personas, dimensions, prompt), the report labels, the authoring taxonomy and
prompts, and the reviewer panel. Everything in `deseretbench/` reads the
*active* pack and is otherwise untouched. Packs are Python (not YAML) because
they carry prompt *builders* — functions — not just data.

The active pack resolves once per process: the `DESERETBENCH_PACK` environment
variable wins, then `pack:` in `configs/run_config.yaml`, then `lds`. (Set
`DESERETBENCH_PACK_PATH` too if your packs live somewhere other than `./packs`.)

## 1. Scaffold

```bash
python -m deseretbench.newpack catholic --name "the Catholic tradition" --title "CatholicBench"
```

This copies the template to `packs/catholic/` (repo root, outside the package,
gitignored), substitutes the
identity fields, and verifies the pack loads. `--name` should read naturally in a
sentence ("a question about *the Catholic tradition*"); `--title` is the report
wordmark. Both default sensibly from the key if omitted.

The key must be a valid Python package name (lowercase, letters/digits/
underscores, starts with a letter), because it becomes an import path and a
directory. A fresh pack namespaces every output — `data/<key>/`, `results/<key>/`,
`reports/<key>/` — so authoring or scoring it can never overwrite another pack's
set.

## 2. Fill in the tradition

Open `packs/<key>/pack.py` and work through the `TODO`s top to
bottom. It is one file, sectioned:

- **Taxonomy.** The three evaluation axes (doctrinal accuracy, cultural fluency,
  life-choice alignment) are kept as tradition-neutral defaults; you define the
  **MC dimensions**, the **distractor traps** that separate real understanding
  from pattern-matching in your tradition, and the dimension→axis map. Keep the
  `cultural_fluency` dimension and the two open dimensions (`life_choice`,
  `cultural_open`) unless you have reason not to.
- **Judge.** Three distinct expert-evaluator personas and the system framing. The
  four scoring dimensions are reusable defaults; the judge JSON is generated from
  them, so if you change the dimensions the prompt stays consistent.
- **Authoring.** The **stance** (what the benchmark rewards and which sources are
  authoritative), the distractor guide, the difficulty descriptions, and the
  **MC_DIMS / OPEN_CELLS** taxonomy (dimensions with target counts and rotating
  subtopics). The authoring prompt builders are already wired to these.
- **Reviewers.** Five reviewer personas that catch different failure modes.

Then write `packs/<key>/grounding_brief.md` — the factual anchor
embedded in every authoring prompt (canon, official teaching bodies, the
mainstream position, common confusions, vocabulary, currency notes). The
placeholder file explains what a good brief contains; `data/grounding_brief.md`
(the LDS brief) is the worked example for density and tone.

Compare against `deseretbench/packs/lds/pack.py` throughout — it is the same
structure, fully filled.

## 3. Select the pack

Either export it for the session:

```bash
export DESERETBENCH_PACK=catholic
```

or set `pack: catholic` in `configs/run_config.yaml` (the env var wins if both
are set).

## 4. Author the candidate set

Authoring calls a model to draft items from your taxonomy and grounding brief.
This is the one place a new pack spends API/CLI budget.

```bash
python -m deseretbench.author            # -> data/<key>/raw/*.jsonl
python -m deseretbench.assemble          # dedup + validate -> data/<key>/candidates_*.jsonl
```

`author` refuses to run if the pack's authoring taxonomy or grounding brief is
still empty, and tells you what to fill.

## 5. Validate

The reviewer panel vets candidates blind and applies the keep-rules, producing
the public set and a stratified private holdout:

```bash
python -m deseretbench.validate_questions   # -> data/<key>/questions_*.jsonl (+ holdout)
python -m deseretbench.balance_positions \
  --in data/<key>/questions_mc.jsonl --out data/<key>/questions_mc.jsonl
```

## 6. Score and report

Run models against your set exactly as for LDS — pick a backend per
[add-a-model.md](add-a-model.md) (local `claude_cli`/`ollama`, or any hosted
model via [run-any-model.md](run-any-model.md)):

```bash
python -m deseretbench.run_benchmark mc   --questions data/<key>/questions_mc.jsonl   --out runs/<key>
python -m deseretbench.run_benchmark open --questions data/<key>/questions_open.jsonl --out runs/<key>
python -m deseretbench.analyze --run runs/<key>     # -> results/<key>/summary.json
python -m deseretbench.report                        # -> reports/<key>/...
```

`analyze` and `report` default their output paths from the active pack, so with
your pack selected they write under `results/<key>/` and `reports/<key>/`
automatically.

## Notes

- **One pack per process.** The active pack is resolved at import; run each
  tradition as its own invocation. Don't try to mix two in one process (the
  schema validators accept an explicit `pack=` for the rare cross-tradition tool,
  but the pipeline entry points use the active pack).
- **The LDS set is safe.** Every non-LDS pack is namespaced by key across data,
  results, and reports. Nothing you do to a new pack touches `data/questions_*`,
  `results/summary.json`, or `reports/`.
- **`lm_eval/deseretbench_mc.yaml`** (the EleutherAI harness scaffold) is
  LDS-specific — its `task` name and `test:` path point at the LDS set. Copy and
  repoint it if you want the same portability for your pack.
- **The one-pager and home page are not pack-aware yet.** `deseretbench.report`
  (the `reports/<key>/` leaderboard + figures) follows your pack; the standalone
  broadsheet (`build_onepager.py`) and the site `index.html` are still
  LDS-branded. Your pack gets the leaderboard and figures; a bespoke landing
  page is a separate exercise.
