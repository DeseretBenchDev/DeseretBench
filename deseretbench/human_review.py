"""Human review round: build reviewer packets, read them back, report.

The shipped questions were written and reviewed by models. This module is the
path for people to review them, in the same schema and under the same keep
rules the automated panel used (`validate_questions.finalize_mc/_open`), and to
check the judge panel against human scores on stored answers.

It makes no model calls and changes no question file. `export` writes a packet
to send to reviewers and a key the organiser keeps. `ingest` reads the filled
sheets and writes a report; what to do about a failing item stays a decision.

    python -m deseretbench.human_review export --run runs/v0_1_plus --out review_round_1
    python -m deseretbench.human_review ingest review_round_1 --out results/human_review.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

import yaml

from . import judge as judgemod
from . import stats as stx
from .packs import active_pack
from .schema import LETTERS, load_jsonl
from .validate_questions import finalize_mc, finalize_open

ROOT = Path(__file__).resolve().parent.parent

MC_ANSWER_COLS = ["best_answer", "n_defensible_options", "clarity", "flags", "comment"]
OPEN_ANSWER_COLS = ["realistic", "rubric_fair", "clarity", "flags", "comment"]
MC_FLAGS = ("ambiguous", "multiple_correct", "unfair", "factually_wrong", "trivia")
OPEN_FLAGS = ("unrealistic", "rubric_heterodox", "factually_wrong")
JUDGE_COUNT_COLS = ["must_include_hits", "should_not_violations"]
# Targets from DESIGN §6.1: the judge is read at scale only if it tracks the
# human mean at least this well; MC reviewers should agree at least this well.
JUDGE_TARGET = 0.6
MC_KAPPA_TARGET = 0.7

INSTRUCTIONS = """\
# Reviewer instructions

Thank you for reviewing. Fill in the empty columns of each sheet and send the
three files back. Use your own judgement; do not look anything up to find "the
intended answer". There are no trick questions, and you are not being tested.

Put your reviewer id (given to you by the organiser) in the file names, for
example `review_mc.R1.csv`. Leave every other column as it is.

## review_mc.csv: multiple-choice questions

You are not shown which option is keyed as correct.

- `best_answer`: the letter of the option that best states current official
  Church teaching.
- `n_defensible_options`: how many options a well-informed member could
  defend as correct (1 is ideal).
- `clarity`: 1 (confusing) to 5 (perfectly clear).
- `flags`: none, or any of: {mc_flags} (separate several with `;`).
- `comment`: optional.

## review_open.csv: open-ended questions and their scoring guides

- `realistic`: 1 to 5, is this a situation members really face?
- `rubric_fair`: 1 to 5, does the scoring guide reward the right things?
- `clarity`: 1 to 5.
- `flags`: none, or any of: {open_flags}.
- `comment`: optional.

## calibration.csv: answers written by AI models

