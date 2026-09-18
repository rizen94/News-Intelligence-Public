#!/usr/bin/env bash
# Pause NI/NRI work that competes with api/scripts/bulk_catchup.py on Widow.
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
MARKER="$ROOT/data/bulk_catchup_competition_pause.json"
STATE="$ROOT/data/bulk_catchup_pause_services.json"

cd "$ROOT"
mkdir -p "$ROOT/data"

if [[ -f "$MARKER" ]]; then
  echo "Pause marker already present: $MARKER"
else
  PYTHONPATH=api .venv/bin/python3 - <<'PY'
from shared.bulk_catchup_pause import write_pause_marker
write_pause_marker(reason="pause_for_bulk_catchup.sh", by="operator")
print("Wrote competition pause marker")
PY
fi

# Record service states for resume
was_active() { systemctl is-active --quiet "$1" 2>/dev/null; }
timer_enabled() { systemctl is-enabled --quiet "$1" 2>/dev/null; }

RSS_ACTIVE=false
NRI_MENTION_TIMER=false
NRI_LOOP_TIMER=false
was_active newsplatform-secondary && RSS_ACTIVE=true
timer_enabled nri-mention-resolver.timer && NRI_MENTION_TIMER=true
timer_enabled nri-loop.timer && NRI_LOOP_TIMER=true

python3 - <<PY
import json
from pathlib import Path
state = {
    "newsplatform_secondary_was_active": $([ "$RSS_ACTIVE" = true ] && echo True || echo False),
    "nri_mention_resolver_timer_enabled": $([ "$NRI_MENTION_TIMER" = true ] && echo True || echo False),
    "nri_loop_timer_enabled": $([ "$NRI_LOOP_TIMER" = true ] && echo True || echo False),
}
Path("$STATE").write_text(json.dumps(state, indent=2))
print("Saved service state to $STATE")
PY

# Stop ingest / NRI batch timers (API stays up for Monitor; automation defers via marker)
for unit in newsplatform-secondary nri-mention-resolver.service; do
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    echo "Stopping $unit"
    sudo systemctl stop "$unit" || systemctl --user stop "$unit" 2>/dev/null || true
  fi
done
for timer in nri-mention-resolver.timer nri-loop.timer; do
  if systemctl is-enabled --quiet "$timer" 2>/dev/null; then
    echo "Stopping $timer"
    sudo systemctl stop "$timer" || true
  fi
done

# Backfill mode pauses RSS inside collection_cycle if API restarts before marker is read
if ! grep -q '^PIPELINE_BACKFILL_MODE=' "$ROOT/.env" 2>/dev/null; then
  echo "PIPELINE_BACKFILL_MODE=true" >> "$ROOT/.env"
elif ! grep -q '^PIPELINE_BACKFILL_MODE=true' "$ROOT/.env"; then
  sed -i 's/^PIPELINE_BACKFILL_MODE=.*/PIPELINE_BACKFILL_MODE=true/' "$ROOT/.env"
fi
RESUME_AT="$(date -u -d '+7 days' +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null || date -u -v+7d +%Y-%m-%dT%H:%M:%S+00:00)"
if grep -q '^PIPELINE_BACKFILL_COLLECTION_RESUME_AT=' "$ROOT/.env"; then
  sed -i "s|^PIPELINE_BACKFILL_COLLECTION_RESUME_AT=.*|PIPELINE_BACKFILL_COLLECTION_RESUME_AT=$RESUME_AT|" "$ROOT/.env"
else
  echo "PIPELINE_BACKFILL_COLLECTION_RESUME_AT=$RESUME_AT" >> "$ROOT/.env"
fi

# Block GNOME/logind idle suspend while bulk runs (logind idle=ignore is set on Widow).
INHIBIT_PID_FILE="$ROOT/data/bulk_catchup_sleep_inhibit.pid"
if [[ -f "$INHIBIT_PID_FILE" ]] && kill -0 "$(cat "$INHIBIT_PID_FILE")" 2>/dev/null; then
  echo "Sleep inhibit already active (pid $(cat "$INHIBIT_PID_FILE"))"
elif command -v systemd-inhibit >/dev/null 2>&1; then
  if systemd-inhibit --what=sleep:idle:shutdown --who=news-intelligence-bulk \
      --why="bulk catch-up in progress" --mode=block true 2>/dev/null; then
    systemd-inhibit --what=sleep:idle:shutdown --who=news-intelligence-bulk \
      --why="bulk catch-up in progress" --mode=block sleep infinity &
    echo $! > "$INHIBIT_PID_FILE"
    echo "Started sleep inhibit (pid $(cat "$INHIBIT_PID_FILE"))"
  else
    rm -f "$INHIBIT_PID_FILE"
    echo "Note: systemd-inhibit not permitted (idle suspend already disabled via logind/GNOME)"
  fi
fi

echo "Done. Cron db-adjacent skips sync while marker exists."
echo "Run bulk: cd $ROOT && PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup.py --force"
echo "Resume:   $ROOT/scripts/resume_after_bulk_catchup.sh"
