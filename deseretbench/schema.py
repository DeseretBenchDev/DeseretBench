"""Item schema, validation, deterministic IDs, and JSONL I/O for DeseretBench."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from .packs import active_pack

# Tradition-agnostic constants stay here. The tradition-specific taxonomy —
# axes, MC/open dimensions, distractor types, and the dimension->axis map —
# lives in the active faith pack (deseretbench.packs) and is resolved at
# validation time, so the same process can validate items against more than one
# tradition by passing an explicit `pack=`.
DIFFICULTIES = {"basic", "intermediate", "advanced", "expert"}

LETTERS = "ABCDEFGH"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def content_hash_id(item: dict) -> str:
    """Deterministic short id from semantic content.

    Stable across authoring reruns of the SAME content. Note: position
    balancing reorders `choices` while keeping the original question_id (the
    item is the same question), so ids on the shipped balanced set do NOT
    recompute from current content — they are provenance ids, not checksums.
    """
    if item.get("format") == "mc":
        basis = item["question"] + "||" + "|".join(item["choices"])
    else:
        basis = item["prompt"]
    h = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:10]
    return f"{item['dimension']}_{item['difficulty']}_{h}"


def validate_mc_item(d: dict, *, pack=None) -> list[str]:
    p = pack or active_pack()
    errs: list[str] = []
    if d.get("format") != "mc":
        errs.append("format must be 'mc'")
    if d.get("axis") not in p.axes:
        errs.append(f"bad axis: {d.get('axis')}")
    if d.get("dimension") not in p.mc_dimensions:
        errs.append(f"bad mc dimension: {d.get('dimension')}")
    if d.get("difficulty") not in DIFFICULTIES:
        errs.append(f"bad difficulty: {d.get('difficulty')}")
    q = d.get("question", "")
    if not isinstance(q, str) or len(q.strip()) < 10:
        errs.append("question too short/missing")
    ch = d.get("choices")
    if not isinstance(ch, list) or not (3 <= len(ch) <= 6):
        errs.append("choices must be a list of 3-6 options")
    else:
        if any((not isinstance(c, str) or not c.strip()) for c in ch):
            errs.append("empty choice present")
        if len(set(c.strip().lower() for c in ch)) != len(ch):
            errs.append("duplicate choices")
        ai = d.get("answer_index")
        if not isinstance(ai, int) or not (0 <= ai < len(ch)):
            errs.append("answer_index out of range")
        dt = d.get("distractor_types")
        if dt is not None:
            if not isinstance(dt, list) or len(dt) != len(ch):
                errs.append("distractor_types length must match choices")
            elif any(t not in p.distractor_types for t in dt):
                errs.append(f"bad distractor_type in {dt}")
            else:
                # exactly one 'correct', and it must sit at the key —
                # balance_positions and per-trap analysis both assume this
                n_correct = dt.count("correct")
                if n_correct != 1:
                    errs.append(f"distractor_types must contain exactly one "
                                f"'correct' (found {n_correct})")
                elif isinstance(ai, int) and 0 <= ai < len(dt) and dt[ai] != "correct":
                    errs.append("'correct' distractor_type is not at answer_index")
    if not d.get("source"):
        errs.append("missing source")
    _check_axis(d, errs, p)
    return errs


def _check_axis(d: dict, errs: list[str], p):
    dim, axis = d.get("dimension"), d.get("axis")
    want = p.axis_for_dimension.get(dim)
    if want and axis != want:
        errs.append(f"axis '{axis}' inconsistent with dimension '{dim}' "
                    f"(expected '{want}')")


def validate_open_item(d: dict, *, pack=None) -> list[str]:
    p = pack or active_pack()
    errs: list[str] = []
    if d.get("format") != "open":
        errs.append("format must be 'open'")
    if d.get("axis") not in p.axes:
        errs.append(f"bad axis: {d.get('axis')}")
    if d.get("dimension") not in p.open_dimensions:
        errs.append(f"bad open dimension: {d.get('dimension')}")
    if d.get("difficulty") not in DIFFICULTIES:
        errs.append(f"bad difficulty: {d.get('difficulty')}")
    if not isinstance(d.get("prompt", ""), str) or len(d.get("prompt", "").strip()) < 20:
        errs.append("prompt too short/missing")
    r = d.get("rubric")
    if not isinstance(r, dict):
        errs.append("rubric missing")
    else:
        for k in ("must_include", "should_not"):
            if not isinstance(r.get(k), list) or not r.get(k):
                errs.append(f"rubric.{k} missing/empty")
        if not isinstance(r.get("ideal_reasoning_pattern", ""), str) or not r.get("ideal_reasoning_pattern"):
            errs.append("rubric.ideal_reasoning_pattern missing")
    _check_axis(d, errs, p)
    return errs


def validate_item(d: dict, *, pack=None) -> list[str]:
    if d.get("format") == "mc":
        return validate_mc_item(d, pack=pack)
    if d.get("format") == "open":
        return validate_open_item(d, pack=pack)
    return [f"unknown format: {d.get('format')}"]


def load_jsonl(path: str | Path) -> list[dict]:
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def dump_jsonl(items: Iterable[dict], path: str | Path) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
            n += 1
    return n
