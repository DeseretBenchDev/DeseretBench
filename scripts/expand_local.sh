#!/usr/bin/env bash
# DeseretBench — bring the local open-weights cohort into the benchmark, OOM-safe.
#
# Phase A ("warm"): for each cohort entry with `backend: ollama`, run the MC and
# open phases ONE MODEL AT A TIME at --max-parallel 1, writing to a scratch out
# dir. The point is the content-addressed cache, not the scratch files: JsonlSink
# rewrites its output file wholesale per invocation, so per-model files are
# throwaway, but every successful call lands in ./cache keyed by content.
# Combined with the server's OLLAMA_MAX_LOADED_MODELS=1 / OLLAMA_NUM_PARALLEL=1,
# at most one local model is ever resident and inference is strictly serial.
#
# Phase B: the normal resilient full-cohort pipeline on the real run dir —
# Claude and warmed local calls replay from cache for free; only stragglers and
# judge work run live, then analyze + report.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
RUN="${1:-runs/v0_1}"
WARM="${WARM:-runs/warm_local}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

LOCALS=$($PY -c "
import yaml
c = yaml.safe_load(open('configs/models.yaml'))
print(' '.join(m['id'] for m in c['cohort'] if m.get('backend') == 'ollama'))
")
if [ -z "$LOCALS" ]; then echo "[expand_local] no backend:ollama cohort entries"; exit 8; fi
echo "[expand_local] local cohort: $LOCALS"

curl -s --max-time 5 "$OLLAMA_URL/api/version" >/dev/null \
  || { echo "[expand_local] FATAL: no ollama server at $OLLAMA_URL"; exit 9; }

echo "=== $(date '+%F %H:%M:%S %Z') [A1] MC warm, per model, serial ==="
for m in $LOCALS; do
  echo "--- $(date '+%F %H:%M:%S %Z') MC warm: $m ---"
  $PY -m deseretbench.run_benchmark mc --questions data/questions_mc.jsonl \
      --out "$WARM" --models "$m" --max-parallel 1 \
      || echo "[expand_local] WARN: mc $m exited rc=$? (leftovers retry in phase B)"
done

echo "=== $(date '+%F %H:%M:%S %Z') [A2] OPEN warm (gen + judge trickle), per model, serial ==="
for m in $LOCALS; do
  echo "--- $(date '+%F %H:%M:%S %Z') OPEN warm: $m ---"
  $PY -m deseretbench.run_benchmark open --questions data/questions_open.jsonl \
      --out "$WARM" --models "$m" --max-parallel 1 \
      || echo "[expand_local] WARN: open $m exited rc=$? (leftovers retry in phase B)"
done

echo "=== $(date '+%F %H:%M:%S %Z') [B] full-cohort resilient pipeline ==="
# Parallelism 4: cache replays and judge calls benefit; any residual local
# calls are serialized server-side by OLLAMA_NUM_PARALLEL=1 regardless.
MAX_PARALLEL="${MAX_PARALLEL:-4}" SLEEP="${SLEEP:-1500}" \
  bash scripts/finish_pipeline.sh "$RUN"
