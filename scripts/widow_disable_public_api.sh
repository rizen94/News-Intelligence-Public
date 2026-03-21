#!/usr/bin/env bash
# On Widow: stop and disable the optional public FastAPI unit (AutomationManager belongs on main GPU host only).
# nginx on Widow can still proxy /api to the main PC (PUBLIC_API_UPSTREAM).
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo on Widow." >&2
  exit 1
fi
systemctl disable --now news-intelligence-api-public.service 2>/dev/null || true
echo "news-intelligence-api-public disabled. Point nginx upstream at main host:8000 if needed."
