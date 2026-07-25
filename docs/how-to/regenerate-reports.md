# How to regenerate the reports

Goal: rebuild the human-readable outputs — `reports/RESULTS.md`,
`reports/leaderboard.html`, the figures, and the self-contained one-pager —
from an existing `results/summary.json`. No model calls are involved.

If the summary itself is stale, refresh it first: see
[rerun-analysis.md](rerun-analysis.md).

## Prerequisites

- `results/summary.json` produced by `deseretbench.analyze`.
- For the one-pager only: `data/validation_report.json` and a summary that
  contains **both** the `mc` and `open` sections (it hard-fails otherwise).
- The environment from [../tutorials/first-run.md](../tutorials/first-run.md).

## 1. Regenerate the main report

```bash
.venv/bin/python -m deseretbench.report --summary results/summary.json
```

`--summary` defaults to `results/summary.json`; the path is resolved relative to
the repo root, not your cwd. This one command emits:

| Output | Content |
|---|---|
| `reports/RESULTS.md` | Full results in Markdown: MC overall/dimension/difficulty tables, provenance audit, item analysis, Holm-adjusted pairwise tests; open-ended tables, pairwise, judge IRR |
| `reports/leaderboard.html` | The same content converted to a standalone-ish HTML page with embedded figure tags |
| `reports/figures/*.png` | Up to 6 PNGs at dpi 120 (see below) |

Figures are conditional on what the summary contains:

- If `mc` is present: `overall_ci.png`, `radar_dimensions.png`,
  `difficulty_bars.png`, `generational.png`.
- If `open` is present: `open_overall_ci.png`, `open_generational.png`
  (listed first in the HTML).

Note that `leaderboard.html` references figures by relative path
(`src="figures/…png"`), so it is **not** self-contained — move it together with
`reports/figures/`, or use the one-pager when you need a single file.

## 2. Regenerate the one-pager

```bash
.venv/bin/python -m deseretbench.build_onepager
```

Flags (all default, all resolved relative to the repo root):

- `--summary results/summary.json`
- `--validation data/validation_report.json`
- `--out reports/deseretbench_report.html`

This emits exactly one artifact: a fully self-contained HTML broadsheet with the
fonts and four figures base64-embedded, designed to print cleanly to PDF and be
shared as a single attachment. It embeds four of the six report figures as
"Plates": `open_overall_ci.png`, `open_generational.png`, `radar_dimensions.png`,
`difficulty_bars.png` (the two remaining MC figures — `overall_ci.png` and the
within-tier `generational.png` — are not embedded).

It refuses to build if the summary lacks either the `mc` or the `open` section —
run analyze on a full run first.

## 3. Understand the stale-figure behavior (there is no hash check)

Neither tool verifies that a PNG on disk matches the summary by content — there
is no md5 or any other hash check anywhere. The two tools guard differently:

- **`report.py` — regeneration-list gating.** `leaderboard.html` embeds only the
  figures that *this invocation* regenerated. A PNG left in `reports/figures/`
  by an earlier run is never embedded, because it may not match the current
  summary. The stale file itself is not deleted, just ignored.
- **`build_onepager.py` — existence-only gating.** Missing PNGs produce a printed
  WARNING ("run deseretbench.report first") and the corresponding plates are
  omitted from the page. But a PNG that *exists* is embedded regardless of age —
  a stale figure from an older run **will** be baked into the one-pager.

Consequence: always run the two tools in order, against the same summary:

```bash
.venv/bin/python -m deseretbench.analyze --run runs/v0_1 --out results/summary.json
.venv/bin/python -m deseretbench.report --summary results/summary.json
.venv/bin/python -m deseretbench.build_onepager
```

## 4. Fonts

The one-pager embeds eight woff2 files from `assets/fonts/` (Cinzel 600/800,
EB Garamond 400/400-italic/600, IBM Plex Mono 400/600, and a Deseret-alphabet
face) as base64 `@font-face` rules. A missing font file is not fatal: the build
prints a WARNING and the page falls back to system fonts — except the Deseret
glyphs in the masthead and colophon, which may render as tofu without the
`deseret-400.woff2` face. `report.py` output uses system fonts and needs nothing
from `assets/fonts/`.

## Related

- [rerun-analysis.md](rerun-analysis.md) — refresh `results/summary.json` first.
- [../reference/cli.md](../reference/cli.md) — full flag reference for both tools.
