"""Faith packs — the tradition-specific surface of the benchmark, made pluggable.

DeseretBench began as one tradition (Latter-day Saint) with its taxonomy, judge,
and authoring prose hardcoded across five modules. A *pack* gathers all of that
into one place so a second tradition — Catholic, Eastern Orthodox, whatever a
contributor brings — is an addition, not a fork. Everything that is NOT
tradition-specific (the runner, the content-addressed cache, MC scoring, the
statistics, the analysis grouping) stays where it is and never imports a pack.

A pack is a Python package under ``deseretbench/packs/<key>/`` that exports a
``PACK`` — a :class:`Pack` instance. Python rather than YAML because a pack
carries prompt *builders* (the judge prompt, the authoring prompts), which are
functions, not data. See ``packs/lds`` for the reference and
``docs/how-to/add-a-faith-pack.md`` for the process.

**Resolution.** The active pack is chosen once per process: the ``DESERETBENCH_PACK``
environment variable wins, else ``pack:`` in ``configs/run_config.yaml``, else
``"lds"``. :func:`active_pack` memoizes the result; :func:`reset_pack_cache`
clears it. The schema validators also accept an explicit ``pack=`` so a single
process (a test, a cross-tradition tool) can validate against more than one pack
without touching the global.
"""

from __future__ import annotations

import dataclasses
import importlib
import os
from pathlib import Path
from typing import Callable, Mapping, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent   # repo root


@dataclasses.dataclass(frozen=True)
class Pack:
    """The complete tradition-specific contract.

    Phase 1 fields (below) cover the taxonomy the schema validates against, the
    judge, the report labels, and output routing. Authoring/reviewer fields are
    added by the authoring phase; a pack that only needs to be *scored* (not
    authored from scratch) can be complete with these.
    """

    # identity + report framing
    key: str
    name: str                     # tradition, e.g. "the Latter-day Saint tradition"
    report_title: str             # wordmark used in report titles, e.g. "DeseretBench"
    report_blurb: str             # one-line description for the report banner

    # output routing — the LDS pack keeps the legacy reports/ + results/ paths
    # (the live site links them directly); other packs namespace by key so a
    # second run never clobbers the first.
    results_dir: str
    reports_dir: str

    # taxonomy — what the schema validates every item against
    axes: frozenset
    mc_dimensions: frozenset
    open_dimensions: frozenset
    distractor_types: frozenset          # includes the "correct" sentinel
    axis_for_dimension: Mapping[str, str]

    # report labels — the radar's dimension order and short display names
    dim_order: tuple
    dim_short: Mapping[str, str]

    # judge — the open-ended panel
    judge_personas: Mapping[str, str]
    judge_system: str
    judge_dimensions: tuple
    build_judge_prompt: Callable[[dict, str, str], str]   # (item, response, persona_key)


def _packs_dir() -> Path:
    return Path(__file__).resolve().parent


def list_packs() -> list[str]:
    """Selectable pack keys: every subdir with a ``pack.py`` whose name does not
    start with ``_`` (``_template`` is scaffolding, not a runnable tradition)."""
    d = _packs_dir()
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_"))
                  and (p / "pack.py").exists())


def load_pack(key: str) -> Pack:
    """Import ``deseretbench.packs.<key>.pack`` and return its ``PACK``."""
    try:
        mod = importlib.import_module(f"deseretbench.packs.{key}.pack")
    except ImportError as e:
        raise ValueError(
            f"unknown faith pack {key!r}; available: {list_packs()}") from e
    pack = getattr(mod, "PACK", None)
    if not isinstance(pack, Pack):
        raise ValueError(f"pack {key!r} must export a Pack instance named PACK")
    return pack


def _resolve_key() -> str:
    env = os.environ.get("DESERETBENCH_PACK")
    if env and env.strip():
        return env.strip()
    try:
        import yaml
        data = yaml.safe_load(
            (_ROOT / "configs" / "run_config.yaml").read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("pack"):
            return str(data["pack"]).strip()
    except Exception:
        pass
    return "lds"


_active: Optional[Pack] = None


def active_pack() -> Pack:
    """The pack for this process (memoized). See module docstring for resolution."""
    global _active
    if _active is None:
        _active = load_pack(_resolve_key())
    return _active


def reset_pack_cache() -> None:
    """Forget the memoized active pack (tests that switch packs in-process)."""
    global _active
    _active = None
