"""Completeness audit for a benchmark phase.

The resilient runner re-runs a phase until nothing is left to do. Deciding
"nothing left" needs two signals that are easy to conflate — and conflating
them is what made the open phase spin forever:

  strict_fail  — records a retry could still heal: uncached failed calls,
                 corrupt lines, and missing records. Drives RETRY.
  accept_fail  — what must be zero before a phase may be called done anyway.
                 ONLY judge-call failures are tolerable, and only while every
                 panel keeps a quorum; a missing or failed GENERATION is never
                 tolerated, or an empty run would read as complete.

Some judge calls never heal no matter how many waves run. The served-model
guard rejects a verdict when the CLI answers with a model other than the one
requested, and whether that happens is a property of the call, not of the
retry. Such a verdict is dropped — never recorded under the wrong model, which
would contaminate the panel it belongs to. `aggregate_panel` already scores a
panel over the judges it has, so a triple that still holds a quorum is
complete: continuing to retry it burns quota to change nothing.

Retry remains best-effort — the caller applies quorum only once retries have
had their chances, so a merely transient failure still heals rather than
silently degrading the panel.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def scan_jsonl(path) -> tuple[int, int, int]:
    """-> (failed, total, corrupt). A missing file is (0, 0, 0); the caller's
    expected-count arithmetic is what turns that into 'missing'."""
    path = Path(path)
    if not path.exists():
        return 0, 0, 0
    failed = total = corrupt = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            total += 1
            try:
                rec = json.loads(line)
            except Exception:
                corrupt += 1
                continue
            if not rec.get("call_ok", True):
                failed += 1
    return failed, total, corrupt


def judge_quorum_shortfall(path, quorum: int) -> int:
    """Number of (model, question_id, run) triples whose PRIMARY panel holds
    fewer than `quorum` parsed verdicts.

    Only scores decide: a call that errored and a call that returned
    unparseable text are both simply not a judge. Crosscheck verdicts come
    from a different judge model for sensitivity analysis and are excluded —
    they must never fill a gap in the scored panel.
    """
    path = Path(path)
    if not path.exists():
        return 0
    panels: dict[tuple, int] = defaultdict(int)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("judge_role", "primary") != "primary":
                continue
            key = (rec.get("model"), rec.get("question_id"), rec.get("run_index"))
            panels[key] += 1 if rec.get("scores") is not None else 0
    return sum(1 for n in panels.values() if n < quorum)


def audit_mc(run, n_items: int, n_models: int, n_runs: int) -> dict:
    expected = n_items * n_models * n_runs
    failed, total, corrupt = scan_jsonl(Path(run) / "mc_responses.jsonl")
    missing = max(0, expected - total)
    strict = failed + corrupt + missing
    # MC has no judge panel: nothing about it is tolerable-but-incomplete.
    return {"strict_fail": strict, "accept_fail": strict, "below_quorum": 0,
            "expected": expected, "have": total, "failed": failed,
            "corrupt": corrupt, "missing": missing}


def audit_open(run, n_items: int, n_models: int, n_runs: int,
               n_personas: int, quorum: int) -> dict:
    run = Path(run)
    expected_gen = n_items * n_models * n_runs
    gf, gt, gc = scan_jsonl(run / "open_responses.jsonl")
    gm = max(0, expected_gen - gt)

    # only a response that generated can be judged
    expected_judge = max(0, gt - gf) * n_personas
    jf, jt, jc = scan_jsonl(run / "open_judge_raw.jsonl")
    jm = max(0, expected_judge - jt)

    # A triple with no judge records at all is invisible to the raw file, so
    # count expected-but-absent triples as shortfalls too — a short or missing
    # file must never read as complete.
    seen_shortfall = judge_quorum_shortfall(run / "open_judge_raw.jsonl", quorum)
    expected_triples = max(0, gt - gf)
    judged_triples = _distinct_primary_triples(run / "open_judge_raw.jsonl")
    below = seen_shortfall + max(0, expected_triples - judged_triples)

    # A judge call that keeps failing is tolerable; a response that never
    # generated is not. Corrupt judge lines mean file damage, not a flaky
    # call, so they block acceptance regardless of quorum.
    accept_fail = gf + gc + gm + jc + below

    return {"strict_fail": gf + gc + gm + jf + jc + jm,
            "accept_fail": accept_fail, "below_quorum": below,
            "gen_failed": gf, "gen_corrupt": gc, "gen_missing": gm,
            "gen_have": gt, "gen_expected": expected_gen,
            "judge_failed": jf, "judge_corrupt": jc, "judge_missing": jm,
            "judge_have": jt, "judge_expected": expected_judge}


def _distinct_primary_triples(path) -> int:
    path = Path(path)
    if not path.exists():
        return 0
    keys = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("judge_role", "primary") != "primary":
                continue
            keys.add((rec.get("model"), rec.get("question_id"),
                      rec.get("run_index")))
    return len(keys)


def main():
    import yaml

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=["mc", "open"])
    ap.add_argument("--run", required=True)
    ap.add_argument("--questions", required=True)
    ap.add_argument("--quorum", type=int, default=2)
    args = ap.parse_args()

    cfg = yaml.safe_load(open("configs/run_config.yaml"))
    models = yaml.safe_load(open("configs/models.yaml"))
    n_models = len(models["cohort"])
    n_personas = len(models["judges"]["personas"])
    n_items = sum(1 for line in open(args.questions) if line.strip())

    if args.phase == "mc":
        r = audit_mc(args.run, n_items, n_models, cfg["runs"]["multiple_choice"])
        detail = (f"  mc_responses: {r['failed']} failed + {r['corrupt']} corrupt "
                  f"+ {r['missing']} missing (have {r['have']}/{r['expected']})")
    else:
        r = audit_open(args.run, n_items, n_models, cfg["runs"]["open_ended"],
                       n_personas, args.quorum)
        detail = (f"  open_responses: {r['gen_failed']} failed + {r['gen_corrupt']} "
                  f"corrupt + {r['gen_missing']} missing "
                  f"(have {r['gen_have']}/{r['gen_expected']}) | "
                  f"open_judge_raw: {r['judge_failed']} failed + "
                  f"{r['judge_corrupt']} corrupt + {r['judge_missing']} missing "
                  f"(have {r['judge_have']}/{r['judge_expected']}) | "
                  f"panels below quorum({args.quorum}): {r['below_quorum']}")

    print(f"{r['strict_fail']} {r['accept_fail']}")
    print(detail, file=sys.stderr)


if __name__ == "__main__":
    main()
