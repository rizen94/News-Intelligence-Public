#!/bin/bash
# Post-unification cutover verification (extends verify_widow_boot.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000}"
FAIL=0

echo "=== Unification cutover verification ==="

if ! "$SCRIPT_DIR/verify_widow_boot.sh"; then
  echo "❌ verify_widow_boot.sh failed"
  FAIL=1
fi

echo ""
echo "Investigation API..."
if curl -sf "$API_BASE/api/investigation/health" | tee /tmp/inv_health.json | head -c 200; then
  echo ""
  if ! grep -q '"status"' /tmp/inv_health.json 2>/dev/null; then
    echo "⚠️  investigation health missing status field"
  fi
else
  echo "❌ /api/investigation/health unreachable"
  FAIL=1
fi

echo ""
if curl -sf "$API_BASE/api/investigation/resolution_stats" | head -c 400; then
  echo ""
else
  echo "❌ /api/investigation/resolution_stats unreachable"
  FAIL=1
fi

echo ""
echo "Legacy /api/nri shim removed (expect 404)..."
if curl -sf -o /dev/null -w "%{http_code}" "$API_BASE/api/nri/health" | grep -q 404; then
  echo "✅ /api/nri/health returns 404 as expected"
elif curl -sf "$API_BASE/api/nri/health" >/dev/null 2>&1; then
  echo "⚠️  /api/nri/health still active — deploy investigation.py without legacy router"
  FAIL=1
else
  echo "✅ /api/nri/health unreachable (shim removed)"
fi

echo ""
echo "Retired NRI systemd units (should be inactive)..."
for unit in nri-api.service nri-mention-resolver.timer nri-loop.timer; do
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    echo "❌ $unit still active — disable per UNIFICATION_CUTOVER.md"
    FAIL=1
  else
    echo "✅ $unit inactive or not installed"
  fi
done

echo ""
echo "nri_core import smoke..."
PY="${PROJECT_DIR}/.venv/bin/python3"
if [ ! -x "$PY" ]; then PY="${PROJECT_DIR}/api/.venv/bin/python3"; fi
if [ ! -x "$PY" ]; then PY="python3"; fi
if [ -f "$PROJECT_DIR/.env" ]; then set -a; source "$PROJECT_DIR/.env"; set +a; fi
if (cd "$PROJECT_DIR/api" && PYTHONPATH=. "$PY" -c "
from nri_core.services.integration import get_investigation_health
from config.investigation_tables import T_RESOLVED_MENTIONS
print('T_RESOLVED_MENTIONS=', T_RESOLVED_MENTIONS)
print('import ok')
"); then
  :
else
  echo "❌ nri_core import failed"
  FAIL=1
fi

echo ""
echo "SSOT script..."
if (cd "$PROJECT_DIR" && PYTHONPATH=api python3 scripts/verify_single_source_of_truth.py); then
  :
else
  echo "⚠️  SSOT violations present (see output)"
  FAIL=1
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "=== Unification verify complete (PASS) ==="
  exit 0
fi
echo "=== Unification verify complete (FAIL) ==="
exit 1
