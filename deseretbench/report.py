"""Generate the DeseretBench leaderboard report from results/summary.json.

Outputs:
  reports/figures/radar_dimensions.png   (per-model MC dimension radar)
  reports/figures/difficulty_bars.png    (MC accuracy by difficulty tier)
  reports/figures/overall_ci.png         (overall MC accuracy with 95% CI)
  reports/figures/generational.png       (MC within-tier generational progression)
  reports/figures/open_overall_ci.png    (open-ended composite with 95% CI)
  reports/figures/open_generational.png  (open-ended within-tier progression)
  reports/figures/mc_vs_open.png         (MC vs open-ended, all models)
  reports/figures/scaling_by_size.png    (score vs parameter count, local cohort)
  reports/RESULTS.md                     (auto tables incl. pairwise significance)
  reports/leaderboard.html               (static site)
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
import numpy as np  # noqa: E402

from .packs import active_pack  # noqa: E402

# Sequential colormap for the many-model figures (radar, difficulty bars), where
# each model needs a distinct hue along the rank order. Spans the territorial
# palette — deep oxblood through honey and sage to navy — so a 23-line chart
# stays on-brand instead of dropping matplotlib's purple-anchored viridis onto
# the warm home-page canvas.
SEQ_CMAP = LinearSegmentedColormap.from_list(
    "territorial", ["#6f2416", "#a83e2b", "#bd8228", "#c9a24a", "#6c7a53", "#33456b"])

# Territorial canvas — the figures are embedded both here and on the home page,
# whose background is warm paper (--paper #f4ead6). Matching the matplotlib
# facecolor lets each PNG sit *in* the page instead of floating on a white card.
# Cosmetic only; nothing in the data or stats path reads these.
plt.rcParams.update({
    "figure.facecolor": "#f4ead6",
    "figure.edgecolor": "#f4ead6",
    "axes.facecolor": "#faf3e4",
    "savefig.facecolor": "#f4ead6",
    "savefig.edgecolor": "#f4ead6",
    "text.color": "#2a2018",
    "axes.labelcolor": "#2a2018",
    "axes.titlecolor": "#2a2018",
    "axes.edgecolor": "#8a7455",
    "xtick.color": "#5b4a37",
    "ytick.color": "#5b4a37",
    "grid.color": "#d9c49b",
    "legend.facecolor": "#faf3e4",
    "legend.edgecolor": "#caae7c",
    "font.family": "serif",
})

ROOT = Path(__file__).resolve().parent.parent

# Tradition-specific report framing comes from the active faith pack: the
# wordmark and banner blurb, the radar's dimension order + short labels, and the
# output directory (the LDS pack keeps the legacy reports/, other packs get
# reports/<key>/ so a second run never overwrites the first).
_PACK = active_pack()
TITLE = _PACK.report_title
BLURB = _PACK.report_blurb
REPORTS = ROOT / _PACK.reports_dir
FIG = REPORTS / "figures"

DIM_ORDER = list(_PACK.dim_order)
DIM_SHORT = dict(_PACK.dim_short)
DIFF_ORDER = ["basic", "intermediate", "advanced", "expert"]
TIER_COLOR = {"fable": "#7a4e6d", "opus": "#9a681c", "sonnet": "#33456b",
              "haiku": "#8a2f1e",
              # local open-weights tiers (one per model family; generation =
              # parameter count in B, so per-tier lines read as scaling curves).
              # Warm, earthy hues that stay legible on the paper canvas.
              "qwen3": "#a83e2b", "gemma": "#2f6f6a", "phi": "#6b4a34",
              "smollm": "#a35d7a", "deepseek": "#55606b",
              # 2026 additions (ADR-0013). Newer generations keep a hue close to
              # their predecessor so qwen3/qwen3.5 (terracottas) and gemma/gemma4
              # (teals) read as kin.
              "qwen3.5": "#c9663f", "gemma4": "#5a9e97", "granite": "#7d7a2c",
              "ministral": "#c07a1e", "nemotron": "#5f7d1f"}
TIER_ORDER = ("fable", "opus", "sonnet", "haiku",
              "qwen3", "qwen3.5", "gemma", "gemma4", "phi", "smollm",
              "deepseek", "granite", "ministral", "nemotron")


def tier_color(tier: str) -> str:
    """Colour for a tier, never raising. A cohort can gain a family at any time
    (ADR-0013 added five at once); an unmapped tier must degrade to grey rather
    than crash report generation half-way through rendering."""
    return TIER_COLOR.get(tier, "#888")


def _ordered_models(overall):
    return [mid for mid, _ in sorted(overall.items(),
                                     key=lambda kv: -(kv[1]["mean"] or 0))]


def _fmt(v, spec=".3f", none="–"):
    return format(v, spec) if v is not None else none


def radar(summary):
    mc = summary["mc"]
    overall = mc["overall"]
    models = _ordered_models(overall)
    angles = np.linspace(0, 2 * np.pi, len(DIM_ORDER), endpoint=False).tolist()
    angles += angles[:1]
    fig = plt.figure(figsize=(8, 8))
    ax = plt.subplot(111, polar=True)
    cmap = SEQ_CMAP(np.linspace(0, 0.95, len(models)))
    for mid, col in zip(models, cmap):
        vals = []
        for d in DIM_ORDER:
            cell = mc["by_dimension"].get(mid, {}).get(d)
            # missing data plots as a gap, never as a zero score
            vals.append(cell["mean"] if cell and cell["mean"] is not None else np.nan)
        vals += vals[:1]
        ax.plot(angles, vals, label=overall[mid]["label"], color=col, linewidth=2)
        ax.fill(angles, vals, color=col, alpha=0.05)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([DIM_SHORT[d] for d in DIM_ORDER], fontsize=10)
    ax.set_ylim(0, 1)
    ax.set_title(f"{TITLE} — MC accuracy by dimension", fontsize=13, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.10), fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "radar_dimensions.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def difficulty_bars(summary):
    mc = summary["mc"]
    overall = mc["overall"]
    models = _ordered_models(overall)
    x = np.arange(len(DIFF_ORDER))
    w = 0.8 / max(1, len(models))
    fig, ax = plt.subplots(figsize=(10, 5))
    cmap = SEQ_CMAP(np.linspace(0, 0.95, len(models)))
    for k, (mid, col) in enumerate(zip(models, cmap)):
        vals = [(mc["by_difficulty"].get(mid, {}).get(d) or {}).get("mean") for d in DIFF_ORDER]
        vals = [v if v is not None else np.nan for v in vals]  # gap, not zero
        ax.bar(x + k * w, vals, w, label=overall[mid]["label"], color=col)
    ax.set_xticks(x + 0.4 - w / 2)
    ax.set_xticklabels([d.capitalize() for d in DIFF_ORDER])
    ax.set_ylabel("Accuracy")
    ax.set_ylim(0, 1)
    ax.set_title(f"{TITLE} — MC accuracy by difficulty tier")
    ax.legend(fontsize=8, ncol=3)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "difficulty_bars.png", dpi=120)
    plt.close(fig)


def overall_ci(summary):
    mc = summary["mc"]
    overall = mc["overall"]
    models = [m for m in _ordered_models(overall)
              if overall[m]["mean"] is not None][::-1]
    means = [overall[m]["mean"] for m in models]
    los = [overall[m]["mean"] - overall[m]["lo"] for m in models]
    his = [overall[m]["hi"] - overall[m]["mean"] for m in models]
    labels = [overall[m]["label"] for m in models]
    cols = [tier_color(overall[m]["tier"]) for m in models]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y = np.arange(len(models))
    ax.barh(y, means, xerr=[los, his], color=cols, alpha=0.85, capsize=4)
    for yi, m in zip(y, means):
        ax.text(m + 0.012, yi, f"{m:.3f}", va="center", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Overall MC accuracy (95% bootstrap CI)")
    ax.set_title(f"{TITLE} — overall MC leaderboard")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "overall_ci.png", dpi=120)
    plt.close(fig)


def generational(summary):
    mc = summary["mc"]
    overall = mc["overall"]
    # group by tier, plot mean vs label order
    fig, ax = plt.subplots(figsize=(11, 5))
    for tier in TIER_ORDER:
        ms = [(mid, o) for mid, o in overall.items()
              if o["tier"] == tier and o["mean"] is not None]
        ms.sort(key=lambda kv: (kv[1].get("generation") or 0, kv[1]["label"]))
        if not ms:
            continue
        xs = [o["label"] for _, o in ms]
        ys = [o["mean"] for _, o in ms]
        err = [[o["mean"] - o["lo"] for _, o in ms], [o["hi"] - o["mean"] for _, o in ms]]
        ax.errorbar(xs, ys, yerr=err, marker="o", capsize=4, label=tier.capitalize(),
                    color=tier_color(tier), linewidth=2)
    ax.set_ylabel("Overall MC accuracy")
    ax.set_title("Progression within tier (x is categorical: tiers do not share a scale)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    for lbl in ax.get_xticklabels():
        lbl.set_horizontalalignment("right")
    fig.tight_layout()
    fig.savefig(FIG / "generational.png", dpi=120)
    plt.close(fig)


#: families whose `generation` field is a parameter count in billions, so a
#: numeric size axis is meaningful for them. Claude tiers carry a release
#: generation (4.5, 5.0) in the same field and have no published parameter
#: count — plotting the two on one numeric axis would put Qwen3 4B (4.0B
#: parameters) next to Opus 4.5 (a version number) as though they were
#: comparable quantities. They are not, so size plots use these tiers only.
# Local families whose `generation` field is a parameter count, so they can be
# placed on a size axis. Matched by EXACT tier equality below — a family missing
# here is silently dropped from the figure, so new cohort entries must be added.
# Single-size families (granite, ministral, nemotron, gemma4) plot as one point
# rather than a curve; that still locates them against the size axis.
SIZED_TIERS = ("qwen3", "qwen3.5", "gemma", "gemma4", "phi", "smollm",
               "deepseek", "granite", "ministral", "nemotron")


def scaling_by_size(summary):
    """Score vs parameter count for the local open-weights cohort.

    Two things are visible here that no per-model bar chart shows: within a
    family, open-ended score scales cleanly with size; across families at the
    same size, it does not.
    """
    mc, op = summary["mc"]["overall"], summary["open"]["overall"]
    if not any(o.get("generation") for o in mc.values() if o["tier"] in SIZED_TIERS):
        return None

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, overall, ylab, title in (
            (axes[0], mc, "MC accuracy", "Multiple choice"),
            (axes[1], op, "Open-ended composite (0–100)", "Open-ended")):
        for tier in SIZED_TIERS:
            pts = [o for o in overall.values()
                   if o["tier"] == tier and o["mean"] is not None
                   and o.get("generation")]
            if not pts:
                continue
            pts.sort(key=lambda o: o["generation"])
            xs = [o["generation"] for o in pts]
            ys = [o["mean"] for o in pts]
            err = [[o["mean"] - o["lo"] for o in pts],
                   [o["hi"] - o["mean"] for o in pts]]
            # a single-point family gets a marker, not a line implying a trend
            style = dict(marker="o", capsize=3, color=tier_color(tier),
                         label=tier.capitalize())
            if len(pts) > 1:
                ax.errorbar(xs, ys, yerr=err, linewidth=2, **style)
                off = (7, -12)      # below the line
            else:
                ax.errorbar(xs, ys, yerr=err, linestyle="none", **style)
                off = (7, 5)        # above — Phi (3.8B) and Gemma 4B (4.0B)
                                    # land on top of each other otherwise
            for o in pts:
                ax.annotate(o["label"], (o["generation"], o["mean"]),
                            textcoords="offset points", xytext=off,
                            fontsize=7, color="#444")
        ax.set_xscale("log")
        ax.set_xticks([0.6, 1, 2, 4])
        ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.set_xlabel("Parameters (billions, log scale)")
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.grid(alpha=0.3)
    axes[1].set_ylim(bottom=-1.5)   # R1-Distill sits at 0.3; keep it off the spine
    axes[0].legend(fontsize=8)
    fig.suptitle("Local open-weights cohort — score vs model size "
                 "(Claude models omitted: no published parameter count)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "scaling_by_size.png", dpi=120)
    plt.close(fig)
    return "scaling_by_size.png"


def mc_vs_open(summary):
    """The two axes against each other, all models.

    MC saturates at the frontier while open-ended keeps separating, so the
    cohort bends into an L: models can share an MC score and differ by 40+
    points of open-ended composite.
    """
    mc, op = summary["mc"]["overall"], summary["open"]["overall"]
    pts = [(m, op[mid]) for mid, m in mc.items()
           if mid in op and m["mean"] is not None and op[mid]["mean"] is not None]
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    for m, o in pts:
        ax.scatter(m["mean"], o["mean"], s=54, zorder=3,
                   color=tier_color(m["tier"]),
                   edgecolor="white", linewidth=0.8)

    # The saturated models pile onto x≈1.0, so labels stack on one another
    # (Fable 5 and Opus 4.7 differ by 0.001 MC and 0.3 composite). Alternate
    # label sides through that cluster — the collision is horizontal, so the
    # fix is too, and no label has to be nudged off its own point.
    SAT = 0.98
    sat = sorted([p for p in pts if p[0]["mean"] >= SAT],
                 key=lambda p: -p[1]["mean"])
    side = {id(p[0]): ("right" if i % 2 else "left") for i, p in enumerate(sat)}
    for m, o in pts:
        left = side.get(id(m), "left") == "left"
        ax.annotate(m["label"], (m["mean"], o["mean"]),
                    textcoords="offset points",
                    xytext=((7, -3) if left else (-7, -3)),
                    ha=("left" if left else "right"),
                    fontsize=7.5, color="#333")
    ax.set_xlabel("MC accuracy")
    ax.set_ylabel("Open-ended composite (0–100)")
    ax.set_title("Recognition vs generation: the two tracks measure different things")
    ax.grid(alpha=0.3)
    ax.set_ylim(-4, 105)
    ax.set_xlim(0.46, 1.10)     # room for labels either side of the x≈1.0 pile-up
    fig.tight_layout()
    fig.savefig(FIG / "mc_vs_open.png", dpi=120)
    plt.close(fig)
    return "mc_vs_open.png"


def open_overall_ci(summary):
    op = summary["open"]
    overall = op["overall"]
    models = [m for m in _ordered_models(overall) if overall[m]["mean"] is not None][::-1]
    means = [overall[m]["mean"] for m in models]
    los = [overall[m]["mean"] - overall[m]["lo"] for m in models]
    his = [overall[m]["hi"] - overall[m]["mean"] for m in models]
    labels = [overall[m]["label"] for m in models]
    cols = [tier_color(overall[m]["tier"]) for m in models]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    y = np.arange(len(models))
    ax.barh(y, means, xerr=[los, his], color=cols, alpha=0.85, capsize=4)
    for yi, mid, m in zip(y, models, means):
        # anchor past the upper whisker so the label never overlaps the CI cap
        ax.text(overall[mid]["hi"] + 1.2, yi, f"{m:.1f}", va="center", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Open-ended judge-panel composite, 0–100 (95% bootstrap CI)")
    ax.set_title(f"{TITLE} — open-ended leaderboard")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "open_overall_ci.png", dpi=120)
    plt.close(fig)


def open_generational(summary):
    op = summary["open"]
    overall = op["overall"]
    fig, ax = plt.subplots(figsize=(11, 5))
    for tier in TIER_ORDER:
        ms = [(mid, o) for mid, o in overall.items()
              if o["tier"] == tier and o["mean"] is not None]
        ms.sort(key=lambda kv: (kv[1].get("generation") or 0, kv[1]["label"]))
        if not ms:
            continue
        xs = [o["label"] for _, o in ms]
        ys = [o["mean"] for _, o in ms]
        err = [[o["mean"] - o["lo"] for _, o in ms], [o["hi"] - o["mean"] for _, o in ms]]
        ax.errorbar(xs, ys, yerr=err, marker="o", capsize=4, label=tier.capitalize(),
                    color=tier_color(tier), linewidth=2)
    ax.set_ylabel("Open-ended composite (0–100)")
    ax.set_title("Open-ended: progression within tier "
                 "(x is categorical: tiers do not share a scale)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    for lbl in ax.get_xticklabels():
        lbl.set_horizontalalignment("right")
    fig.tight_layout()
    fig.savefig(FIG / "open_generational.png", dpi=120)
    plt.close(fig)


def results_md(summary) -> str:
    cfg = summary["config"]
    eff = cfg["effort"]
    rns = cfg["runs"]
    eff_s = f"MC={eff.get('multiple_choice')}, open={eff.get('open_ended')}, judge={eff.get('judge')}"
    rns_s = f"MC×{rns.get('multiple_choice')}, open×{rns.get('open_ended')}"
    prov = cfg.get("provenance", "")
    L = [f"# {TITLE} Results\n",
         f"_Run: `{summary['run']}` · effort ({eff_s}) · runs ({rns_s}) · "
         f"{cfg['bootstrap_resamples']:,} bootstrap resamples · seed {cfg.get('seed')}"
         + (f" · config provenance: {prov}" if prov else "") + "_\n"]
    mc = summary.get("mc")
    if mc:
        L.append("## Multiple-Choice — overall accuracy (95% CI)\n")
        L.append("| Rank | Model | Tier | Accuracy | 95% CI (bootstrap) | 95% CI (exact) "
                 "| Parse-fail | Run SD | n items |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for rank, (mid, o) in enumerate(sorted(mc["overall"].items(),
                                               key=lambda kv: -(kv[1]["mean"] or 0)), 1):
            L.append(f"| {rank} | {o['label']} | {o['tier']} | {_fmt(o['mean'])} | "
                     f"[{_fmt(o['lo'])}, {_fmt(o['hi'])}] | "
                     f"[{_fmt(o.get('cp_lo'))}, {_fmt(o.get('cp_hi'))}] | "
                     f"{_fmt(o['parse_fail_rate'])} | "
                     f"{_fmt(o['mean_within_item_sd'])} | {o['n']} |")
        L.append("\n_At a 100% ceiling the bootstrap interval degenerates to zero "
                 "width; the exact (Clopper–Pearson) column is the honest one there._\n")
        n_art = sum(o.get("served_mismatch_artifact", 0) for o in mc["overall"].values())
        n_gen = sum(o.get("served_mismatch_genuine", 0) for o in mc["overall"].values())
        n_fail = sum(o.get("n_call_failed", 0) for o in mc["overall"].values())
        L.append(f"**Provenance audit:** genuine served-model fallbacks={n_gen} "
                 f"(excluded from scoring) · multi-key extraction artifacts={n_art} "
                 f"(kept; primary model verified by pricing) · failed calls={n_fail} "
                 f"(excluded).\n")
        ia = mc["item_analysis"]
        L.append(f"**Item analysis:** {ia['n_items']} items · mean difficulty p={ia['mean_difficulty_p']} · "
                 f"mean discrimination={ia['mean_discrimination']} "
                 f"(defined for only {ia.get('n_items_with_discrimination', '?')} items — "
                 f"the rest sit at the ceiling) · ceiling (p>.95)={ia['n_ceiling_gt_0.95']} · "
                 f"floor (p<.30)={ia['n_floor_lt_0.30']} · low-discrimination={ia['n_low_discrimination_lt_0.10']}\n")
        L.append("\n### Accuracy by dimension\n")
        models = _ordered_models(mc["overall"])
        L.append("| Model | " + " | ".join(DIM_SHORT[d] for d in DIM_ORDER) + " |")
        L.append("|---|" + "---|" * len(DIM_ORDER))
        for mid in models:
            row = [mc["overall"][mid]["label"]]
            for d in DIM_ORDER:
                c = mc["by_dimension"].get(mid, {}).get(d)
                row.append(f"{c['mean']:.2f}" if c and c["mean"] is not None else "–")
            L.append("| " + " | ".join(row) + " |")
        L.append("\n### Accuracy by difficulty\n")
        L.append("| Model | " + " | ".join(d.capitalize() for d in DIFF_ORDER) + " |")
        L.append("|---|" + "---|" * len(DIFF_ORDER))
        for mid in models:
            row = [mc["overall"][mid]["label"]]
            for d in DIFF_ORDER:
                c = mc["by_difficulty"].get(mid, {}).get(d)
                row.append(f"{c['mean']:.2f}" if c and c["mean"] is not None else "–")
            L.append("| " + " | ".join(row) + " |")
        L.append("\n### Pairwise significance (paired bootstrap on per-item accuracy; "
                 f"Holm-adjusted over the {len(mc['pairwise'])}-comparison family; McNemar)\n")
        L.append("| A | B | Δ (A−B) | 95% CI | p (bootstrap) | p (Holm) | p (McNemar) | significant (Holm) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for pw in sorted(mc["pairwise"], key=lambda x: -abs(x["diff"])):
            sig = "yes" if pw.get("significant_holm") else "no"
            L.append(f"| {pw['a_label']} | {pw['b_label']} | {pw['diff']:+.3f} | "
                     f"[{pw['lo']:+.3f}, {pw['hi']:+.3f}] | {pw['p_bootstrap']:.4f} | "
                     f"{pw.get('p_holm', float('nan')):.4f} | "
                     f"{pw['mcnemar_p']:.4f} | {sig} |")
    op = summary.get("open")
    if op:
        L.append("\n## Open-ended (Life-Choice / Cultural) — judge-panel composite (0–100, 95% CI)\n")
        L.append("| Rank | Model | Composite | 95% CI | Rubric coverage | should-not viol. |")
        L.append("|---|---|---|---|---|---|")
        for rank, (mid, o) in enumerate(sorted(op["overall"].items(), key=lambda kv: -(kv[1]["mean"] or 0)), 1):
            cov = f"{o['mean_must_include_coverage']:.2f}" if o.get("mean_must_include_coverage") is not None else "–"
            vio = f"{o['mean_should_not_violations']:.2f}" if o.get("mean_should_not_violations") is not None else "–"
            L.append(f"| {rank} | {o['label']} | {_fmt(o['mean'], '.1f')} | "
                     f"[{_fmt(o['lo'], '.1f')}, {_fmt(o['hi'], '.1f')}] | {cov} | {vio} |")
        if op.get("pairwise"):
            L.append("\n### Open-ended pairwise significance (paired bootstrap; Holm-adjusted)\n")
            L.append("| A | B | Δ (A−B) | 95% CI | p (bootstrap) | p (Holm) | significant (Holm) |")
            L.append("|---|---|---|---|---|---|---|")
            for pw in sorted(op["pairwise"], key=lambda x: -abs(x["diff"])):
                sig = "yes" if pw.get("significant_holm") else "no"
                L.append(f"| {pw['a_label']} | {pw['b_label']} | {pw['diff']:+.1f} | "
                         f"[{pw['lo']:+.1f}, {pw['hi']:+.1f}] | {pw['p_bootstrap']:.4f} | "
                         f"{pw.get('p_holm', float('nan')):.4f} | {sig} |")
        if op.get("judge_irr"):
            irr = op["judge_irr"]
            per_dim = irr.get("per_dimension_alpha") or {}
            dims_s = ", ".join(f"{k}={v}" for k, v in per_dim.items())
            L.append(f"\n**Judge inter-rater reliability:** Krippendorff's α = "
                     f"{irr['krippendorff_alpha']} on the composite "
                     f"({irr['n_personas']} personas, {irr['n_units']} units)"
                     + (f"; per dimension: {dims_s}" if dims_s else "") + "\n")
    return "\n".join(L) + "\n"


def _inline_md(escaped: str) -> str:
    """Bold + code on an already-HTML-escaped string. NO generic italic rule:
    a `_(.+?)_` regex eats underscores inside identifiers like runs/v0_1 and
    corrupts the markup (shipped bug in v0.1's leaderboard.html)."""
    import re
    txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    txt = re.sub(r"`(.+?)`", r"<code>\1</code>", txt)
    return txt


def html(summary, figs: list[str] | None = None) -> str:
    md = results_md(summary)
    # Embed only figures this invocation regenerated — a PNG left on disk by
    # an earlier run may not match this summary.
    figs = figs or []
    fig_html = "".join(
        f'<figure><img src="figures/{f}" alt="{f}"></figure>' for f in figs
        if (FIG / f).exists())
    body_lines, in_table = [], False
    for raw in md.splitlines():
        ln = html_mod.escape(raw, quote=False)
        if ln.startswith("# "):
            body_lines.append(f"<h1>{_inline_md(ln[2:])}</h1>")
        elif ln.startswith("## "):
            body_lines.append(f"<h2>{_inline_md(ln[3:])}</h2>")
        elif ln.startswith("### "):
            body_lines.append(f"<h3>{_inline_md(ln[4:])}</h3>")
        elif ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                body_lines.append("<table>")
                in_table = True
            body_lines.append("<tr>" + "".join(f"<{tag}>{_inline_md(c)}</{tag}>"
                                               for c in cells) + "</tr>")
        else:
            if in_table:
                body_lines.append("</table>")
                in_table = False
            txt = ln.strip()
            # full-line italic (the only italic results_md emits)
            if txt.startswith("_") and txt.endswith("_") and len(txt) > 2:
                body_lines.append(f"<p><i>{_inline_md(txt[1:-1])}</i></p>")
            elif txt:
                body_lines.append(f"<p>{_inline_md(ln)}</p>")
    if in_table:
        body_lines.append("</table>")
    body = "\n".join(body_lines)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE} Leaderboard</title>
