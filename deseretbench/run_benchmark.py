"""DeseretBench orchestrator.

Builds jobs (model x item x repeat-run), drives the cached Runner, scores MC
inline, and runs the open-ended generate -> judge-panel pipeline. Writes
per-call records to runs/<name>/ as JSONL. Resumable: the Runner cache means a
re-run only fills gaps.

Usage:
  python -m deseretbench.run_benchmark mc   --questions data/questions_mc.jsonl   --out runs/v0_1
  python -m deseretbench.run_benchmark open --questions data/questions_open.jsonl --out runs/v0_1
Options: --models a,b  --runs N  --limit K  --max-parallel P
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
from pathlib import Path

import yaml
from jinja2 import Template

from .runner import Runner
from .schema import LETTERS, load_jsonl
from .score_mc import is_correct
from . import judge as judgemod
from .packs import active_pack

ROOT = Path(__file__).resolve().parent.parent


def load_configs():
    run_cfg = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())
    models = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text())
    return run_cfg, models


def render_mc(item: dict, template: str) -> str:
    lettered = list(zip(LETTERS, item["choices"]))
    return Template(template).render(question=item["question"], lettered_choices=lettered)


def render_open(item: dict, template: str) -> str:
    return Template(template).render(prompt=item["prompt"])


class JsonlSink:
    """Atomic JSONL writer: records go to <path>.tmp and replace <path> only on
    close(). A crash or interrupted wave leaves the previous complete file
    intact instead of a truncated one (re-runs rebuild from the call cache)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._tmp = self.path.with_name(self.path.name + ".tmp")
        self._fh = open(self._tmp, "w", encoding="utf-8")
        self._lock = threading.Lock()
        self.n = 0

    def write(self, rec: dict):
        with self._lock:
            self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._fh.flush()
            self.n += 1

    def close(self):
        self._fh.close()
        os.replace(self._tmp, self.path)


def select_cohort(models: dict, requested: str) -> list[dict]:
    """Filter the cohort by a comma-separated id list; a typo'd or unknown id
    is a hard error (an empty cohort would silently produce an empty run)."""
    cohort = models["cohort"]
    if not requested:
        return cohort
    known = {m["id"] for m in cohort}
    wanted = [s.strip() for s in requested.split(",") if s.strip()]
    unknown = [w for w in wanted if w not in known]
    if unknown or not wanted:
        raise SystemExit(
            f"error: unknown model id(s) {unknown or requested!r} — "
            f"valid cohort ids: {sorted(known)}")
    return [m for m in cohort if m["id"] in wanted]


def pick_crosscheck_keys(keys: list, fraction: float, seed: int) -> list:
    """Deterministic, seeded subsample of (model, question_id, run) keys for
    the cross-check judge (judge-model sensitivity analysis)."""
    n = round(len(keys) * fraction)
    rng = random.Random(seed)
    return sorted(rng.sample(sorted(keys), n))


def write_config_snapshot(out: Path, phase: str, run_cfg: dict, cohort: list[dict],
                          extra: dict | None = None):
    """Record the exact config a phase ran under, inside the run directory, so
    analyze reports true provenance instead of whatever the config file says
    at analysis time."""
    import time as _time
    path = Path(out) / "config_snapshot.json"
    snap = {}
    if path.exists():
        try:
            snap = json.loads(path.read_text())
        except json.JSONDecodeError:
            snap = {}
    snap[phase] = {
        "written_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "pack": active_pack().key,
        "cohort": [m["id"] for m in cohort],
        "run_config": run_cfg,
        **(extra or {}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, ensure_ascii=False, indent=1))


# --------------------------------------------------------------------------- #
# MC
# --------------------------------------------------------------------------- #


