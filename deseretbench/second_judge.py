"""Score stored open-ended answers with a second judge family, and compare.

Every open-ended score comes from one judge model family. Its three personas agree
closely, but that is one family agreeing with itself. This module re-judges answers
already stored in a run, with the same personas, prompt and rubric, on a judge from
another family, and reports how far the two judges agree: answer by answer, and on
the model ranking the standings print.

It never regenerates an answer and never writes into the run it reads, so the
standings stay the primary judge's. Its outputs live in their own directory.

    python -m deseretbench.second_judge run --run runs/v0_1_plus --out runs/second_judge \
        [--judge-model ID --backend B] [--models a,b] [--fraction F]
    python -m deseretbench.second_judge compare --run runs/v0_1_plus --second runs/second_judge
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import yaml

from . import judge as judgemod
from . import stats as stx
from .runner import Runner
from .run_benchmark import JsonlSink, pick_crosscheck_keys, select_cohort
from .packs import active_pack
from .schema import load_jsonl

ROOT = Path(__file__).resolve().parent.parent

RAW = "second_judge_raw.jsonl"
SCORES = "second_scores.jsonl"
SNAPSHOT = "second_judge_snapshot.json"


def family(model_id: str) -> str:
    """The lab family a model id belongs to, by its first name part:
    `claude-sonnet-4-6` -> claude, `kimi-k3` -> kimi, `glm-5.3` -> glm."""
    return re.split(r"[-:/._ ]", model_id.strip().lower(), maxsplit=1)[0]


def judge_settings(models_cfg: dict, judge_model: str = "", backend: str = "") -> dict:
    """The second judge, from the command line or `judges.second` in models.yaml.
    Refused before any call when it is missing or of the primary judge's family:
    a second judge from the same lab measures nothing this module is for."""
    j = models_cfg["judges"]
    cfg = dict(j.get("second") or {})
    if judge_model:
        # a judge named on the command line carries only what is named with it
        cfg = {"model": judge_model, "backend": backend or None, "backend_opts": None}
    if not cfg.get("model"):
        raise SystemExit("error: no second judge: pass --judge-model, or set "
                         "judges.second.model in configs/models.yaml")
    primary = j["primary_model"]
    if family(cfg["model"]) == family(primary):
        raise SystemExit(f"error: {cfg['model']} is the same family as the primary "
                         f"judge {primary}; a second judge must come from another lab")
    return cfg


def _neutral(recs: list[dict], path) -> list[dict]:
    other = sorted({r["condition"] for r in recs if r.get("condition", "neutral") != "neutral"})
    if other:
        raise SystemExit(f"error: {path} holds {other} records; the second judge "
                         "scores neutral runs only")
    return recs


def plan(run_dir: Path, items: list[dict], cohort_ids: set | None,
         fraction: float, seed: int) -> list[tuple]:
    """(model, item, run_index, text) for every stored answer the primary panel
    scored, optionally limited to some models and a seeded fraction. Answers the
    primary panel did not score cannot be compared, so they are not bought."""
    by_qid = {it["question_id"]: it for it in items}
    scored = {(r["model"], r["question_id"], r["run_index"])
              for r in _neutral(load_jsonl(run_dir / "open_scores.jsonl"),
                                run_dir / "open_scores.jsonl")
              if r.get("composite_100") is not None}
    texts = {}
    for r in _neutral(load_jsonl(run_dir / "open_responses.jsonl"),
                      run_dir / "open_responses.jsonl"):
        k = (r["model"], r["question_id"], r["run_index"])
        if r.get("text") and k in scored and r["question_id"] in by_qid and \
                (cohort_ids is None or r["model"] in cohort_ids):
            texts[k] = r["text"]
    keys = sorted(texts)
    if fraction < 1.0:
        keys = sorted(pick_crosscheck_keys(keys, fraction, seed))
    return [(m, by_qid[q], r, texts[(m, q, r)]) for m, q, r in keys]


def run(run_dir: Path, out: Path, judge: dict, personas: list[str], effort: str,
        runner, todo: list[tuple]) -> dict:
    """Judge every planned answer under every persona; write raw verdicts and
    per-answer panel scores in the run phase's own formats."""
    if out.resolve() == run_dir.resolve():
        raise SystemExit("error: --out must not be the run directory; the standings "
                         "keep the primary judge's scores")
    jobs, metas = [], []
    for m, it, r, text in todo:
        for persona in personas:
            jobs.append({"model": judge["model"], "system": judgemod.JUDGE_SYSTEM,
                         "prompt": judgemod.build_judge_prompt(it, text, persona),
                         "effort": effort, "run_index": 0,
                         "backend": judge.get("backend"),
                         "backend_opts": judge.get("backend_opts")})
            metas.append((m, it, r, persona))
    results = runner.map(jobs)
    raw = JsonlSink(out / RAW)
    panel = {}
    n_failed = n_unparsed = 0
    for (m, it, r, persona), jr in zip(metas, results):
        parsed = judgemod.parse_judge_json(jr.text) if jr.ok else None
        n_failed += not jr.ok
        n_unparsed += bool(jr.ok and parsed is None)
        raw.write({"model": m, "question_id": it["question_id"], "run_index": r,
                   "persona": persona, "judge_model": judge["model"],
                   "judge_role": "second", "call_ok": jr.ok,
                   "parse_ok": parsed is not None, "judge_served": jr.model_served,
                   "error": jr.error, "called_at": jr.called_at, "scores": parsed})
        panel.setdefault((m, it["question_id"], r), []).append(parsed)
    raw.close()
    scores = JsonlSink(out / SCORES)
    for (m, q, r), verdicts in sorted(panel.items()):
        agg = judgemod.aggregate_panel(verdicts)
        scores.write({"model": m, "question_id": q, "run_index": r,
                      "judge_model": judge["model"],
                      "composite_100": agg["composite_100"],
                      "dim_means": agg["dim_means"], "n_judges": agg["n_judges"]})
    scores.close()
    summary = {"run": str(run_dir), "judge": judge, "personas": personas,
               "effort": effort, "n_answers": len(todo), "n_calls": len(jobs),
               "n_failed": n_failed, "n_unparsed": n_unparsed}
    (out / SNAPSHOT).write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def _per_item(scores: dict, model: str, keys: set) -> dict:
    g = defaultdict(list)
    for (m, q, r) in keys:
        if m == model:
            g[q].append(scores[(m, q, r)])
    return {q: sum(v) / len(v) for q, v in g.items()}


