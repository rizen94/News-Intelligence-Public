#!/usr/bin/env bash
# Multi-day Dockside EMBED queue (nomic-embed-text on GTX 1050 Ti).
# Generate/extract work belongs on PopOS — see scripts/popos_generate_queue.sh.
# DB-only event_dedup belongs on Widow — see scripts/widow_db_queue.sh.
#
# Sequence (repeat until DOCKSIDE_QUEUE_DAYS elapse or process killed):
#   1. chunks            — embedding_chunks (articles + ref/wiki/context)
#   2. article_vectors   — domain articles.embedding_vector
#   3. topic_embeddings  — domain topics.embedding
#
# Run on Widow (tunnel :11435 → Dockside). Stop existing chunk-only burns first.
#
# Usage:
#   nohup /opt/news-intelligence/scripts/dockside_embed_queue.sh >>/tmp/dockside_embed_queue.log 2>&1 &
# Stop:
#   kill $(cat /tmp/dockside_embed_queue.pid)
#
# Env:
#   DOCKSIDE_QUEUE_DAYS=4              wall-clock run length (default 4)
#   DOCKSIDE_QUEUE_PHASE_MAX_EMPTY=6   consecutive empty batches → advance phase
#   DOCKSIDE_QUEUE_PHASE_MAX_SEC=0     optional per-phase wall cap (0=unlimited)
#   DOCKSIDE_QUEUE_IDLE_SLEEP=8
#   DOCKSIDE_QUEUE_CHUNK_BATCH=80
#   DOCKSIDE_QUEUE_ARTICLE_BATCH=40
#   DOCKSIDE_QUEUE_TOPIC_BATCH=60
#   DOCKSIDE_QUEUE_DEDUP_BATCH=80

set -euo pipefail

ROOT="${NI_ROOT:-/opt/news-intelligence}"
VENV="${ROOT}/.venv/bin/python"
LOG="${DOCKSIDE_QUEUE_LOG:-/tmp/dockside_embed_queue.log}"
PIDFILE="${DOCKSIDE_QUEUE_PID:-/tmp/dockside_embed_queue.pid}"
STATEFILE="${DOCKSIDE_QUEUE_STATE:-/tmp/dockside_embed_queue.state}"
DAYS="${DOCKSIDE_QUEUE_DAYS:-4}"
MAX_EMPTY="${DOCKSIDE_QUEUE_PHASE_MAX_EMPTY:-6}"
PHASE_MAX_SEC="${DOCKSIDE_QUEUE_PHASE_MAX_SEC:-0}"
IDLE_SLEEP="${DOCKSIDE_QUEUE_IDLE_SLEEP:-8}"
CYCLE_SLEEP="${DOCKSIDE_QUEUE_CYCLE_SLEEP:-30}"

# Override: DOCKSIDE_QUEUE_PHASES="chunks article_vectors topic_embeddings"
if [[ -n "${DOCKSIDE_QUEUE_PHASES:-}" ]]; then
  # shellcheck disable=SC2206
  PHASES=(${DOCKSIDE_QUEUE_PHASES})
else
  PHASES=(chunks article_vectors topic_embeddings)
fi

echo $$ >"$PIDFILE"
exec >>"$LOG" 2>&1

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

cleanup() {
  rm -f "$PIDFILE"
}
trap cleanup EXIT

if [[ ! -x "$VENV" ]]; then
  log "ERROR: missing venv python at $VENV"
  exit 1
fi

set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
set +a

export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:$PYTHONPATH}"
export EMBEDDINGS_YIELD_CLAIM_BACKLOG="${EMBEDDINGS_YIELD_CLAIM_BACKLOG:-999999}"
export EMBEDDINGS_COMMIT_EVERY_ARTICLES="${EMBEDDINGS_COMMIT_EVERY_ARTICLES:-3}"
export EMBEDDINGS_WORKER_BATCH_LIMIT="${DOCKSIDE_QUEUE_CHUNK_BATCH:-80}"
export EMBEDDINGS_REFERENCE_EVENT_BATCH_LIMIT="${EMBEDDINGS_REFERENCE_EVENT_BATCH_LIMIT:-15}"
export EMBEDDINGS_WIKIPEDIA_BATCH_LIMIT="${EMBEDDINGS_WIKIPEDIA_BATCH_LIMIT:-8}"
export EMBEDDINGS_CONTEXT_BATCH_LIMIT="${EMBEDDINGS_CONTEXT_BATCH_LIMIT:-20}"

