#!/usr/bin/env bash
# Bootstrap news_intel_dev on PopOS for v11 local development.
#
# Default: Docker pgvector on 127.0.0.1:5433 (no sudo / no host Postgres role needed).
# Optional: --native uses host Postgres on 5432 (requires postgresql-16-pgvector + role).
#
# Widow is used READ-ONLY for schema dump + optional sample data. Never writes to Widow.
#
# Usage:
#   ./scripts/dev/bootstrap_local_db.sh
#   ./scripts/dev/bootstrap_local_db.sh --with-sample
#   WIDOW_DSN='host=192.168.93.101 ...' ./scripts/dev/bootstrap_local_db.sh --with-sample

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

CONTAINER_NAME="${NI_DEV_PG_CONTAINER:-news-intel-dev-pg}"
LOCAL_PORT="${NI_DEV_PG_PORT:-5433}"
LOCAL_DB="${NI_DEV_DB_NAME:-news_intel_dev}"
LOCAL_USER="${NI_DEV_DB_USER:-newsapp}"
LOCAL_PASS="${NI_DEV_DB_PASSWORD:-ni-dev-local-only}"
IMAGE="${NI_DEV_PG_IMAGE:-pgvector/pgvector:pg16}"

WITH_SAMPLE=0
NATIVE=0
for arg in "$@"; do
  case "$arg" in
    --with-sample) WITH_SAMPLE=1 ;;
    --native) NATIVE=1 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
  esac
done

if [[ "${ENVIRONMENT:-}" == "development" || "${ENVIRONMENT:-}" == "dev" ]]; then
  if [[ "${DB_HOST:-}" == "192.168.93.101" ]]; then
    echo "ERROR: ENVIRONMENT=development with DB_HOST=Widow is refused." >&2
    exit 1
  fi
fi

WORK=/tmp/ni-dev-bootstrap
mkdir -p "$WORK"

LOCAL_DSN="host=127.0.0.1 port=${LOCAL_PORT} dbname=${LOCAL_DB} user=${LOCAL_USER} password=${LOCAL_PASS}"

start_docker_pg() {
  if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Container $CONTAINER_NAME already running."
    return
  fi
  if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "Starting existing container $CONTAINER_NAME..."
    docker start "$CONTAINER_NAME" >/dev/null
  else
    echo "Creating $CONTAINER_NAME ($IMAGE) on 127.0.0.1:${LOCAL_PORT}..."
    docker run -d --name "$CONTAINER_NAME" \
      -e POSTGRES_USER="$LOCAL_USER" \
      -e POSTGRES_PASSWORD="$LOCAL_PASS" \
      -e POSTGRES_DB="$LOCAL_DB" \
      -p "127.0.0.1:${LOCAL_PORT}:5432" \
      "$IMAGE" >/dev/null
  fi
  for i in $(seq 1 30); do
    if PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -c 'SELECT 1' >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -v ON_ERROR_STOP=1 -c \
    "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
}

dump_widow_schema() {
  local widow_dsn="${WIDOW_DSN:-}"
  if [[ -z "$widow_dsn" ]]; then
    # Prefer credentials from repo .env for READ-ONLY dump only.
    if [[ -f "$ROOT/.env" ]]; then
      # shellcheck disable=SC1091
      set -a
      # Only load DB_* for the dump source; do not export into the shell permanently.
      WIDOW_HOST="$(grep -E '^DB_HOST=' "$ROOT/.env" | head -1 | cut -d= -f2-)"
      WIDOW_PORT="$(grep -E '^DB_PORT=' "$ROOT/.env" | head -1 | cut -d= -f2-)"
      WIDOW_NAME="$(grep -E '^DB_NAME=' "$ROOT/.env" | head -1 | cut -d= -f2-)"
      WIDOW_USER="$(grep -E '^DB_USER=' "$ROOT/.env" | head -1 | cut -d= -f2-)"
      WIDOW_PASS="$(grep -E '^DB_PASSWORD=' "$ROOT/.env" | head -1 | cut -d= -f2-)"
      set +a
      widow_dsn="host=${WIDOW_HOST} port=${WIDOW_PORT:-5432} dbname=${WIDOW_NAME} user=${WIDOW_USER} password=${WIDOW_PASS} sslmode=prefer"
    else
      echo "ERROR: set WIDOW_DSN or provide $ROOT/.env for read-only schema dump." >&2
      exit 1
    fi
  fi
  if [[ "$widow_dsn" != *"192.168.93.101"* && "$widow_dsn" != *"widow"* ]]; then
    echo "NOTE: WIDOW_DSN does not look like Widow; continuing anyway (read-only dump)."
  fi
  echo "Dumping schema from Widow (read-only)..."
  pg_dump "$widow_dsn" --schema-only --no-owner --no-acl -f "$WORK/widow_schema.sql"
  echo "Schema dump: $(wc -l < "$WORK/widow_schema.sql") lines"
  echo "$widow_dsn" > "$WORK/widow_dsn.txt"
}

