"""List pairs of questions that may ask the same thing in other words.

`assemble` drops exact duplicates by content hash, so a reworded copy of a
question survives it. In the v0.1 multiple-choice set at least 8 such groups
were found by hand (DATASET_CARD.md). This lists candidate pairs by word
overlap, for a person to judge. It changes nothing and makes no model calls.

    python -m deseretbench.near_duplicates data/questions_mc.jsonl [--min 0.45]
"""
from __future__ import annotations

import argparse
import itertools
import re

from .schema import load_jsonl

# Words every item shares, which would make unrelated items look alike.
STOP = frozenset("""a an the of to in and or is are be by for on with as that this which
what how why when who it its his her their from at was were has have not no does do
church latter day saints jesus christ""".split())


def words(text: str) -> frozenset:
    return frozenset(w for w in re.findall(r"[a-z0-9']+", text.lower())
                     if w not in STOP and len(w) > 2)


def item_words(item: dict) -> frozenset:
    """An MC item is its question plus its keyed answer; an open item its prompt.
    The keyed answer matters: two stems can differ while the tested fact is one."""
    if "choices" in item:
        return words(item["question"] + " " + item["choices"][item["answer_index"]])
    return words(item["prompt"])


def jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def candidate_pairs(items: list[dict], min_score: float = 0.45) -> list[tuple]:
    """(score, id_a, id_b) for every pair at or above `min_score`, highest first."""
    w = {it["question_id"]: item_words(it) for it in items}
    pairs = ((round(jaccard(w[a], w[b]), 3), a, b) for a, b in itertools.combinations(w, 2))
    return sorted((p for p in pairs if p[0] >= min_score), key=lambda p: (-p[0], p[1], p[2]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("questions")
    ap.add_argument("--min", type=float, default=0.45,
                    help="lowest word-overlap score to list (0-1, default 0.45)")
    a = ap.parse_args()
    items = load_jsonl(a.questions)
    by_id = {it["question_id"]: it for it in items}
    pairs = candidate_pairs(items, a.min)
    for s, x, y in pairs:
        print(f"{s:.2f}  {x}\n      {by_id[x].get('question') or by_id[x]['prompt']}\n"
              f"      {y}\n      {by_id[y].get('question') or by_id[y]['prompt']}\n")
    print(f"{len(pairs)} pair(s) at or above {a.min} among {len(items)} items. "
          "Word overlap is a lead, not a verdict: judge each pair by hand.")


if __name__ == "__main__":
    main()
