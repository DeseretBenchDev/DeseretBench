"""report.py presentation invariants.

These exist because a cohort change is the most common way report generation
breaks, and it breaks LATE — after a multi-hour run, while rendering. ADR-0013
added five model families at once and three call sites indexed the colour map
directly (`TIER_COLOR[tier]`), which is a KeyError for any new tier.
"""

import pathlib

import yaml

from deseretbench.report import TIER_COLOR, TIER_ORDER, tier_color

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _cohort_tiers():
    cfg = yaml.safe_load((ROOT / "configs/models.yaml").read_text())
    return {m["tier"] for m in cfg["cohort"]}


def test_every_cohort_tier_has_a_colour():
    """A tier the cohort actually uses must be plottable. Missing entries used to
    surface as a KeyError mid-render, destroying the run's only artifact."""
    missing = sorted(_cohort_tiers() - set(TIER_COLOR))
    assert not missing, f"tiers in models.yaml with no TIER_COLOR entry: {missing}"


def test_every_cohort_tier_is_ordered():
    """Figures iterate TIER_ORDER; a tier absent from it is silently dropped from
    the plot rather than erroring — worse than a crash, because it looks fine."""
    missing = sorted(_cohort_tiers() - set(TIER_ORDER))
    assert not missing, f"tiers in models.yaml missing from TIER_ORDER: {missing}"


def test_tier_colour_never_raises_on_unknown_tier():
    """Degrade to grey, never crash: a cohort can gain a family at any time."""
    assert tier_color("a-family-that-does-not-exist-yet") == "#888"
    assert tier_color("") == "#888"


def test_known_tier_colours_are_distinct():
    """Two families sharing a colour makes a multi-family figure unreadable."""
    dupes = {c for c in TIER_COLOR.values()
             if list(TIER_COLOR.values()).count(c) > 1}
    assert not dupes, f"colours reused across tiers: {sorted(dupes)}"
