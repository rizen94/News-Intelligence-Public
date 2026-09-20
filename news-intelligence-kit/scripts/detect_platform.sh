#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"

detect_platform() {
  OS="linux"
  ARCH="$(uname -m)"
  GPU_VENDOR="none"
  GPU_USABLE="false"
  COMPOSE_EXTRA=""
  WARNINGS=()

  if grep -qi microsoft /proc/version 2>/dev/null; then
    OS="wsl"
    if pwd | grep -q '^/mnt/'; then
      WARNINGS+=("Kit is on /mnt/c — move to ~/news-intelligence-kit for Postgres performance")
    fi
  fi
  if [[ "$(uname -s)" == Darwin ]]; then
    OS="darwin"
    COMPOSE_EXTRA="compose.mac-host-ollama.yaml"
  fi
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_VENDOR="nvidia"
    GPU_USABLE="true"
    COMPOSE_EXTRA="compose.gpu-nvidia.yaml"
  fi

  cat > "$KIT_ROOT/platform.json" <<EOF
{"os":"$OS","arch":"$ARCH","gpu_vendor":"$GPU_VENDOR","gpu_usable_in_compose":$GPU_USABLE,"compose_extra":"$COMPOSE_EXTRA","warnings":$(printf '%s\n' "${WARNINGS[@]}" | jq -R . | jq -s . 2>/dev/null || echo '[]')}
EOF
}

detect_platform
echo "Platform: $(cat platform.json)"
