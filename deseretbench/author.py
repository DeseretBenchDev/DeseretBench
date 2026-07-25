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

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

GROUNDING = (ROOT / "data" / "grounding_brief.md").read_text(encoding="utf-8")

STANCE = """DeseretBench rewards accurate representation of the MAINSTREAM, OFFICIAL, CORRELATED
position of The Church of Jesus Christ of Latter-day Saints (canon, the General Handbook, and
current First Presidency / Quorum of the Twelve teaching), while acknowledging where genuine
doctrinal ambiguity exists. Key answers to the official position. Folk doctrine, heterodox
("Sunstone") readings, and anti-Mormon framings appear ONLY as distractors."""

DISTRACTORS = """DISTRACTOR TYPES (label each choice in distractor_types; the correct choice = "correct"):
- protestant_trap: correct in mainstream Christianity, wrong in LDS theology (grace-alone, Nicene Trinity, ex nihilo)
- folk_doctrine_trap: commonly believed by members but not official (e.g. "Kolob is where God lives")
- anti_mormon_trap: factual-sounding but hostile/CES-Letter spin
- progressive_trap: heterodox/"Sunstone" answer not reflecting the mainstream position
- correlation_oversimplification: too-simple Sunday-School answer vs. the real nuance
- plausible_near_miss: close-but-wrong technical detail (date, name, sequence)"""

RULES = """RULES:
- Test UNDERSTANDING, not photographic trivia. Separate models that grasp LDS thought from
  those pattern-matching Christian keywords. No "which section header" trivia.
- Distractors must be plausible and discriminative; use at least TWO distinct trap types per item.
- Exactly one defensibly-correct answer keyed to official sources. For genuinely unsettled matters,
  the correct answer correctly reports it as unsettled/non-canonical.
- Vary subtopics; do NOT duplicate well-worn examples; avoid near-duplicate stems.
- 'source' cites official/authoritative material; 'notes' explains the trap logic + why it tests understanding."""

MC_EXAMPLE = '{"format":"mc","axis":"doctrinal_accuracy","dimension":"doctrine_scripture","difficulty":"basic","question":"...","choices":["...","...","...","..."],"answer_index":1,"distractor_types":["protestant_trap","correct","folk_doctrine_trap","plausible_near_miss"],"source":"D&C 130:22","notes":"..."}'
OPEN_EXAMPLE = '{"format":"open","axis":"life_choice_alignment","dimension":"life_choice","difficulty":"advanced","prompt":"...","rubric":{"must_include":["...","..."],"should_not":["...","..."],"ideal_reasoning_pattern":"..."}}'

DIFF_DESC = {
    "basic": "Seminary level — any active member should know it.",
    "intermediate": "Institute/mission level — real doctrinal literacy required.",
    "advanced": "BYU Religion faculty level — doctrinal development, historical context, nuance.",
    "expert": "Roberts/Nibley/Givens level — synthesis across domains; unsettled questions.",
}

AXIS_OF = {
    "doctrine_scripture": "doctrinal_accuracy", "ordinances_covenants": "doctrinal_accuracy",
    "church_organization": "doctrinal_accuracy", "eternal_family": "doctrinal_accuracy",
    "restoration_history": "doctrinal_accuracy", "living_gospel": "doctrinal_accuracy",
    "cultural_fluency": "cultural_fluency",
}

MC_DIMS = [
    ("doctrine_scripture", 45, "Plan of Salvation, the Godhead, the Restoration, and the standard works.",
     ["nature of God/Godhead", "premortal life & intelligences", "degrees of glory & judgment", "Fall & Atonement",
      "Book of Mormon doctrine", "D&C revelations", "Moses/Abraham (PoGP)", "grace & works/soteriology",
      "agency & the plan", "apostasy & Restoration"]),
    ("ordinances_covenants", 30, "Temple ordinances, baptism, the sacrament, priesthood, and work for the dead.",
     ["baptism & confirmation", "the sacrament", "endowment & sealing", "work for the dead",
      "Aaronic vs Melchizedek priesthood", "keys vs office", "covenant theology", "temple recommend worthiness"]),
    ("church_organization", 22, "Prophetic authority and keys, ward/stake structure, callings, councils, correlation.",
     ["prophetic authority & keys", "succession in the presidency", "ward vs stake", "quorums & auxiliaries",
      "callings & sustaining", "common consent", "correlation", "church councils"]),
    ("eternal_family", 25, "Sealing, the Family Proclamation, marriage and family roles, family history.",
     ["eternal marriage & sealing", "The Family: A Proclamation", "gender & family roles", "family history & temple work",
      "exaltation & eternal increase", "children & sealing", "singles without temple marriage"]),
    ("restoration_history", 30, "Joseph Smith, the Restoration, succession, plural marriage, Missouri/Nauvoo, pioneers, OD-1/OD-2.",
     ["First Vision & accounts", "coming forth of the Book of Mormon", "priesthood restoration",
      "Kirtland/Missouri/Nauvoo", "martyrdom & succession 1844", "plural marriage & the Manifesto",
      "pioneer trek & colonization", "1978 priesthood revelation"]),
    ("living_gospel", 28, "Word of Wisdom, Sabbath, tithing & offerings, missionary work, self-reliance, ministering.",
     ["Word of Wisdom (incl. 2019 clarifications)", "Sabbath & sacrament meeting", "tithing & fast offerings",
      "missionary work & ministering", "self-reliance & welfare", "personal revelation & study",
      "repentance & worthiness", "Come Follow Me / home-centered learning"]),
    ("cultural_fluency", 25, "Mission culture, BYU life, ward dynamics, dating norms, temple-recommend practice, vernacular.",
     ["mission culture & vernacular (RM, greenie, trunky, transfers, P-day)", "BYU life & Honor Code",
      "ward dynamics & callings in practice", "dating/courtship & 'ring by spring'",
      "how a bishop is called & sustained", "'I prayed about it' in decisions", "temple recommend in practice",
      "convert integration", "youth programs & seminary"]),
]

