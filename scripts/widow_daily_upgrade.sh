#!/usr/bin/env bash
# Daily apt update + upgrade for Widow (USB root) — gated by disk IO pressure.
# Scheduled 03:30 US/Eastern via /etc/cron.d/widow-daily-upgrade.
#
# Env:
#   WIDOW_DISK_IO_FORCE=1     — skip pressure gate
#   WIDOW_DISK_IO_MAX_DEFER=6 — max systemd-run reschedules per calendar day
#   NEWS_INTEL_ROOT           — default /opt/news-intelligence
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG_DIR=/var/log/widow-daily-upgrade
LOG="${LOG_DIR}/upgrade.log"
RUN_JSON="${DISK_IO_PRESSURE_RUN_PATH:-/run/news-intelligence/disk_io_pressure.json}"
LOCK_FILE=/run/lock/widow-daily-upgrade.lock
DEFER_COUNT_FILE="/run/news-intelligence/widow-daily-upgrade.defer_count"
MAX_DEFER="${WIDOW_DISK_IO_MAX_DEFER:-6}"

mkdir -p "$LOG_DIR" /run/news-intelligence /run/lock
exec >>"$LOG" 2>&1

echo "========================================"
echo "START $(date -Is) ($(timedatectl show -p Timezone --value 2>/dev/null || echo unknown))"
echo "========================================"

# Serialize against apt-daily-upgrade / concurrent runs
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "SKIP $(date -Is): another apt/upgrade holds $LOCK_FILE"
  exit 0
fi

_refresh_pressure() {
  if [[ -x /usr/local/sbin/widow_disk_io_governor.sh ]]; then
    /usr/local/sbin/widow_disk_io_governor.sh || true
  elif [[ -x "${ROOT}/scripts/widow_disk_io_governor.sh" ]]; then
    NEWS_INTEL_ROOT="$ROOT" "${ROOT}/scripts/widow_disk_io_governor.sh" || true
  fi
}

_should_defer_heavy() {
  if [[ "${WIDOW_DISK_IO_FORCE:-}" == "1" ]]; then
    return 1
  fi
  _refresh_pressure
  if [[ ! -f "$RUN_JSON" ]]; then
    # Fail-open if governor never ran
    return 1
  fi
  # Prefer python parse; fall back to grep
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$RUN_JSON" <<'PY'
import json, sys, time
from datetime import datetime, timezone
path = sys.argv[1]
try:
    data = json.load(open(path))
except Exception:
    sys.exit(0)  # fail-open
written = data.get("written_at") or data.get("updated_at")
age = 9999.0
if written:
    try:
        ts = datetime.fromisoformat(str(written).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
    except Exception:
        age = 9999.0
if age > 120:
    sys.exit(0)  # stale → fail-open
defer = bool(data.get("defer_heavy_writes") or data.get("defer_new_work"))
sys.exit(1 if defer else 0)
PY
    return $?
  fi
  if grep -q '"defer_heavy_writes": true' "$RUN_JSON" 2>/dev/null \
    || grep -q '"defer_new_work": true' "$RUN_JSON" 2>/dev/null; then
    return 0
  fi
  return 1
}

_defer_count_today() {
  local today count
  today="$(date +%F)"
  if [[ -f "$DEFER_COUNT_FILE" ]]; then
    read -r file_day count <"$DEFER_COUNT_FILE" || true
    if [[ "${file_day:-}" == "$today" ]]; then
      echo "${count:-0}"
      return
    fi
  fi
  echo 0
}

_bump_defer_count() {
  local today count
  today="$(date +%F)"
  count="$(_defer_count_today)"
  count=$((count + 1))
  echo "$today $count" >"$DEFER_COUNT_FILE"
  echo "$count"
}

_reschedule() {
  local count
  count="$(_bump_defer_count)"
  if [[ "$count" -gt "$MAX_DEFER" ]]; then
    echo "ABORT $(date -Is): disk still hot after $MAX_DEFER defers today; giving up"
    exit 0
  fi
  echo "DEFER $(date -Is): disk IO hot (defer #$count/$MAX_DEFER); systemd-run +30min"
  if command -v systemd-run >/dev/null 2>&1; then
    systemd-run --on-active=30min --unit="widow-daily-upgrade-defer-${count}" \
      /usr/local/sbin/widow-daily-upgrade.sh || \
      systemd-run --on-active=30min /usr/local/sbin/widow-daily-upgrade.sh || true
  else
    echo "WARN: systemd-run unavailable; not rescheduled"
  fi
  exit 0
}

if _should_defer_heavy; then
  _reschedule
fi

# Low IO priority for package writes on USB root
run_apt() {
  nice -n 19 ionice -c3 apt-get "$@"
}

run_apt update -y
run_apt upgrade -y \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold"

# Keep Pi-hole itself current (non-interactive); gravity stays on Pi-hole's weekly cron
if command -v pihole >/dev/null 2>&1; then
  echo "--- pihole -up ---"
  nice -n 19 ionice -c3 pihole -up || echo "WARN: pihole -up failed (exit $?)"
fi

run_apt autoremove -y || true
run_apt autoclean -y || true

echo "END $(date -Is)"
echo
