"""Randomize the position of the correct answer in every MC item, with a fixed
seed, so the key carries no positional information.

v0.1 authoring left a skewed key distribution (e.g. correct == 'B' ~51% of the
time). That does not invalidate a saturated (≈100%) result — a position-biased
guesser would score at the key frequency, not 100% — but it makes the shipped
instrument unfair to weaker models a position-biased reader could game. We
therefore permute each item's `choices` and the parallel `distractor_types`
together, draw the correct slot uniformly at random per item (seeded), and keep
`question_id` stable (the item is the same question, only reordered).

Usage:
  python -m deseretbench.balance_positions \
      --in data/questions_mc.jsonl --out data/questions_mc.jsonl --seed 19470417
The original is backed up to <out>.prebalance.jsonl on first run.
"""
from __future__ import annotations

import argparse
import json
import os
import random
from collections import Counter
from pathlib import Path

from .schema import load_jsonl, dump_jsonl, validate_mc_item, LETTERS


def balance(items: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for it in items:
        choices = list(it["choices"])
        has_dtypes = "distractor_types" in it
        if has_dtypes and not isinstance(it["distractor_types"], list):
            raise ValueError(f"item {it.get('question_id')}: distractor_types is "
                             f"{it['distractor_types']!r}, expected a list or absent")
        dtypes = list(it["distractor_types"]) if has_dtypes else [None] * len(choices)
        if len(dtypes) != len(choices):
            raise ValueError(f"item {it.get('question_id')}: distractor_types "
                             f"length {len(dtypes)} != choices {len(choices)}")
        ai = it["answer_index"]
        n = len(choices)
        correct_choice = choices[ai]
        correct_dtype = dtypes[ai]
        # distractors are shuffled too (their original order could itself
        # carry information), then the correct slot is drawn uniformly
        distractors = [(c, d) for i, (c, d) in enumerate(zip(choices, dtypes)) if i != ai]
        rng.shuffle(distractors)
        target = rng.randrange(n)  # uniform slot for the correct answer
        new_choices = [None] * n
        new_dtypes = [None] * n
        new_choices[target] = correct_choice
        new_dtypes[target] = correct_dtype
        di = 0
        for slot in range(n):
            if slot == target:
                continue
            new_choices[slot], new_dtypes[slot] = distractors[di]
            di += 1
        nit = dict(it)
        nit["choices"] = new_choices
        if has_dtypes:
            nit["distractor_types"] = new_dtypes
        nit["answer_index"] = target
        out.append(nit)
    return out


def make_position_map(old_items: list[dict], new_items: list[dict]) -> dict:
    """question_id -> {order, answer_from, answer_to}.

    `order[k]` is the OLD index of the choice now sitting at NEW slot k, so
    pre-balance artifacts (e.g. reviewer letters in reviews_mc.jsonl) remain
    interpretable against the shipped, reordered set.
    """
    pm = {}
    for old, new in zip(old_items, new_items):
        order = [old["choices"].index(c) for c in new["choices"]]
        pm[old["question_id"]] = {"order": order,
                                  "answer_from": old["answer_index"],
                                  "answer_to": new["answer_index"]}
    return pm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--seed", type=int, default=19470417)
    ap.add_argument("--force", action="store_true",
                    help="re-balance even though a balance marker exists")
    args = ap.parse_args()

    meta_path = Path(args.out + ".balance_meta.json")
    bak = Path(args.out).with_suffix(".prebalance.jsonl")
    if not args.force:
        if meta_path.exists():
            raise SystemExit(
                f"error: {meta_path} exists — this set was already balanced "
                f"(the permutation is not idempotent; re-balancing would silently "
                f"diverge from the published run). Use --force only after re-authoring.")
        if bak.exists():
            raise SystemExit(
                f"error: {bak} exists, which means {args.out} was already balanced "
                f"(even though no balance marker is present). Use --force only "
                f"after re-authoring.")

    items = load_jsonl(args.inp)
    before = Counter(LETTERS[it["answer_index"]] for it in items)

    if bak.exists() and args.force:
        # --force means the input is a NEW set; a stale backup would silently
        # disagree with the meta we are about to write. Rotate it aside.
        rotated = bak.with_suffix(".prebalance.1.jsonl")
        os.replace(bak, rotated)
        print(f"rotated stale backup -> {rotated}")
    dump_jsonl(items, bak)
    print(f"backed up original -> {bak}")

    balanced = balance(items, args.seed)
    bad = [(it.get("question_id"), errs) for it in balanced
           if (errs := validate_mc_item(it))]
    if bad:
        raise SystemExit(f"error: balancing produced schema-invalid items: {bad[:5]}")
    after = Counter(LETTERS[it["answer_index"]] for it in balanced)
    dump_jsonl(balanced, args.out)
    meta_path.write_text(json.dumps(
        {"seed": args.seed, "n_items": len(balanced),
         "position_map": make_position_map(items, balanced)},
        ensure_ascii=False, indent=1))
    print(f"wrote {len(balanced)} items -> {args.out} (seed={args.seed})")
    print(f"wrote balance marker + position map -> {meta_path}")
    print("key position BEFORE:", dict(sorted(before.items())))
    print("key position AFTER :", dict(sorted(after.items())))


if __name__ == "__main__":
    main()