OPEN_CELLS = [
    ("life_choice", "intermediate", 8, "career vs. family, Sabbath/Word-of-Wisdom pressure at work, education vs. mission/marriage timing"),
    ("life_choice", "advanced", 8, "faith crisis & doubt, a child/sibling who leaves the Church, ministering to the disaffected"),
    ("life_choice", "advanced", 8, "mixed-faith marriage & interfaith dating, marrying a non-member, raising children in mixed-faith homes"),
    ("life_choice", "advanced", 8, "LGBTQ family members (a gay teenager, a child who comes out, love+belonging alongside doctrine), singles/midsingle life"),
    ("life_choice", "expert", 6, "demanding callings vs. family/health, financial strain vs. tithing, ethically gray business, end-of-life/medical ethics"),
    ("cultural_open", "intermediate", 7, "spirit vs. letter of the law (Sabbath, Word of Wisdom), being the only member at a work dinner, ward social dynamics"),
    ("cultural_open", "advanced", 7, "mission-culture nuance, how 'I prayed about it' functions, convert integration, bishop-interview dynamics, weight of a temple recommend"),
    ("cultural_open", "expert", 5, "subtle insider/outsider distinctions, where cultural practice diverges from doctrine, generational shifts in LDS culture"),
]


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
    return f"""You are a Latter-day Saint doctrine and culture expert authoring multiple-choice items for DeseretBench, a research benchmark.
{STANCE}

{GROUNDING}

{DISTRACTORS}

{RULES}

TASK: Author EXACTLY {c['count']} multiple-choice items.
  dimension: {c['dim']} — {c['desc']}
  axis: {c['axis']}
  difficulty: {c['diff']} — {DIFF_DESC[c['diff']]}
  emphasize (rotate across, vary, no duplicates): {'; '.join(c['subs'])}

Each item is a JSON object with EXACTLY these keys (example):
{MC_EXAMPLE}
4 choices (5 allowed for advanced/expert). distractor_types length == choices length, exactly one "correct" at answer_index, >= 2 distinct trap types.

OUTPUT: Respond with ONLY a JSON array of the {c['count']} item objects. No prose, no markdown fences."""


def open_prompt(c):
    return f"""You are a Latter-day Saint life-counsel and culture expert authoring OPEN-ENDED, judge-scored scenario items for DeseretBench.
{STANCE}

{GROUNDING}

{RULES}

TASK: Author EXACTLY {c['count']} open-ended scenario items.
  dimension: {c['dim']}
  axis: {c['axis']}
  difficulty: {c['diff']} — {DIFF_DESC[c['diff']]}
  themes (vary across them): {c['theme']}

Real, hard life situations with no catechism answer but a recognizably Latter-day Saint reasoning
pattern distinct from secular and from generic-Protestant advice. Each item is a JSON object with
EXACTLY these keys (example):
{OPEN_EXAMPLE}
rubric.must_include: 4-6 substantive points a faithful, thoughtful Latter-day Saint answer must engage.
rubric.should_not: 3-5 failure modes/wrong defaults. rubric.ideal_reasoning_pattern: the LDS reasoning arc.
Be compassionate and realistic, reflecting actual mainstream pastoral practice (e.g. for LGBTQ scenarios,
love and belonging alongside doctrine on the law of chastity and temple marriage).

OUTPUT: Respond with ONLY a JSON array of the {c['count']} item objects. No prose, no markdown fences."""


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
