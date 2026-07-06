#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"
source "$KIT_ROOT/.env" 2>/dev/null || true
PORT="${INTAKE_WEB_PORT:-8080}"
FAIL=0

echo "=== verify_kit ==="

if ! docker info >/dev/null 2>&1; then
  echo "FAIL: Docker daemon not running"
  exit 1
fi

for svc in postgres ollama api intake-web open-webui; do
  if ! docker compose ps --status running "$svc" 2>/dev/null | grep -q "$svc"; then
    echo "FAIL: $svc not running"
    FAIL=1
  fi
done

curl -sf "http://localhost:${PORT}/api/setup/status" >/dev/null || { echo "FAIL: setup/status"; FAIL=1; }
curl -sf "http://localhost:${PORT}/setup/" | grep -qi setup || { echo "FAIL: setup page"; FAIL=1; }
curl -sf "http://localhost:${PORT}/api/system_monitoring/kit_status" >/dev/null || { echo "FAIL: kit_status"; FAIL=1; }

if [[ "$FAIL" -eq 0 ]]; then
  echo "verify_kit: PASS"
  curl -s "http://localhost:${PORT}/api/setup/status" | head -c 500
  echo ""
  exit 0
fi
echo "verify_kit: FAIL — run ./scripts/repair.sh"
exit 1
