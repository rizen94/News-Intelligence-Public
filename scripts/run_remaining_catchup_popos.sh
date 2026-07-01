#!/usr/bin/env bash
# Drain remaining GPU/CPU catch-up backlogs using PopOS RTX 5090 (full GPU lane).
# Run on Widow from repo root: bash scripts/run_remaining_catchup_popos.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python3"
LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="${LOG_DIR}/remaining_catchup_popos_${STAMP}.log"

exec > >(tee -a "$LOG") 2>&1

set -a
# shellcheck source=/dev/null
source "$ROOT/.env" 2>/dev/null || true
# shellcheck source=/dev/null
source "$ROOT/scripts/catchup_env.sh"
set +a

# Full PopOS GPU — no Widow CPU lane split during this window
export BULK_USE_POPOS_GPU=true
export MAJOR_CATCHUP_USE_POPOS_GPU=true
export BULK_DUAL_LANE_CATCHUP=false
export MAJOR_CATCHUP_DUAL_LANE=false
export AUTOMATION_DUAL_LANE=false
export BULK_GPU_PARALLEL="${BULK_GPU_PARALLEL:-8}"
export MAJOR_CATCHUP_GPU_PARALLEL="${MAJOR_CATCHUP_GPU_PARALLEL:-8}"
export BULK_CPU_PARALLEL="${BULK_CPU_PARALLEL:-2}"
export MAJOR_CATCHUP_CPU_PARALLEL="${MAJOR_CATCHUP_CPU_PARALLEL:-2}"
export ENTITY_EXTRACTION_PARALLEL="${ENTITY_EXTRACTION_PARALLEL:-8}"
export EVENT_EXTRACTION_PARALLEL="${EVENT_EXTRACTION_PARALLEL:-12}"
export ENTITY_EXTRACTION_RUN_BUDGET_SECONDS="${ENTITY_EXTRACTION_RUN_BUDGET_SECONDS:-3600}"
export BULK_OLLAMA_TIMEOUT="${BULK_OLLAMA_TIMEOUT:-900}"
export MAJOR_CATCHUP_OLLAMA_TIMEOUT="${MAJOR_CATCHUP_OLLAMA_TIMEOUT:-900}"
export BULK_ENTITY_EXTRACTION_PER_DOMAIN="${BULK_ENTITY_EXTRACTION_PER_DOMAIN:-600}"
export BULK_ENTITY_PARALLEL="${BULK_ENTITY_PARALLEL:-8}"
export ENTITY_PROFILE_BUILD_ANYTIME=true
export ENTITY_PROFILE_BUILD_UPSTREAM_GATE="${ENTITY_PROFILE_BUILD_UPSTREAM_GATE:-false}"
export PYTHONPATH="${PYTHONPATH:-api}"
export DB_PORT="${DB_PORT:-6432}"

repause() {
  "$PY" - <<'PY'
from shared.bulk_catchup_pause import write_pause_marker
write_pause_marker(reason="run_remaining_catchup_popos.sh", by="operator")
print("competition pause marker refreshed")
PY
}

pending_line() {
  "$PY" - <<'PY'
from services.backlog_metrics import get_all_pending_counts
pc = get_all_pending_counts()
keys = (
    "entity_extraction", "event_extraction", "entity_profile_build",
    "claim_extraction", "story_enhancement", "topic_clustering",
    "metadata_enrichment", "context_sync", "event_tracking",
)
print("pending:", {k: pc.get(k, 0) for k in keys if pc.get(k, 0)})
PY
}

echo "=== Remaining catch-up (PopOS GPU) ==="
echo "log=$LOG"
echo "PopOS host=${OLLAMA_GPU_HOST:-${OLLAMA_POP_OS_HOST:-unset}}"

if [[ -f "$ROOT/scripts/pause_for_bulk_catchup.sh" ]]; then
  bash "$ROOT/scripts/pause_for_bulk_catchup.sh" || true
fi
repause

echo "--- backlog at start ---"
pending_line

run_step() {
  local label="$1"
  shift
  echo ""
  echo "========== $label =========="
  repause
  "$@" || echo "WARN: $label exited non-zero ($?)"
  repause
  pending_line
}

# 1) Unified intake drain (replaces legacy entity/event/sentiment/quality)
run_step "unified_intake_extraction (burn-down)" \
  "$PY" api/scripts/run_extraction_burn_down.py --force --loops 0 --floor 0 \
  --phases unified_intake_extraction \
  --budget-seconds "${UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS:-14400}" \
  --gpu-parallel "$BULK_GPU_PARALLEL" --cpu-parallel "$BULK_CPU_PARALLEL" \
  --ollama-timeout "$BULK_OLLAMA_TIMEOUT"

# 2) Major GPU phases: profile build → story → dossier (no event_extraction — unified owns events)
run_step "major backlog (profile, story, dossier)" \
  "$PY" api/scripts/run_major_backlog_catchup.py --force --use-popos-gpu --no-dual-lane \
  --gpu-parallel "$MAJOR_CATCHUP_GPU_PARALLEL" --loops 250 --floor 0 \
  --phases entity_profile_build story_enhancement entity_dossier_compile

# 3) Claim drain
run_step "claim extraction drain" \
  "$PY" api/scripts/run_event_extraction_catchup.py \
  --loops 999 --budget-seconds 7200 --per-schema 120 --batch-size 4 --phase claim_extraction

# 4) Bulk claim / metadata / context / event tracking
for phase in claim_extraction metadata_enrichment context_sync event_tracking; do
  run_step "bulk $phase" \
    "$PY" api/scripts/bulk_catchup.py --force --use-popos-gpu --no-dual-lane \
    --phase "$phase" --loops 200 --floor 0
done

# 5) Topic clustering (Widow CPU/GPU mix via service defaults)
run_step "topic_clustering" \
  "$PY" api/scripts/catchup_topic_clustering.py --batch-size 50 --concurrency 8 --max-batches 800

echo ""
echo "--- backlog at end ---"
pending_line

repause
echo "=== Catch-up chain finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "Resume automation when satisfied: bash scripts/resume_after_bulk_catchup.sh"