You are not told which model wrote an answer or how it was scored. Rate each
answer 1 (poor) to 5 (excellent) on: {dims}.
Then count `must_include_hits` (how many of the listed must-include points the
answer covers) and `should_not_violations` (how many of the listed should-not
points it commits).
"""


def _write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _bullets(points) -> str:
    return "\n".join(f"- {p}" for p in points or [])


def response_id(model: str, qid: str, run: int, seed: int) -> str:
    """An id that names a stored answer without revealing the model."""
    return hashlib.sha256(f"{seed}|{model}|{qid}|{run}".encode()).hexdigest()[:12]


def calibration_sample(scores: list[dict], n: int, seed: int) -> list[dict]:
    """Pick `n` scored answers spread evenly over the judge's score range:
    sort by composite, cut into `n` equal bands, draw one from each. A sample
    of only strong or only weak answers could not show whether humans and the
    judge order answers the same way."""
    pool = sorted((r for r in scores if r.get("composite_100") is not None),
                  key=lambda r: (r["composite_100"], r["model"], r["question_id"],
                                 r["run_index"]))
    if n >= len(pool):
        return pool
    rng = random.Random(seed)
    return [rng.choice(pool[i * len(pool) // n:(i + 1) * len(pool) // n])
            for i in range(n)]


def export(run_dir: Path, out: Path, n_calibration: int, seed: int,
           mc_items: list[dict], open_items: list[dict]) -> dict:
    """Write the packet (to send) and the organiser's key (to keep)."""
    packet = out / "packet"
    width = max(len(it["choices"]) for it in mc_items)
    letters = list(LETTERS[:width])
    mc_rows = [{"question_id": it["question_id"], "question": it["question"],
                **{L: (it["choices"][i] if i < len(it["choices"]) else "")
                   for i, L in enumerate(letters)}}
               for it in mc_items]   # no answer_index: reviewers are blind to the key
    _write_csv(packet / "review_mc.csv",
               ["question_id", "question", *letters, *MC_ANSWER_COLS], mc_rows)

    open_rows = [{"question_id": it["question_id"], "prompt": it["prompt"],
                  "must_include": _bullets(it["rubric"].get("must_include")),
                  "should_not": _bullets(it["rubric"].get("should_not"))}
                 for it in open_items]
    _write_csv(packet / "review_open.csv",
               ["question_id", "prompt", "must_include", "should_not", *OPEN_ANSWER_COLS],
               open_rows)

    dims = list(active_pack().judge_dimensions)
    by_qid = {it["question_id"]: it for it in open_items}
    key, cal_rows = {}, []
    scores_path, resp_path = run_dir / "open_scores.jsonl", run_dir / "open_responses.jsonl"
    if n_calibration and scores_path.exists() and resp_path.exists():
        texts = {(r["model"], r["question_id"], r["run_index"]): r.get("text") or ""
                 for r in load_jsonl(resp_path)}
        scores = [r for r in load_jsonl(scores_path)
                  if r["question_id"] in by_qid
                  and texts.get((r["model"], r["question_id"], r["run_index"]))]
        for r in calibration_sample(scores, n_calibration, seed):
            rid = response_id(r["model"], r["question_id"], r["run_index"], seed)
            it = by_qid[r["question_id"]]
            key[rid] = {"model": r["model"], "question_id": r["question_id"],
                        "run_index": r["run_index"],
                        "judge_composite_100": r["composite_100"]}
            cal_rows.append({
                "response_id": rid, "prompt": it["prompt"],
                "must_include": _bullets(it["rubric"].get("must_include")),
                "should_not": _bullets(it["rubric"].get("should_not")),
                "answer": texts[(r["model"], r["question_id"], r["run_index"])]})
        random.Random(seed).shuffle(cal_rows)   # not in score order
    _write_csv(packet / "calibration.csv",
               ["response_id", "prompt", "must_include", "should_not", "answer",
                *dims, *JUDGE_COUNT_COLS, "comment"], cal_rows)
    (packet / "INSTRUCTIONS.md").write_text(INSTRUCTIONS.format(
        mc_flags=", ".join(MC_FLAGS), open_flags=", ".join(OPEN_FLAGS),
        dims=", ".join(d.replace("_", " ") for d in dims)), encoding="utf-8")
    (out / "organiser").mkdir(parents=True, exist_ok=True)
    (out / "organiser" / "calibration_key.json").write_text(
        json.dumps({"seed": seed, "run": str(run_dir), "responses": key}, indent=1) + "\n")
    return {"mc": len(mc_rows), "open": len(open_rows), "calibration": len(cal_rows)}


# --------------------------------------------------------------------------- #
# ingest
# --------------------------------------------------------------------------- #


def _int(v, lo=None, hi=None):
    try:
        n = int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None
    if (lo is not None and n < lo) or (hi is not None and n > hi):
        return None
    return n


def _flags(v) -> list[str]:
    out = [f.strip().lower().replace(" ", "_") for f in str(v or "").replace(",", ";").split(";")]
    return [f for f in out if f] or ["none"]