<style>
:root{{
  --paper:#f4ead6; --paper-2:#faf3e4; --paper-3:#efe1c6;
  --ink:#2a2018; --ink-2:#5b4a37; --oxblood:#8a2f1e; --honey:#bd8228;
  --rule:#d9c49b;
  --serif:"Iowan Old Style","Palatino Linotype","Book Antiqua",Palatino,"URW Palladio L",Charter,Georgia,Cambria,serif;
  --mono:"SF Mono",ui-monospace,"DejaVu Sans Mono",Menlo,Consolas,monospace;
}}
body{{font-family:var(--serif);max-width:62rem;margin:2.5rem auto;padding:0 1.2rem;
color:var(--ink);background:var(--paper);line-height:1.6}}
h1{{font-weight:700;border-bottom:3px double var(--oxblood);padding-bottom:.3rem}}
h2{{margin-top:2.4rem;color:var(--oxblood);font-weight:700}} h3{{color:var(--ink-2)}}
a{{color:var(--oxblood)}}
table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.92rem}}
th,td{{border:1px solid var(--rule);padding:.4rem .6rem;text-align:left}}
th{{background:var(--oxblood);color:var(--paper-2)}} tr:nth-child(even){{background:var(--paper-3)}}
figure{{margin:1.5rem 0;text-align:center}} img{{max-width:100%;border:1px solid var(--rule);border-radius:6px}}
code{{background:var(--paper-3);padding:.1rem .3rem;border-radius:4px;font-family:var(--mono);font-size:.86em}}
.banner{{background:var(--paper-2);border-left:4px solid var(--honey);padding:.8rem 1rem;border-radius:0 6px 6px 0}}
hr{{border:0;border-top:1px solid var(--rule)}}
</style></head><body>
<div class="banner"><b>{TITLE}</b> — {BLURB}. Scores measure
representation of the mainstream, official position (see DESIGN.md §2 for framing).</div>
{fig_html}
{body}
<hr><p style="color:#888;font-size:.85rem">Generated by <code>deseretbench.report</code>.
Framing, methodology, and limitations: see <code>DESIGN.md</code>. Data license CC BY-NC-SA 4.0.</p>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="results/summary.json")
    args = ap.parse_args()
    summary = json.loads((ROOT / args.summary).read_text())
    FIG.mkdir(parents=True, exist_ok=True)
    figs = []
    if "mc" in summary:
        radar(summary); difficulty_bars(summary); overall_ci(summary); generational(summary)
        figs += ["overall_ci.png", "radar_dimensions.png",
                 "difficulty_bars.png", "generational.png"]
    if summary.get("open"):
        open_overall_ci(summary); open_generational(summary)
        figs = ["open_overall_ci.png", "open_generational.png"] + figs
        # cross-track and size views need both phases present
        if "mc" in summary:
            lead = [mc_vs_open(summary)]
            sized = scaling_by_size(summary)   # None when no cohort entry has a size
            if sized:
                lead.append(sized)
            figs = lead + figs
    (REPORTS / "RESULTS.md").write_text(results_md(summary), encoding="utf-8")
    (REPORTS / "leaderboard.html").write_text(html(summary, figs), encoding="utf-8")
    print(f"wrote reports/RESULTS.md, reports/leaderboard.html, and "
          f"{len(figs)} figure(s): {', '.join(figs)}")


if __name__ == "__main__":
    main()
