#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

TIER="standard"
RAM_GB=$(free -g 2>/dev/null | awk '/Mem:/ {print $2}' || echo 16)
if [[ "$RAM_GB" -lt 16 ]]; then TIER="minimal"; fi
if [[ "$RAM_GB" -ge 48 ]]; then TIER="performance"; fi

if [[ -f "$KIT_ROOT/.env" ]]; then
  grep -q KIT_HARDWARE_TIER "$KIT_ROOT/.env" && sed -i "s/^KIT_HARDWARE_TIER=.*/KIT_HARDWARE_TIER=$TIER/" "$KIT_ROOT/.env" || echo "KIT_HARDWARE_TIER=$TIER" >> "$KIT_ROOT/.env"
else
  echo "KIT_HARDWARE_TIER=$TIER" >> "$KIT_ROOT/.env.template"
fi
echo "Hardware tier: $TIER (${RAM_GB}GB RAM)"
