#!/usr/bin/env bash
# Quiesce for dedicated unified-intake catch-up: stop API competitors, keep widow-db-adjacent cron.
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
cd "$ROOT"
mkdir -p "$ROOT/logs" "$ROOT/data"

echo "=== Intake catch-up quiesce $(date -u -Iseconds) ==="

# Kill ad-hoc catch-ups (not cron — flock skips if a prior run is active)
for pattern in \
  "run_major_backlog_catchup.py" \
  "bulk_catchup.py" \
  "catchup_topic_clustering.py" \
  "run_extraction_burn_down.py" \
  "run_secondary_worker.py"; do
  pkill -f "$pattern" 2>/dev/null || true
done
sleep 2

bash "$ROOT/scripts/pause_for_bulk_catchup.sh" || true

if systemctl is-active --quiet news-intelligence-api-public 2>/dev/null; then
  echo "ERROR: news-intelligence-api-public is still active — stop API before dedicated catch-up."
  exit 1
fi

sudo systemctl stop newsplatform-secondary 2>/dev/null || true

# Ensure DB-adjacent cron stays enabled (context_sync + entity_profile_sync every 15m)
if [[ -f /etc/cron.d/widow-db-adjacent.disabled ]] && [[ ! -f /etc/cron.d/widow-db-adjacent ]]; then
  echo "Re-enabling widow-db-adjacent cron"
  sudo cp "$ROOT/infrastructure/widow-db-adjacent.cron" /etc/cron.d/widow-db-adjacent
  sudo chmod 644 /etc/cron.d/widow-db-adjacent
  sudo rm -f /etc/cron.d/widow-db-adjacent.disabled
fi

echo "Cron: $(ls -la /etc/cron.d/widow-db-adjacent 2>/dev/null || echo 'NOT INSTALLED')"
echo "Quiesce complete (cron preserved for context_sync / entity_profile_sync)"
