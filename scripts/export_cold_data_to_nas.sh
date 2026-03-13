#!/usr/bin/env bash
# Export "cold" (old) data from Widow PostgreSQL to NAS for long-term storage.
# Does NOT delete from the database by default — use for safety. Prune separately if desired.
# Run on Widow; NAS must be mounted at NAS_MOUNT.
#
# Usage:
#   export COLD_DAYS=90 NAS_MOUNT=/mnt/nas
#   ./scripts/export_cold_data_to_nas.sh
#
# Optional: set PRUNE_AFTER_EXPORT=1 to run a prune step (removes exported articles older than COLD_DAYS).
# Prune is destructive; ensure exports are verified first.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COLD_DAYS="${COLD_DAYS:-90}"
NAS_MOUNT="${NAS_MOUNT:-/mnt/nas}"
COLD_EXPORT_BASE="${COLD_EXPORT_BASE:-$NAS_MOUNT/news-intelligence/cold-export}"
PRUNE_AFTER_EXPORT="${PRUNE_AFTER_EXPORT:-0}"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-news_intel}"
DB_USER="${DB_USER:-newsapp}"
export PGPASSWORD="${DB_PASSWORD:-}"

if [ -f "$PROJECT_ROOT/.db_password_widow" ]; then
  PGPASSWORD=$(cat "$PROJECT_ROOT/.db_password_widow")
  export PGPASSWORD
fi

if [ ! -d "$NAS_MOUNT" ] || ! mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
  echo "[$(date)] NAS not mounted at $NAS_MOUNT — aborting cold export"
  exit 1
fi

mkdir -p "$COLD_EXPORT_BASE"
YMD=$(date +%Y%m%d)
OUT_DIR="$COLD_EXPORT_BASE/$YMD"
mkdir -p "$OUT_DIR"

echo "[$(date)] Exporting data older than $COLD_DAYS days to $OUT_DIR"

# Export per-domain articles older than COLD_DAYS (schema: politics, finance, science_tech)
for schema in politics finance science_tech; do
  TABLE="${schema}.articles"
  FILE="$OUT_DIR/${schema}_articles_older_than_${COLD_DAYS}d.csv"
  # Check table exists
  if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='$schema' AND table_name='articles'" | grep -q 1; then
    echo "  Skipping $TABLE (no such table)"
    continue
  fi
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\COPY (SELECT * FROM $TABLE WHERE published_at < NOW() - INTERVAL '$COLD_DAYS days') TO STDOUT WITH CSV HEADER" > "$FILE" 2>/dev/null || true
  if [ -s "$FILE" ]; then
    echo "  Exported $TABLE -> $FILE ($(wc -l < "$FILE") lines)"
  else
    rm -f "$FILE"
  fi
done

# Optional: export intelligence.contexts older than COLD_DAYS
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='intelligence' AND table_name='contexts'" | grep -q 1; then
  FILE="$OUT_DIR/intelligence_contexts_older_than_${COLD_DAYS}d.csv"
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\COPY (SELECT id, source_type, domain_key, title, LEFT(content, 500) AS content_preview, created_at FROM intelligence.contexts WHERE created_at < NOW() - INTERVAL '$COLD_DAYS days') TO STDOUT WITH CSV HEADER" > "$FILE" 2>/dev/null || true
  if [ -s "$FILE" ]; then
    echo "  Exported intelligence.contexts (preview) -> $FILE"
  else
    rm -f "$FILE"
  fi
fi

echo "[$(date)] Cold export done"

# Prune: optional and destructive
if [ "$PRUNE_AFTER_EXPORT" = "1" ]; then
  echo "[$(date)] WARNING: PRUNE_AFTER_EXPORT=1 — deleting exported rows from DB"
  for schema in politics finance science_tech; do
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='$schema' AND table_name='articles'" | grep -q 1; then
      psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "DELETE FROM $schema.articles WHERE published_at < NOW() - INTERVAL '$COLD_DAYS days'"
      echo "  Pruned $schema.articles"
    fi
  done
  echo "[$(date)] Run VACUUM on Widow if you need to reclaim disk: psql -c 'VACUUM ANALYZE' per schema"
fi
