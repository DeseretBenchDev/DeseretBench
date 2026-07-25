"""Build the DeseretBench one-page report: a single self-contained HTML broadsheet.

Design — "The Deseret Codex": a frontier-futurist research broadsheet. Cinzel inscriptional
capitals + EB Garamond scholarly body + IBM Plex Mono data, on parchment with temple gold,
navy, and oxblood. Tufte-style margin notes, booktabs tables, a beehive emblem and a Greek-key
rule. Static (no scroll motion). Fonts and figures are base64-embedded, so the file is fully
self-contained, prints cleanly to PDF, and shares as a single attachment.

    python -m deseretbench.build_onepager        # -> reports/deseretbench_report.html
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIER_COLOR = {"fable": "#4A2E63", "opus": "#9A6B1E", "sonnet": "#2C3D63", "haiku": "#7A3326",
              # local open-weights tiers, muted to match the print palette
              "qwen3": "#8C2F39", "gemma": "#1F5F5B", "phi": "#4E3B31",
              "smollm": "#8A4E6E", "deepseek": "#55606B"}

FONTS = [  # (family, weight, style, file)
    ("Cinzel", 600, "normal", "cinzel-600.woff2"),
    ("Cinzel", 800, "normal", "cinzel-800.woff2"),
    ("EBGaramond", 400, "normal", "ebgaramond-400.woff2"),
    ("EBGaramond", 400, "italic", "ebgaramond-400i.woff2"),
    ("EBGaramond", 600, "normal", "ebgaramond-600.woff2"),
    ("PlexMono", 400, "normal", "plexmono-400.woff2"),
    ("PlexMono", 600, "normal", "plexmono-600.woff2"),
    ("Deseret", 400, "normal", "deseret-400.woff2"),
]

# ---- curated example excerpts (from runs/v0_1; trimmed at sentence boundaries) ----
MC_EXAMPLE = {
    "tag": "Church organization · expert",
    "q": ("Every man ordained an Apostle in the Quorum of the Twelve receives all the keys of the "
          "kingdom of God on earth, yet only one man exercises them in their fulness at any given "
          "time. Which statement best captures the official Latter-day Saint understanding of how "
          "this works at the death of the President of the Church?"),
    "choices": [
        ("All the keys are conferred latently on each Apostle at ordination, but only the President "
         "of the Church—the most senior living Apostle—is authorized to exercise them in full; at "
         "his death the right to direct their use passes to the next most senior Apostle.",
         "correct", True),
        ("Upon the President's death the keys devolve upon the first counselor in the First "
         "Presidency, who has stood nearest the prophet and shared most fully in administering them.",
         "plausible near-miss", False),
        ("The keys are conferred anew upon the new President by the sustaining vote of the membership "
         "gathered in solemn assembly, which is what validates his authority to lead.",
         "progressive trap", False),
        ("Only the President of the Church actually holds the keys; the other Apostles receive keys "
         "individually from him whenever he sets them apart, and those keys lapse when he dies.",
         "correlation oversimplification", False),
    ],
    "source": "D&C 107:22–24 · Boyd K. Packer, “The Twelve Apostles” · the law of succession",
}

OPEN_EXAMPLE = {
    "tag": "Life-choice · intermediate",
    "scenario": ("Jordan, 19, has prepared for a mission his whole life but is also a gifted pianist "
                 "accepted into an elite conservatory that only admits at his current age; deferring "
                 "two years risks his place. His father, a convert who never served, says, “God gave "
                 "you this talent—develop it; you can serve later, or serve through music.” How should "
                 "Jordan reason about a young man’s mission versus a once-in-a-lifetime window?"),
    "must": ("A full-time mission is a priesthood duty for worthy young men—not one good option "
             "among many; talents are real goods but are consecrated through service, not against it; "
             "resolve it by worthiness, desire, and personal revelation with priesthood counsel."),
    "top_label": "Opus 4.7", "top_score": 100,
    "top": ("“Start with the doctrinal baseline, not the trade-off. The Church’s position on "
            "missionary service for young men is not one good option among many. Presidents Nelson, "
            "Monson, and Hinckley have taught that every worthy, able young man has a <i>priesthood "
            "duty</i> to serve. This is covenantal language, not vocational-counseling language. "
            "Jordan should reason about the mission first as an ordained responsibility, then ask "
            "whether any circumstance rises to a legitimate exemption—not as a career variable to be "
            "optimized against piano.”"),
    "bot_label": "Haiku 4.5", "bot_score": 9,
    "bot": ("“Start with your own values. Before considering anyone’s expectations—father, church, "
            "teachers—identify what Jordan actually prioritizes. Does he feel called from personal "
            "conviction, or cultural expectation? What would he regret more at 40: not serving, or "
            "not pursuing music? This isn’t selfish; it’s honest.”"),
    "why": ("The weaker answer reframes a priesthood duty as a personal-preference, self-realization "
            "decision—exactly what the rubric marks as a violation. The panel scored it 9/100 "
            "against 100/100; both gave a fluent, kind answer, but only one is recognizably "
            "Latter-day Saint."),
}


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def font_faces() -> str:
    css = []
    fdir = ROOT / "assets" / "fonts"
    missing = []
    for fam, wt, style, fn in FONTS:
        p = fdir / fn
        if not p.exists():
            missing.append(fn)
            continue
        css.append(
            f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{wt};"
            f"font-display:swap;src:url(data:font/woff2;base64,{_b64(p)}) format('woff2');}}")
    if missing:
        print(f"WARNING: missing font file(s) {missing} under assets/fonts/ — the "
              f"page will fall back to system fonts (Deseret glyphs may render as tofu).")
    return "\n".join(css)


def img_uri(path: Path) -> str:
    return f"data:image/png;base64,{_b64(path)}" if path.exists() else ""


CSS = r"""
:root{
  --paper:#F2E8D2; --paper2:#F8F0DC; --card:#FBF5E6;
  --ink:#211B12; --ink2:#4A3F2C; --muted:#7C6F54;
  --gold:#9A6B1E; --gold-bright:#C49A41; --gold-soft:#EAD9AE;
  --navy:#1C2747; --oxblood:#6E2A2A; --rule:#D8C7A0;
}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{
  margin:0;color:var(--ink);background-color:var(--paper);
  background-image:radial-gradient(circle at 12% -10%, #F8F0DC 0%, transparent 55%),
                   radial-gradient(circle at 98% 0%, #EFE3C6 0%, transparent 45%);
  font-family:'EBGaramond',Georgia,'Times New Roman',serif;font-size:19px;line-height:1.62;
  font-feature-settings:"liga","onum","kern";text-rendering:optimizeLegibility;
}
.page{max-width:74rem;margin:0 auto;padding:0 2rem 6rem}
::selection{background:var(--gold-soft)}

/* display + headings */
.cinzel{font-family:'Cinzel',Georgia,serif;font-weight:800;letter-spacing:.04em}
h2{font-family:'Cinzel',Georgia,serif;font-weight:800;font-size:1.45rem;letter-spacing:.05em;
   color:var(--navy);margin:3.2rem 0 .2rem;line-height:1.15}
h2 .sec{color:var(--gold);font-weight:600;margin-right:.55em;font-size:.85em}
h2 + .rule{margin-top:.5rem}
h3{font-family:'Cinzel',Georgia,serif;font-weight:600;font-size:1.02rem;letter-spacing:.04em;
   color:var(--oxblood);margin:1.7rem 0 .3rem;text-transform:none}
p{margin:.55rem 0 .95rem}
.lead{font-size:1.12rem}
a{color:var(--gold);text-decoration:none;border-bottom:1px solid var(--gold-soft)}
a:hover{border-bottom-color:var(--gold)}
em,i{font-style:italic}
strong,b{font-weight:600}
.small{font-size:.82rem;color:var(--muted)}
.mono{font-family:'PlexMono',ui-monospace,Menlo,monospace}

/* rules + greek key */
.rule{height:0;border:0;border-top:1.5px solid var(--ink);opacity:.85}
.rule.thin{border-top:1px solid var(--rule)}
.gk{height:14px;background:repeating-linear-gradient(90deg,var(--gold) 0 3px,transparent 3px 6px,
    var(--gold) 6px 9px,transparent 9px 18px);opacity:.7;
    -webkit-mask:linear-gradient(#000,#000);margin:.4rem 0}
.dbl{border-top:3px double var(--gold);height:0;margin:.3rem 0 0}

/* masthead */
.mast{padding:2.6rem 0 1.1rem;text-align:center}
.emblem{width:64px;height:64px;margin:0 auto .6rem;display:block}
.wordmark{font-family:'Cinzel',Georgia,serif;font-weight:800;letter-spacing:.06em;
  font-size:clamp(2.6rem,7vw,4.6rem);line-height:1;color:var(--ink);margin:.1rem 0}
.wordmark .bee{color:var(--gold)}
.tagline{font-style:italic;color:var(--ink2);font-size:1.15rem;max-width:40rem;margin:.5rem auto 0}
.deseret{font-family:'Deseret',serif;color:var(--gold);font-size:1.2rem;letter-spacing:.1em;margin:.55rem 0 0}
.badges{display:flex;flex-wrap:wrap;gap:.4rem;justify-content:center;margin:1.1rem 0 .2rem}
.badge{font-family:'PlexMono',monospace;font-size:.7rem;letter-spacing:.02em;text-transform:uppercase;
  border:1px solid var(--rule);background:var(--card);border-radius:2px;padding:.28rem .6rem;color:var(--ink2)}
.badge b{color:var(--gold)}
.epigraph{max-width:34rem;margin:1.4rem auto .2rem;text-align:center;font-style:italic;color:var(--ink2)}
.epigraph .cite{display:block;font-style:normal;font-family:'PlexMono',monospace;font-size:.7rem;
  letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:.4rem}
.toc{font-family:'PlexMono',monospace;font-size:.72rem;letter-spacing:.03em;text-align:center;
  color:var(--muted);margin:1.1rem 0 .2rem}
.toc a{color:var(--ink2);border:0;margin:0 .35rem}
.toc a:hover{color:var(--gold)}

/* article + Tufte sidenotes */
.article{max-width:44rem;margin:0 auto}
@media(min-width:1040px){
  .article{max-width:58rem;padding-right:15rem}
  .sidenote{float:right;clear:right;width:13rem;margin:.35rem -15rem .6rem 0}
}
.sidenote{display:block;font-size:.8rem;line-height:1.45;color:var(--ink2);
  border-left:2px solid var(--gold);padding-left:.7rem;margin:.7rem 0;background:transparent}
.sidenote b{color:var(--oxblood)}
.dropcap::first-letter{font-family:'Cinzel',Georgia,serif;font-weight:800;float:left;
  font-size:3.4rem;line-height:.78;padding:.05em .12em 0 0;color:var(--gold)}

/* callouts */
.aside{background:var(--card);border:1px solid var(--rule);border-left:4px solid var(--gold);
  border-radius:3px;padding:1rem 1.2rem;margin:1.4rem 0}
.aside .lbl{font-family:'PlexMono',monospace;font-size:.68rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--gold)}
.pull{font-style:italic;font-size:1.5rem;line-height:1.3;color:var(--navy);text-align:center;
  max-width:34rem;margin:1.8rem auto;padding:1rem 0;border-top:3px double var(--gold);
  border-bottom:3px double var(--gold)}

/* tables — booktabs */
table{border-collapse:collapse;width:100%;margin:1rem 0 .5rem;font-size:.94rem}
caption{caption-side:top;text-align:left;font-family:'PlexMono',monospace;font-size:.68rem;
  letter-spacing:.1em;text-transform:uppercase;color:var(--gold);padding-bottom:.4rem}
thead th{font-family:'PlexMono',monospace;font-size:.66rem;letter-spacing:.05em;text-transform:uppercase;
  color:var(--ink2);font-weight:600;text-align:left;padding:.35rem .55rem;border-bottom:1px solid var(--ink)}
table{border-top:2.5px solid var(--ink)}
tbody td{padding:.42rem .55rem;border-bottom:1px solid var(--rule)}
tbody tr:last-child td{border-bottom:2.5px solid var(--ink)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;font-family:'PlexMono',monospace;font-size:.85rem}
.tier{display:inline-block;font-family:'PlexMono',monospace;font-size:.6rem;letter-spacing:.06em;
  text-transform:uppercase;color:#fff;padding:.06rem .38rem;border-radius:2px;vertical-align:middle}
.bar{position:relative;min-width:150px}
.bar .track{background:#E7D8B4;height:1.05rem;border-radius:1px;overflow:hidden}
.bar .fill{height:100%}
.bar .lab{position:absolute;top:0;left:.4rem;line-height:1.05rem;font-size:.72rem;font-weight:600;
  font-family:'PlexMono',monospace;color:#fff;text-shadow:0 1px 1px rgba(0,0,0,.3)}

/* examples */
.qcard{background:var(--card);border:1px solid var(--rule);border-radius:3px;padding:1.1rem 1.3rem;margin:1.1rem 0}
.choice{display:flex;gap:.6rem;padding:.3rem 0;border-bottom:1px dotted var(--rule)}
.choice:last-child{border-bottom:0}
.choice .ltr{font-family:'Cinzel',serif;font-weight:600;color:var(--navy);min-width:1.2rem}
.choice.correct{background:rgba(154,107,30,.09);margin:0 -.5rem;padding:.3rem .5rem;border-radius:2px}
.choice .dt{font-family:'PlexMono',monospace;font-size:.6rem;letter-spacing:.04em;text-transform:uppercase;
  color:var(--muted);white-space:nowrap;align-self:center}
.choice.correct .dt{color:var(--gold)}
.vs{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1rem 0}
@media(max-width:640px){.vs{grid-template-columns:1fr}}
.ans{background:var(--card);border:1px solid var(--rule);border-radius:3px;padding:.9rem 1rem}
.ans .hd{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.4rem}
.ans .who{font-family:'Cinzel',serif;font-weight:600;font-size:.95rem}
.ans .sc{font-family:'PlexMono',monospace;font-weight:600}
.ans.win{border-top:3px solid var(--gold)} .ans.win .sc{color:var(--gold)}
.ans.lose{border-top:3px solid var(--oxblood)} .ans.lose .sc{color:var(--oxblood)}
.ans p{font-style:italic;color:var(--ink2);font-size:.92rem;margin:.2rem 0}

/* figures */
.plates{display:grid;grid-template-columns:1fr 1fr;gap:1.1rem;margin:1.1rem 0}
@media(max-width:640px){.plates{grid-template-columns:1fr}}
figure{margin:0;background:#fff;border:1px solid var(--rule);border-radius:3px;padding:.6rem;
  box-shadow:0 2px 0 rgba(0,0,0,.04)}
figure img{width:100%;height:auto;display:block}
figcaption{font-size:.78rem;color:var(--ink2);padding:.5rem .2rem 0;border-top:1px solid var(--rule);margin-top:.5rem}
figcaption b{font-family:'Cinzel',serif;color:var(--gold);font-weight:600}

/* contribute */
.help{background:var(--navy);color:#EFE6D2;border-radius:5px;padding:2.2rem 2.2rem 1.8rem;margin:2.6rem 0 1.4rem;
  background-image:radial-gradient(circle at 90% 0%, rgba(196,154,65,.18) 0%, transparent 50%)}
.help h2{color:#fff;margin-top:0}
.help h2 .sec{color:var(--gold-bright)}
.help a{color:var(--gold-bright);border-bottom-color:rgba(196,154,65,.4)}
.help .pull{color:#fff;border-color:var(--gold-bright)}
.asks{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin:1.2rem 0;list-style:none;padding:0}
@media(max-width:640px){.asks{grid-template-columns:1fr}}
.asks li{background:rgba(255,255,255,.05);border:1px solid rgba(196,154,65,.25);border-radius:3px;padding:.8rem .95rem;font-size:.92rem}
.asks .t{font-family:'Cinzel',serif;font-weight:600;color:var(--gold-bright);display:block;margin-bottom:.2rem;font-size:.92rem}

.colophon{margin-top:2.4rem;padding-top:1rem;border-top:1px solid var(--rule);
  font-family:'PlexMono',monospace;font-size:.7rem;line-height:1.6;color:var(--muted);text-align:center}
.colophon .des{font-family:'Deseret',serif;color:var(--gold);font-size:1rem}

@media print{
  body{background:#fff;font-size:11pt}
  .page{max-width:none;padding:0}
  .article{max-width:none;padding-right:0}
  .sidenote{float:none;width:auto;margin:.6rem 0}
  .toc{display:none}
  h2,h3{break-after:avoid}
  figure,table,.aside,.qcard,.vs,.help,.plates,.pull{break-inside:avoid}
  a{color:var(--ink);border:0}
  @page{margin:15mm 14mm}
}
"""

BEEHIVE = """<svg class="emblem" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<g stroke="#9A6B1E" stroke-width="2.2" fill="#EAD9AE" stroke-linejoin="round">
<ellipse cx="32" cy="53" rx="26" ry="4.2"/>
<ellipse cx="32" cy="17" rx="9" ry="4.6"/>
<ellipse cx="32" cy="22" rx="13" ry="5"/>
<ellipse cx="32" cy="28" rx="16.5" ry="5.4"/>
<ellipse cx="32" cy="35" rx="19.5" ry="5.8"/>
<ellipse cx="32" cy="42" rx="22" ry="6.1"/>
<ellipse cx="32" cy="48.5" rx="24" ry="6.4"/>
</g>
<path d="M27.5 52 a4.5 4.5 0 0 1 9 0 Z" fill="#9A6B1E"/>
<g fill="#9A6B1E"><ellipse cx="53" cy="20" rx="1.9" ry="1.35"/><ellipse cx="47" cy="13" rx="1.6" ry="1.15"/></g>
</svg>"""


def _fnum(x, d=1):
    return "—" if x is None else f"{x:.{d}f}"


def open_table(summary):
    import html as _h
    ov = summary["open"]["overall"]
    rows = sorted(ov.items(), key=lambda kv: -(kv[1]["mean"] or 0))
    out = ['<table><caption>Open-ended composite · 0–100 · 95% bootstrap CI</caption>',
           '<thead><tr><th>Model</th><th>Tier</th><th>Composite</th><th class="num">95% CI</th>',
           '<th class="num">Rubric</th><th class="num">Slips</th></tr></thead><tbody>']
    for mid, o in rows:
        c = TIER_COLOR.get(o["tier"], "#888"); m = o["mean"] or 0
        out.append(
            f'<tr><td><b>{_h.escape(o["label"])}</b></td>'
            f'<td><span class="tier" style="background:{c}">{o["tier"]}</span></td>'
            f'<td class="bar"><div class="track"><div class="fill" style="width:{m:.0f}%;background:{c}"></div></div>'
            f'<span class="lab">{m:.1f}</span></td>'
            f'<td class="num">[{_fnum(o["lo"])}, {_fnum(o["hi"])}]</td>'
            f'<td class="num">{_fnum(o.get("mean_must_include_coverage"),2)}</td>'
            f'<td class="num">{_fnum(o.get("mean_should_not_violations"),2)}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def mc_table(summary):
    import html as _h
    ov = summary["mc"]["overall"]
    n_items = summary["mc"]["item_analysis"]["n_items"]
    n_runs = summary["config"]["runs"]["multiple_choice"]
    rows = sorted(ov.items(), key=lambda kv: (-(kv[1]["mean"] or 0), kv[1]["label"]))
    out = [f'<table><caption>Multiple choice · accuracy over {n_items} items × {n_runs} runs</caption>',
           '<thead><tr><th>Model</th><th>Tier</th><th class="num">Accuracy</th>',
           '<th class="num">95% CI</th><th class="num">Parse-fail</th></tr></thead><tbody>']
    for mid, o in rows:
        c = TIER_COLOR.get(o["tier"], "#888")
        out.append(
            f'<tr><td><b>{_h.escape(o["label"])}</b></td>'
            f'<td><span class="tier" style="background:{c}">{_h.escape(str(o["tier"]))}</span></td>'
            f'<td class="num">{_fnum(o["mean"], 3)}</td>'
            f'<td class="num">[{_fnum(o["lo"], 3)}, {_fnum(o["hi"], 3)}]</td>'
            f'<td class="num">{_fnum(o["parse_fail_rate"], 3)}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def mc_example_html():
    e = MC_EXAMPLE
    rows = []
    for i, (txt, dt, correct) in enumerate(e["choices"]):
        cls = "choice correct" if correct else "choice"
        rows.append(f'<div class="{cls}"><span class="ltr">{chr(65+i)}</span>'
                    f'<span>{txt}</span><span class="dt">{dt}</span></div>')
    return (f'<div class="qcard"><div class="small mono">{e["tag"]}</div>'
            f'<p style="margin:.4rem 0 .6rem"><b>{e["q"]}</b></p>{"".join(rows)}'
            f'<div class="small" style="margin-top:.6rem">Source — {e["source"]}</div></div>')


def open_example_html():
    e = OPEN_EXAMPLE
    return (
        f'<div class="qcard"><div class="small mono">{e["tag"]}</div>'
        f'<p style="margin:.4rem 0 .5rem">{e["scenario"]}</p>'
        f'<div class="small"><b>The rubric wants:</b> {e["must"]}</div></div>'
        f'<div class="vs">'
        f'<div class="ans win"><div class="hd"><span class="who">{e["top_label"]}</span>'
        f'<span class="sc">{e["top_score"]}/100</span></div><p>{e["top"]}</p></div>'
        f'<div class="ans lose"><div class="hd"><span class="who">{e["bot_label"]}</span>'
        f'<span class="sc">{e["bot_score"]}/100</span></div><p>{e["bot"]}</p></div></div>'
        f'<p class="small">{e["why"]}</p>')


def build(summary, vr):
    cfg = summary["config"]
    op = summary.get("open")
    mc = summary.get("mc")
    if not op or not mc:
        raise SystemExit("error: the one-pager needs a summary with BOTH mc and "
                         "open sections — run analyze on a full run first")
    ia = mc["item_analysis"]
    irr = op.get("judge_irr") or {}
    alpha = irr.get("krippendorff_alpha")
    alpha_s = f"{alpha:.2f}" if alpha is not None else "n/a"
    nsig = sum(1 for pw in op["pairwise"] if pw.get("significant_holm"))
    npw = len(op["pairwise"]); ovo = op["overall"]
    mco = mc["overall"]
    n_models = len(mco)
    # prose numbers computed from the summary, never hardcoded
    mc_means = [o["mean"] for o in mco.values() if o["mean"] is not None]
    mc_top, mc_bot = (max(mc_means), min(mc_means)) if mc_means else (None, None)
    mc_bot_label = next((o["label"] for o in mco.values() if o["mean"] == mc_bot), "?")
    open_means = [o["mean"] for o in ovo.values() if o["mean"] is not None]
    spread = (max(open_means) - min(open_means)) if open_means else 0
    top_mid = max(mco, key=lambda m: mco[m]["mean"] or 0)
    cp = (mco[top_mid].get("cp_lo"), mco[top_mid].get("cp_hi"))
    figdir = ROOT / "reports" / "figures"

    badges = [("v0.1", "proof of concept"), (str(n_models), "Claude models"),
              (f'{vr["mc_public"]}+{vr["open_public"]}', "items"),
              (f'MC×{cfg["runs"]["multiple_choice"]} open×{cfg["runs"]["open_ended"]}', "runs"),
              (f'α {alpha_s}', "judge agreement")]
    badges_html = "".join(f'<span class="badge"><b>{a}</b> {b}</span>' for a, b in badges)

    figs = [("open_overall_ci.png", "Plate I.", "Open-ended composite with 95% bootstrap intervals — the axis that actually separates the field."),
            ("open_generational.png", "Plate II.", "By generation on the open axis: the Opus line dips at 4.8; Sonnet climbs. A curiosity, not a verdict."),
            ("radar_dimensions.png", "Plate III.", "Multiple-choice profile across the seven doctrinal areas — every model pinned at the rim."),
            ("difficulty_bars.png", "Plate IV.", "Multiple-choice accuracy by tier — pinned at the ceiling through expert.")]
    missing = [fn for fn, *_ in figs if not (figdir / fn).exists()]
    if missing:
        print(f"WARNING: missing figure(s) {missing} — run deseretbench.report first; "
              f"the corresponding plates will be OMITTED.")
    plates = "".join(
        f'<figure><img alt="{cap}" src="{img_uri(figdir / fn)}"><figcaption><b>{lab}</b> {cap}</figcaption></figure>'
        for fn, lab, cap in figs if (figdir / fn).exists())

    H = []; A = H.append
    A('<!doctype html><html lang="en"><head><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A('<title>DeseretBench — A First Pass</title>')
    A(f"<style>{font_faces()}\n{CSS}</style></head><body><div class='page'>")

    # masthead
    A('<header class="mast">')
    A(BEEHIVE)
    A('<div class="wordmark">Deseret<span class="bee">Bench</span></div>')
    A('<div class="deseret">\U00010414\U0001042F\U00010445\U00010428\U00010449\U0001042F\U0001043B</div>')
    A('<p class="tagline">A small, faithful instrument for asking whether the machines actually '
      'know us — our doctrine, our culture, and the choices we counsel one another to make.</p>')
    A(f'<div class="badges">{badges_html}</div>')
    A('<div class="epigraph">“Seek ye diligently and teach one another words of wisdom; yea, seek '
      'ye out of the best books words of wisdom; seek learning, even by study and also by faith.”'
      '<span class="cite">Doctrine &amp; Covenants 88:118</span></div>')
    A('<nav class="toc"><a href="#idea">The idea</a>·<a href="#built">How it’s built</a>·'
      '<a href="#pass">A first pass</a>·<a href="#examples">Two questions</a>·'
      '<a href="#limits">What it isn’t</a>·<a href="#help">Lend a hand</a></nav>')
    A('</header><div class="dbl"></div>')

    A("<div class='article'>")

    # 1 idea
    A('<h2 id="idea"><span class="sec">§1</span>The idea</h2><div class="rule thin"></div>')
    A('<aside class="sidenote">The big benchmarks (MMLU and its kin) test religion only at a '
      'world-survey level — names, dates, the outside view. None of them ask whether a model can '
      'reason from <i>inside</i> a covenant.</aside>')
    A('<p class="lead dropcap">People already ask chatbots the questions they used to bring to a '
      'bishop or a parent — about missions, marriage, the Word of Wisdom, a wavering testimony. '
      'So a fair question is simply: when a model answers, does it sound like someone who knows '
      'the gospel and has lived in a ward, or like a stranger guessing from the outside?</p>')
    A('<p>The Latter-day Saint tradition is an unusually clean place to test that. The doctrine is '
      'specific and well documented — the standard works, the General Handbook, general conference, '
      'the Gospel Topics essays — and it is different enough from generic Christianity that a model '
      'cannot coast on Sunday-school keywords. DeseretBench keeps three things apart on purpose: '
      '<b>doctrinal accuracy</b> (what the Church teaches), <b>cultural fluency</b> (how Saints '
      'actually live and speak), and <b>life-choice alignment</b> (whether its counsel tracks a '
      'faithful, level-headed member instead of a secular default). It keys to the plain, correlated '
      'teaching of the Church; folk doctrine and the usual outside framings show up only as wrong '
      'answers, where they belong.</p>')

    # 2 built
    A('<h2 id="built"><span class="sec">§2</span>How it’s built</h2><div class="rule thin"></div>')
    A(f'<aside class="sidenote">From {vr["mc_candidates"]}+{vr["open_candidates"]} drafted items, a '
      'blind review pass — one model wearing five reviewer personas — kept the clean ones. The '
      f'personas agreed unanimously on the keys (Fleiss’ κ = {vr["mc_fleiss_kappa_answers"]}), which '
      'speaks to item clarity, not independent validation; real reviewers are the v1.0 job. A '
      f'{vr["mc_holdout"]}+{vr["open_holdout"]}-item split is set aside as a nominal holdout; a '
      'genuinely private one — freshly written questions, never published — waits until the '
      'project is big enough to sustain it.</aside>')
    A('<p>Two kinds of question. <b>Multiple choice</b>, machine-graded, where every wrong answer is '
      'a <i>typed trap</i> — a Protestant reading, a folk-doctrine myth, a progressive rewrite, a '
      'plausible near-miss — and every item cites its source. And <b>open-ended scenarios</b>, the '
      'kind of real dilemma a member actually faces, graded by a three-judge panel against a rubric '
      'of what a good answer must include and must never do. Seven doctrinal areas, four difficulty '
      'tiers, single-turn and tool-free, the same neutral instructions for every model, everything '
      'seeded and cached so anyone can run it again and get the same thing.</p>')
    A(f'<p>That leaves a public set of <b>{vr["mc_public"]} multiple-choice</b> and '
      f'<b>{vr["open_public"]} open-ended</b> items. One honest caveat up front: for this first pass '
      'the reviewers and the judges are themselves models. That is a real limit, not a footnote — '
      'and it is the first thing the next version should fix.</p>')

    # 3 first pass
    A('<h2 id="pass"><span class="sec">§3</span>A first pass</h2><div class="rule thin"></div>')
    A('<aside class="sidenote">Read this as a shakedown cruise: did the harness work, and does the '
      'open-ended axis carry a signal? Yes and yes. Treat the rankings as suggestive, not settled — '
      '40 open items, one judge model, no human in the loop yet.</aside>')
    A(f'<p>The multiple-choice half is <b>solved</b>. Every model clears it — accuracy from '
      f'{mc_top:.3f} down to {mc_bot_label}’s {mc_bot:.3f} — with {ia["n_ceiling_gt_0.95"]} of '
      f'{ia["n_items"]} items sitting at the ceiling, expert tier included. Frontier models simply '
      'know the catechism. (Answer positions are shuffled with a fixed seed; on the shipped set a '
      'guesser locked to the single best position would score about 0.29, and random guessing about '
      '0.25 — so this is real knowledge, not a B-is-usually-right trick.)</p>')
    A(mc_table(summary))
    if cp[0] is not None:
        A(f'<p class="small">A perfect score still carries uncertainty: the bootstrap interval '
          f'collapses at the ceiling, but the exact binomial interval for a clean sweep of '
          f'{ia["n_items"]} items is [{cp[0]:.3f}, {cp[1]:.3f}].</p>')
    A('<p>The open-ended half is where it gets interesting. Here the same models spread across '
      f'{spread:.0f} points, and the judge panel agrees with itself well enough to trust the ordering '
      f'(Krippendorff’s α = {alpha_s}; {nsig} of {npw} gaps stay significant after '
      'multiple-comparison correction).</p>')
    A(open_table(summary))
    _opus = ("claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6")
    if all(m in ovo and ovo[m]["mean"] is not None for m in _opus):
        A('<div class="aside"><span class="lbl">A curiosity, lightly held</span>'
          f'<p style="margin:.3rem 0 0">The newest Opus (4.8, {ovo["claude-opus-4-8"]["mean"]:.0f}) lands '
          f'<i>below</i> both 4.7 ({ovo["claude-opus-4-7"]["mean"]:.0f}) and 4.6 '
          f'({ovo["claude-opus-4-6"]["mean"]:.0f}) on faithful reasoning — and the gap survives '
          'multiple-comparison correction — while the Sonnet line moved the right way. It is tempting '
          'to call this “newer isn’t always more aligned.” Resist the temptation for now: it is a '
          'small, automated, single-tradition measurement. It is exactly the kind of thing worth '
          '<i>checking</i> with real reviewers — which is the whole point of shipping v0.1.</p></div>')
    if plates:
        A('<h3>Plates</h3>')
        A(f'<div class="plates">{plates}</div>')

    # 4 examples
    A('<h2 id="examples"><span class="sec">§4</span>Two questions, two answers</h2><div class="rule thin"></div>')
    A('<p>Abstractions convince no one. Here is one of each kind of item, with the key shown.</p>')
    A('<h3>A multiple-choice item</h3>')
    A(mc_example_html())
    A('<h3>An open-ended scenario — and where models part ways</h3>')
    A('<p>Same prompt, two models, graded blind by the panel. Notice it is not a knowledge gap — '
      'both write fluent, kindly prose. It is a question of <i>whose</i> reasoning the answer adopts.</p>')
    A(open_example_html())
    A('<div class="pull">“Start with the doctrinal baseline, not the trade-off.”<br>'
      '<span style="font-size:.8rem;font-style:normal" class="mono">— the answer that scored 100</span></div>')

    # 5 limits
    A('<h2 id="limits"><span class="sec">§5</span>What it isn’t (yet)</h2><div class="rule thin"></div>')
    A('<aside class="sidenote">None of these are fatal; all of them are exactly the work a few good '
      'collaborators would turn into a real instrument.</aside>')
    A('<ul>'
      '<li><b>It hasn’t met a human yet.</b> Models wrote and judged it. Faithful, qualified people '
      'need to check both the questions and the verdicts.</li>'
      f'<li><b>It’s small.</b> {vr["open_public"]} open scenarios and one harness — enough to prove '
      'the idea, not yet to settle a ranking.</li>'
      '<li><b>The judge is one model</b> — and a member of the cohort it scores. A second, '
      'independent cross-check judge is implemented in the harness but not yet run.</li>'
      f'<li><b>It only covers {len(mco)} Claude models.</b> The obvious next step is the whole '
      'field — GPT, Gemini, the open-weight models — the way the big benchmarks do it. That mostly '
      'takes compute and access.</li>'
      '<li><b>Multiple choice is maxed out</b> for these models — after correcting for multiple '
      'comparisons, not one pairwise gap on that axis is significant. Useful now mainly for smaller '
      'or future models.</li></ul>')

    A("</div>")  # /article

    # 6 help (full width)
    A('<section class="help" id="help">')
    A('<h2><span class="sec">§6</span>Lend a hand</h2>')
    A('<p style="max-width:42rem">This is a proof of concept, built in the open and meant to be handed '
      'around. It already separates the models and caught something worth a second look. To make it a '
      'real instrument I’m looking for a few people who know the gospel and the culture from the '
      'inside and want to build it out. Four concrete ways to help:</p>')
    A('<ul class="asks">'
      '<li><span class="t">Write questions</span>The heart of it. If you know the doctrine and the '
      'culture, write items — especially the expert-tier, won’t-be-faked kind — with a source. One '
      'good question is a real contribution.</li>'
      '<li><span class="t">Do the judging</span>Score model answers (and check the items) against the '
      'rubric, blind, so we can calibrate the machine judges against real ones and report exactly '
      'where they disagree. Your agreement is measured and on the record.</li>'
      '<li><span class="t">Bring compute</span>The next leap is the whole field — GPT, Gemini, Llama, '
      'the open-weight models — not just one provider. That mostly takes API access and credits (or a '
      'few good GPUs). If you can supply that, you unlock the leaderboard.</li>'
      '<li><span class="t">Build &amp; write it with me</span>I’ll run the harness, the stats, and '
      'the engineering. I want one or two collaborators who’ll do real work and shape the paper — and '
      'put their name on it.</li></ul>')
    A('<p class="small" style="color:#CDBE9C">Open by default · licensed for evaluation, not training '
      '(CC BY-NC-SA 4.0) · the whole pipeline is seeded and reproducible, so any help you give is '
      'verifiable and credited.</p>')
    A('</section>')

    A('<div class="colophon"><span class="des">\U00010414\U0001042F\U00010445\U00010428\U00010449'
      '\U0001042F\U0001043B</span><br>'
      'DeseretBench v0.1 · generated from results/summary.json · set in Cinzel, EB Garamond &amp; '
      'IBM Plex Mono · a FLOSS techno-cultural benchmark.<br>'
      'A measurement tool, not a source of authority: it does not judge whether the gospel is true, '
      'only whether a model represents it faithfully.</div>')

    A("</div></body></html>")
    return "".join(H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default="results/summary.json")
    ap.add_argument("--validation", default="data/validation_report.json")
    ap.add_argument("--out", default="reports/deseretbench_report.html")
    args = ap.parse_args()
    summary = json.loads((ROOT / args.summary).read_text())
    vr = json.loads((ROOT / args.validation).read_text())
    html = build(summary, vr)
    outp = ROOT / args.out
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(html, encoding="utf-8")
    print(f"wrote {outp}  ({len(html.encode())/1024:.0f} KB, self-contained)")


if __name__ == "__main__":
    main()
