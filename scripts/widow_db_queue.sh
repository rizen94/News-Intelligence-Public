#!/usr/bin/env bash
# Widow DB-only catch-up queue (no Ollama generate, no Dockside embeds).
# Companion to dockside_embed_queue.sh + popos_generate_queue.sh.
#
# Default phase: event_dedup (fingerprint / entity tiers; embed tier only if column exists).
#
# Usage (Widow):
#   nohup /opt/news-intelligence/scripts/widow_db_queue.sh >>/tmp/widow_db_queue.log 2>&1 &
# Stop:
#   kill $(cat /tmp/widow_db_queue.pid)

set -euo pipefail

ROOT="${NI_ROOT:-/opt/news-intelligence}"
VENV="${ROOT}/.venv/bin/python"
LOG="${WIDOW_DB_QUEUE_LOG:-/tmp/widow_db_queue.log}"
PIDFILE="${WIDOW_DB_QUEUE_PID:-/tmp/widow_db_queue.pid}"
STATEFILE="${WIDOW_DB_QUEUE_STATE:-/tmp/widow_db_queue.state}"
DAYS="${WIDOW_DB_QUEUE_DAYS:-4}"
MAX_EMPTY="${WIDOW_DB_QUEUE_PHASE_MAX_EMPTY:-8}"
IDLE_SLEEP="${WIDOW_DB_QUEUE_IDLE_SLEEP:-10}"
CYCLE_SLEEP="${WIDOW_DB_QUEUE_CYCLE_SLEEP:-60}"

if [[ -n "${WIDOW_DB_QUEUE_PHASES:-}" ]]; then
  # shellcheck disable=SC2206
  PHASES=(${WIDOW_DB_QUEUE_PHASES})
else
  PHASES=(event_dedup)
fi

echo $$ >"$PIDFILE"
exec >>"$LOG" 2>&1

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }
cleanup() { rm -f "$PIDFILE"; }
trap cleanup EXIT

if [[ ! -x "$VENV" ]]; then
  log "ERROR: missing venv at $VENV"
  exit 1
fi

set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
set +a
export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:$PYTHONPATH}"

END_EPOCH=$(( $(date +%s) + DAYS * 86400 ))
log "START root=$ROOT days=$DAYS phases=${PHASES[*]}"

declare -A TOTALS=()
for p in "${PHASES[@]}"; do TOTALS[$p]=0; done
CYCLE=0

run_one() {
  local phase="$1"
  cd "$ROOT/api" && "$VENV" - "$phase" <<'PY'
import json, sys
from services.dockside_embed_queue_service import run_phase
print(json.dumps(run_phase(sys.argv[1]), default=str))
PY
}

while [[ $(date +%s) -lt "$END_EPOCH" ]]; do
  CYCLE=$((CYCLE + 1))
  log "CYCLE_START n=$CYCLE remaining_h=$(( (END_EPOCH - $(date +%s)) / 3600 ))"
  for phase in "${PHASES[@]}"; do
    EMPTY=0
    log "PHASE_BEGIN phase=$phase"
    printf '%s\n' "cycle=$CYCLE phase=$phase started=$(date -Iseconds)" >"$STATEFILE"
    while [[ $(date +%s) -lt "$END_EPOCH" ]]; do
      OUT=$(run_one "$phase") || {
        log "BATCH_FAIL phase=$phase"
        EMPTY=$((EMPTY + 1))
        sleep "$IDLE_SLEEP"
        [[ "$EMPTY" -ge "$MAX_EMPTY" ]] && break
        continue
      }
      log "BATCH phase=$phase $OUT"
      DONE=$(printf '%s' "$OUT" | "$VENV" -c 'import json,sys;d=json.load(sys.stdin);print(int(d.get("done") or 0))')
      TOTALS[$phase]=$(( TOTALS[$phase] + DONE ))
      printf '%s\n' "cycle=$CYCLE phase=$phase done=$DONE total=${TOTALS[$phase]} at=$(date -Iseconds)" >"$STATEFILE"
      if [[ "$DONE" -eq 0 ]]; then
        EMPTY=$((EMPTY + 1))
        if [[ "$EMPTY" -ge "$MAX_EMPTY" ]]; then
          log "PHASE_ADVANCE phase=$phase total=${TOTALS[$phase]}"
          break
        fi
        sleep "$IDLE_SLEEP"
      else
        EMPTY=0
      fi
    done
    log "PHASE_END phase=$phase total=${TOTALS[$phase]}"
  done
  log "CYCLE_END n=$CYCLE"
  sleep "$CYCLE_SLEEP"
done

log "FINISHED"
printf '%s\n' "finished=$(date -Iseconds)" >"$STATEFILE"
