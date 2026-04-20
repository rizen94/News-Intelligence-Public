#!/bin/bash
# News Intelligence — Widow (secondary machine) SSH setup
# Provides: SSH config, persistent connection, and remote update script.
# Run from PRIMARY machine. Widow = 192.168.93.101

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
SSH_PORT="${SSH_PORT:-22}"

# Ensure ~/.ssh exists
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

# SSH config snippet for Widow
CONFIG_SNIPPET="# News Intelligence — Widow (secondary machine)
Host widow
  HostName ${WIDOW_HOST}
  User ${WIDOW_USER}
  Port ${SSH_PORT}
  ServerAliveInterval 60
  ServerAliveCountMax 3
  ControlMaster auto
  ControlPath ~/.ssh/cm-widow-%r@%h:%p
  ControlPersist 10m
"

CONFIG_FILE="$HOME/.ssh/config"
MARKER_START="# BEGIN News Intelligence Widow"
MARKER_END="# END News Intelligence Widow"

[[ -f "$CONFIG_FILE" ]] || touch "$CONFIG_FILE"
if ! grep -q "$MARKER_START" "$CONFIG_FILE" 2>/dev/null; then
    echo "Adding Widow SSH config to $CONFIG_FILE"
    echo "" >> "$CONFIG_FILE"
    echo "$MARKER_START" >> "$CONFIG_FILE"
    echo "$CONFIG_SNIPPET" >> "$CONFIG_FILE"
    echo "$MARKER_END" >> "$CONFIG_FILE"
    echo "✅ SSH config added. Use: ssh widow"
else
    echo "Widow SSH config already present. Use: ssh widow"
fi

# Ensure ControlPath directory exists for multiplexing
mkdir -p ~/.ssh
echo ""
echo "Usage:"
echo "  ssh widow                    # Connect to Widow"
echo "  ./scripts/run_widow_updates.sh   # Run apt update/upgrade on Widow via SSH"
echo ""
