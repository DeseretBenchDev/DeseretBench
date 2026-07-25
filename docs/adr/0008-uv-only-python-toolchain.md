# ADR-0008: uv-only Python toolchain

Status: Accepted

Date: 2026-06

## Context

DeseretBench is a reproducible benchmark: the environment that produced the
numbers has to be reconstructible by a stranger. Python packaging offers several
ways to do that — `pip` + `requirements.txt`, `conda`, `poetry`, `pipenv`, `uv`
— and mixing them invites the classic failure where a contributor's environment
subtly differs from the one that generated the published results.

We also want a single, fast, deterministic path that resolves and installs
dependencies the same way every time, pins the interpreter, and keeps
dev-only tooling (pytest) out of the runtime dependency set.

## Decision

Standardize on **[uv](https://github.com/astral-sh/uv)** as the only supported
toolchain, and pin **Python 3.12**.

- **Interpreter pin.** [`pyproject.toml`](../../pyproject.toml) sets
  `requires-python = ">=3.12"`; the documented setup creates the venv with
  `uv venv --python 3.12 .venv`.
- **Editable install via uv.** Runtime setup is
  `uv pip install --python .venv/bin/python -e .`. Modules run as
  `.venv/bin/python -m deseretbench.<module>`.
- **Dev tooling as a dependency-group.** pytest lives in a
  `[dependency-groups] dev = ["pytest>=8"]` block, installed with
  `uv pip install --python .venv/bin/python --group dev` — not in `dependencies`,
  so a plain runtime install stays lean.
- **No `requirements.txt`.** The dependency set is declared once in
  `pyproject.toml` (`dependencies` for runtime, `[project.optional-dependencies]`
  `api`/`hub` extras for backends and publishing). uv is the resolver of record.
- Build backend is `hatchling`, packaging only the `deseretbench` directory.

## Consequences

- **Contributors need uv installed.** There is no `pip install -r requirements.txt`
  fallback; the documented commands assume `uv` is on `PATH`. This is a small,
  deliberate barrier in exchange for one reproducible path.
- **One resolution story.** Everyone resolves dependencies the same way against
  the same interpreter pin, so "works on my machine" drift is minimized.
- **Lean runtime, explicit dev extras.** Someone who only wants to run the
  benchmark never installs pytest; someone running the API backend opts into
  `.[api]` explicitly.
- **Interpreter floor, not ceiling.** `>=3.12` allows newer patch/minor
  interpreters; contributors reproducing exact numbers should use 3.12 as
  documented.

## Links

- Environment setup: [docs/tutorials/first-run.md](../tutorials/first-run.md).
- Reproduction guide: [REPRODUCE.md](../../REPRODUCE.md) §0 Environment.
- CLI reference: [docs/reference/cli.md](../reference/cli.md).
- Manifest: [pyproject.toml](../../pyproject.toml).
