"""Reviewer-persona validation (the automated stand-in for the human expert panel).

Five independent reviewer personas (run through the Runner, 8-wide & cached):
  orthodox_member, byu_religion_instructor, church_historian, adult_convert,
  international_returned_missionary

MC items are reviewed BLIND (no key shown) so reviewer answer-agreement is a real
signal. We compute key-agreement, mean clarity, Fleiss' kappa, and ambiguity
flags, then apply keep-rules. Open items are vetted for realism + rubric quality.

Output:
  data/reviews_mc.jsonl, data/reviews_open.jsonl     (raw per-persona reviews)
  data/questions_mc.jsonl, data/questions_open.jsonl (kept public set)
  data/private_holdout/{mc,open}.jsonl               (20% stratified, git-ignored)
  data/validation_report.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

import yaml

from .runner import Runner
from .schema import LETTERS, load_jsonl, dump_jsonl
from .judge import extract_last_json as parse_review_json  # generic JSON extractor
from .packs import active_pack
from . import stats as stx

ROOT = Path(__file__).resolve().parent.parent

# Reviewer personas and the two review prompts are tradition-specific and come
# from the active faith pack. Bound at import (one pack per validation run).
_PACK = active_pack()
REVIEWERS = _PACK.reviewers or {}

REVIEW_SYSTEM = "You are an expert reviewer validating questions for a research benchmark. Output only the requested JSON."


def mc_review_prompt(item: dict) -> str:
    return active_pack().mc_review_prompt(item)


def open_review_prompt(item: dict) -> str:
    return active_pack().open_review_prompt(item)


def _runner(max_parallel: int) -> Runner:
    # Honor configs/run_config.yaml (backend, retries, timeout, CLI flags)
    # so the documented anthropic_api reproduction path works here too.
    run_cfg = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())
    rc = dict(run_cfg.get("runner") or {})
    rc["max_parallel"] = max_parallel
    return Runner({"runner": rc}, cache_dir=ROOT / "cache")


REVIEW_MODEL = "claude-opus-4-8"  # fixed strong model for review


def _bump_effort(effort: str) -> str:
    order = ["low", "medium", "high", "xhigh", "max"]
    i = order.index(effort) if effort in order else 1
    return order[min(i + 1, len(order) - 1)]


def _review(items, runner, effort, prompt_fn, label):
    """One review pass + a re-solicit pass for failures.

    An ok-but-unparseable review is cached and replays byte-identically, so
    retrying at the same effort can never heal it — the re-solicit runs at a
    bumped effort (different cache key). Item content must never decide
    whether it gets reviewed; without this, systematic refusals on sensitive
    topics silently bias the pool (v0.1 lost 7 sensitive open items this way).
    """
    jobs, metas = [], []
    for it in items:
        for pkey, psys in REVIEWERS.items():
            jobs.append({"model": REVIEW_MODEL, "system": psys, "prompt": prompt_fn(it),
                         "effort": effort, "run_index": 0})
            metas.append((it, pkey, psys))
    print(f"[review {label}] {len(items)} items x {len(REVIEWERS)} personas = {len(jobs)} calls")
    results = runner.map(jobs)
    by_item = defaultdict(dict)
    raw = []
    retry = []
    for (it, pkey, psys), res in zip(metas, results):
        parsed = parse_review_json(res.text) if res.ok else None
        if parsed is None:
            retry.append((it, pkey, psys))
        by_item[it["question_id"]][pkey] = parsed
        raw.append({"question_id": it["question_id"], "persona": pkey,
                    "parse_ok": parsed is not None, "resolicited": False,
                    "review": parsed})
    if retry:
        # run_index=1 guarantees a fresh cache key even at effort=max (where
        # _bump_effort is a no-op and the cached bad response would replay)
        eff2 = _bump_effort(effort)
        print(f"[review {label}] re-soliciting {len(retry)} failed review(s) at effort={eff2}")
        jobs2 = [{"model": REVIEW_MODEL, "system": psys, "prompt": prompt_fn(it),
                  "effort": eff2, "run_index": 1} for it, pkey, psys in retry]
        results2 = runner.map(jobs2)
        for (it, pkey, psys), res in zip(retry, results2):
            parsed = parse_review_json(res.text) if res.ok else None
            if parsed is not None:
                by_item[it["question_id"]][pkey] = parsed
            raw.append({"question_id": it["question_id"], "persona": pkey,
                        "parse_ok": parsed is not None, "resolicited": True,
                        "review": parsed})
        still = sum(1 for it, pkey, _ in retry if by_item[it["question_id"]][pkey] is None)
        if still:
            print(f"[review {label}] WARNING: {still} review(s) still unparseable after "
                  f"re-solicit — affected items may lack quorum and will be reported "
                  f"as UNREVIEWED, not as rejected.")
    return by_item, raw


def review_mc(items, runner, effort):
    return _review(items, runner, effort, mc_review_prompt, "MC")


def review_open(items, runner, effort):
    return _review(items, runner, effort, open_review_prompt, "OPEN")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def finalize_mc(items, by_item):
    kept, dropped = [], []
    fleiss_rows = []  # per item: list of category indices (chosen letters)
    for it in items:
        revs = by_item.get(it["question_id"], {})
        answers, clar, ndef, flags = [], [], [], []
        for pkey, rv in revs.items():
            if not rv:
                continue
            la = str(rv.get("best_answer", "")).strip().upper()[:1]
            if la and la in set(LETTERS[:len(it["choices"])]):
                answers.append(la)
            clar.append(rv.get("clarity"))
            ndef.append(rv.get("n_defensible_options"))
            for f in (rv.get("flags") or []):
                if f and f != "none":
                    flags.append(f)
        key_letter = LETTERS[it["answer_index"]]
        key_agree = (sum(a == key_letter for a in answers) / len(answers)) if answers else 0.0
        mean_clar = _mean(clar) or 0.0
        mean_ndef = _mean(ndef) or 1.0
        bad_flags = sum(1 for f in flags if f in
                        ("ambiguous", "multiple_correct", "unfair", "factually_wrong"))
        it["_review"] = {"key_agreement": round(key_agree, 3), "mean_clarity": round(mean_clar, 2),
                         "mean_n_defensible": round(mean_ndef, 2), "n_reviewers": len(answers),
                         "bad_flags": bad_flags, "flags": flags}
        if answers:
            fleiss_rows.append([LETTERS.index(a) for a in answers])
        if len(answers) < 3:
            # no quorum: an infrastructure/parse outcome, not a quality verdict
            it["_review"]["unreviewed"] = True
            dropped.append(it)
            continue
        keep = (key_agree >= 0.6 and mean_clar >= 4.0 and mean_ndef <= 1.5 and
                bad_flags <= 1)
        (kept if keep else dropped).append(it)
    # Fleiss kappa needs equal raters; pad/truncate to mode count
    kappa = None
    if fleiss_rows:
        n = max(set(len(r) for r in fleiss_rows), key=lambda k: sum(len(r) == k for r in fleiss_rows))
        eq = [r for r in fleiss_rows if len(r) == n]
        if eq and n >= 2:
            kappa = stx.fleiss_kappa(eq, n_categories=6)
    return kept, dropped, kappa


def finalize_open(items, by_item):
    kept, dropped = [], []
    for it in items:
        revs = by_item.get(it["question_id"], {})
        realistic, fair, clar, flags = [], [], [], []
        for pkey, rv in revs.items():
            if not rv:
                continue
            # quorum counts only reviews that actually rated the item —
            # a parseable-but-contentless review is an infrastructure
            # failure, not an opinion
            if rv.get("realistic") is None:
                continue
            realistic.append(rv.get("realistic"))
            fair.append(rv.get("rubric_fair"))
            clar.append(rv.get("clarity"))
            for f in (rv.get("flags") or []):
                if f and f != "none":
                    flags.append(f)
        mr, mf, mc = _mean(realistic) or 0, _mean(fair) or 0, _mean(clar) or 0
        bad = sum(1 for f in flags if f in ("unrealistic", "rubric_heterodox", "factually_wrong"))
        it["_review"] = {"mean_realistic": round(mr, 2), "mean_rubric_fair": round(mf, 2),
                         "mean_clarity": round(mc, 2), "n_reviewers": len(realistic),
                         "bad_flags": bad, "flags": flags}
        if len(realistic) < 3:
            it["_review"]["unreviewed"] = True
            dropped.append(it)
            continue
        keep = mr >= 4.0 and mf >= 4.0 and mc >= 4.0 and bad <= 1
        (kept if keep else dropped).append(it)
    return kept, dropped


def stratified_holdout(items, frac, seed):
    by_strata = defaultdict(list)
    for it in items:
        by_strata[(it["dimension"], it["difficulty"])].append(it)
    rng = random.Random(seed)
    public, holdout = [], []
    for k, group in by_strata.items():
        g = group[:]
        rng.shuffle(g)
        n_hold = max(0, round(len(g) * frac))
        holdout.extend(g[:n_hold])
        public.extend(g[n_hold:])
    return public, holdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-parallel", type=int, default=8)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-holdout", action="store_true")
    args = ap.parse_args()

    p = active_pack()
    if not p.reviewers or p.mc_review_prompt is None or p.open_review_prompt is None:
        raise SystemExit(
            f"faith pack {p.key!r} has no reviewer panel — fill reviewers and the "
            f"review prompts in its pack.py before validating a candidate set "
            f"(see docs/how-to/add-a-faith-pack.md).")

    run_cfg = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())
    seed = run_cfg["stats"]["rng_seed"]
    frac = run_cfg["stats"]["holdout_fraction"]
    runner = _runner(args.max_parallel)

    mc = load_jsonl(ROOT / "data" / "candidates_mc.jsonl")
    op = load_jsonl(ROOT / "data" / "candidates_open.jsonl")
    if args.limit:
        mc, op = mc[: args.limit], op[: args.limit]

    mc_by, mc_raw = review_mc(mc, runner, args.effort)
    op_by, op_raw = review_open(op, runner, args.effort)
    dump_jsonl(mc_raw, ROOT / "data" / "reviews_mc.jsonl")
    dump_jsonl(op_raw, ROOT / "data" / "reviews_open.jsonl")

    mc_keep, mc_drop, kappa = finalize_mc(mc, mc_by)
    op_keep, op_drop = finalize_open(op, op_by)

    for it in mc_keep + op_keep:
        it.pop("_review", None)  # keep public files clean (review stored separately)

    if args.no_holdout:
        mc_pub, mc_hold, op_pub, op_hold = mc_keep, [], op_keep, []
    else:
        mc_pub, mc_hold = stratified_holdout(mc_keep, frac, seed)
        op_pub, op_hold = stratified_holdout(op_keep, frac, seed + 1)

    dump_jsonl(mc_pub, ROOT / "data" / "questions_mc.jsonl")
    dump_jsonl(op_pub, ROOT / "data" / "questions_open.jsonl")
    (ROOT / "data" / "private_holdout").mkdir(exist_ok=True)
    dump_jsonl(mc_hold, ROOT / "data" / "private_holdout" / "mc.jsonl")
    dump_jsonl(op_hold, ROOT / "data" / "private_holdout" / "open.jsonl")

    def _split_drop(drops):
        rejected = [d for d in drops if not d.get("_review", {}).get("unreviewed")]
        unreviewed = [d for d in drops if d.get("_review", {}).get("unreviewed")]
        return rejected, unreviewed

    mc_rej, mc_unrev = _split_drop(mc_drop)
    op_rej, op_unrev = _split_drop(op_drop)
    report = {
        "mc_candidates": len(mc), "mc_kept": len(mc_keep),
        "mc_rejected": len(mc_rej), "mc_unreviewed": len(mc_unrev),
        "open_candidates": len(op), "open_kept": len(op_keep),
        "open_rejected": len(op_rej), "open_unreviewed": len(op_unrev),
        "mc_fleiss_kappa_answers": kappa,
        "mc_public": len(mc_pub), "mc_holdout": len(mc_hold),
        "open_public": len(op_pub), "open_holdout": len(op_hold),
        "drop_reasons_mc": [{"id": d["question_id"], **d.get("_review", {})} for d in mc_drop][:50],
        "drop_reasons_open": [{"id": d["question_id"], **d.get("_review", {})} for d in op_drop][:50],
        # unreviewed = review quorum never reached (parse failures/refusals);
        # these are NOT quality rejections and deserve human attention
        "unreviewed_mc": [d["question_id"] for d in mc_unrev],
        "unreviewed_open": [d["question_id"] for d in op_unrev],
        "live_spend_usd": round(runner.total_spend_usd, 2),
    }
    (ROOT / "data" / "validation_report.json").write_text(json.dumps(report, indent=2))
    print("\n=== VALIDATION REPORT ===")
    print(f"MC:   {report['mc_candidates']} cand -> kept {report['mc_kept']} "
          f"(public {report['mc_public']} / holdout {report['mc_holdout']}), rejected {report['mc_rejected']}, unreviewed {report['mc_unreviewed']}")
    print(f"OPEN: {report['open_candidates']} cand -> kept {report['open_kept']} "
          f"(public {report['open_public']} / holdout {report['open_holdout']}), rejected {report['open_rejected']}, unreviewed {report['open_unreviewed']}")
    print(f"MC reviewer Fleiss' kappa (answers): {kappa}")
    print(f"live spend ${report['live_spend_usd']}")


if __name__ == "__main__":
    main()
