#!/usr/bin/env bash
# DeseretBench — finish the measurement pipeline unattended and rate-limit-safe.
# Re-runs MC (on the position-balanced set), runs OPEN (generation + judge panel),
# then analyzes and reports. Each model phase uses the resilient wrapper, which
# retries only failed (uncached) calls across session-limit reset windows.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
RUN="${1:-runs/v0_1}"
SLEEP="${SLEEP:-1500}"
export MAX_PARALLEL="${MAX_PARALLEL:-8}"

# Resolve paths from the active faith pack (DESERETBENCH_PACK / run_config
# `pack:`), so a non-LDS pack reads and writes under its own data/ + results/
# and never touches the LDS set. For the LDS pack these are data/ and results/.
DATA=$($PY -c 'from deseretbench.packs import active_pack as a; print(a().data_dir)')
RESULTS=$($PY -c 'from deseretbench.packs import active_pack as a; print(a().results_dir)')

echo "=== $(date '+%F %H:%M:%S %Z') public set ==="
wc -l "$DATA/questions_mc.jsonl" "$DATA/questions_open.jsonl"
NMODELS=$(grep -c '^  - id:' configs/models.yaml)

echo "=== $(date '+%F %H:%M:%S %Z') [1/4] MC phase ($NMODELS models, balanced) ==="
bash scripts/resilient_run.sh mc "$RUN" "$DATA/questions_mc.jsonl" "$SLEEP" || { echo "[finish] MC FAILED"; exit 2; }

echo "=== $(date '+%F %H:%M:%S %Z') [2/4] OPEN phase ($NMODELS models + judge panel) ==="
bash scripts/resilient_run.sh open "$RUN" "$DATA/questions_open.jsonl" "$SLEEP" || { echo "[finish] OPEN FAILED"; exit 3; }

echo "=== $(date '+%F %H:%M:%S %Z') [3/4] analyze ==="
$PY -m deseretbench.analyze --run "$RUN" --out "$RESULTS/summary.json" || { echo "[finish] ANALYZE FAILED"; exit 4; }

echo "=== $(date '+%F %H:%M:%S %Z') [4/4] report ==="
$PY -m deseretbench.report --summary "$RESULTS/summary.json" || { echo "[finish] REPORT FAILED"; exit 5; }

echo "=== $(date '+%F %H:%M:%S %Z') PIPELINE_COMPLETE -> reports/leaderboard.html ==="