def run_mc(args):
    run_cfg, models = load_configs()
    rc = dict(run_cfg["runner"])
    if args.max_parallel:
        rc["max_parallel"] = args.max_parallel
    runner = Runner({"runner": rc}, cache_dir=ROOT / rc.get("cache_dir", "cache"))

    items = load_jsonl(args.questions)
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit(f"error: no items loaded from {args.questions}")
    cohort = select_cohort(models, args.models)
    n_runs = args.runs or run_cfg["runs"]["multiple_choice"]
    effort = run_cfg["effort"]["multiple_choice"]
    system = run_cfg["system_prompt"]
    template = run_cfg["mc_prompt_template"]

    jobs, metas = [], []
    for m in cohort:
        for it in items:
            prompt = render_mc(it, template)
            for r in range(n_runs):
                jobs.append({"model": m["id"], "system": system, "prompt": prompt,
                             "effort": effort, "run_index": r,
                             "backend": m.get("backend")})
                metas.append((m, it, r))
    if not jobs:
        raise SystemExit("error: zero jobs built — refusing to touch output files")

    out = Path(args.out)
    sink = JsonlSink(out / "mc_responses.jsonl")
    print(f"[MC] {len(cohort)} models x {len(items)} items x {n_runs} runs "
          f"= {len(jobs)} calls | effort={effort} parallel={rc.get('max_parallel')}")

    done = [0]
    lock = threading.Lock()

    def on_done(i, job, res):
        m, it, r = metas[i]
        correct, letter = (False, None)
        if res.ok:
            correct, letter = is_correct(res.text, it["answer_index"], it["choices"])
        sink.write({
            "format": "mc", "model": m["id"], "tier": m["tier"], "label": m["label"],
            "question_id": it["question_id"], "dimension": it["dimension"],
            "difficulty": it["difficulty"], "axis": it["axis"], "run_index": r,
            "model_served": res.model_served, "served_all": res.served_all,
            "provider_model": res.provider_model,
            "call_ok": res.ok, "stop_reason": res.stop_reason,
            "called_at": res.called_at,
            "answer_index": it["answer_index"], "parsed_letter": letter,
            "correct": bool(correct), "parse_ok": letter is not None,
            "cost_usd": res.cost_usd, "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens, "duration_ms": res.duration_ms,
            "attempts": res.attempts, "cache_hit": res.cache_hit, "error": res.error,
            "text": res.text,
        })
        with lock:
            done[0] += 1
            if done[0] % 50 == 0 or done[0] == len(jobs):
                print(f"  ... {done[0]}/{len(jobs)} (${runner.total_spend_usd:.2f} live)",
                      flush=True)

    runner.map(jobs, on_done=on_done)
    sink.close()
    # snapshot AFTER the phase commits, so provenance never describes a run
    # whose outputs were interrupted before landing
    write_config_snapshot(out, "mc", run_cfg, cohort,
                          {"n_items": len(items), "n_runs": n_runs})
    print(f"[MC] wrote {sink.n} records to {sink.path} | live spend ${runner.total_spend_usd:.2f}")
    _quick_mc_summary(sink.path, cohort)


def _quick_mc_summary(path: Path, cohort):
    recs = load_jsonl(path)
    print("\n[MC] quick accuracy (over completed calls; transport failures excluded):")
    for m in cohort:
        rows = [r for r in recs if r["model"] == m["id"]]
        if not rows:
            continue
        ok = [r for r in rows if r.get("call_ok", True)]
        n_failed = len(rows) - len(ok)
        acc = sum(r["correct"] for r in ok) / len(ok) if ok else float("nan")
        pf = sum(not r["parse_ok"] for r in ok) / len(ok) if ok else float("nan")
        extra = f"  CALL_FAILURES={n_failed}" if n_failed else ""
        print(f"  {m['label']:12s} acc={acc:.3f}  parse_fail={pf:.3f}  n={len(ok)}{extra}")


# --------------------------------------------------------------------------- #
# OPEN (generate -> judge)
# --------------------------------------------------------------------------- #


