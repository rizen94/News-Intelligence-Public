#!/usr/bin/env bash
# Multi-day PopOS GENERATE/EXTRACT queue (RTX 5090 Ollama).
# Embeddings stay on Dockside — see scripts/dockside_embed_queue.sh.
#
# Pauses systemd PopOS workers for the run so five lanes do not 503-thrash one GPU,
# then drains phases in sequence (loops for POPOS_QUEUE_DAYS).
#
# Sequence (default):
#   unified_intake_extraction → claim_extraction → topic_clustering →
#   entity_profile_build → story_continuation → storyline_assembly →
#   content_refinement_queue (70b last)
#
# Usage (on PopOS):
#   nohup /home/pete/ni-popos-worker/scripts/popos_generate_queue.sh >>/tmp/popos_generate_queue.log 2>&1 &
# Stop:
#   kill $(cat /tmp/popos_generate_queue.pid)   # trap restores workers

set -euo pipefail

ROOT="${NI_ROOT:-/home/pete/ni-popos-worker}"
VENV="${ROOT}/.venv/bin/python"
WORKER="${ROOT}/scripts/run_popos_phase_worker.py"
LOG="${POPOS_QUEUE_LOG:-/tmp/popos_generate_queue.log}"
PIDFILE="${POPOS_QUEUE_PID:-/tmp/popos_generate_queue.pid}"
STATEFILE="${POPOS_QUEUE_STATE:-/tmp/popos_generate_queue.state}"
DAYS="${POPOS_QUEUE_DAYS:-4}"
MAX_EMPTY="${POPOS_QUEUE_PHASE_MAX_EMPTY:-4}"
PHASE_MAX_SEC="${POPOS_QUEUE_PHASE_MAX_SEC:-0}"
IDLE_SLEEP="${POPOS_QUEUE_IDLE_SLEEP:-15}"
CYCLE_SLEEP="${POPOS_QUEUE_CYCLE_SLEEP:-45}"
BUDGET="${POPOS_QUEUE_BUDGET_SECONDS:-900}"
PAUSE_SYSTEMD="${POPOS_QUEUE_PAUSE_SYSTEMD:-true}"
TARGET="${POPOS_WORKERS_TARGET:-news-intelligence-popos-workers.target}"

if [[ -n "${POPOS_QUEUE_PHASES:-}" ]]; then
  # shellcheck disable=SC2206
  PHASES=(${POPOS_QUEUE_PHASES})
else
  PHASES=(
    unified_intake_extraction
    claim_extraction
    topic_clustering
    entity_profile_build
    story_continuation
    storyline_assembly
    content_refinement_queue
  )
fi

echo $$ >"$PIDFILE"
exec >>"$LOG" 2>&1

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

WORKERS_WERE_ACTIVE=0
restore_workers() {
  if [[ "$PAUSE_SYSTEMD" == "true" && "$WORKERS_WERE_ACTIVE" -eq 1 ]]; then
    log "RESTORE $TARGET"
    systemctl --user start "$TARGET" || log "WARN: failed to restart $TARGET"
  fi
  rm -f "$PIDFILE"
}
trap restore_workers EXIT

if [[ ! -x "$VENV" || ! -f "$WORKER" ]]; then
  log "ERROR: missing venv or worker under $ROOT"
  exit 1
fi

# Load KEY=VAL via python dotenv (bash `source` breaks on unquoted spaces).
"$VENV" - <<PY
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:
    raise SystemExit(0)
root = Path("$ROOT")
load_dotenv(root / ".env", override=False)
load_dotenv(root / ".env.popos_worker", override=True)
PY
# Export selected keys into this shell for the worker child
eval "$("$VENV" - <<'PY'
import os
from pathlib import Path
try:
    from dotenv import dotenv_values
except ImportError:
    raise SystemExit(0)
root = Path("/home/pete/ni-popos-worker")
vals = {}
vals.update({k: v for k, v in (dotenv_values(root / ".env") or {}).items() if v is not None})
vals.update({k: v for k, v in (dotenv_values(root / ".env.popos_worker") or {}).items() if v is not None})
keep_prefixes = (
    "DB_", "OLLAMA_", "PIPELINE_", "POPOS_", "WORKER_", "AUTOMATION_",
    "REFINEMENT_", "STORY_", "CONTINUATION_", "NARRATIVE_", "ENTITY_",
    "CLAIM_", "BULK_", "MAX_CONCURRENT", "NEWS_INTEL_", "NI_",
)
for k, v in vals.items():
    if any(k.startswith(p) for p in keep_prefixes) or k in ("PYTHONPATH",):
        # shell-escape
        esc = v.replace("\\", "\\\\").replace('"', '\\"')
        print(f'export {k}="{esc}"')
PY
)"

