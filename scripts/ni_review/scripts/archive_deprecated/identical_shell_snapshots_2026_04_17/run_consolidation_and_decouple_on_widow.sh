#!/bin/bash
# Run entity consolidation then decouple on Widow (one SSH session, updates DB).
# From project root: ./scripts/run_consolidation_and_decouple_on_widow.sh [--dry-run] [--confidence 0.6]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_DIR="${REMOTE_DIR:-/opt/news-intelligence}"
WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
CONF="0.6"
DRY=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)   DRY="--dry-run"; shift ;;
    --confidence) CONF="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if grep -q "Host widow" ~/.ssh/config 2>/dev/null; then
  SSH_TARGET="widow"
else
  SSH_TARGET="${WIDOW_USER}@${WIDOW_HOST}"
fi

echo "Running consolidation then decouple on Widow (${SSH_TARGET}), confidence=${CONF}..."
ssh "$SSH_TARGET" "cd ${REMOTE_DIR} && set -a && [ -f .env ] && . ./.env && set +a && source .venv/bin/activate && PYTHONPATH=api python scripts/run_entity_consolidation.py --confidence $CONF $DRY && PYTHONPATH=api python scripts/run_decouple_role_merges.py"
echo "Done."