def run_open(args):
    run_cfg, models = load_configs()
    rc = dict(run_cfg["runner"])
    if args.max_parallel:
        rc["max_parallel"] = args.max_parallel
    runner = Runner({"runner": rc}, cache_dir=ROOT / rc.get("cache_dir", "cache"))

    items = load_jsonl(args.questions)
    if args.limit:
        items = items[: args.limit]
    if not items:
        raise SystemExit(f"error: no items loaded from {args.questions}")
    cohort = select_cohort(models, args.models)
    n_runs = args.runs or run_cfg["runs"]["open_ended"]
    gen_effort = run_cfg["effort"]["open_ended"]
    system = run_cfg["system_prompt"]
    template = run_cfg["open_prompt_template"]
    jcfg = models["judges"]
    personas = jcfg["personas"]
    judge_model = jcfg["primary_model"]
    # validate crosscheck config BEFORE spending anything, not after judging
    if getattr(args, "judge_crosscheck", False) and not jcfg.get("crosscheck_model"):
        raise SystemExit("error: --judge-crosscheck set but models.yaml has "
                         "no judges.crosscheck_model")

    out = Path(args.out)

    # ---- Phase 1: generate responses ----
    gjobs, gmetas = [], []
    for m in cohort:
        for it in items:
            prompt = render_open(it, template)
            for r in range(n_runs):
                gjobs.append({"model": m["id"], "system": system, "prompt": prompt,
                              "effort": gen_effort, "run_index": r,
                              "backend": m.get("backend")})
                gmetas.append((m, it, r))
    print(f"[OPEN gen] {len(cohort)}x{len(items)}x{n_runs} = {len(gjobs)} responses "
          f"| effort={gen_effort}", flush=True)
    gdone = [0]
    glock = threading.Lock()

    def gen_progress(i, job, res):
        with glock:
            gdone[0] += 1
            if gdone[0] % 25 == 0 or gdone[0] == len(gjobs):
                print(f"  [gen] {gdone[0]}/{len(gjobs)} (${runner.total_spend_usd:.2f} live)",
                      flush=True)
    gresults = runner.map(gjobs, on_done=gen_progress)
    responses = []  # (m, it, r, text)
    for (m, it, r), res in zip(gmetas, gresults):
        responses.append((m, it, r, res.text if res.ok else "", res))
    gen_sink = JsonlSink(out / "open_responses.jsonl")
    for m, it, r, text, res in responses:
        gen_sink.write({"model": m["id"], "tier": m["tier"], "label": m["label"],
                        "question_id": it["question_id"], "dimension": it["dimension"],
                        "difficulty": it["difficulty"], "run_index": r,
                        "call_ok": res.ok, "model_served": res.model_served,
                        "served_all": res.served_all, "provider_model": res.provider_model,
                        "stop_reason": res.stop_reason,
                        "called_at": res.called_at, "error": res.error,
                        "attempts": res.attempts, "cache_hit": res.cache_hit,
                        "text": text, "cost_usd": res.cost_usd,
                        "input_tokens": res.input_tokens,
                        "output_tokens": res.output_tokens})
    gen_sink.close()
    n_gen_failed = sum(1 for *_x, res in responses if not res.ok)
    print(f"[OPEN gen] wrote {gen_sink.n} responses")
    if n_gen_failed:
        print(f"[OPEN gen] WARNING: {n_gen_failed} generation(s) FAILED and will "
              f"receive no judge scores — per-model n will shrink accordingly; "
              f"re-run this phase to retry them before analyzing.", flush=True)

    # ---- Phase 2: judge panel ----
    jeffort = run_cfg["effort"].get("judge", "medium")
    jjobs, jmetas = [], []
    for m, it, r, text, res in responses:
        if not text:
            continue
        for persona in personas:
            jp = judgemod.build_judge_prompt(it, text, persona)
            jjobs.append({"model": judge_model, "system": judgemod.JUDGE_SYSTEM,
                          "prompt": jp, "effort": jeffort,
                          "run_index": 0})
            jmetas.append((m, it, r, persona))
    print(f"[OPEN judge] {len(jjobs)} judge calls on {judge_model} "
          f"({len(personas)} personas)", flush=True)
    jdone = [0]
    jlock = threading.Lock()

    def judge_progress(i, job, res):
        with jlock:
            jdone[0] += 1
            if jdone[0] % 50 == 0 or jdone[0] == len(jjobs):
                print(f"  [judge] {jdone[0]}/{len(jjobs)} (${runner.total_spend_usd:.2f} live)",
                      flush=True)
    jresults = runner.map(jjobs, on_done=judge_progress)

    # collect per (model,item,run) -> {persona: parsed}
    panel = {}
    judge_sink = JsonlSink(out / "open_judge_raw.jsonl")
    n_parse_failed = 0
    for (m, it, r, persona), jr in zip(jmetas, jresults):
        parsed = judgemod.parse_judge_json(jr.text) if jr.ok else None
        if jr.ok and parsed is None:
            n_parse_failed += 1
        # served/served_all/error are the attribution evidence: without them a
        # rejected verdict has to be reproduced live to learn why it failed
        # (ADR-0012).
        judge_sink.write({"model": m["id"], "question_id": it["question_id"],
                          "run_index": r, "persona": persona,
                          "judge_model": judge_model, "judge_role": "primary",
                          "call_ok": jr.ok, "parse_ok": parsed is not None,
                          "judge_served": jr.model_served,
                          "judge_served_all": jr.served_all, "error": jr.error,
                          "called_at": jr.called_at, "scores": parsed})
        panel.setdefault((m["id"], it["question_id"], r), {"meta": (m, it, r), "judges": {}})
        panel[(m["id"], it["question_id"], r)]["judges"][persona] = parsed

    # ---- Optional cross-check judge (judge-model sensitivity; --judge-crosscheck).
    # Raw verdicts only — they inform sensitivity analysis, not the panel scores.
    if getattr(args, "judge_crosscheck", False):
        cc_model = jcfg["crosscheck_model"]  # validated at setup
        frac = float(jcfg.get("crosscheck_fraction", 0.25))
        seed = int(run_cfg.get("stats", {}).get("rng_seed", 0))
        by_key = {(m["id"], it["question_id"], r): (m, it, r, text)
                  for m, it, r, text, res in responses if text}
        cc_keys = pick_crosscheck_keys(list(by_key), frac, seed)
        cjobs, cmetas = [], []
        for key in cc_keys:
            m, it, r, text = by_key[key]
            for persona in personas:
                cjobs.append({"model": cc_model, "system": judgemod.JUDGE_SYSTEM,
                              "prompt": judgemod.build_judge_prompt(it, text, persona),
                              "effort": jeffort, "run_index": 0})
                cmetas.append((m, it, r, persona))
        print(f"[OPEN crosscheck] {len(cjobs)} calls on {cc_model} "
              f"({frac:.0%} of triples, seed {seed})", flush=True)
        cresults = runner.map(cjobs)
        for (m, it, r, persona), jr in zip(cmetas, cresults):
            parsed = judgemod.parse_judge_json(jr.text) if jr.ok else None
            judge_sink.write({"model": m["id"], "question_id": it["question_id"],
                              "run_index": r, "persona": persona,
                              "judge_model": cc_model, "judge_role": "crosscheck",
                              "call_ok": jr.ok, "parse_ok": parsed is not None,
                              "judge_served": jr.model_served,
                              "judge_served_all": jr.served_all, "error": jr.error,
                              "called_at": jr.called_at, "scores": parsed})
    judge_sink.close()

    if n_parse_failed:
        print(f"[OPEN judge] WARNING: {n_parse_failed} judge output(s) returned ok "
              f"but did not parse. These are cached and will NOT heal on re-run — "
              f"the affected panels aggregate over fewer judges.", flush=True)

    score_sink = JsonlSink(out / "open_scores.jsonl")
    for key, v in panel.items():
        m, it, r = v["meta"]
        agg = judgemod.aggregate_panel(list(v["judges"].values()))
        score_sink.write({"model": m["id"], "tier": m["tier"], "label": m["label"],
                          "question_id": it["question_id"], "dimension": it["dimension"],
                          "difficulty": it["difficulty"], "run_index": r,
                          "judge_model": judge_model,
                          "composite_100": agg["composite_100"],
                          "dim_means": agg["dim_means"],
                          "must_include_coverage": agg["must_include_coverage"],
                          "mean_should_not_violations": agg["mean_should_not_violations"],
                          "n_judges": agg["n_judges"]})
    score_sink.close()
    # snapshot AFTER all open-phase outputs commit
    write_config_snapshot(out, "open", run_cfg, cohort,
                          {"n_items": len(items), "n_runs": n_runs,
                           "judge_model": judge_model, "personas": personas})
    print(f"[OPEN] wrote {score_sink.n} panel scores | live spend ${runner.total_spend_usd:.2f}")
    _quick_open_summary(score_sink.path, cohort)


def _quick_open_summary(path: Path, cohort):
    recs = load_jsonl(path)
    print("\n[OPEN] quick mean composite (0-100):")
    for m in cohort:
        rows = [r for r in recs if r["model"] == m["id"] and r["composite_100"] is not None]
        if not rows:
            continue
        mean = sum(r["composite_100"] for r in rows) / len(rows)
        print(f"  {m['label']:12s} composite={mean:.1f}  n={len(rows)}")


# --------------------------------------------------------------------------- #


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("mc", "open"):
        p = sub.add_parser(name)
        p.add_argument("--questions", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--models", default="")
        p.add_argument("--runs", type=int, default=0)
        p.add_argument("--limit", type=int, default=0)
        p.add_argument("--max-parallel", type=int, default=0)
        if name == "open":
            p.add_argument("--judge-crosscheck", action="store_true",
                           help="also run models.yaml judges.crosscheck_model on a "
                                "seeded crosscheck_fraction of triples (raw verdicts "
                                "recorded for judge-sensitivity analysis)")
    args = ap.parse_args()
    if args.cmd == "mc":
        run_mc(args)
    elif args.cmd == "open":
        run_open(args)


if __name__ == "__main__":
    main()