def compare(run_dir: Path, second_dir: Path, labels: dict, seed: int,
            n_boot: int, ci: float) -> dict:
    """Agreement between the primary panel and the second judge on the answers
    both scored: per answer, per model, and on the model ranking."""
    prim = {(r["model"], r["question_id"], r["run_index"]): r["composite_100"]
            for r in _neutral(load_jsonl(run_dir / "open_scores.jsonl"),
                              run_dir / "open_scores.jsonl")
            if r.get("composite_100") is not None}
    sec = {(r["model"], r["question_id"], r["run_index"]): r["composite_100"]
           for r in load_jsonl(second_dir / SCORES) if r.get("composite_100") is not None}
    keys = set(prim) & set(sec)
    if not keys:
        raise SystemExit("error: no answer was scored by both judges")
    ks = sorted(keys)
    a, b = [prim[k] for k in ks], [sec[k] for k in ks]
    out = {"answers": {
        "n": len(ks), "spearman_rho": stx.spearman(a, b),
        "krippendorff_alpha": stx.krippendorff_alpha_interval([a, b]),
        "mean_second_minus_primary": round(sum(y - x for x, y in zip(a, b)) / len(ks), 2)}}
    models = sorted({k[0] for k in ks})
    rows = {}
    for m in models:
        pa, sa = _per_item(prim, m, keys), _per_item(sec, m, keys)
        qs = sorted(pa)
        d = stx.paired_bootstrap_diff([sa[q] for q in qs], [pa[q] for q in qs], n_boot,
                                      stx.derive_seed(seed, "second-judge", m), ci)
        rows[m] = {"label": labels.get(m, m),
                   "primary": round(sum(pa.values()) / len(pa), 2),
                   "second": round(sum(sa.values()) / len(sa), 2),
                   "diff": d["diff"], "lo": d["lo"], "hi": d["hi"], "p": d["p"],
                   "n_items": len(qs)}
    for m, p in zip(models, stx.holm_bonferroni([rows[m]["p"] for m in models])):
        rows[m]["p_holm"] = p
        rows[m]["significant_holm"] = bool(p < (1 - ci))
    prim_rank = sorted(models, key=lambda m: -rows[m]["primary"])
    sec_rank = sorted(models, key=lambda m: -rows[m]["second"])
    for i, m in enumerate(prim_rank, 1):
        rows[m]["rank_primary"] = i
        rows[m]["rank_second"] = sec_rank.index(m) + 1
    pairs = [(x, y) for i, x in enumerate(models) for y in models[i + 1:]]
    flips = [(x, y) for x, y in pairs
             if (rows[x]["primary"] - rows[y]["primary"])
             * (rows[x]["second"] - rows[y]["second"]) < 0]
    out["models"] = rows
    out["ranking"] = {
        "n_models": len(models),
        "spearman_rho": stx.spearman([rows[m]["primary"] for m in models],
                                     [rows[m]["second"] for m in models]),
        "n_pairs": len(pairs), "n_pairs_reordered": len(flips),
        "pairs_reordered": [[labels.get(x, x), labels.get(y, y)] for x, y in flips]}
    return out


def _f(v, spec):
    return "–" if v is None else format(v, spec)


