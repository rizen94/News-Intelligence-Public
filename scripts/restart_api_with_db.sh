#!/bin/bash
#
# Restart News Intelligence API (production: systemd; fallback: manual uvicorn).
#
# On Widow production (/opt/news-intelligence), prefer:
#   sudo systemctl restart news-intelligence-api-public
# Install stack: ./scripts/setup_widow_boot_stack.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if systemctl list-unit-files news-intelligence-api-public.service &>/dev/null 2>&1 \
  && systemctl is-enabled news-intelligence-api-public &>/dev/null 2>&1; then
  echo "🔄 Restarting news-intelligence-api-public via systemd..."
  sudo systemctl restart news-intelligence-api-public
  echo "✅ Restart requested — check: systemctl status news-intelligence-api-public"
  echo "   Readiness: curl -s http://127.0.0.1:8000/api/system_monitoring/startup/readiness | jq .ready"
  exit 0
fi

# Fallback: legacy manual restart (dev or pre-systemd hosts)
exec "$SCRIPT_DIR/restart_api_with_db_manual.sh"
