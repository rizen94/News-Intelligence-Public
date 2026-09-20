#!/usr/bin/env bash
# Verify PopOS GPU + Widow local lanes for bulk catch-up.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export BULK_DUAL_LANE_CATCHUP=1
export OLLAMA_DUAL_HOST_ROUTING_ENABLED=true
export OLLAMA_GPU_HOST="${OLLAMA_POP_OS_HOST:-http://192.168.93.99:11434}"
export OLLAMA_CPU_HOST="${OLLAMA_HOST:-http://localhost:11434}"
export BULK_USE_POPOS_EXTRACTION=1
PYTHONPATH=api .venv/bin/python3 api/scripts/verify_dual_lane_catchup.py "$@"
