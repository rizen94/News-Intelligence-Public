#!/usr/bin/env bash
set -euo pipefail
LOG="/home/pete/Documents/projects/News Intelligence/logs/quality_watch/api_restart_0800.log"
{
  echo "=== $(date -Is) starting scheduled API restart ==="
  systemctl --user restart news-intel-api.service
  sleep 8
  systemctl --user is-active news-intel-api.service
  curl -sS -m 5 http://127.0.0.1:8000/api/health || echo "health check failed"
  echo "=== $(date -Is) restart complete ==="
} | tee -a "$LOG"
