#!/bin/bash
# Resume longitudinal stack after Widow maintenance (run on Widow or via PgBouncer tunnel).
#
# Idempotent: skips migrations already in public.applied_migrations when runners succeed.
# Requires: repo .env, .venv, postgres reachable at DB_HOST:DB_PORT.
#
# Usage:
#   ./scripts/resume_longitudinal_widow.sh
#   ./scripts/resume_longitudinal_widow.sh --skip-seeds
#   ./scripts/resume_longitudinal_widow.sh --skip-external

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
SKIP_SEEDS=false
SKIP_EXTERNAL=false
for arg in "$@"; do
  case "$arg" in
    --skip-seeds) SKIP_SEEDS=true ;;
    --skip-external) SKIP_EXTERNAL=true ;;
  esac
done

set -a && . ./.env && set +a
export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_PORT="${DB_PORT:-6432}"
PY="${REPO}/.venv/bin/python"
export PYTHONPATH="${REPO}/api"

echo "=== 1. Migration ledger (before) ==="
"$PY" api/scripts/migration_ledger_report.py --active-only || true

apply_migration() {
  local num="$1"
  local runner="api/scripts/run_migration_${num}.py"
  local sql_file
  sql_file="$(ls api/database/migrations/${num}_*.sql 2>/dev/null | head -1)"
  if [ ! -f "$runner" ]; then
    echo "WARN: no runner for migration ${num}"
    return 0
  fi
  echo "--- migration ${num} ---"
  if "$PY" "$runner"; then
    if [ -n "$sql_file" ]; then
      "$PY" api/scripts/register_applied_migration.py "$num" \
        --notes resume_longitudinal_widow.sh \
        --file "$sql_file" || true
    fi
  else
    echo "ERROR: migration ${num} failed — fix and re-run"
    exit 1
  fi
}

echo "=== 2. Apply migrations 221–225 (221/222 may already be applied) ==="
for n in 221 222 223 224 225 226; do
  apply_migration "$n"
done

echo "=== 3. pgvector extension (superuser if 223 failed on extension) ==="
if ! sudo -n -u postgres psql -d "${DB_NAME:-news_intel}" -c 'CREATE EXTENSION IF NOT EXISTS vector;' 2>/dev/null; then
  echo "WARN: CREATE EXTENSION vector needs postgres superuser — run manually if verify fails"
fi

echo "=== 4. Schema verify ==="
"$PY" api/scripts/verify_longitudinal_schema.py

echo "=== 5. Arc YAML → DB + reference seeds ==="
"$PY" -c "from services.arc_catalog_service import sync_arc_definitions_from_yaml; print(sync_arc_definitions_from_yaml())"
if [ "$SKIP_SEEDS" = false ]; then
  "$PY" api/scripts/load_longitudinal_seeds.py
fi

echo "=== 6. Politics RSS from spec (idempotent seed) ==="
"$PY" api/scripts/generate_domain_artifacts.py \
  --spec api/config/domains/specs/politics.domain.json --force
"$PY" api/scripts/seed_domain_rss_from_yaml.py --config api/config/domains/politics.yaml || true

echo "=== 7. Point-in-time sanity check ==="
"$PY" api/scripts/verify_arc_point_in_time.py --arc resource_geopolitics

if [ "$SKIP_EXTERNAL" = false ]; then
  echo "=== 8. External events + sanctions (optional creds) ==="
  "$PY" -c "
from services.ucdp_client import run_ucdp_backfill_batch
from services.sanctions_ingest_service import run_sanctions_refresh
try:
    print('ucdp', run_ucdp_backfill_batch(pages=1, pagesize=50))
except Exception as e:
    print('ucdp skip:', e)
try:
    print('sanctions', run_sanctions_refresh(limit=100))
except Exception as e:
    print('sanctions skip:', e)
" || true
fi

echo "=== 9. Refresh materialized views ==="
"$PY" -c "
from shared.database.connection import get_db_connection_context
with get_db_connection_context() as conn:
    with conn.cursor() as cur:
        try:
            cur.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY intelligence.mv_arc_spine_events')
            cur.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY intelligence.mv_tension_heatmap_monthly')
        except Exception:
            cur.execute('REFRESH MATERIALIZED VIEW intelligence.mv_arc_spine_events')
            cur.execute('REFRESH MATERIALIZED VIEW intelligence.mv_tension_heatmap_monthly')
    conn.commit()
print('matviews refreshed')
"

echo "=== 10. Migration ledger (after) ==="
"$PY" api/scripts/migration_ledger_report.py --active-only || true

echo ""
echo "Done. Next steps on the API host:"
echo "  1. git pull (this repo)"
echo "  2. Restart API + automation worker"
echo "  3. Rebuild web if UI changed: cd web && npm run build"
echo "  4. Optional: generate first brief at /{domain}/arcs/resource_geopolitics/brief"
echo "  5. Monitor: GET /api/system_monitoring/backlog_status → longitudinal_pipeline"
