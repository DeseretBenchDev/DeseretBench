"""Regenerate the question explorer's data from a run + summary.

reports/explorer.html is a hand-built page shell; this rewrites only its
inlined `<script id="data">` payload and version line, and writes the
lazy-loaded answer texts to reports/explorer_texts.json.

    python -m deseretbench.build_explorer --run runs/v0_1_plus
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LETTERS = "ABCDEFGH"


def build_data(models, mc_questions, open_questions, mc_records, open_scores,
               open_responses, summary):
    mc_mean = {m: v["mean"] for m, v in summary["mc"]["overall"].items()}
    op_mean = {m: v["mean"] for m, v in (summary.get("open") or {}).get("overall", {}).items()}
    cohort = [m for m in models if m["id"] in mc_mean]
    with_open = sorted((m for m in cohort if m["id"] in op_mean),
                       key=lambda m: -op_mean[m["id"]])
    ordered = with_open + [m for m in cohort if m["id"] not in op_mean]
    frontier = sorted(m["id"] for m in cohort if mc_mean[m["id"]] == 1.0)

    picks = defaultdict(list)                      # qid -> [(model, letter, correct)]
    for r in mc_records:
        if r.get("call_ok") and r.get("parsed_letter"):
            picks[r["question_id"]].append((r["model"], r["parsed_letter"], bool(r["correct"])))

    mc_items = []
    for q in mc_questions:
        qid, got = q["question_id"], picks[q["question_id"]]
        dist = [0] * len(q["choices"])
        per = defaultdict(list)
        for model, letter, ok in got:
            i = LETTERS.find(letter)
            if 0 <= i < len(dist):
                dist[i] += 1
            per[model].append(ok)
        missed = {m: round(sum(v) / len(v), 2) for m, v in per.items() if not all(v)}
        mc_items.append({
            "id": qid, "track": "mc", "dim": q["dimension"], "diff": q["difficulty"],
            "axis": q["axis"], "q": q["question"], "choices": q["choices"],
            "dt": q.get("distractor_types", []), "ans": q["answer_index"],
            "src": q.get("source", ""), "notes": q.get("notes", ""), "dist": dist,
            "n": len(got), "p": round(sum(ok for *_, ok in got) / len(got), 3) if got else 0,
            "missed": missed, "fmiss": any(m in frontier for m in missed)})

    scores = defaultdict(lambda: defaultdict(dict))    # qid -> model -> run -> rec
    for r in open_scores:
        scores[r["question_id"]][r["model"]][r["run_index"]] = r
    text = {(r["question_id"], r["model"], r["run_index"]): r.get("text", "")
            for r in open_responses if r.get("call_ok")}

    open_items, texts = [], {}
    for q in open_questions:
        qid, per_model = q["question_id"], {}
        for m in with_open:
            runs = scores[qid].get(m["id"])
            if not runs:
                continue
            first = min(runs)
            r = runs[first]
            per_model[m["id"]] = {
                "comp": r["composite_100"],
                "mean": round(sum(x["composite_100"] for x in runs.values()) / len(runs), 1),
                "run": first,
                "dims": {k: round(v, 1) for k, v in r["dim_means"].items()},
                "cov": r.get("must_include_coverage")}
            t = text.get((qid, m["id"], first))
            if t is not None:
                texts.setdefault(qid, {})[m["id"]] = t
        means = [v["mean"] for v in per_model.values()]
        open_items.append({
            "id": qid, "track": "open", "dim": q["dimension"], "diff": q["difficulty"],
            "axis": q["axis"], "prompt": q["prompt"], "rubric": q.get("rubric", {}),
            "cavg": round(sum(means) / len(means), 1) if means else None,
            "models": per_model})

    data = {"models": [{"id": m["id"], "label": m["label"], "tier": m["tier"],
                        "comp": round(op_mean[m["id"]], 1) if m["id"] in op_mean else None}
                       for m in ordered],
            "frontier": frontier, "mc": mc_items, "open": open_items,
            "meta": {"n_mc": len(mc_items), "n_open": len(open_items),
                     "n_models": len(ordered)}}
    return data, texts


def _jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--summary", default="results/summary.json")
    ap.add_argument("--page", default="reports/explorer.html")
    ap.add_argument("--label", default=None,
                    help="version text for the page heading, e.g. 'v0.1 + Oct 2026'")
    a = ap.parse_args()
    run = ROOT / a.run
    data, texts = build_data(
        models=yaml.safe_load((ROOT / "configs/models.yaml").read_text())["cohort"],
        mc_questions=_jsonl(ROOT / "data/questions_mc.jsonl"),
        open_questions=_jsonl(ROOT / "data/questions_open.jsonl"),
        mc_records=_jsonl(run / "mc_responses.jsonl"),
        open_scores=_jsonl(run / "open_scores.jsonl"),
        open_responses=_jsonl(run / "open_responses.jsonl"),
        summary=json.loads((ROOT / a.summary).read_text()))
    page = ROOT / a.page
    html = page.read_text()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html, n = re.subn(r'(<script id="data" type="application/json">).*?(</script>)',
                      lambda m: m.group(1) + payload + m.group(2), html, count=1, flags=re.S)
    assert n == 1, "explorer page has no data block"
    if a.label:
        html = re.sub(r"(<small>DeseretBench )[^<]*?( · \d+ MC \+ \d+ open</small>)",
                      lambda m: f"{m.group(1)}{a.label}{m.group(2)}", html, count=1)
    page.write_text(html)
    (page.parent / "explorer_texts.json").write_text(
        json.dumps(texts, ensure_ascii=False, separators=(",", ":")))
    m = data["meta"]
    print(f"wrote {page} ({m['n_models']} models, {m['n_mc']} MC + {m['n_open']} open)")


if __name__ == "__main__":
    main()
