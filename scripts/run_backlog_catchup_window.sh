#!/usr/bin/env bash
# Operator maintenance window: drain large automation backlogs on Widow.
# Run from repo root on Widow (pauses automation via bulk_catchup_pause marker).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="/opt/news-intelligence/.venv/bin/python3"
fi

set -a
# shellcheck source=/dev/null
source "$ROOT/.env" 2>/dev/null || true
set +a
# shellcheck source=/dev/null
source "$ROOT/scripts/catchup_env.sh"

# Steady-state automation (API process) — raise limits while catch-up runs
export METADATA_ENRICHMENT_LIMIT_PER_DOMAIN="${METADATA_ENRICHMENT_LIMIT_PER_DOMAIN:-40}"
export ENTITY_PROFILE_BUILD_LIMIT="${ENTITY_PROFILE_BUILD_LIMIT:-75}"
export ENTITY_DOSSIER_COMPILE_MAX="${ENTITY_DOSSIER_COMPILE_MAX:-50}"

PHASE="${1:-all}"
LOOPS="${BULK_CATCHUP_LOOPS:-80}"
FORCE="${BULK_CATCHUP_FORCE:---force}"

run_phase() {
  local phase="$1"
  echo "=== bulk_catchup phase=$phase loops=$LOOPS ==="
  "$PY" api/scripts/bulk_catchup.py $FORCE --phase "$phase" --loops "$LOOPS"
}

case "$PHASE" in
  metadata_enrichment)
    run_phase metadata_enrichment
    ;;
  entity_extraction)
    run_phase entity_extraction
    ;;
  topic_clustering)
    # Automation owns steady-state; dual-host routing helps GPU phases after API restart.
    echo "topic_clustering: rely on automation with OLLAMA_DUAL_HOST_ROUTING_ENABLED=true"
  ;;
  all)
    run_phase metadata_enrichment
    run_phase entity_extraction
    ;;
  *)
    echo "Usage: $0 [metadata_enrichment|entity_extraction|topic_clustering|all]" >&2
    exit 1
    ;;
esac
