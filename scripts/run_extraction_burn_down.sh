#!/usr/bin/env bash
# Phased extraction burn-down (claims → entity → event → topic_clustering).
# Pauses competing automation; saturates PopOS GPU for bulk extraction.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
set -a
# shellcheck disable=SC1091
[ -f .env ] && source .env
set +a
# shellcheck disable=SC1091
source "$ROOT/scripts/catchup_env.sh"
export PYTHONPATH="${PYTHONPATH:-api}"
exec python3 api/scripts/run_extraction_burn_down.py --force "$@"
