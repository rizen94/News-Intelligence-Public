#!/bin/bash
# Post-start readiness wait for news-intelligence-api-public.service
#
# Keep this short: with Type=simple, a long ExecStartPost leaves the unit in
# "activating (start-post)" and makes restarts feel like an outage even when
# uvicorn is already accepting traffic. Prefer nonblocking-readiness.conf
# (ignore-fail + TimeoutStartSec=120) on Widow.
set -euo pipefail

URL="${NI_READINESS_URL:-http://127.0.0.1:8000/api/system_monitoring/startup/readiness}"
MAX_ATTEMPTS="${NI_READINESS_ATTEMPTS:-24}"
SLEEP_SEC="${NI_READINESS_SLEEP_SEC:-2}"

for i in $(seq 1 "$MAX_ATTEMPTS"); do
  if response=$(curl -sf --max-time 3 "$URL" 2>/dev/null); then
    if echo "$response" | grep -q '"ready"[[:space:]]*:[[:space:]]*true'; then
      echo "systemd_wait_readiness: ready after ${i} attempt(s)"
      exit 0
    fi
  fi
  sleep "$SLEEP_SEC"
done

echo "systemd_wait_readiness: API did not become ready within $((MAX_ATTEMPTS * SLEEP_SEC))s (continuing; ExecStartPost should be ignore-fail)" >&2
exit 1
