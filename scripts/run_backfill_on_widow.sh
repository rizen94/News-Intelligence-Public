#!/bin/bash
# Run entity description backfill on Widow (runs Python on Widow; Widow .env must have DB credentials).
# If your DB credentials are in local .env only, run locally instead:
#   PYTHONPATH=api uv run python scripts/backfill_entity_descriptions.py --api-fallback [--limit N]
# From project root: ./scripts/run_backfill_on_widow.sh [--deploy] [--limit N]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REMOTE_DIR="${REMOTE_DIR:-/opt/news-intelligence}"

WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
DEPLOY_FIRST=false
LIMIT=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --deploy) DEPLOY_FIRST=true; shift ;;
    --limit)  LIMIT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if grep -q "Host widow" ~/.ssh/config 2>/dev/null; then
  SSH_TARGET="widow"
else
  SSH_TARGET="${WIDOW_USER}@${WIDOW_HOST}"
fi

if [[ "$DEPLOY_FIRST" == true ]]; then
  echo "Deploying to Widow..."
  "$SCRIPT_DIR/deploy_to_widow.sh"
fi

EXTRA_ARGS="--api-fallback"
[[ -n "$LIMIT" ]] && EXTRA_ARGS="$EXTRA_ARGS --limit $LIMIT"

echo "Running backfill on Widow (${SSH_TARGET})..."
# On Widow, .env has DB_HOST=127.0.0.1; must source it so the backfill connects locally.
ssh "$SSH_TARGET" "cd ${REMOTE_DIR} && set -a && [ -f .env ] && . ./.env && set +a && source .venv/bin/activate && PYTHONPATH=api python scripts/backfill_entity_descriptions.py $EXTRA_ARGS"
