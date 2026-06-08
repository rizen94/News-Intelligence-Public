#!/bin/bash
# Post-start readiness wait for news-intelligence-api-public.service
set -euo pipefail

URL="${NI_READINESS_URL:-http://127.0.0.1:8000/api/system_monitoring/startup/readiness}"
MAX_ATTEMPTS="${NI_READINESS_ATTEMPTS:-36}"
SLEEP_SEC="${NI_READINESS_SLEEP_SEC:-5}"

for i in $(seq 1 "$MAX_ATTEMPTS"); do
  if response=$(curl -sf --max-time 5 "$URL" 2>/dev/null); then
    if echo "$response" | grep -q '"ready"[[:space:]]*:[[:space:]]*true'; then
      echo "systemd_wait_readiness: ready after ${i} attempt(s)"
      exit 0
    fi
  fi
  sleep "$SLEEP_SEC"
done

echo "systemd_wait_readiness: API did not become ready within $((MAX_ATTEMPTS * SLEEP_SEC))s" >&2
exit 1
