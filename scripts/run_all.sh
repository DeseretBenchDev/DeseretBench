#!/usr/bin/env bash
# DeseretBench — full pipeline, one command. Resumable (cache-backed).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
RUN="${1:-runs/v0_1}"
P="${MAX_PARALLEL:-8}"

echo "== 1/7 author =="     ; $PY -m deseretbench.author --max-parallel "$P"
echo "== 2/7 assemble =="   ; $PY -m deseretbench.assemble
echo "== 3/7 validate =="   ; $PY -m deseretbench.validate_questions --max-parallel "$P"
echo "== 4/7 balance =="    # freshly validated set => any old balance marker is stale
rm -f data/questions_mc.jsonl.balance_meta.json data/questions_mc.prebalance.jsonl
$PY -m deseretbench.balance_positions --in data/questions_mc.jsonl --out data/questions_mc.jsonl
echo "== 5/7 run MC =="     ; $PY -m deseretbench.run_benchmark mc   --questions data/questions_mc.jsonl   --out "$RUN" --max-parallel "$P"
echo "== 6/7 run OPEN =="   ; $PY -m deseretbench.run_benchmark open --questions data/questions_open.jsonl --out "$RUN" --max-parallel "$P"
echo "== 7/7 analyze+report ==" ; $PY -m deseretbench.analyze --run "$RUN" && $PY -m deseretbench.report
echo "done -> reports/leaderboard.html"
