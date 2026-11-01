"""Counts stated in DATASET_CARD.md that come from the shipped data files."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_card_counts_the_items_whose_options_were_reordered():
    # The card says the options moved in 210 of 213 items, which is why the
    # letters in `notes` are stale. Change the card and this test together.
    meta = json.loads((ROOT / "data/questions_mc.jsonl.balance_meta.json").read_text())
    pm = meta["position_map"]
    moved = sum(r["order"] != sorted(r["order"]) for r in pm.values())
    assert (moved, len(pm)) == (210, 213)
    assert "210 of\nthe 213 multiple-choice items" in (ROOT / "DATASET_CARD.md").read_text()


def test_the_card_counts_match_the_validation_report_and_the_files():
    r = json.loads((ROOT / "data/validation_report.json").read_text())
    card = (ROOT / "DATASET_CARD.md").read_text()
    lines = lambda p: sum(1 for x in (ROOT / p).read_text().splitlines() if x.strip())
    assert r["mc_candidates"] + r["open_candidates"] == 324
    assert "From 324 authored candidates" in card
    assert f"**{r['mc_kept']} / {r['mc_candidates']} MC**" in card
    assert f"**{r['open_kept']} / {r['open_candidates']}\nopen**" in card
    assert f"Of the {r['open_dropped']} dropped open items" in card
    assert (r["mc_public"], r["open_public"]) == (lines("data/questions_mc.jsonl"),
                                                  lines("data/questions_open.jsonl"))
    assert f"| **public** (this dataset) | {r['mc_public']} | {r['open_public']} |" in card
    assert f"| private holdout (withheld) | {r['mc_holdout']} | {r['open_holdout']} |" in card
    assert f"| **kept total** | {r['mc_kept']} | {r['open_kept']} |" in card
