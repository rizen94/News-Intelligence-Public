#!/usr/bin/env bash
# Dedicated PopOS GPU unified-intake burn-down. API must be stopped; cron keeps sync phases moving.
#
#   sudo systemctl stop news-intelligence-api-public.service
#   bash scripts/start_dedicated_unified_catchup.sh
#
# Resume API when done:
#   bash scripts/resume_after_bulk_catchup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export NEWS_INTEL_ROOT="$ROOT"

LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR" "${ROOT}/data"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/dedicated_unified_catchup_${STAMP}.log"
PID_FILE="${ROOT}/data/dedicated_unified_catchup.pid"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${old_pid:-}" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Dedicated unified catch-up already running (pid $old_pid)"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

bash "$ROOT/scripts/quiesce_for_intake_catchup.sh"

set -a
# shellcheck source=/dev/null
source "$ROOT/.env" 2>/dev/null || true
# shellcheck source=/dev/null
source "$ROOT/scripts/catchup_env.sh"
set +a

# Dedicated burn-down profile (PopOS 5090 saturated, no API worker pool contention)
export BULK_USE_POPOS_GPU=true
export BULK_DUAL_LANE_CATCHUP=false
export AUTOMATION_DUAL_LANE=false
export UNIFIED_INTAKE_EXTRACTION_PARALLEL=8
export UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS=14400
export UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE=6
export BULK_EXTRACTION_MODEL=qwen2.5:14b-instruct
export FAST_NER_BACKEND=spacy
export OLLAMA_GPU_CONCURRENCY=8
export BULK_GPU_PARALLEL=8
export BULK_CPU_PARALLEL=2
export BULK_OLLAMA_TIMEOUT=900
export PYTHONPATH="${PYTHONPATH:-api}"
export DB_PORT="${DB_PORT:-6432}"

echo "==> Starting dedicated unified intake burn-down"
echo "    UNIFIED_INTAKE_PARALLEL=$UNIFIED_INTAKE_EXTRACTION_PARALLEL"
echo "    UNIFIED_INTAKE_BUDGET=${UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS}s"
echo "    UNIFIED_INTAKE_BATCH_SIZE=$UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE"
echo "    BULK_EXTRACTION_MODEL=$BULK_EXTRACTION_MODEL"
echo "    FAST_NER_BACKEND=$FAST_NER_BACKEND"
echo "    OLLAMA_GPU_CONCURRENCY=$OLLAMA_GPU_CONCURRENCY"
echo "    log=$LOG"
echo "    (widow-db-adjacent cron continues context_sync + entity_profile_sync)"

nohup "$ROOT/.venv/bin/python3" api/scripts/run_extraction_burn_down.py \
  --force --loops 0 --floor 0 \
  --phases unified_intake_extraction \
  --budget-seconds "$UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS" \
  --gpu-parallel "$BULK_GPU_PARALLEL" \
  --cpu-parallel "$BULK_CPU_PARALLEL" \
  --ollama-timeout "$BULK_OLLAMA_TIMEOUT" \
  >>"$LOG" 2>&1 &
echo $! >"$PID_FILE"
echo "   PID $(cat "$PID_FILE")"
echo "   tail -f $LOG"
