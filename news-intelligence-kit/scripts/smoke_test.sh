#!/usr/bin/env bash
# Post-install smoke test (sports + entertainment headless provision optional)
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"

echo "=== smoke_test ==="
"$KIT_ROOT/scripts/verify_kit.sh"

BASE="http://localhost:${INTAKE_WEB_PORT:-8080}"
curl -sf "$BASE/setup/" | grep -qi "Setup" || { echo "setup page missing"; exit 1; }

STATUS=$(curl -sf "$BASE/api/setup/status")
echo "$STATUS" | grep -q db_ok || { echo "setup status bad"; exit 1; }

if [[ "${SMOKE_PROVISION:-}" == "1" ]]; then
  SPEC="$KIT_ROOT/config/setup/smoke_domains.json"
  if [[ -f "$SPEC" ]]; then
    docker compose exec -T api python3 /app/kit/scripts/provision_from_spec.py /app/kit/config/setup/smoke_domains.json || true
  fi
fi

echo "smoke_test: PASS"
