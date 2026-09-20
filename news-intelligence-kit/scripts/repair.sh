#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"
source "$KIT_ROOT/.env" 2>/dev/null || true
PORT="${INTAKE_WEB_PORT:-8080}"

echo "=== News Intelligence Kit repair ==="

if ! docker info >/dev/null 2>&1; then
  echo "REPAIR: FAIL — start Docker daemon"
  exit 1
fi

docker compose up -d
sleep 5

if ! docker compose exec -T postgres pg_isready -U "${DB_USER:-newsapp}" -q 2>/dev/null; then
  echo "Restarting postgres..."
  docker compose restart postgres
  sleep 8
fi

if ! docker compose exec -T ollama ollama list >/dev/null 2>&1; then
  echo "Restarting ollama..."
  docker compose restart ollama
  sleep 5
fi

"$KIT_ROOT/scripts/pull_ollama_models.sh" || true
docker compose restart api
sleep 8

# Disk warning
DATA_PCT=$(df -P "$KIT_ROOT/data" 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}' || echo 0)
if [[ "${DATA_PCT:-0}" -gt 90 ]]; then
  echo "WARNING: data/ disk usage ${DATA_PCT}% — free space soon"
fi

SETUP=$(curl -sf "http://localhost:${PORT}/api/setup/status" 2>/dev/null || echo '{}')
if echo "$SETUP" | grep -q '"setup_complete": false'; then
  echo "REPAIR: OK (setup incomplete) — open http://localhost:${PORT}/setup/"
  exit 0
fi

if "$KIT_ROOT/scripts/verify_kit.sh"; then
  echo "REPAIR: OK — see docs/TROUBLESHOOTING.md if issues persist"
else
  echo "REPAIR: issues remain — docs/TROUBLESHOOTING.md"
  exit 1
fi
