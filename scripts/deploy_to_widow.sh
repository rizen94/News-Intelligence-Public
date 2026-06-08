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
echo "Post-deploy: migrations, schema audit, API restart"
echo "=========================================="

ssh "${WIDOW_USER}@${WIDOW_HOST}" "bash -s" <<REMOTE
set -euo pipefail
cd ${REMOTE_DIR}
export PYTHONPATH=api

if [ -f .db_password_widow ]; then
  export PGPASSWORD="\$(cat .db_password_widow | tr -d '\\n')"
elif [ -f .env.public_demo ]; then
  export PGPASSWORD="\$(grep -E '^DB_PASSWORD=' .env.public_demo | cut -d= -f2- | tr -d '\"' | tr -d \"'\")"
fi

echo "Schema audit (politics/finance)..."
python3 api/scripts/audit_politics_finance_schemas.py --strict || exit 1

echo "Checking tracked_events.global_narrative column..."
psql -h 127.0.0.1 -U newsapp -d news_intel -tAc \\
  "SELECT 1 FROM information_schema.columns WHERE table_schema='intelligence' AND table_name='tracked_events' AND column_name='global_narrative'" \\
  | grep -q 1 || { echo "FAIL: migration 196 (global_narrative) not applied"; exit 1; }

echo "Ensuring tracked_events(updated_at) index..."
psql -h 127.0.0.1 -U newsapp -d news_intel -v ON_ERROR_STOP=1 -c \\
  "CREATE INDEX IF NOT EXISTS idx_tracked_events_updated_at ON intelligence.tracked_events (updated_at DESC)"

for mig in 196 231 232; do
  if [ -f "api/database/migrations/\${mig}"*.sql ]; then
    file=\$(ls api/database/migrations/\${mig}*.sql | head -1)
    applied=\$(psql -h 127.0.0.1 -U newsapp -d news_intel -tAc "SELECT 1 FROM public.applied_migrations WHERE migration_id='\${mig}'" 2>/dev/null || true)
    if [ "\${applied}" != "1" ]; then
      echo "Applying migration \${mig}..."
      python3 api/scripts/run_migration.py "\${mig}" || psql -h 127.0.0.1 -U newsapp -d news_intel -v ON_ERROR_STOP=1 -f "\$file"
      python3 api/scripts/register_applied_migration.py "\${mig}" --notes "deploy_to_widow.sh" --file "\$file" 2>/dev/null || true
    fi
  fi
done

sudo systemctl restart news-intelligence-api-public || true
sleep 4

echo "Smoke tests..."
curl -sf http://127.0.0.1:8000/api/ping | head -c 80
curl -sf "http://127.0.0.1:8000/api/politics/report?lead_limit=1" | head -c 80
curl -sf "http://127.0.0.1:8000/api/tracked_events?limit=1" | head -c 80
echo ""
echo "Post-deploy checks OK"
REMOTE

echo ""
echo "=========================================="
echo "Phase 5 deployment complete."
echo "Dev fix ≠ prod fix until this script succeeds (see PROJECT_STATUS.md)."
echo "Next: bash scripts/deploy_public_demo_to_widow.sh for SPA"
echo "=========================================="
