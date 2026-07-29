"""Assemble raw authored cells into a deduplicated, validated candidate pool.

raw (data/raw/*.jsonl) -> data/candidates_mc.jsonl + data/candidates_open.jsonl

Tolerant to stray markdown fences / blank lines in agent-written files. Drops
schema-invalid items (logged). Deduplicates by content hash and normalized stem.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

from .schema import validate_item, content_hash_id  # noqa
from . import schema as _schema
from .packs import active_pack

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / active_pack().data_dir   # data/ for LDS, data/<key> otherwise
RAW = DATA / "raw"


def _tolerant_lines(path: Path):
    """Yield candidate JSON objects from a file that should be JSONL but might
    contain code fences or pretty-printed blocks."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"```[a-zA-Z]*", "", text)  # strip code fences
    # Fast path: line-by-line.
    objs, buf, depth = [], "", 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if depth == 0:
            try:
                objs.append(json.loads(s))
                continue
            except json.JSONDecodeError:
                pass
        # accumulate across lines for pretty-printed objects
        buf += line + "\n"
        depth += line.count("{") - line.count("}")
        if depth <= 0 and buf.strip():
            try:
                objs.append(json.loads(buf))
            except json.JSONDecodeError:
                pass
            buf, depth = "", 0
    return objs


def _norm_stem(item: dict) -> str:
    s = item.get("question") or item.get("prompt") or ""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()[:160]


def assemble() -> dict:
    files = sorted(glob.glob(str(RAW / "*.jsonl")))
    raw_items, n_lines = [], 0
    for f in files:
        for obj in _tolerant_lines(Path(f)):
            n_lines += 1
            raw_items.append((f, obj))

    seen_hash, seen_stem = set(), set()
    mc, open_, dropped = [], [], []
    for src, it in raw_items:
        errs = validate_item(it)
        if errs:
            dropped.append((src, errs, _norm_stem(it)[:60]))
            continue
        it["question_id"] = content_hash_id(it)
        stem = _norm_stem(it)
        if it["question_id"] in seen_hash or stem in seen_stem:
            dropped.append((src, ["duplicate"], stem[:60]))
            continue
        seen_hash.add(it["question_id"])
        seen_stem.add(stem)
        (mc if it["format"] == "mc" else open_).append(it)

    _schema.dump_jsonl(mc, DATA / "candidates_mc.jsonl")
    _schema.dump_jsonl(open_, DATA / "candidates_open.jsonl")

    # breakdowns
    def breakdown(items):
        b = {}
        for it in items:
            k = (it["dimension"], it["difficulty"])
            b[k] = b.get(k, 0) + 1
        return b

    return {
        "files": len(files), "raw_lines": n_lines,
        "mc": len(mc), "open": len(open_), "dropped": len(dropped),
        "mc_breakdown": breakdown(mc), "open_breakdown": breakdown(open_),
        "dropped_detail": dropped[:40],
    }


if __name__ == "__main__":
    rep = assemble()
    print(f"files={rep['files']} raw_lines={rep['raw_lines']} "
          f"-> MC={rep['mc']} OPEN={rep['open']} dropped={rep['dropped']}")
    print("\nMC by (dimension, difficulty):")
    for k in sorted(rep["mc_breakdown"]):
        print(f"  {k[0]:22s} {k[1]:12s} {rep['mc_breakdown'][k]}")
    print("\nOPEN by (dimension, difficulty):")
    for k in sorted(rep["open_breakdown"]):
        print(f"  {k[0]:22s} {k[1]:12s} {rep['open_breakdown'][k]}")
    if rep["dropped_detail"]:
        print("\nSample dropped:")
        for src, errs, stem in rep["dropped_detail"][:15]:
            print(f"  {Path(src).name}: {errs} :: {stem}")
