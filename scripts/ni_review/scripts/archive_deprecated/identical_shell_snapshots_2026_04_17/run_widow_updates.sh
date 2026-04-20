#!/bin/bash
# Run apt update and upgrade on Widow (secondary machine) via SSH.
# Uses 'widow' from SSH config if available, else pete@192.168.93.101.
# Execute from PRIMARY machine.

set -e

WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
SSH_PORT="${SSH_PORT:-22}"

# Prefer SSH config Host "widow" if it exists
if grep -q "Host widow" ~/.ssh/config 2>/dev/null; then
    SSH_TARGET="widow"
else
    SSH_TARGET="${WIDOW_USER}@${WIDOW_HOST}"
fi

echo "Running apt update and upgrade on Widow (${SSH_TARGET})..."
echo ""

ssh -p "${SSH_PORT}" "${SSH_TARGET}" "sudo apt update && sudo apt upgrade -y"

echo ""
echo "✅ Updates complete on Widow"
