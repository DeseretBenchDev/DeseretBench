"""Merge separately-run cohorts into one run dir that `analyze` can read.

Models added after a release are run into their own directories (the run
phases rewrite their output files with only the models passed, so filling a
new model into the release dir would drop everyone else). This concatenates
the record files record-for-record, refuses duplicate keys, and writes a
config snapshot that keeps the first source's phases (what analyze stamps)
while recording every source's own snapshot under `merged_from`.

    python -m deseretbench.merge_runs --out runs/v0_1_plus \
        runs/v0_1 runs/claude_new_mc runs/claude_new_open runs/go_mc_r2 \
        --exclude-open kimi-k3
"""

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

RECORD_FILES = ("mc_responses.jsonl", "open_responses.jsonl",
                "open_scores.jsonl", "open_judge_raw.jsonl")


def _key(name, r):
    k = (r["model"], r["question_id"], r["run_index"])
    if name == "open_judge_raw.jsonl":
        k += (r.get("persona"), r.get("judge_role"), r.get("judge_model"))
    return k


def merge_runs(sources, out, exclude_open=frozenset(), unpinned=frozenset()):
    """`unpinned`: model ids whose reasoning effort the backend does not pin."""
    sources = [Path(s) for s in sources]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    present_models = {}
    for name in RECORD_FILES:
        present = [s for s in sources if (s / name).exists()]
        if not present:
            continue
        seen, lines = set(), []
        present_models[name] = set()
        for s in present:
            for line in (s / name).read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if name.startswith("open_") and r["model"] in exclude_open:
                    continue
                k = _key(name, r)
                if k in seen:
                    raise ValueError(f"duplicate record {k} in {s / name}")
                seen.add(k)
                present_models[name].add(r["model"])
                lines.append(line + "\n")
        (out / name).write_text("".join(lines))

    snaps = {str(s): json.loads((s / "config_snapshot.json").read_text())
             for s in sources if (s / "config_snapshot.json").exists()}
    base = json.loads(json.dumps(next(iter(snaps.values()), {})))
    # analyze stamps runs/effort from the base phases; make them true of the merge
    for phase, key, rec in (("mc", "multiple_choice", "mc_responses.jsonl"),
                            ("open", "open_ended", "open_scores.jsonl")):
        if phase not in base:
            continue
        here = [sn[phase] for sn in snaps.values() if phase in sn]
        rc = base[phase].setdefault("run_config", {})
        counts = sorted({ph.get("n_runs") for ph in here if ph.get("n_runs") is not None})
        if len(counts) > 1:
            rc.setdefault("runs", {})[key] = f"{counts[0]}–{counts[-1]}"
        if present_models.get(rec, set()) & set(unpinned) and key in rc.get("effort", {}):
            rc["effort"][key] = f"{rc['effort'][key]} (openai_compat models: provider default)"
    base["merged_from"] = {"sources": snaps, "excluded_open": sorted(exclude_open)}
    (out / "config_snapshot.json").write_text(json.dumps(base, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sources", nargs="+", help="run dirs, base release first")
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude-open", default="",
                    help="comma-separated model ids whose open-ended records are "
                         "incomplete and must not be ranked yet")
    a = ap.parse_args()
    excl = {m for m in a.exclude_open.split(",") if m}
    cohort = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text())["cohort"]
    rc = yaml.safe_load((ROOT / "configs" / "run_config.yaml").read_text())["runner"]
    unpinned = set() if rc.get("openai_map_effort") else \
        {m["id"] for m in cohort if m.get("backend") == "openai_compat"}
    merge_runs(a.sources, a.out, excl, unpinned)
    print(f"merged {len(a.sources)} run dir(s) into {a.out}")


if __name__ == "__main__":
    main()
