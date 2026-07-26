#!/usr/bin/env bash
# Install PopOS phase workers (user systemd by default).
# Default: three split workers (UIE / claim+topic / assembly) under a target.
# Legacy monolith: --monolith
# System unit (sudo): --system  (monolith only; prefer --user split)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LINK="${HOME}/ni-popos-worker"
USER_UNIT_DIR="${HOME}/.config/systemd/user"
MODE="split"
[[ "${1:-}" == "--monolith" ]] && MODE="monolith"
[[ "${1:-}" == "--system" ]] && MODE="system"
[[ "${1:-}" == "--user" ]] && MODE="split"

mkdir -p "$ROOT/logs" "$USER_UNIT_DIR"
ln -sfn "$ROOT" "$LINK"

install_user_unit() {
  local src="$1"
  local name
  name="$(basename "$src")"
  # strip .user.service → .service for systemd
  local dst_name="${name%.user.service}.service"
  [[ "$dst_name" == "$name" ]] || true
  if [[ "$name" == *.user.service ]]; then
    dst_name="${name%.user.service}.service"
  elif [[ "$name" == *.target ]]; then
    dst_name="$name"
  else
    dst_name="$name"
  fi
  cp "$src" "${USER_UNIT_DIR}/${dst_name}"
  echo "installed ${USER_UNIT_DIR}/${dst_name}"
}

if [[ "$MODE" == "system" ]]; then
  UNIT_ROOT=/opt/ni-popos-worker
  sudo ln -sfn "$ROOT" "$UNIT_ROOT"
  sudo cp "$ROOT/infrastructure/news-intelligence-popos-worker.service" /etc/systemd/system/news-intelligence-popos-worker.service
  sudo systemctl daemon-reload
  sudo systemctl disable --now news-intelligence-popos-worker 2>/dev/null || true
  sudo systemctl reset-failed news-intelligence-popos-worker 2>/dev/null || true
  sudo systemctl enable --now news-intelligence-popos-worker
  systemctl is-active news-intelligence-popos-worker
  exit 0
fi

if [[ "$MODE" == "monolith" ]]; then
  # Stop split workers if present
  systemctl --user disable --now \
    news-intelligence-popos-worker-uie \
    news-intelligence-popos-worker-claim-topic \
    news-intelligence-popos-worker-assembly \
    news-intelligence-popos-workers.target 2>/dev/null || true
  cat >"${USER_UNIT_DIR}/news-intelligence-popos-worker.service" <<'EOF'
[Unit]
Description=News Intelligence PopOS phase worker (monolith)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pete/ni-popos-worker
Environment=PYTHONPATH=/home/pete/ni-popos-worker/api
Environment=WORKER_EXECUTION_HOST=popos
Environment=OLLAMA_HOST=http://127.0.0.1:11434
Environment=OLLAMA_DUAL_HOST_ROUTING_ENABLED=false
Environment=AUTOMATION_DUAL_LANE=false
Environment=BULK_DUAL_LANE_CATCHUP=false
EnvironmentFile=-/home/pete/ni-popos-worker/.env
EnvironmentFile=-/home/pete/ni-popos-worker/.env.popos_worker
ExecStartPre=/bin/mkdir -p /home/pete/ni-popos-worker/logs
ExecStart=/home/pete/ni-popos-worker/.venv/bin/python /home/pete/ni-popos-worker/scripts/run_popos_phase_worker.py --worker-id monolith --phases unified_intake_extraction,claim_extraction,topic_clustering,storyline_assembly
Restart=always
RestartSec=15
TimeoutStartSec=120
MemoryMax=24G
StandardOutput=journal
StandardError=journal
SyslogIdentifier=news-intelligence-popos-worker

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  loginctl enable-linger "$USER" 2>/dev/null || true
  systemctl --user enable --now news-intelligence-popos-worker
  sleep 2
  systemctl --user status news-intelligence-popos-worker --no-pager -l | head -20
  exit 0
fi

# --- split mode (default) ---
# Disable monolith so it cannot fight split workers for the same queues.
systemctl --user disable --now news-intelligence-popos-worker 2>/dev/null || true

install_user_unit "$ROOT/infrastructure/news-intelligence-popos-worker-uie.user.service"
install_user_unit "$ROOT/infrastructure/news-intelligence-popos-worker-claim-topic.user.service"
install_user_unit "$ROOT/infrastructure/news-intelligence-popos-worker-assembly.user.service"
install_user_unit "$ROOT/infrastructure/news-intelligence-popos-worker-editorial.user.service"
cp "$ROOT/infrastructure/news-intelligence-popos-workers.target" \
  "${USER_UNIT_DIR}/news-intelligence-popos-workers.target"

systemctl --user daemon-reload
if command -v loginctl >/dev/null; then
  loginctl enable-linger "$USER" 2>/dev/null || true
fi

systemctl --user enable --now \
  news-intelligence-popos-worker-uie \
  news-intelligence-popos-worker-claim-topic \
  news-intelligence-popos-worker-assembly \
  news-intelligence-popos-worker-editorial \
  news-intelligence-popos-workers.target

sleep 3
echo "=== split workers ==="
for u in \
  news-intelligence-popos-worker-uie \
  news-intelligence-popos-worker-claim-topic \
  news-intelligence-popos-worker-assembly \
  news-intelligence-popos-worker-editorial
 do
  echo -n "$u: "
  systemctl --user is-active "$u" || true
done
systemctl --user status \
  news-intelligence-popos-worker-uie \
  news-intelligence-popos-worker-claim-topic \
  news-intelligence-popos-worker-assembly \
  news-intelligence-popos-worker-editorial \
  --no-pager -l 2>/dev/null | head -55
echo "Done. Link=$LINK — journals: journalctl --user -u news-intelligence-popos-worker-editorial -f"
