#!/usr/bin/env bash
# Sample Widow root disk IO and write /run/news-intelligence/disk_io_pressure.json (tmpfs).
# Optionally publish to public.disk_io_pressure_advisory when NI venv + DB are available.
#
# Install: systemd timer widow-disk-io-governor.timer (every 15s) via setup_widow_boot_stack
# or: */1 * * * * root ... (prefer systemd).
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
RUN_DIR="${DISK_IO_PRESSURE_RUN_DIR:-/run/news-intelligence}"
export DISK_IO_PRESSURE_RUN_DIR="$RUN_DIR"
mkdir -p "$RUN_DIR"

# Load NI DB env so optional advisory upsert works
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${ROOT}/.env"
  set +a
fi

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || true)"
fi
if [[ -z "$PY" ]]; then
  echo "widow_disk_io_governor: no python" >&2
  exit 1
fi

export PYTHONPATH="${ROOT}/api${PYTHONPATH:+:$PYTHONPATH}"
cd "${ROOT}/api" 2>/dev/null || cd "$ROOT" || true

# Sample → /run JSON always; DB upsert best-effort (fail-open if DB down).
"$PY" - <<'PY'
from shared.database.disk_io_pressure_advisory import publish_disk_io_pressure_advisory

signal = publish_disk_io_pressure_advisory(source="governor", force=True) or {}
print(
    f"device={signal.get('device')} util={signal.get('util_pct')} "
    f"w_kb_s={signal.get('write_kb_s')} "
    f"heavy={signal.get('defer_heavy_writes')} work={signal.get('defer_new_work')}"
)
PY
