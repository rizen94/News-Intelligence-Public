#!/bin/bash
# Run entity decouple (split role-word merges) on Widow.
# From project root: ./scripts/run_decouple_on_widow.sh [--domain DOMAIN]
# Uses SSH config Host "widow" if present, else WIDOW_USER@WIDOW_HOST.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_DIR="${REMOTE_DIR:-/opt/news-intelligence}"
WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
DOMAIN=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --domain) DOMAIN="--domain $2"; shift 2 ;;
    *) shift ;;
  esac
done

if grep -q "Host widow" ~/.ssh/config 2>/dev/null; then
  SSH_TARGET="widow"
else
  SSH_TARGET="${WIDOW_USER}@${WIDOW_HOST}"
fi

echo "Running decouple (split role-word merges) on Widow (${SSH_TARGET})..."
ssh "$SSH_TARGET" "cd ${REMOTE_DIR} && set -a && [ -f .env ] && . ./.env && set +a && source .venv/bin/activate && PYTHONPATH=api python scripts/run_decouple_role_merges.py $DOMAIN"