def _reviewer_files(folder: Path, stem: str) -> dict[str, Path]:
    """{reviewer id: path} for files named `<stem>.<reviewer>.csv`."""
    found = {}
    for p in sorted(folder.glob(f"{stem}.*.csv")):
        rid = p.name[len(stem) + 1:-len(".csv")]
        if rid:
            found[rid] = p
    return found


def read_reviews(folder: Path) -> dict:
    """Filled sheets -> review records in the automated panel's own schema,
    with the reviewer id where the persona name goes."""
    mc, op, cal = [], [], defaultdict(dict)
    for rid, path in _reviewer_files(folder, "review_mc").items():
        for row in _read_csv(path):
            la = str(row.get("best_answer", "")).strip().upper()[:1]
            if not la:
                continue    # an unanswered row is no review, not a wrong one
            mc.append({"question_id": row["question_id"], "persona": rid,
                       "source": "human", "parse_ok": True,
                       "review": {"best_answer": la,
                                  "n_defensible_options": _int(row.get("n_defensible_options"), 0),
                                  "clarity": _int(row.get("clarity"), 1, 5),
                                  "flags": _flags(row.get("flags")),
                                  "comment": row.get("comment", "")}})
    for rid, path in _reviewer_files(folder, "review_open").items():
        for row in _read_csv(path):
            realistic = _int(row.get("realistic"), 1, 5)
            if realistic is None:
                continue
            op.append({"question_id": row["question_id"], "persona": rid,
                       "source": "human", "parse_ok": True,
                       "review": {"realistic": realistic,
                                  "rubric_fair": _int(row.get("rubric_fair"), 1, 5),
                                  "clarity": _int(row.get("clarity"), 1, 5),
                                  "flags": _flags(row.get("flags")),
                                  "comment": row.get("comment", "")}})
    dims = list(active_pack().judge_dimensions)
    for rid, path in _reviewer_files(folder, "calibration").items():
        for row in _read_csv(path):
            vals = {d: _int(row.get(d), 1, 5) for d in dims}
            if all(v is None for v in vals.values()):
                continue
            vals["must_include_hits"] = _int(row.get("must_include_hits"), 0)
            vals["should_not_violations"] = _int(row.get("should_not_violations"), 0)
            cal[row["response_id"]][rid] = vals
    return {"mc": mc, "open": op, "calibration": dict(cal)}


def _by_item(recs: list[dict]) -> dict:
    out = defaultdict(dict)
    for r in recs:
        out[r["question_id"]][r["persona"]] = r["review"]
    return out


