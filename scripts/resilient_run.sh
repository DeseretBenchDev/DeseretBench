#!/usr/bin/env bash
# Resilient phase runner for DeseretBench.
#
# The authenticated `claude` CLI enforces a rolling session usage limit; long
# runs hit HTTP 429 ("You've hit your session limit") partway through. Every
# successful call is content-addressed and cached, and failed (ok=False) calls
# are NOT cached, so simply re-running a phase retries only what failed while
# completed work returns instantly from cache. This wrapper loops a phase until
# zero rate-limited failures remain, sleeping through each reset window.
#
# Usage:
#   scripts/resilient_run.sh mc   runs/v0_1 data/questions_mc.jsonl   [sleep_secs]
#   scripts/resilient_run.sh open runs/v0_1 data/questions_open.jsonl [sleep_secs]
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python

PHASE="$1"; RUN="$2"; Q="$3"; SLEEP="${4:-1500}"; P="${MAX_PARALLEL:-8}"
MAXWAVES="${MAXWAVES:-40}"

# Two questions, two answers (deseretbench.audit):
#   strict — records a retry could still heal. Drives the retry decision.
#   accept — what must be zero before the phase may finish anyway. Only judge
#            calls are tolerable, and only while every panel keeps a quorum.
#
# They differ because some calls never heal. The served-model guard rejects a
# verdict the CLI answered with a model other than the one requested; that
# verdict is dropped rather than recorded under the wrong model, and the panel
# scores over its remaining judges. Retrying such a call forever burns quota to
# change nothing, so once retries have had GRACE_WAVES honest chances, a phase
# whose panels all still hold a quorum is done.
QUORUM="${QUORUM:-2}"
GRACE_WAVES="${GRACE_WAVES:-3}"

audit() {
  $PY -m deseretbench.audit "$PHASE" --run "$RUN" --questions "$Q" --quorum "$QUORUM"
}

wave=0
while :; do
  wave=$((wave+1))
  echo "[resilient $PHASE] === wave $wave (max $MAXWAVES) $(date '+%H:%M:%S %Z') ==="
  $PY -m deseretbench.run_benchmark "$PHASE" --questions "$Q" --out "$RUN" --max-parallel "$P"
  RC=$?
  if [ "$RC" -ne 0 ]; then
    echo "[resilient $PHASE] run_benchmark exited $RC — deterministic setup errors don't heal by retrying; ABORTING"
    exit "$RC"
  fi
  read -r STRICT ACCEPT < <(audit)
  echo "[resilient $PHASE] wave $wave -> $STRICT needing retry, $ACCEPT blocking completion"
  if [ "${STRICT:-1}" -eq 0 ]; then
    echo "[resilient $PHASE] CLEAN after $wave wave(s) at $(date '+%H:%M:%S %Z')"
    break
  fi
  if [ "$wave" -ge "$GRACE_WAVES" ] && [ "${ACCEPT:-1}" -eq 0 ]; then
    echo "[resilient $PHASE] CLEAN (quorum) after $wave wave(s) at $(date '+%H:%M:%S %Z'):" \
         "$STRICT call(s) did not heal in $GRACE_WAVES waves; every panel still holds" \
         "$QUORUM+ judges, so the phase is scoreable. Dropped verdicts are never" \
         "recorded under the wrong model."
    break
  fi
  if [ "$wave" -ge "$MAXWAVES" ]; then
    echo "[resilient $PHASE] GIVING UP after $MAXWAVES waves with $STRICT failures ($ACCEPT blocking)"
    exit 2
  fi
  echo "[resilient $PHASE] sleeping ${SLEEP}s for limit reset, then retrying..."
  sleep "$SLEEP"
done