if [[ -z "${OLLAMA_EMBEDDINGS_HOST:-}" ]]; then
  log "ERROR: OLLAMA_EMBEDDINGS_HOST unset — refusing to run on generate host"
  exit 1
fi

END_EPOCH=$(( $(date +%s) + DAYS * 86400 ))
log "START root=$ROOT host=$OLLAMA_EMBEDDINGS_HOST days=$DAYS end=$(date -d "@$END_EPOCH" -Iseconds 2>/dev/null || date -r "$END_EPOCH" -Iseconds 2>/dev/null || echo "$END_EPOCH")"
log "PHASES=${PHASES[*]}"

declare -A TOTALS=()
for p in "${PHASES[@]}"; do TOTALS[$p]=0; done
CYCLE=0

run_one_batch() {
  local phase="$1"
  cd "$ROOT/api" && "$VENV" - "$phase" <<'PY'
import json, os, sys
from services.dockside_embed_queue_service import run_phase
phase = sys.argv[1]
print(json.dumps(run_phase(phase), default=str))
PY
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
        log "PHASE_TIMEBOX phase=$phase elapsed=$(( $(date +%s) - PHASE_START ))s"
        break
      fi
      OUT=$(run_one_batch "$phase") || {
        log "BATCH_FAIL phase=$phase"
        EMPTY=$((EMPTY + 1))
        sleep "$IDLE_SLEEP"
        if [[ "$EMPTY" -ge "$MAX_EMPTY" ]]; then
          break
        fi
        continue
      }
      log "BATCH phase=$phase $OUT"
      read -r DONE YIELDED < <(
        printf '%s' "$OUT" | "$VENV" -c '
import json,sys
d=json.load(sys.stdin)
print(int(d.get("done") or 0), 1 if d.get("yielded") else 0)
'
      )
      TOTALS[$phase]=$(( TOTALS[$phase] + DONE ))
      printf '%s\n' "cycle=$CYCLE phase=$phase done_batch=$DONE total_phase=${TOTALS[$phase]} at=$(date -Iseconds)" >"$STATEFILE"
      if [[ "$YIELDED" -eq 1 || "$DONE" -eq 0 ]]; then
        EMPTY=$((EMPTY + 1))
        log "EMPTY/YIELD phase=$phase streak=$EMPTY total=${TOTALS[$phase]}"
        if [[ "$EMPTY" -ge "$MAX_EMPTY" ]]; then
          log "PHASE_ADVANCE phase=$phase reason=empty_streak total=${TOTALS[$phase]}"
          break
        fi
        sleep "$IDLE_SLEEP"
      else
        EMPTY=0
      fi
    done
    log "PHASE_END phase=$phase total=${TOTALS[$phase]} wall=$(( $(date +%s) - PHASE_START ))s"
  done
  log "CYCLE_END n=$CYCLE chunks=${TOTALS[chunks]:-0} article_vectors=${TOTALS[article_vectors]:-0} topic_embeddings=${TOTALS[topic_embeddings]:-0}"
  sleep "$CYCLE_SLEEP"
done

log "FINISHED days=$DAYS chunks=${TOTALS[chunks]:-0} article_vectors=${TOTALS[article_vectors]:-0} topic_embeddings=${TOTALS[topic_embeddings]:-0}"
printf '%s\n' "finished=$(date -Iseconds) chunks=${TOTALS[chunks]:-0} article_vectors=${TOTALS[article_vectors]:-0} topic_embeddings=${TOTALS[topic_embeddings]:-0}" >"$STATEFILE"