def render(res: dict, meta: dict) -> str:
    A, R = res["answers"], res["ranking"]
    L = [f"# {active_pack().report_title}: a second judge family\n",
         f"_Primary judge `{meta['primary']}` · second judge `{meta['second']}` · "
         f"same personas, prompt and rubric · {meta['n_boot']:,} bootstrap resamples · "
         f"seed {meta['seed']}_\n",
         "A separate measurement. The standings keep the primary judge's scores.\n",
         "## Answer by answer\n",
         f"- Answers scored by both judges: {A['n']:,}",
         f"- Rank agreement (Spearman ρ): {_f(A['spearman_rho'], '.3f')}",
         f"- Agreement on the score itself (Krippendorff's α, interval): "
         f"{_f(A['krippendorff_alpha'], '.3f')}",
         f"- Second judge minus primary, mean: {A['mean_second_minus_primary']:+.2f} "
         "composite points\n",
         "## The ranking\n",
         f"- Rank agreement over {R['n_models']} models (Spearman ρ): "
         f"{_f(R['spearman_rho'], '.3f')}",
         f"- Pairs of models whose order the second judge reverses: "
         f"{R['n_pairs_reordered']} of {R['n_pairs']}\n",
         "| Model | Primary | Second | Difference | 95% CI | Holm p | Rank (primary → second) |",
         "|---|---|---|---|---|---|---|"]
    for m, r in sorted(res["models"].items(), key=lambda kv: kv[1]["rank_primary"]):
        star = " \\*" if r["significant_holm"] else ""
        L.append(f"| {r['label']} | {r['primary']:.1f} | {r['second']:.1f} | "
                 f"{r['diff']:+.1f}{star} | [{r['lo']:+.1f}, {r['hi']:+.1f}] | "
                 f"{r['p_holm']:.4f} | {r['rank_primary']} → {r['rank_second']} |")
    L.append("\n_\\* the two judges differ significantly on this model after Holm "
             "correction across models._\n")
    if R["pairs_reordered"]:
        L.append("Reordered pairs: " + "; ".join(f"{x} / {y}" for x, y in R["pairs_reordered"]) + "\n")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="judge stored answers with the second judge (model calls)")
    r.add_argument("--run", required=True, help="neutral run dir holding the stored answers")
    r.add_argument("--out", required=True, help="new dir for the second judge's records")
    r.add_argument("--judge-model", default="")
    r.add_argument("--backend", default="", help="runner backend for the judge model")
    r.add_argument("--models", default="", help="only these scored models")
    r.add_argument("--fraction", type=float, default=1.0,
                   help="seeded share of answers to judge (default all)")
    r.add_argument("--max-parallel", type=int, default=0)
    c = sub.add_parser("compare", help="agreement report (no model calls)")
    c.add_argument("--run", required=True)
    c.add_argument("--second", required=True)
    c.add_argument("--out", default="", help="default <pack.results_dir>/judge_agreement.json")
    c.add_argument("--report", default="", help="default <pack.reports_dir>/JUDGE_AGREEMENT.md")
    a = ap.parse_args()

    run_cfg = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())
    models = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text())
    st = run_cfg["stats"]
    seed, n_boot, ci = st["rng_seed"], st["bootstrap_resamples"], st["ci_level"]
    pack = active_pack()
    if a.cmd == "run":
        if not 0 < a.fraction <= 1:
            raise SystemExit("error: --fraction must be in (0, 1]")
        judge = judge_settings(models, a.judge_model, a.backend)
        ids = {m["id"] for m in select_cohort(models, a.models)} if a.models else None
        items = load_jsonl(ROOT / pack.data_dir / "questions_open.jsonl")
        todo = plan(Path(a.run), items, ids, a.fraction, seed)
        if not todo:
            raise SystemExit("error: no stored, scored answer matches; nothing to judge")
        rc = dict(run_cfg["runner"])
        if a.max_parallel:
            rc["max_parallel"] = a.max_parallel
        runner = Runner({"runner": rc}, cache_dir=ROOT / rc.get("cache_dir", "cache"))
        personas = models["judges"]["personas"]
        print(f"[second judge] {len(todo)} answers x {len(personas)} personas on "
              f"{judge['model']}", flush=True)
        s = run(Path(a.run), Path(a.out), judge, personas,
                run_cfg["effort"].get("judge", "medium"), runner, todo)
        print(f"[second judge] {s['n_calls']} calls, {s['n_failed']} failed, "
              f"{s['n_unparsed']} unparsed; wrote {a.out}")
        return
    labels = {m["id"]: m["label"] for m in models["cohort"]}
    res = compare(Path(a.run), Path(a.second), labels, seed, n_boot, ci)
    snap = json.loads((Path(a.second) / SNAPSHOT).read_text())
    meta = {"primary": models["judges"]["primary_model"], "second": snap["judge"]["model"],
            "seed": seed, "n_boot": n_boot, "run": a.run, "second_dir": a.second}
    out = ROOT / (a.out or f"{pack.results_dir}/judge_agreement.json")
    rep = ROOT / (a.report or f"{pack.reports_dir}/JUDGE_AGREEMENT.md")
    out.write_text(json.dumps({"meta": meta, **res}, indent=1, ensure_ascii=False) + "\n")
    rep.write_text(render(res, meta))
    print(f"wrote {out} and {rep}")


if __name__ == "__main__":
    main()