restore_local() {
  echo "Restoring schema into local ${LOCAL_DB}..."
  # Drop and recreate public/domain schemas is heavy; prefer empty DB from docker init.
  # For re-runs: recreate container.
  PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -v ON_ERROR_STOP=0 -f "$WORK/widow_schema.sql" \
    > "$WORK/restore.log" 2>&1 || true
  local n
  n="$(PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -Atc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')")"
  echo "Local tables: $n"
  if [[ "${n:-0}" -lt 50 ]]; then
    echo "ERROR: schema restore looks incomplete; see $WORK/restore.log" >&2
    exit 1
  fi
}

sample_from_widow() {
  local widow_dsn
  widow_dsn="$(cat "$WORK/widow_dsn.txt")"
  echo "Sampling medicine fixtures from Widow (read-only) into local..."
  # Domains registry
  PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -v ON_ERROR_STOP=0 <<'SQL' || true
TRUNCATE public.domains CASCADE;
SQL
  psql "$widow_dsn" -Atc \
    "COPY (SELECT id, domain_key, name, schema_name, display_order, description, is_active, created_at, updated_at
           FROM public.domains ORDER BY id) TO STDOUT" \
    | PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -c \
      "COPY public.domains (id, domain_key, name, schema_name, display_order, description, is_active, created_at, updated_at) FROM STDIN" \
    || echo "WARNING: domains sample skipped (column mismatch); continuing."

  # Sample recent medicine articles (up to 2000)
  psql "$widow_dsn" -Atc \
    "COPY (
       SELECT * FROM medicine.articles
       ORDER BY COALESCE(published_at, created_at) DESC NULLS LAST
       LIMIT 2000
     ) TO STDOUT" \
    | PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -c "COPY medicine.articles FROM STDIN" \
    || echo "WARNING: medicine.articles sample skipped."

  echo "Sample load finished (best-effort)."
}

apply_v11_migrations() {
  echo "Applying v11 additive migrations 282–290 (idempotent)..."
  local mig
  for mig in \
    282_domain_processing_mode.sql \
    283_neurodiversity_domain_silo.sql \
    284_claim_evidence_appraisal.sql \
    285_editorial_packages_and_news_stories.sql \
    286_editorial_package_legacy_seed_index.sql \
    287_editorial_packages_primary_modal_system.sql \
    288_editorial_reduction_decision_actions.sql \
    289_editorial_narrative_decision_actions.sql \
    290_editorial_research_decision_actions.sql
  do
    local path="$ROOT/api/database/migrations/$mig"
    if [[ ! -f "$path" ]]; then
      echo "WARNING: missing $path" >&2
      continue
    fi
    echo "  → $mig"
    PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -v ON_ERROR_STOP=1 -f "$path" \
      || echo "WARNING: $mig failed (see above); continuing."
    # Best-effort ledger (table may not exist on fresh dumps)
    PGPASSWORD="$LOCAL_PASS" psql "$LOCAL_DSN" -v ON_ERROR_STOP=0 -c \
      "INSERT INTO public.applied_migrations (filename, applied_at)
       VALUES ('$mig', NOW())
       ON CONFLICT DO NOTHING;" >/dev/null 2>&1 || true
  done
}

if [[ "$NATIVE" -eq 1 ]]; then
  LOCAL_PORT=5432
  LOCAL_DSN="host=127.0.0.1 port=5432 dbname=${LOCAL_DB} user=${LOCAL_USER} password=${LOCAL_PASS}"
  echo "Native mode: ensure role/db exist and pgvector is installed, then re-run restore manually."
  dump_widow_schema
  restore_local
else
  start_docker_pg
  dump_widow_schema
  # Recreate DB for clean restore on re-run
  if [[ "${NI_DEV_FORCE_RECREATE:-0}" == "1" ]]; then
    docker rm -f "$CONTAINER_NAME" >/dev/null
    start_docker_pg
  fi
  restore_local
fi

if [[ "$WITH_SAMPLE" -eq 1 ]]; then
  sample_from_widow
fi

apply_v11_migrations

echo
echo "Done. Point local work at:"
echo "  export \$(grep -v '^#' .env.dev | xargs)"
echo "  # or: set -a; source .env.dev; set +a"
echo "Container: $CONTAINER_NAME  DSN port: $LOCAL_PORT  DB: $LOCAL_DB"
echo "Do NOT deploy these changes to Widow until the v11 cutover runbook."
echo "Legacy package seed (optional):"
echo "  PYTHONPATH=api python3 api/scripts/backfill_editorial_packages_from_legacy.py --dry-run"
