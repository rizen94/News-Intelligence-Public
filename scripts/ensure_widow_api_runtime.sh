#!/usr/bin/env bash
# Ensure Widow production API is the systemd unit under /opt/news-intelligence.
# Stops ad-hoc workspace uvicorn on :8000 so AutomationManager has a single runtime.
#
# Run ON Widow (or: ssh widow 'bash -s' < scripts/ensure_widow_api_runtime.sh)
# Prefer: ./scripts/deploy_to_widow.sh then this script if unit was inactive.
set -euo pipefail

DEPLOY_DIR="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
UNIT="${NEWS_INTEL_API_UNIT:-news-intelligence-api-public}"
WORKSPACE_HINT="${NEWS_INTEL_WORKSPACE:-/home/pete/Documents/projects/News Intelligence}"

echo "=== ensure Widow API runtime ==="
echo "DEPLOY_DIR=$DEPLOY_DIR UNIT=$UNIT"

if [[ ! -d "$DEPLOY_DIR/api" ]]; then
  echo "FAIL: $DEPLOY_DIR/api missing — run scripts/deploy_to_widow.sh first" >&2
  exit 1
fi

# Kill workspace / stray uvicorn holding :8000 (not the systemd unit)
mapfile -t PIDS < <(ss -ltnp 2>/dev/null | awk '/:8000/ {print}' | grep -oP 'pid=\K[0-9]+' || true)
for pid in "${PIDS[@]:-}"; do
  [[ -z "${pid:-}" ]] && continue
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  cmd="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  if [[ "$cwd" == "$DEPLOY_DIR"* ]] || [[ "$cmd" == *"$DEPLOY_DIR"* ]]; then
    echo "OK: pid $pid already under deploy dir ($cwd)"
    continue
  fi
  if [[ "$cwd" == "$WORKSPACE_HINT"* ]] || [[ "$cmd" == *"Documents/projects/News Intelligence"* ]]; then
    echo "Stopping workspace uvicorn pid=$pid cwd=$cwd"
    kill "$pid" 2>/dev/null || true
    sleep 2
    kill -9 "$pid" 2>/dev/null || true
  fi
done

if [[ ! -f "/etc/systemd/system/${UNIT}.service" ]] && [[ ! -f "/lib/systemd/system/${UNIT}.service" ]]; then
  echo "Installing unit from $DEPLOY_DIR/infrastructure/${UNIT}.service"
  sudo cp "$DEPLOY_DIR/infrastructure/${UNIT}.service" "/etc/systemd/system/${UNIT}.service"
  sudo systemctl daemon-reload
fi

sudo systemctl enable "$UNIT"
sudo systemctl restart "$UNIT"
sleep 4
sudo systemctl --no-pager --full status "$UNIT" | head -20

if ! systemctl is-active --quiet "$UNIT"; then
  echo "FAIL: $UNIT not active" >&2
  exit 1
fi

# Verify listener cwd
listen_pid="$(ss -ltnp 2>/dev/null | awk '/:8000/ {print}' | grep -oP 'pid=\K[0-9]+' | head -1 || true)"
if [[ -n "${listen_pid:-}" ]]; then
  cwd="$(readlink -f "/proc/$listen_pid/cwd" 2>/dev/null || true)"
  echo "Listener pid=$listen_pid cwd=$cwd"
  if [[ "$cwd" != "$DEPLOY_DIR"* ]]; then
    echo "FAIL: :8000 not under $DEPLOY_DIR (got $cwd)" >&2
    exit 1
  fi
fi

curl -sf --max-time 10 "http://127.0.0.1:8000/api/ping" | head -c 120 || {
  echo "FAIL: ping" >&2
  exit 1
}
echo
echo "OK: $UNIT serving from $DEPLOY_DIR"
