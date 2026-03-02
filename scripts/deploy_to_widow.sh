#!/bin/bash
# News Intelligence — Phase 5: Deploy application to Widow (secondary)
# Run from PRIMARY machine. Rsyncs code to Widow and runs setup.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
REMOTE_DIR="${REMOTE_DIR:-/opt/news-intelligence}"

echo "=========================================="
echo "Phase 5: Deploy to Widow (${WIDOW_HOST})"
echo "=========================================="
echo "Source: $PROJECT_DIR"
echo "Target: ${WIDOW_USER}@${WIDOW_HOST}:${REMOTE_DIR}"
echo ""

# Ensure remote directory exists
ssh "${WIDOW_USER}@${WIDOW_HOST}" "sudo mkdir -p ${REMOTE_DIR} && sudo chown ${WIDOW_USER}:${WIDOW_USER} ${REMOTE_DIR}"

# Rsync exclude patterns (match start_system.sh exclusions where relevant)
rsync -avz --progress \
  --exclude='.venv' \
  --exclude='.venv.backup' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.env' \
  --exclude='*.db' \
  --exclude='logs/' \
  --exclude='chroma_data' \
  --exclude='News-Intelligence-Archive' \
  "${PROJECT_DIR}/" "${WIDOW_USER}@${WIDOW_HOST}:${REMOTE_DIR}/"

# Copy DB password if present (for .env and .pgpass on Widow)
if [ -f "$PROJECT_DIR/.db_password_widow" ]; then
  scp "$PROJECT_DIR/.db_password_widow" "${WIDOW_USER}@${WIDOW_HOST}:${REMOTE_DIR}/"
  echo "✅ .db_password_widow copied"
else
  echo "⚠️  .db_password_widow not found — run setup manually and set DB_PASSWORD in .env"
fi

echo ""
echo "✅ Code deployed. Running setup on Widow..."
ssh "${WIDOW_USER}@${WIDOW_HOST}" "cd ${REMOTE_DIR} && ./scripts/setup_widow_app.sh"

echo ""
echo "=========================================="
echo "Phase 5 deployment complete."
echo "Next: sudo systemctl enable newsplatform-secondary"
echo "      sudo systemctl start newsplatform-secondary  (after Phase 6 validation)"
echo "=========================================="
