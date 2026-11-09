"""The home page (`index.html`) is hand-maintained HTML, not a generated report.

Its standings table therefore drifts whenever `results/summary.json` is
regenerated and the page is not touched: the November 2026 cohort was folded
into every generated report while the page still showed thirty models. These
tests pin the table and the cohort count to the summary, so that drift fails
the suite. Prose on the page is not checked here.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_ROW = re.compile(r'<tr><td class="rk">(.*?)</td><td class="mdl">(.*?)</td>')


def _summary():
    s = json.loads((ROOT / "results" / "summary.json").read_text())
    return s["mc"]["overall"], s["open"]["overall"]


def _page():
    return (ROOT / "index.html").read_text(encoding="utf-8")


def _rows():
    """label -> (rank cell, [numbers in <b>], whether the open cell is pending)."""
    rows = {}
    for line in _page().splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        label = re.sub(r"\s*<sup>.*?</sup>", "", m.group(2)).strip()
        assert label not in rows, f"model listed twice on the home page: {label}"
        rows[label] = (m.group(1), re.findall(r"<b>([\d.]+)</b>", line),
                       "in progress" in line)
    return rows


def test_home_page_lists_exactly_the_scored_cohort():
    mc, _ = _summary()
    rows = _rows()
    assert set(rows) == {o["label"] for o in mc.values()}
    assert f"<dd>{len(mc)} models</dd>" in _page()


def test_home_page_scores_and_ranks_match_the_summary():
    mc, op = _summary()
    rows = _rows()
    rank = {m: i + 1 for i, m in
            enumerate(sorted(op, key=lambda m: -op[m]["mean"]))}
    for m, o in mc.items():
        rk, nums, pending = rows[o["label"]]
        if m in op:
            assert not pending, o["label"]
            assert rk == str(rank[m]), (o["label"], rk, rank[m])
            assert nums == [f"{op[m]['mean']:.1f}", f"{o['mean']:.3f}"], o["label"]
        else:
            assert pending, f"{o['label']} has no open score but is not marked pending"
            assert rk == "&ndash;", o["label"]
            assert nums == [f"{o['mean']:.3f}"], o["label"]
