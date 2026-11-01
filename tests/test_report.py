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


def test_onepager_palette_covers_every_tier_report_knows():
    """The one-pager keeps its own print palette, so a tier added to report.py
    alone renders there as a grey chip: seventeen tiers did, across three cohort
    additions, and nothing failed."""
    from deseretbench import build_onepager
    missing = sorted((_cohort_tiers() | set(TIER_COLOR))
                     - set(build_onepager.TIER_COLOR))
    assert not missing, f"tiers with no one-pager colour: {missing}"


def test_onepager_tier_colours_are_distinct_and_carry_white_text():
    """The tier chip and the bar label are white text on the tier colour."""
    from deseretbench.build_onepager import TIER_COLOR as PAGE

    def luminance(colour):
        chans = [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                   for c in chans)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    colours = [c.upper() for c in PAGE.values()]
    assert len(set(colours)) == len(colours), "colours reused across tiers"
    faint = {t: round(1.05 / (luminance(c) + 0.05), 2) for t, c in PAGE.items()
             if 1.05 / (luminance(c) + 0.05) < 4.5}
    assert not faint, f"white text below 4.5:1 on: {faint}"


def test_onepager_cohort_badge_counts_every_model_without_calling_them_claude():
    from deseretbench.build_onepager import cohort_badge
    mco = {"claude-opus-5": {}, "kimi-k3": {}, "qwen3:4b": {}}
    assert cohort_badge(mco) == ("3", "models")