def report(reviews: dict, mc_items: list[dict], open_items: list[dict],
           key: dict) -> dict:
    """Apply the automated panel's keep rules to the human reviews and compare
    the judge with the human mean on the calibration answers."""
    out = {"targets": {"mc_fleiss_kappa": MC_KAPPA_TARGET, "judge_vs_human": JUDGE_TARGET}}
    mc_items = [dict(it) for it in mc_items]      # finalize_* annotate in place
    open_items = [dict(it) for it in open_items]
    reviewers = sorted({r["persona"] for r in reviews["mc"] + reviews["open"]}
                       | {rid for v in reviews["calibration"].values() for rid in v})
    out["reviewers"] = reviewers

    if reviews["mc"]:
        kept, dropped, kappa = finalize_mc(mc_items, _by_item(reviews["mc"]))
        unrev = [it for it in dropped if it["_review"].get("unreviewed")]
        failed = [it for it in dropped if not it["_review"].get("unreviewed")]
        out["mc"] = {
            "n_items": len(mc_items), "n_kept": len(kept), "n_failed": len(failed),
            "n_unreviewed": len(unrev), "fleiss_kappa": kappa,
            "meets_kappa_target": (kappa is not None and kappa >= MC_KAPPA_TARGET),
            "mean_key_agreement": round(sum(
                it["_review"]["key_agreement"] for it in kept + failed)
                / max(1, len(kept) + len(failed)), 3),
            "failed": [{"question_id": it["question_id"], **it["_review"]} for it in failed]}
    if reviews["open"]:
        kept, dropped = finalize_open(open_items, _by_item(reviews["open"]))
        unrev = [it for it in dropped if it["_review"].get("unreviewed")]
        failed = [it for it in dropped if not it["_review"].get("unreviewed")]
        out["open"] = {
            "n_items": len(open_items), "n_kept": len(kept), "n_failed": len(failed),
            "n_unreviewed": len(unrev),
            "failed": [{"question_id": it["question_id"], **it["_review"]} for it in failed]}
    if reviews["calibration"]:
        human, judge, rows = [], [], []
        for rid, by_reviewer in sorted(reviews["calibration"].items()):
            if rid not in key:
                continue      # a row the organiser's key does not know is not scored
            # the same aggregation the judge panel uses, over human raters
            agg = judgemod.aggregate_panel(list(by_reviewer.values()))
            if agg["composite_100"] is None:
                continue
            human.append(agg["composite_100"])
            judge.append(key[rid]["judge_composite_100"])
            rows.append({"response_id": rid, "n_reviewers": len(by_reviewer),
                         "human_composite_100": round(agg["composite_100"], 2),
                         "judge_composite_100": round(key[rid]["judge_composite_100"], 2)})
        rho = stx.spearman(human, judge)
        alpha = (stx.krippendorff_alpha_interval([human, judge])
                 if len(human) >= 2 else None)
        out["calibration"] = {
            "n_responses": len(rows), "spearman_rho": rho,
            "krippendorff_alpha_human_vs_judge": alpha,
            "mean_human_minus_judge": (round(sum(h - j for h, j in zip(human, judge))
                                             / len(human), 2) if human else None),
            "meets_judge_target": (rho is not None and rho >= JUDGE_TARGET),
            "responses": rows}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="write the reviewer packet and the organiser's key")
    e.add_argument("--run", required=True, help="neutral run dir to draw stored answers from")
    e.add_argument("--out", required=True, help="new folder for this review round")
    e.add_argument("--calibration", type=int, default=40,
                   help="number of stored answers for reviewers to score (default 40)")
    i = sub.add_parser("ingest", help="read filled sheets and write the report")
    i.add_argument("folder", help="the review round folder; filled sheets go in "
                                  "<folder>/returned/ as <sheet>.<reviewer>.csv")
    i.add_argument("--out", default="", help="default <pack.results_dir>/human_review.json")
    a = ap.parse_args()

    pack = active_pack()
    seed = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())["stats"]["rng_seed"]
    mc_items = load_jsonl(ROOT / pack.data_dir / "questions_mc.jsonl")
    open_items = load_jsonl(ROOT / pack.data_dir / "questions_open.jsonl")
    if a.cmd == "export":
        out = Path(a.out)
        if out.exists() and any(out.iterdir()):
            raise SystemExit(f"error: {out} is not empty; a review round gets a new folder")
        n = export(Path(a.run), out, a.calibration, seed, mc_items, open_items)
        print(f"wrote {out}/packet ({n['mc']} MC, {n['open']} open-ended, "
              f"{n['calibration']} answers to score) and {out}/organiser (keep this)")
        return
    folder = Path(a.folder)
    reviews = read_reviews(folder / "returned")
    if not (reviews["mc"] or reviews["open"] or reviews["calibration"]):
        raise SystemExit(f"error: no filled sheets in {folder / 'returned'}")
    key = json.loads((folder / "organiser" / "calibration_key.json").read_text())["responses"]
    rep = report(reviews, mc_items, open_items, key)
    out = ROOT / (a.out or f"{pack.results_dir}/human_review.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}: reviewers {rep['reviewers']}")


if __name__ == "__main__":
    main()
