"""Runner-based question authoring (pure-Python, 8-wide, reproducible).

One high-effort completion per (dimension, difficulty, batch) cell. The model
returns a JSON array of items, which we validate and write to data/raw/<cell>.jsonl.
Cells whose file already exists with enough valid items are skipped, so this
complements any items authored by the multi-agent workflow.

  python -m deseretbench.author --max-parallel 8 [--force] [--model claude-opus-4-8]
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import yaml

from .runner import Runner
from .schema import validate_item
from .packs import active_pack

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# The tradition surface — grounding brief, stance, distractor guide, rules, the
# authoring taxonomy (MC_DIMS / OPEN_CELLS), and the two prompt builders — comes
# from the active faith pack (deseretbench.packs). AXIS_OF is the pack's
# dimension->axis map. Bound at import because authoring runs one pack per
# process; select a tradition with DESERETBENCH_PACK or run_config `pack:`.
_PACK = active_pack()
MC_DIMS = _PACK.mc_dims
OPEN_CELLS = _PACK.open_cells
AXIS_OF = _PACK.axis_for_dimension


def split_counts(target: int) -> dict:
    a = math.ceil(target * 1.3)
    basic = round(a * 0.30)
    inter = round(a * 0.40)
    adv = round(a * 0.20)
    expert = max(2, a - basic - inter - adv)
    return {"basic": basic, "intermediate": inter, "advanced": adv, "expert": expert}


def batches(n: int, size: int = 9):
    out, i, rem = [], 0, n
    while rem > 0:
        c = min(size, rem)
        out.append((i, c))
        rem -= c
        i += 1
    return out


def build_cells():
    cells = []
    for key, target, desc, subs in MC_DIMS:
        counts = split_counts(target)
        for diff in ("basic", "intermediate", "advanced", "expert"):
            for idx, c in batches(counts[diff]):
                rot = subs[idx % len(subs):] + subs[: idx % len(subs)]
                cells.append({"kind": "mc", "dim": key, "desc": desc, "axis": AXIS_OF[key],
                              "diff": diff, "count": c, "subs": rot,
                              "path": RAW / f"mc_{key}_{diff}_b{idx}.jsonl"})
    for i, (dim, diff, count, theme) in enumerate(OPEN_CELLS):
        axis = "life_choice_alignment" if dim == "life_choice" else "cultural_fluency"
        cells.append({"kind": "open", "dim": dim, "axis": axis, "diff": diff, "count": count,
                      "theme": theme, "path": RAW / f"open_{dim}_b{i}.jsonl"})
    return cells


def mc_prompt(c):
    return active_pack().mc_authoring_prompt(c)


def open_prompt(c):
    return active_pack().open_authoring_prompt(c)


def extract_array(text: str):
    """Pull the outermost JSON array from a response."""
    if not text:
        return None
    text = re.sub(r"```[a-zA-Z]*", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        # tolerant: parse object-by-object
        objs, depth, buf = [], 0, ""
        for ch in text[start + 1:end]:
            buf += ch
            depth += (ch == "{") - (ch == "}")
            if depth == 0 and buf.strip().endswith("}"):
                try:
                    objs.append(json.loads(buf[buf.find("{"):]))
                except json.JSONDecodeError:
                    pass
                buf = ""
        return objs or None


def existing_ok(path: Path, expected: int) -> bool:
    if not path.exists():
        return False
    good = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            if not validate_item(json.loads(line)):
                good += 1
        except json.JSONDecodeError:
            pass
    return good >= max(1, math.ceil(0.7 * expected))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-parallel", type=int, default=8)
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    p = active_pack()
    if (p.mc_dims is None or p.open_cells is None or p.mc_authoring_prompt is None
            or not p.grounding):
        raise SystemExit(
            f"faith pack {p.key!r} has no authoring taxonomy — fill mc_dims, "
            f"open_cells, grounding, and the authoring prompts in its pack.py "
            f"before authoring a fresh question set "
            f"(see docs/how-to/add-a-faith-pack.md).")

    cells = build_cells()
    todo = [c for c in cells if args.force or not existing_ok(c["path"], c["count"])]
    skipped = len(cells) - len(todo)
    print(f"authoring: {len(cells)} cells, {skipped} already complete, {len(todo)} to author "
          f"(model={args.model}, effort={args.effort}, parallel={args.max_parallel})")

    # Honor configs/run_config.yaml (backend, retries, CLI flags); authoring
    # outputs are long, so keep at least a 300s timeout.
    run_cfg = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())
    rc = dict(run_cfg.get("runner") or {})
    rc["max_parallel"] = args.max_parallel
    rc["timeout_seconds"] = max(300, int(rc.get("timeout_seconds", 300)))
    runner = Runner({"runner": rc}, cache_dir=ROOT / "cache")
    sysp = "You are an expert author of assessment items. Output only what is requested."
    jobs, metas = [], []
    for c in todo:
        prompt = mc_prompt(c) if c["kind"] == "mc" else open_prompt(c)
        jobs.append({"model": args.model, "system": sysp, "prompt": prompt,
                     "effort": args.effort, "run_index": 0})
        metas.append(c)

    written_total = 0
    done = [0]

    def on_done(i, job, res):
        c = metas[i]
        arr = extract_array(res.text) if res.ok else None
        kept = []
        if arr:
            for it in arr:
                if not isinstance(it, dict):
                    continue
                it.setdefault("format", "mc" if c["kind"] == "mc" else "open")
                it.setdefault("axis", c["axis"])
                it.setdefault("dimension", c["dim"])
                it.setdefault("difficulty", c["diff"])
                if not validate_item(it):
                    kept.append(it)
        if kept:
            with open(c["path"], "w", encoding="utf-8") as f:
                for it in kept:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
        done[0] += 1
        nonlocal written_total
        written_total += len(kept)
        print(f"  [{done[0]}/{len(todo)}] {c['path'].name}: {len(kept)} valid "
              f"(asked {c['count']}){'  <EMPTY/parse-fail>' if not kept else ''}", flush=True)

    runner.map(jobs, on_done=on_done)
    print(f"done. authored {written_total} new valid items across {len(todo)} cells. "
          f"live spend ${runner.total_spend_usd:.2f}")


if __name__ == "__main__":
    main()
