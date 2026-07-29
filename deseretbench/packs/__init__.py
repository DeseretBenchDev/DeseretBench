"""Faith packs — the tradition-specific surface of the benchmark, made pluggable.

DeseretBench began as one tradition (Latter-day Saint) with its taxonomy, judge,
and authoring prose hardcoded across five modules. A *pack* gathers all of that
into one place so a second tradition — Catholic, Eastern Orthodox, whatever a
contributor brings — is an addition, not a fork. Everything that is NOT
tradition-specific (the runner, the content-addressed cache, MC scoring, the
statistics, the analysis grouping) stays where it is and never imports a pack.

A pack is a Python package with a ``pack.py`` that exports a ``PACK`` — a
:class:`Pack` instance. DeseretBench itself ships exactly one in-package pack,
``lds`` (plus ``_template``); it is the LDS benchmark. A *contributed* tradition
is SEPARATE — it lives outside the deseretbench package and is discovered on the
external search path (:func:`external_pack_dirs`: ``DESERETBENCH_PACK_PATH``,
default ``<repo>/packs``), which is searched before the in-package location.
Only the framework is shared. Python rather than YAML because a pack carries
prompt *builders* (the judge prompt, the authoring prompts), which are functions,
not data. See ``packs/lds`` for the reference and
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
import importlib.util
import os
import sys
from pathlib import Path
from typing import Callable, Mapping, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent   # repo root
_INPKG = Path(__file__).resolve().parent                # deseretbench/packs


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

    # output + data routing — the LDS pack keeps the legacy data/ + reports/ +
    # results/ paths (the live site and the shipped question set live there);
    # other packs namespace by key (data/<key>, reports/<key>, results/<key>) so
    # authoring or reporting a second tradition never overwrites the first.
    data_dir: str
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

    # ---- authoring (optional) ---------------------------------------------- #
    # Generating a fresh question set for this tradition. A pack that only needs
    # to be *scored* (running models against a set someone else authored) can
    # leave these None; deseretbench.author raises a clear error if asked to
    # author without them. The grounding brief is the factual anchor embedded in
    # the authoring prompts (for LDS it stays at data/grounding_brief.md).
    grounding: Optional[str] = None
    authoring_stance: Optional[str] = None
    distractor_guide: Optional[str] = None
    authoring_rules: Optional[str] = None
    mc_example: Optional[str] = None
    open_example: Optional[str] = None
    diff_desc: Optional[Mapping[str, str]] = None
    mc_dims: Optional[tuple] = None       # (dimension, target_count, description, subtopics)
    open_cells: Optional[tuple] = None    # (dimension, difficulty, count, themes)
    mc_authoring_prompt: Optional[Callable[[dict], str]] = None
    open_authoring_prompt: Optional[Callable[[dict], str]] = None

    # ---- reviewer validation (optional) ------------------------------------ #
    # The automated expert panel that vets authored candidates. Same rule:
    # required to *validate* a fresh set, not to score an existing one.
    reviewers: Optional[Mapping[str, str]] = None
    mc_review_prompt: Optional[Callable[[dict], str]] = None
    open_review_prompt: Optional[Callable[[dict], str]] = None


def external_pack_dirs() -> list[Path]:
    """Directories searched for *external* packs — separate traditions that live
    outside the deseretbench package (DeseretBench itself is lds-only). Set
    ``DESERETBENCH_PACK_PATH`` (os.pathsep-separated) to override; the default is
    ``<repo>/packs``. Only existing directories are returned."""
    raw = os.environ.get("DESERETBENCH_PACK_PATH")
    dirs = ([Path(p) for p in raw.split(os.pathsep) if p.strip()] if raw
            else [_ROOT / "packs"])
    return [d for d in dirs if d.is_dir()]


def _pack_dirs(d: Path) -> list[str]:
    if not d.is_dir():
        return []
    return [p.name for p in d.iterdir()
            if p.is_dir() and not p.name.startswith((".", "_"))
            and (p / "pack.py").exists()]


def list_packs() -> list[str]:
    """Selectable pack keys — the in-package packs (lds) unioned with every
    external pack on the search path. ``_template`` and dotfiles are hidden."""
    names = set(_pack_dirs(_INPKG))
    for d in external_pack_dirs():
        names.update(_pack_dirs(d))
    return sorted(names)


def _load_pack_file(key: str, pack_py: Path) -> Pack:
    """Load an external pack from a pack.py path (not on the import path)."""
    modname = f"_dbpack_{key}"
    spec = importlib.util.spec_from_file_location(modname, pack_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod          # so dataclasses/typing resolve during exec
    spec.loader.exec_module(mod)        # its `from deseretbench.packs import Pack` resolves
    pack = getattr(mod, "PACK", None)
    if not isinstance(pack, Pack):
        raise ValueError(f"pack {key!r} at {pack_py} must export a Pack named PACK")
    return pack


def load_pack(key: str) -> Pack:
    """Return the ``PACK`` for a key. External packs (on the search path) win
    over in-package ones, so a contributed tradition never needs to touch the
    deseretbench package."""
    for root in external_pack_dirs():
        pack_py = root / key / "pack.py"
        if pack_py.exists():
            return _load_pack_file(key, pack_py)
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
