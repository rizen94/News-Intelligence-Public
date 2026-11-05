#!/usr/bin/env bash
# Burn-down intelligence.embedding_chunks backlog via Dockside (OLLAMA_EMBEDDINGS_HOST).
# Runs on Widow outside AutomationManager so nightly allowlists / 1h intervals cannot starve it.
#
# Usage:
#   nohup /opt/news-intelligence/scripts/embeddings_dockside_burn.sh >>/tmp/embeddings_dockside_burn.log 2>&1 &
# Stop:
#   kill $(cat /tmp/embeddings_dockside_burn.pid)
#
# Env knobs (optional):
#   EMBEDDINGS_BURN_BATCH=150
#   EMBEDDINGS_BURN_IDLE_SLEEP=5
#   EMBEDDINGS_BURN_BUDGET_SECONDS=0   # 0 = run until empty / stop
#   EMBEDDINGS_BURN_MAX_EMPTY=8         # consecutive empty/yielded batches before exit

set -euo pipefail

ROOT="${NI_ROOT:-/opt/news-intelligence}"
VENV="${ROOT}/.venv/bin/python"
LOG="${EMBEDDINGS_BURN_LOG:-/tmp/embeddings_dockside_burn.log}"
PIDFILE="${EMBEDDINGS_BURN_PID:-/tmp/embeddings_dockside_burn.pid}"
BATCH="${EMBEDDINGS_BURN_BATCH:-150}"
IDLE_SLEEP="${EMBEDDINGS_BURN_IDLE_SLEEP:-5}"
BUDGET_SECONDS="${EMBEDDINGS_BURN_BUDGET_SECONDS:-0}"
MAX_EMPTY="${EMBEDDINGS_BURN_MAX_EMPTY:-8}"

echo $$ >"$PIDFILE"
exec >>"$LOG" 2>&1

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

if [[ ! -x "$VENV" ]]; then
  log "ERROR: missing venv python at $VENV"
  exit 1
fi

set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
set +a

export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:$PYTHONPATH}"
# Force article-first burn after .env source (do not inherit .env side-lane limits).
export EMBEDDINGS_WORKER_BATCH_LIMIT="${EMBEDDINGS_BURN_BATCH:-$BATCH}"
export EMBEDDINGS_REFERENCE_EVENT_BATCH_LIMIT="${EMBEDDINGS_BURN_REF_LIMIT:-0}"
export EMBEDDINGS_WIKIPEDIA_BATCH_LIMIT="${EMBEDDINGS_BURN_WIKI_LIMIT:-0}"
export EMBEDDINGS_CONTEXT_BATCH_LIMIT="${EMBEDDINGS_BURN_CTX_LIMIT:-0}"
export EMBEDDINGS_COMMIT_EVERY_ARTICLES="${EMBEDDINGS_COMMIT_EVERY_ARTICLES:-3}"
# Do not yield to claim backlog during dedicated Dockside burn.
export EMBEDDINGS_YIELD_CLAIM_BACKLOG=999999

if [[ -z "${OLLAMA_EMBEDDINGS_HOST:-}" ]]; then
  log "ERROR: OLLAMA_EMBEDDINGS_HOST unset — refusing to burn on generate host"
  exit 1
fi

log "START root=$ROOT host=$OLLAMA_EMBEDDINGS_HOST batch=$EMBEDDINGS_WORKER_BATCH_LIMIT budget=${BUDGET_SECONDS}s"
START_EPOCH=$(date +%s)
EMPTY=0
TOTAL_ART=0
TOTAL_REF=0
TOTAL_WIKI=0
TOTAL_CTX=0
ITER=0

while true; do
  NOW=$(date +%s)
  if [[ "$BUDGET_SECONDS" -gt 0 && $((NOW - START_EPOCH)) -ge "$BUDGET_SECONDS" ]]; then
    log "BUDGET_DONE elapsed=$((NOW - START_EPOCH))s arts=$TOTAL_ART ref=$TOTAL_REF wiki=$TOTAL_WIKI ctx=$TOTAL_CTX"
    break
  fi
  ITER=$((ITER + 1))
  # shellcheck disable=SC2086
  OUT=$(
    cd "$ROOT/api" && "$VENV" - <<'PY'
import json
import os
from services.embeddings_worker_service import run_embeddings_worker_batch

limit = int(os.environ.get("EMBEDDINGS_WORKER_BATCH_LIMIT", "150"))
r = run_embeddings_worker_batch(batch_limit=limit)
print(json.dumps(r, default=str))
PY
  ) || {
    log "BATCH_FAIL iter=$ITER"
    EMPTY=$((EMPTY + 1))
    sleep "$IDLE_SLEEP"
    if [[ "$EMPTY" -ge "$MAX_EMPTY" ]]; then
      log "TOO_MANY_FAILURES empty=$EMPTY"
      break
    fi
    continue
  }

  log "BATCH iter=$ITER $OUT"
  # Parse totals with python for safety
  read -r ART REF WIKI CTX YIELDED < <(
    printf '%s' "$OUT" | "$VENV" -c '
import json,sys
d=json.load(sys.stdin)
print(
  int(d.get("embedded_articles") or 0),
  int(d.get("embedded_reference_events") or 0),
  int(d.get("embedded_wikipedia") or 0),
  int(d.get("embedded_contexts") or 0),
  1 if d.get("yielded") else 0,
)
'
  )
  TOTAL_ART=$((TOTAL_ART + ART))
  TOTAL_REF=$((TOTAL_REF + REF))
  TOTAL_WIKI=$((TOTAL_WIKI + WIKI))
  TOTAL_CTX=$((TOTAL_CTX + CTX))
  DONE=$((ART + REF + WIKI + CTX))
  if [[ "$YIELDED" -eq 1 || "$DONE" -eq 0 ]]; then
    EMPTY=$((EMPTY + 1))
    log "EMPTY/YIELD streak=$EMPTY arts_total=$TOTAL_ART"
    if [[ "$EMPTY" -ge "$MAX_EMPTY" ]]; then
      log "DONE empty_streak=$EMPTY arts=$TOTAL_ART ref=$TOTAL_REF wiki=$TOTAL_WIKI ctx=$TOTAL_CTX"
      break
    fi
    sleep "$IDLE_SLEEP"
  else
    EMPTY=0
  fi
done

log "EXIT arts=$TOTAL_ART ref=$TOTAL_REF wiki=$TOTAL_WIKI ctx=$TOTAL_CTX iters=$ITER"
rm -f "$PIDFILE"
