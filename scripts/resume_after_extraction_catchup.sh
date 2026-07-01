#!/usr/bin/env bash
# Restart NI API after focused extraction catch-up completes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export NEWS_INTEL_ROOT="$ROOT"
PID_FILE="${ROOT}/data/extraction_catchup.pid"

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "Catch-up still running (pid $pid). Wait or: kill $pid"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

if [[ -x "$ROOT/scripts/resume_after_bulk_catchup.sh" ]]; then
  bash "$ROOT/scripts/resume_after_bulk_catchup.sh"
else
  PYTHONPATH=api python3 - <<'PY'
from shared.bulk_catchup_pause import clear_pause_marker
clear_pause_marker()
print("Cleared competition pause marker")
PY
fi

echo "==> Starting News Intelligence API with project .env + catch-up overlay"
set -a
# shellcheck disable=SC1091
[[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
# shellcheck disable=SC1091
[[ -f "$ROOT/configs/env.extraction_catchup.env" ]] && source "$ROOT/configs/env.extraction_catchup.env"
set +a
if systemctl list-unit-files news-intelligence-api-public.service &>/dev/null 2>&1 \
  && systemctl is-enabled news-intelligence-api-public &>/dev/null 2>&1; then
  sudo systemctl start news-intelligence-api-public.service
  echo "   started news-intelligence-api-public.service"
  echo "   readiness: curl -s http://127.0.0.1:8000/api/system_monitoring/startup/readiness | jq .ready"
else
  exec "$ROOT/scripts/restart_api_with_db_manual.sh"
fi
