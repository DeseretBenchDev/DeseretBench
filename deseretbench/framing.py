"""Compare a framed run with the neutral standings, model by model.

The framed edition asks every question twice over: once under the neutral system
prompt (the standings) and once with the pack's one-sentence instruction to answer
from inside the tradition. The gap, framed minus neutral, separates what a model
knows from what it says by default. A model with a large positive gap knows the
teaching and reaches for another frame unless told.

This module never touches the standings. It reads a neutral run directory and a
framed one and writes its own two files.

    python -m deseretbench.framing --neutral runs/v0_1_plus --framed runs/framed \
        # -> <results_dir>/framing.json, <reports_dir>/FRAMING.md
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import yaml

from . import stats as stx
from .analyze import _classify_served_mismatch
from .packs import active_pack
from .schema import load_jsonl

ROOT = Path(__file__).resolve().parent.parent

# (track, record file, per-record score or None when the record cannot be scored)
TRACKS = (
    ("mc", "mc_responses.jsonl", lambda r: 1.0 if r["correct"] else 0.0),
    ("open", "open_scores.jsonl", lambda r: r["composite_100"]),
)


def _condition_of(recs: list[dict]) -> set:
    return {r.get("condition", "neutral") for r in recs}


def _per_item(recs: list[dict], mid: str, track: str, score) -> dict:
    """question_id -> mean score across this model's scoreable repeats."""
    mrecs = [r for r in recs if r["model"] == mid]
    if track == "mc":
        # the same exclusions the standings apply: failed calls and genuine
        # served-model fallbacks are not this model's answers
        mrecs, _, _ = _classify_served_mismatch(mrecs, mid)
    g = defaultdict(list)
    for r in mrecs:
        v = score(r)
        if v is not None:
            g[r["question_id"]].append(v)
    return {q: sum(v) / len(v) for q, v in g.items()}


def compare(neutral_dir: Path, framed_dir: Path, cohort: list[dict],
            seed: int, n_boot: int, ci: float) -> dict:
    """Per track and model: neutral mean, framed mean, and the paired gap over the
    items both runs scored, with a bootstrap interval and a Holm-adjusted p across
    the models of that track."""
    labels = {m["id"]: m["label"] for m in cohort}
    order = [m["id"] for m in cohort]
    out = {}
    for track, fname, score in TRACKS:
        npath, fpath = Path(neutral_dir) / fname, Path(framed_dir) / fname
        if not (npath.exists() and fpath.exists()):
            continue
        nrecs, frecs = load_jsonl(npath), load_jsonl(fpath)
        if _condition_of(nrecs) != {"neutral"}:
            raise SystemExit(f"error: {npath} is not a neutral run "
                             f"(conditions: {sorted(_condition_of(nrecs))})")
        if _condition_of(frecs) != {"framed"}:
            raise SystemExit(f"error: {fpath} is not a framed run "
                             f"(conditions: {sorted(_condition_of(frecs))})")
        both = {r["model"] for r in nrecs} & {r["model"] for r in frecs}
        rows = {}
        for mid in [m for m in order if m in both]:
            n_map = _per_item(nrecs, mid, track, score)
            f_map = _per_item(frecs, mid, track, score)
            shared = sorted(set(n_map) & set(f_map))
            if not shared:
                continue
            f_vals = [f_map[q] for q in shared]
            n_vals = [n_map[q] for q in shared]
            d = stx.paired_bootstrap_diff(
                f_vals, n_vals, n_boot, stx.derive_seed(seed, "framing", track, mid), ci)
            rows[mid] = {
                "label": labels[mid],
                "neutral": round(sum(n_vals) / len(n_vals), 4),
                "framed": round(sum(f_vals) / len(f_vals), 4),
                "gap": d["diff"], "lo": d["lo"], "hi": d["hi"], "p": d["p"],
                "n_items": len(shared),
                "n_items_neutral_only": len(set(n_map) - set(f_map)),
                "n_items_framed_only": len(set(f_map) - set(n_map)),
            }
        mids = list(rows)
        for mid, p in zip(mids, stx.holm_bonferroni([rows[m]["p"] for m in mids])):
            rows[mid]["p_holm"] = p
            rows[mid]["significant_holm"] = bool(p < (1 - ci))
        out[track] = rows
    return out


def render(result: dict, meta: dict) -> str:
    L = [f"# {active_pack().report_title}: framed against neutral\n",
         f"_Neutral run: `{meta['neutral']}` · framed run: `{meta['framed']}` · "
         f"{meta['n_boot']:,} bootstrap resamples · seed {meta['seed']}_\n",
         "The framed run adds one sentence to the system prompt:\n",
         f"> {meta['instruction']}\n",
         "Gap is framed minus neutral, over the items both runs scored. A positive "
         "gap means the model answers better when told which tradition to answer "
         "from. These figures are a separate measurement and are not part of the "
         "standings.\n"]
    titles = {"mc": ("Multiple choice (accuracy, 0–1)", ".3f"),
              "open": ("Open-ended (composite, 0–100)", ".1f")}
    for track, (title, spec) in titles.items():
        rows = result.get(track)
        if not rows:
            continue
        L.append(f"\n## {title}\n")
        L.append("| Model | Neutral | Framed | Gap | 95% CI | Holm p | Items |")
        L.append("|---|---|---|---|---|---|---|")
        for mid, r in sorted(rows.items(), key=lambda kv: -kv[1]["gap"]):
            star = " \\*" if r["significant_holm"] else ""
            L.append(f"| {r['label']} | {r['neutral']:{spec}} | {r['framed']:{spec}} | "
                     f"{r['gap']:+{spec}}{star} | [{r['lo']:+{spec}}, {r['hi']:+{spec}}] | "
                     f"{r['p_holm']:.4f} | {r['n_items']} |")
        L.append("\n_\\* significant after Holm correction across the models in "
                 "this table._\n")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neutral", required=True, help="neutral run dir (the standings)")
    ap.add_argument("--framed", required=True, help="framed run dir")
    ap.add_argument("--out", default="", help="default <pack.results_dir>/framing.json")
    ap.add_argument("--report", default="", help="default <pack.reports_dir>/FRAMING.md")
    a = ap.parse_args()
    pack = active_pack()
    if not pack.framed_instruction:
        raise SystemExit(f"error: pack {pack.key!r} defines no framed_instruction")
    run_cfg = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())
    cohort = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text())["cohort"]
    st = run_cfg["stats"]
    seed, n_boot, ci = st["rng_seed"], st["bootstrap_resamples"], st["ci_level"]
    result = compare(Path(a.neutral), Path(a.framed), cohort, seed, n_boot, ci)
    if not result:
        raise SystemExit("error: no track has both a neutral and a framed record file")
    meta = {"neutral": a.neutral, "framed": a.framed, "seed": seed, "n_boot": n_boot,
            "ci_level": ci, "pack": pack.key, "instruction": pack.framed_instruction}
    out = ROOT / (a.out or f"{pack.results_dir}/framing.json")
    rep = ROOT / (a.report or f"{pack.reports_dir}/FRAMING.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    rep.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, **result}, indent=1, ensure_ascii=False) + "\n")
    rep.write_text(render(result, meta))
    print(f"wrote {out} and {rep}")


if __name__ == "__main__":
    main()
