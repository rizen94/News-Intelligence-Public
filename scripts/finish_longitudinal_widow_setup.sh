#!/bin/bash
# Finish longitudinal setup on Widow — migrations, seeds, RSS, matviews, pgvector.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
set -a && . ./.env && set +a
export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_PORT="${DB_PORT:-6432}"
PY="${REPO}/.venv/bin/python"
export PYTHONPATH="${REPO}/api"

echo "=== pgvector extension (may need sudo postgres) ==="
if ! sudo -n -u postgres psql -d "${DB_NAME:-news_intel}" -c 'CREATE EXTENSION IF NOT EXISTS vector;' 2>/dev/null; then
  echo "WARN: could not CREATE EXTENSION vector — run manually as postgres superuser"
else
  "$PY" api/scripts/run_migration_223.py && \
    "$PY" api/scripts/register_applied_migration.py 223 \
      --notes finish_longitudinal_widow_setup.sh \
      --file api/database/migrations/223_pgvector_embedding_chunks.sql || true
fi

echo "=== migration 224 ==="
"$PY" api/scripts/run_migration_224.py
"$PY" api/scripts/register_applied_migration.py 224 \
  --notes finish_longitudinal_widow_setup.sh \
  --file api/database/migrations/224_arc_operator_feedback.sql

echo "=== migration 225 (quarantine + analogues) ==="
"$PY" api/scripts/run_migration_225.py
"$PY" api/scripts/register_applied_migration.py 225 \
  --notes finish_longitudinal_widow_setup.sh \
  --file api/database/migrations/225_longitudinal_schema_alignment.sql

echo "=== schema verify ==="
"$PY" api/scripts/verify_longitudinal_schema.py

echo "=== seeds ==="
"$PY" api/scripts/load_longitudinal_seeds.py

echo "=== politics RSS ==="
"$PY" api/scripts/generate_domain_artifacts.py \
  --spec api/config/domains/specs/politics.domain.json --force
"$PY" api/scripts/seed_domain_rss_from_yaml.py --config api/config/domains/politics.yaml

echo "=== external events + matviews ==="
"$PY" -c "
from services.ucdp_client import run_ucdp_backfill_batch
from services.sanctions_ingest_service import run_sanctions_refresh
print('ucdp', run_ucdp_backfill_batch(pages=1, pagesize=50))
print('sanctions', run_sanctions_refresh(limit=100))
"
"$PY" -c "
from shared.database.connection import get_db_connection_context
with get_db_connection_context() as conn:
    with conn.cursor() as cur:
        cur.execute('REFRESH MATERIALIZED VIEW intelligence.mv_arc_spine_events')
        cur.execute('REFRESH MATERIALIZED VIEW intelligence.mv_tension_heatmap_monthly')
    conn.commit()
print('matviews refreshed')
"

echo "=== weekly backup cron ==="
bash "${REPO}/scripts/install_weekly_backup_cron.sh" || true

echo "Done. Restart main API + rebuild web on the host that serves the UI."
