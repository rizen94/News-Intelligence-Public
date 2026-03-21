#!/bin/bash
# Check entity pipeline status on Widow: DB counts and optional process check.
# From project root: ./scripts/check_widow_entity_status.sh

set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-/opt/news-intelligence}"
WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"

if grep -q "Host widow" ~/.ssh/config 2>/dev/null; then
  SSH_TARGET="widow"
else
  SSH_TARGET="${WIDOW_USER}@${WIDOW_HOST}"
fi

echo "Checking Widow (${SSH_TARGET}) entity status..."
echo ""

# 1) Entity DB status (run Python on Widow with local .env)
ssh "$SSH_TARGET" "cd ${REMOTE_DIR} && set -a && [ -f .env ] && . ./.env && set +a && source .venv/bin/activate 2>/dev/null || true && PYTHONPATH=api python scripts/check_widow_entity_status.py"
STATUS=$?

# 2) Any entity-related processes currently running?
echo ""
echo "--- Processes (entity consolidation / decouple / backfill) ---"
ssh "$SSH_TARGET" "pgrep -af 'run_entity_consolidation|run_decouple_role_merges|backfill_entity_descriptions' || echo '  (none running)'"
echo ""

exit $STATUS
