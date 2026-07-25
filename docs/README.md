# DeseretBench documentation

Organized by [Diátaxis](https://diataxis.fr/): **tutorials** teach by doing,
**how-to guides** solve one task, **reference** describes completely, **explanation**
deepens understanding. Pick the quadrant that matches what you need right now.

## Tutorials — learning by doing

- [Your first DeseretBench run](tutorials/first-run.md) — clean clone to reading
  results, on a deliberately tiny (cheap) scope.

## How-to guides — one task, done

- [Add a model to the cohort](how-to/add-a-model.md)
- [Add or revise questions](how-to/add-questions.md)
- [Re-analyze without re-running models](how-to/rerun-analysis.md)
- [Regenerate the reports and one-pager](how-to/regenerate-reports.md)
- [Run the judge cross-check](how-to/run-judge-crosscheck.md)
- [Recover an interrupted run](how-to/recover-interrupted-run.md)
- [Release checklist](how-to/release-checklist.md)

## Reference — look it up

- [Command-line interfaces](reference/cli.md) — every runnable module, every flag
- [Configuration](reference/configuration.md) — `models.yaml`, `run_config.yaml`, `pyproject.toml`
- [The response cache](reference/cache.md) — layout, key tuple, guards, invalidation
- [Data formats](reference/data-formats.md) — every record schema, field by field
- [Scripts](reference/scripts.md) — the wave-loop wrappers
- [Glossary](reference/glossary.md)

## Explanation — why it is this way

- [Why typed distractors](explanation/why-typed-distractors.md)
- [How the judge is designed (and its biases)](explanation/judge-design.md)
- [Measurement integrity](explanation/measurement-integrity.md) — the threat model
  and its answers
- [The statistics, justified](explanation/statistics.md)
- [The holdout stance](explanation/holdout-stance.md)
- [Project philosophy](explanation/philosophy.md) — FLOSS, licensing, AI authorship

## Decisions

Architectural decision records live in [adr/](adr/) — one decision per file, with
status and consequences. Start at
[ADR-0001](adr/0001-record-architecture-decisions.md).

## The root-level canon

| Document | Role |
|---|---|
| [VISION.md](../VISION.md) | Why the project exists; principles and non-goals |
| [PAPER.md](../PAPER.md) | White paper — motivation, method, results |
| [YELLOWPAPER.md](../YELLOWPAPER.md) | Yellow paper — normative technical spec |
| [DESIGN.md](../DESIGN.md) | Narrative design history |
| [RELATED_WORK.md](../RELATED_WORK.md) | The faith-AI evaluation landscape |
| [DATASET_CARD.md](../DATASET_CARD.md) | Dataset card for the question pool |
| [REPRODUCE.md](../REPRODUCE.md) | End-to-end reproduction instructions |
| [AGENTS.md](../AGENTS.md) | Working agreement for contributors (AI and human) |
