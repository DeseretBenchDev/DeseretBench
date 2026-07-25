# ADR-0009: Dual licensing — MIT for code, CC BY-NC-SA 4.0 for data

Status: Accepted

Date: 2026-06

## Context

DeseretBench ships two very different kinds of artifact under one repository. The
**code** — runner, analysis, judge, reporting — is ordinary tooling we want
reused as widely as possible, including in commercial settings. The **data** —
questions, answer keys, typed distractors, rubrics, and the model-response and
judging records — is the intellectual core of the benchmark, and its value
depends on staying an *evaluation* set rather than becoming *training* material.
A single permissive license across both would let the questions be swept into a
commercial training corpus, which defeats the point of a held-out benchmark.

## Decision

License the two artifact classes separately, with the split written into both
license files and cross-referenced.

- **Code: MIT** ([`LICENSE`](../../LICENSE)). Scoped to `deseretbench/`,
  `scripts/`, `lm_eval/`, `configs/`, and `tests/`. Reuse freely, including
  commercially.
- **Data: CC BY-NC-SA 4.0** ([`LICENSE-DATA`](../../LICENSE-DATA)). Scoped to
  `data/`, `runs/`, and `results/` — the questions, keys, distractors, rubrics,
  and all model-response/judging data. Attribution required, non-commercial,
  share-alike.
- **Eval-not-training intent, stated.** The README and dataset card both say the
  data is "intended for model evaluation, not training." NonCommercial +
  ShareAlike is the mechanism that backs that intent for the dataset.
- Each license file carries an explicit **NOTE ON SCOPE** pointing at the other,
  so a reader who opens either one learns the split immediately.

## Consequences

- **The dataset is not freely embeddable in commercial training corpora.** Using
  the questions to train a commercial model would require a separate license
  from the maintainers; NC forbids the default commercial path and SA forces
  derivatives to stay under the same terms.
- **The code carries no such restriction.** Anyone can build on the harness.
- **SPDX caveat.** [`pyproject.toml`](../../pyproject.toml) records
  `license = { text = "CC-BY-NC-SA-4.0 (data) / MIT (code)" }`. That string is
  human-readable documentation of the dual split, **not** a valid single SPDX
  expression — automated SPDX tooling will not parse it. The authoritative,
  scoped terms live in `LICENSE` and `LICENSE-DATA`, not in the manifest field.
- **Two-license overhead for redistributors.** Anyone repackaging the repo must
  honor both licenses and keep the scope notes intact.

## Links

- Code license: [LICENSE](../../LICENSE) (MIT, with scope note).
- Data license: [LICENSE-DATA](../../LICENSE-DATA) (CC BY-NC-SA 4.0, with scope note).
- Dataset card: [DATASET_CARD.md](../../DATASET_CARD.md) (front-matter `license: cc-by-nc-sa-4.0`).
- Manifest field: [pyproject.toml](../../pyproject.toml).