export WORKER_EXECUTION_HOST=popos
# Force catch-up overrides after dotenv (file may set quiet_hours=false / game defer).
export PIPELINE_QUIET_HOURS_DISABLED=true
export POPOS_GPU_COTENANT_DEFER=false
export POPOS_GPU_GAME_DEFER=false
export OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
export OLLAMA_DUAL_HOST_ROUTING_ENABLED=false
# Never burn embeds on PopOS during generate queue
unset OLLAMA_EMBEDDINGS_HOST || true

END_EPOCH=$(( $(date +%s) + DAYS * 86400 ))
log "START root=$ROOT ollama=$OLLAMA_HOST days=$DAYS end=$(date -d "@$END_EPOCH" -Iseconds 2>/dev/null || echo "$END_EPOCH")"
log "PHASES=${PHASES[*]}"

if [[ "$PAUSE_SYSTEMD" == "true" ]]; then
  if systemctl --user is-active --quiet "$TARGET"; then
    WORKERS_WERE_ACTIVE=1
    log "PAUSE $TARGET (serialize generate onto one lane)"
    systemctl --user stop "$TARGET"
    sleep 3
  else
    log "NOTE: $TARGET already inactive"
  fi
fi

declare -A TOTALS=()
for p in "${PHASES[@]}"; do TOTALS[$p]=0; done
CYCLE=0

phase_had_work() {
  # Best-effort: non-zero processed / linked / embedded-like counters in JSON summary.
  printf '%s' "$1" | "$VENV" -c '
import json,sys,re
raw=sys.stdin.read()
# worker logs before JSON; find last {...}
m=None
for m in re.finditer(r"\{.*\}", raw, re.S):
    pass
if not m:
    print(0); raise SystemExit
try:
    d=json.loads(m.group(0))
except Exception:
    print(0); raise SystemExit
phases=d.get("phases") or {}
n=0
for payload in phases.values():
    if not isinstance(payload, dict):
        continue
    if payload.get("skipped"):
        continue
    for k,v in payload.items():
        if k in ("error","message","success","domains") or v is None:
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int,float)) and v>0:
            n += int(v)
        elif isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv,(int,float)) and vv>0:
                    n += int(vv)
print(1 if n>0 else 0)
'
}

while [[ $(date +%s) -lt "$END_EPOCH" ]]; do
  CYCLE=$((CYCLE + 1))
  log "CYCLE_START n=$CYCLE remaining_h=$(( (END_EPOCH - $(date +%s)) / 3600 ))"
  for phase in "${PHASES[@]}"; do
    if [[ $(date +%s) -ge "$END_EPOCH" ]]; then
      break
    fi
    EMPTY=0
    PHASE_START=$(date +%s)
    log "PHASE_BEGIN phase=$phase"
    printf '%s\n' "cycle=$CYCLE phase=$phase started=$(date -Iseconds)" >"$STATEFILE"
    while [[ $(date +%s) -lt "$END_EPOCH" ]]; do
      if [[ "$PHASE_MAX_SEC" -gt 0 && $(( $(date +%s) - PHASE_START )) -ge "$PHASE_MAX_SEC" ]]; then
        log "PHASE_TIMEBOX phase=$phase"
        break
      fi
      OUT=$(
        cd "$ROOT" && "$VENV" "$WORKER" \
          --worker-id "generate-queue" \
          --phases "$phase" \
          --once \
          --budget-seconds "$BUDGET" \
          --idle-sleep "$IDLE_SLEEP" 2>&1
      ) || {
        log "BATCH_FAIL phase=$phase"
        EMPTY=$((EMPTY + 1))
        sleep "$IDLE_SLEEP"
        [[ "$EMPTY" -ge "$MAX_EMPTY" ]] && break
        continue
      }
      # Truncate noisy logs in the queue log
      log "BATCH phase=$phase $(printf '%s' "$OUT" | tail -n 3 | tr '\n' ' ' | head -c 600)"
      HAD=$(phase_had_work "$OUT" || echo 0)
      if [[ "$HAD" == "1" ]]; then
        TOTALS[$phase]=$(( TOTALS[$phase] + 1 ))
        EMPTY=0
        printf '%s\n' "cycle=$CYCLE phase=$phase productive=1 total_batches=${TOTALS[$phase]} at=$(date -Iseconds)" >"$STATEFILE"
      else
        EMPTY=$((EMPTY + 1))
        log "EMPTY phase=$phase streak=$EMPTY"
        if [[ "$EMPTY" -ge "$MAX_EMPTY" ]]; then
          log "PHASE_ADVANCE phase=$phase reason=empty_streak batches=${TOTALS[$phase]}"
          break
        fi
        sleep "$IDLE_SLEEP"
      fi
    done
    log "PHASE_END phase=$phase productive_batches=${TOTALS[$phase]} wall=$(( $(date +%s) - PHASE_START ))s"
  done
  log "CYCLE_END n=$CYCLE"
  sleep "$CYCLE_SLEEP"
done

log "FINISHED days=$DAYS"
printf '%s\n' "finished=$(date -Iseconds)" >"$STATEFILE"
