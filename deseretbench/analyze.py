"""Analyze a DeseretBench run into results/summary.json (the basis for reports).

Computes, with seeded bootstrap:
  MC  : per-model accuracy + 95% CI (overall / by dimension / by difficulty / by axis),
        parse-failure rate, run-to-run variance, pairwise paired-bootstrap diffs +
        McNemar, classical item analysis (difficulty + discrimination, ceiling/floor),
        and silent-fallback (served != requested) checks.
  OPEN: per-model mean composite (0-100) + CI, rubric coverage, should-not violations,
        by-dimension breakdown, judge inter-rater reliability (Krippendorff's alpha),
        and pairwise diffs.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import yaml

from .schema import load_jsonl
from .runner import _served_matches
from . import stats as stx
from .judge import DIMENSIONS as JUDGE_DIMS
from .packs import active_pack

ROOT = Path(__file__).resolve().parent.parent


def _attach_holm(pairwise: list[dict], alpha: float = 0.05):
    """Add Holm-Bonferroni-adjusted p and a family-wise significance flag to a
    family of pairwise comparisons (in place)."""
    ps = [pw["p_bootstrap"] for pw in pairwise]
    for pw, ph in zip(pairwise, stx.holm_bonferroni(ps)):
        pw["p_holm"] = round(ph, 5)
        pw["significant_holm"] = ph < alpha


def _classify_served_mismatch(mrecs: list[dict], mid: str) -> tuple[list[dict], int, int]:
    """Split a model's records into (scoreable, n_artifact, n_genuine).

    A served_mismatch record is either a multi-key modelUsage extraction
    artifact (the primary call WAS the requested model — evidenced by
    requested-model pricing and/or a recorded served_all) or a genuine silent
    fallback (served AND priced as a different model). Artifacts stay in
    scoring under the requested model; genuine fallbacks are excluded — their
    text is another model's output.
    """
    ok = [r for r in mrecs if r.get("call_ok", True)]
    clean, mism = [], []
    for r in ok:
        # same alias<->dated-snapshot tolerance as the runner's live guard
        if _served_matches(mid, r.get("model_served")):
            clean.append(r)
        else:
            mism.append(r)
    if not mism:
        return ok, 0, 0
    clean_costs = sorted(r.get("cost_usd", 0.0) or 0.0 for r in clean)
    median = clean_costs[len(clean_costs) // 2] if clean_costs else 0.0
    if median <= 0:
        # no cost evidence to distinguish artifact from fallback: classify all
        # mismatches as genuine (excluded) and say so loudly, rather than
        # silently guessing either way
        print(f"WARNING: {mid}: {len(mism)} served-mismatch record(s) and no "
              f"clean-cost baseline — excluding all of them from scoring.")
        return list(clean), 0, len(mism)
    keep, n_art, n_gen = list(clean), 0, 0
    for r in mism:
        # served_all counts as artifact evidence only if the requested model
        # actually appears among the reported serving models
        sa = r.get("served_all") or ""
        in_served_all = any(_served_matches(mid, k) for k in sa.split(",") if k)
        is_artifact = in_served_all or (r.get("cost_usd", 0.0) or 0.0) / median > 0.5
        if is_artifact:
            keep.append(r)
            n_art += 1
        else:
            n_gen += 1
    return keep, n_art, n_gen


def analyze_mc(path: Path, cohort, seed, n_boot, ci):
    recs = load_jsonl(path)
    labels = {m["id"]: m["label"] for m in cohort}
    tiers = {m["id"]: m["tier"] for m in cohort}
    # For local families `generation` is the parameter count in billions; the
    # report needs it to draw scaling-by-size. Absent (e.g. closed models with
    # no published size) stays None — never inferred.
    generations = {m["id"]: m.get("generation") for m in cohort}
    known = set(labels)
    unknown_models = sorted({r["model"] for r in recs} - known)
    if unknown_models:
        n_dropped = sum(1 for r in recs if r["model"] in set(unknown_models))
        print(f"WARNING: {n_dropped} record(s) from model id(s) not in "
              f"configs/models.yaml — excluded from analysis: {unknown_models}")
    model_ids = [m["id"] for m in cohort if any(r["model"] == m["id"] for r in recs)]

    overall, by_dim, by_diff, by_axis = {}, {}, {}, {}
    per_item_for_pairwise, meta = {}, {}
    all_scoreable = []  # same exclusions everywhere, incl. item analysis
    for mid in model_ids:
        mrecs = [r for r in recs if r["model"] == mid]
        scoreable, n_art, n_gen = _classify_served_mismatch(mrecs, mid)
        all_scoreable.extend(scoreable)
        n_failed = sum(1 for r in mrecs if not r.get("call_ok", True))

        items = defaultdict(list)
        for r in scoreable:
            items[r["question_id"]].append(1 if r["correct"] else 0)
            meta[r["question_id"]] = (r["dimension"], r["difficulty"], r["axis"])
        ids = sorted(items)
        p_map = {i: sum(items[i]) / len(items[i]) for i in ids}
        per_item_for_pairwise[mid] = p_map
        p_list = [p_map[i] for i in ids]
        ci_o = stx.bootstrap_mean_ci(p_list, n_boot,
                                     stx.derive_seed(seed, "mc-overall", mid), ci)
        rv = stx.run_variance([items[i] for i in ids])
        parse_fail = (sum(not r["parse_ok"] for r in scoreable) / len(scoreable)
                      if scoreable else None)
        # Exact binomial CI over item-majority correctness: the honest interval
        # when the bootstrap collapses to zero width at the accuracy ceiling.
        maj_k = sum(1 for i in ids if p_map[i] >= 0.5)
        cp_lo, cp_hi = stx.clopper_pearson(maj_k, len(ids), ci)
        overall[mid] = {"label": labels[mid], "tier": tiers[mid],
                        "generation": generations.get(mid), **ci_o,
                        "cp_lo": round(cp_lo, 4), "cp_hi": round(cp_hi, 4),
                        "parse_fail_rate": round(parse_fail, 4) if parse_fail is not None else None,
                        "mean_within_item_sd": round(rv["mean_within_item_sd"], 4),
                        "served_mismatch_artifact": n_art,
                        "served_mismatch_genuine": n_gen,
                        "n_call_failed": n_failed, "n_calls": len(mrecs)}

        def grouped(keyidx):
            g = defaultdict(list)
            for i in ids:
                g[meta[i][keyidx]].append(p_map[i])
            return {k: stx.bootstrap_mean_ci(
                        v, n_boot, stx.derive_seed(seed, "mc-group", mid, str(keyidx), k), ci)
                    for k, v in g.items()}
        by_dim[mid] = grouped(0)
        by_diff[mid] = grouped(1)
        by_axis[mid] = grouped(2)

    # pairwise (only items both answered), Holm-adjusted within the family
    pairwise = []
    for a in range(len(model_ids)):
        for b in range(a + 1, len(model_ids)):
            ma, mb = model_ids[a], model_ids[b]
            common = sorted(set(per_item_for_pairwise[ma]) & set(per_item_for_pairwise[mb]))
            if not common:
                continue
            av = [per_item_for_pairwise[ma][i] for i in common]
            bv = [per_item_for_pairwise[mb][i] for i in common]
            d = stx.paired_bootstrap_diff(av, bv, n_boot,
                                          stx.derive_seed(seed, "mc-pair", ma, mb), ci)
            mc = stx.mcnemar_test([per_item_for_pairwise[ma][i] >= 0.5 for i in common],
                                  [per_item_for_pairwise[mb][i] >= 0.5 for i in common])
            pairwise.append({"a": ma, "a_label": labels[ma], "b": mb, "b_label": labels[mb],
                             "diff": round(d["diff"], 4), "lo": round(d["lo"], 4),
                             "hi": round(d["hi"], 4), "p_bootstrap": round(d["p"], 5),
                             "mcnemar_p": round(mc["p"], 5)})
    _attach_holm(pairwise)

    # item analysis: respondents = (model, run); aligned across items; built
    # from the SAME scoreable sets as the per-model scores (call failures and
    # genuine served-model fallbacks are missing data, not wrong answers)
    ok_recs = all_scoreable
    resp_keys = sorted({(r["model"], r["run_index"]) for r in ok_recs})
    rk_index = {k: i for i, k in enumerate(resp_keys)}
    by_item_resp = defaultdict(lambda: [None] * len(resp_keys))
    for r in ok_recs:
        by_item_resp[r["question_id"]][rk_index[(r["model"], r["run_index"])]] = 1 if r["correct"] else 0
    # drop items missing any respondent (keep complete matrix)
    complete = {i: v for i, v in by_item_resp.items() if all(x is not None for x in v)}
    ia = stx.item_analysis(complete)
    diffs = [v["difficulty_p"] for v in ia.values()]
    discs = [v["discrimination"] for v in ia.values() if v["discrimination"] is not None]
    item_summary = {
        "n_items": len(ia),
        "mean_difficulty_p": round(sum(diffs) / len(diffs), 4) if diffs else None,
        # discrimination is undefined for zero-variance (ceiling) items, so
        # this mean summarizes ONLY the n_items_with_discrimination below —
        # read the two fields together
        "mean_discrimination": round(sum(discs) / len(discs), 4) if discs else None,
        "n_items_with_discrimination": len(discs),
        "n_ceiling_gt_0.95": sum(1 for d in diffs if d > 0.95),
        "n_floor_lt_0.30": sum(1 for d in diffs if d < 0.30),
        "n_low_discrimination_lt_0.10": sum(1 for d in discs if d < 0.10),
        "hardest": sorted(({"id": i, **v} for i, v in ia.items()),
                          key=lambda x: x["difficulty_p"])[:10],
    }
    return {"overall": overall, "by_dimension": by_dim, "by_difficulty": by_diff,
            "by_axis": by_axis, "pairwise": pairwise, "item_analysis": item_summary,
            "n_records": len(recs)}


def analyze_open(scores_path: Path, judge_raw_path: Path, cohort, seed, n_boot, ci):
    if not scores_path.exists():
        return None
    recs = load_jsonl(scores_path)
    labels = {m["id"]: m["label"] for m in cohort}
    tiers = {m["id"]: m["tier"] for m in cohort}
    # For local families `generation` is the parameter count in billions; the
    # report needs it to draw scaling-by-size. Absent (e.g. closed models with
    # no published size) stays None — never inferred.
    generations = {m["id"]: m.get("generation") for m in cohort}
    model_ids = [m["id"] for m in cohort if any(r["model"] == m["id"] for r in recs)]

    def per_item(mid):
        g = defaultdict(list)
        for r in recs:
            if r["model"] == mid and r["composite_100"] is not None:
                g[r["question_id"]].append(r["composite_100"])
        return {i: sum(v) / len(v) for i, v in g.items()}

    overall, by_dim = {}, {}
    pip = {}
    for mid in model_ids:
        p = per_item(mid)
        pip[mid] = p
        ci_o = stx.bootstrap_mean_ci(list(p.values()), n_boot,
                                     stx.derive_seed(seed, "open-overall", mid), ci)
        mrecs = [r for r in recs if r["model"] == mid]
        n_missing = sum(1 for r in mrecs if r["composite_100"] is None)
        cov = [r["must_include_coverage"] for r in mrecs if r["must_include_coverage"] is not None]
        viol = [r["mean_should_not_violations"] for r in mrecs if r["mean_should_not_violations"] is not None]
        overall[mid] = {"label": labels[mid], "tier": tiers[mid],
                        "generation": generations.get(mid), **ci_o,
                        "n_unscored_records": n_missing,
                        "mean_must_include_coverage": round(sum(cov) / len(cov), 4) if cov else None,
                        "mean_should_not_violations": round(sum(viol) / len(viol), 4) if viol else None}
        # By-dimension over per-item means — same sampling unit as the overall
        # CI. Bootstrapping raw run-records would treat the 3 correlated runs
        # of one item as independent (pseudo-replication -> too-narrow CIs).
        g = defaultdict(lambda: defaultdict(list))
        for r in mrecs:
            if r["composite_100"] is not None:
                g[r["dimension"]][r["question_id"]].append(r["composite_100"])
        by_dim[mid] = {
            k: stx.bootstrap_mean_ci(
                [sum(v) / len(v) for v in items.values()], n_boot,
                stx.derive_seed(seed, "open-dim", mid, k), ci)
            for k, items in g.items()}
        # Judge-dimension means (1-5 scale) so per-dimension claims (e.g. the
        # distinctiveness failure signature) trace to a computed artifact.
        jd = defaultdict(lambda: defaultdict(list))
        for r in mrecs:
            for d, v in (r.get("dim_means") or {}).items():
                if v is not None:
                    jd[d][r["question_id"]].append(v)
        overall[mid]["judge_dimension_means"] = {
            d: round(sum(sum(v) / len(v) for v in items.values()) / len(items), 3)
            for d, items in jd.items() if items}

    pairwise = []
    for a in range(len(model_ids)):
        for b in range(a + 1, len(model_ids)):
            ma, mb = model_ids[a], model_ids[b]
            common = sorted(set(pip[ma]) & set(pip[mb]))
            if not common:
                continue
            d = stx.paired_bootstrap_diff([pip[ma][i] for i in common],
                                          [pip[mb][i] for i in common], n_boot,
                                          stx.derive_seed(seed, "open-pair", ma, mb), ci)
            pairwise.append({"a": ma, "a_label": labels[ma], "b": mb, "b_label": labels[mb],
                             "diff": round(d["diff"], 3), "lo": round(d["lo"], 3),
                             "hi": round(d["hi"], 3), "p_bootstrap": round(d["p"], 5)})
    _attach_holm(pairwise)

    # Judge IRR (Krippendorff alpha over personas): on the composite AND on
    # each dimension separately — averaging four dimensions before computing
    # alpha smooths out per-dimension disagreement and inflates the headline.
    irr = None
    if judge_raw_path.exists():
        jr = load_jsonl(judge_raw_path)
        # primary-judge verdicts only (crosscheck rows are sensitivity data)
        jr = [r for r in jr if r.get("judge_role", "primary") == "primary"]
        units = defaultdict(dict)      # key -> {persona: composite}
        dim_units = {d: defaultdict(dict) for d in JUDGE_DIMS}
        personas = set()
        for r in jr:
            sc = r.get("scores")
            if not sc:
                continue
            vals = [sc.get(d) for d in JUDGE_DIMS if isinstance(sc.get(d), (int, float))]
            if len(vals) == len(JUDGE_DIMS):
                key = (r["model"], r["question_id"], r["run_index"])
                units[key][r["persona"]] = sum(vals) / len(vals)
                for d in JUDGE_DIMS:
                    dim_units[d][key][r["persona"]] = float(sc[d])
                personas.add(r["persona"])
        personas = sorted(personas)
        if len(personas) >= 2 and units:
            def alpha_of(u):
                ukeys = sorted(u)
                matrix = [[u[k].get(p) for k in ukeys] for p in personas]
                a = stx.krippendorff_alpha_interval(matrix)
                return round(a, 4) if a is not None else None
            per_dim = {d: alpha_of(dim_units[d]) for d in JUDGE_DIMS}
            defined = [v for v in per_dim.values() if v is not None]
            irr = {"krippendorff_alpha": alpha_of(units),
                   "per_dimension_alpha": per_dim,
                   "min_dimension_alpha": min(defined) if defined else None,
                   "n_personas": len(personas), "n_units": len(units)}

    return {"overall": overall, "by_dimension": by_dim, "pairwise": pairwise,
            "judge_irr": irr, "n_records": len(recs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run dir, e.g. runs/v0_1")
    ap.add_argument("--out", default=None,
                    help="output summary path; default <pack.results_dir>/summary.json "
                         "(results/summary.json for the LDS pack)")
    args = ap.parse_args()
    out_rel = args.out or f"{active_pack().results_dir}/summary.json"

    run_cfg = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())
    models = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text())
    cohort = models["cohort"]
    s = run_cfg["stats"]
    seed, n_boot, ci = s["rng_seed"], s["bootstrap_resamples"], s["ci_level"]

    run = Path(args.run)
    # Provenance: prefer the config snapshot the run itself wrote; the live
    # config file may have changed since the run and would stamp false values.
    snap_path = run / "config_snapshot.json"
    snap = None
    if snap_path.exists():
        try:
            snap = json.loads(snap_path.read_text()) or None
        except json.JSONDecodeError:
            print(f"WARNING: {snap_path} is corrupt — falling back to live config.")
    if snap:
        # stamp each phase from ITS OWN snapshot; fall back to the live config
        # per missing phase (e.g. an mc-only run has no 'open' entry)
        def phase_cfg(phase, key):
            ph = snap.get(phase) or {}
            return (ph.get("run_config") or {}).get(key) or run_cfg[key]
        config = {"effort": {**run_cfg["effort"],
                             **{k: v for k, v in phase_cfg("mc", "effort").items()
                                if k == "multiple_choice"},
                             **{k: v for k, v in phase_cfg("open", "effort").items()
                                if k in ("open_ended", "judge")}},
                  "runs": {"multiple_choice": phase_cfg("mc", "runs")["multiple_choice"],
                           "open_ended": phase_cfg("open", "runs")["open_ended"]},
                  "ci_level": ci, "bootstrap_resamples": n_boot, "seed": seed,
                  "provenance": "run config_snapshot.json (per phase; live config "
                                "fills phases without a snapshot)"}
    else:
        print(f"WARNING: {snap_path} not found — stamping provenance from the "
              f"CURRENT config files, which may differ from what the run used.")
        config = {"effort": run_cfg["effort"], "runs": run_cfg["runs"],
                  "ci_level": ci, "bootstrap_resamples": n_boot, "seed": seed,
                  "provenance": "config files at analyze time (no run snapshot)"}
    summary = {"run": str(run), "pack": active_pack().key, "config": config}
    mc_path = run / "mc_responses.jsonl"
    if mc_path.exists():
        summary["mc"] = analyze_mc(mc_path, cohort, seed, n_boot, ci)
    # MC-only runs (e.g. a quick single-model pass on a new pack) have no open
    # phase; only analyze it when its scores exist, so report can skip it.
    if (run / "open_scores.jsonl").exists():
        summary["open"] = analyze_open(run / "open_scores.jsonl",
                                       run / "open_judge_raw.jsonl",
                                       cohort, seed, n_boot, ci)

    outp = ROOT / out_rel
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(summary, indent=2))
    print(f"wrote {outp}")
    def _f(v, spec=".3f"):
        return format(v, spec) if v is not None else "n/a"

    if "mc" in summary:
        print("\nMC leaderboard (acc [95% CI]):")
        for mid, o in sorted(summary["mc"]["overall"].items(),
                             key=lambda kv: -(kv[1]["mean"] or 0)):
            print(f"  {o['label']:12s} {_f(o['mean'])} [{_f(o['lo'])},{_f(o['hi'])}] "
                  f"exactCI=[{_f(o['cp_lo'])},{_f(o['cp_hi'])}] "
                  f"parse_fail={_f(o['parse_fail_rate'])} n={o['n']}")
        ia = summary["mc"]["item_analysis"]
        print(f"  item analysis: mean_p={ia['mean_difficulty_p']} "
              f"mean_disc={ia['mean_discrimination']} "
              f"(over {ia['n_items_with_discrimination']}/{ia['n_items']} items with "
              f"defined discrimination) ceiling={ia['n_ceiling_gt_0.95']} "
              f"floor={ia['n_floor_lt_0.30']}")
    if summary.get("open"):
        print("\nOPEN leaderboard (composite 0-100 [95% CI]):")
        for mid, o in sorted(summary["open"]["overall"].items(),
                             key=lambda kv: -(kv[1]["mean"] or 0)):
            print(f"  {o['label']:12s} {_f(o['mean'], '.1f')} "
                  f"[{_f(o['lo'], '.1f')},{_f(o['hi'], '.1f')}]")
        if summary["open"].get("judge_irr"):
            irr = summary["open"]["judge_irr"]
            print(f"  judge IRR (Krippendorff alpha): {irr['krippendorff_alpha']} "
                  f"(min single dimension: {irr.get('min_dimension_alpha')})")


if __name__ == "__main__":
    main()
