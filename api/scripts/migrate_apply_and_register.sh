#!/usr/bin/env bash
# ──────────────────────────────────────────────────────
# migrate_apply_and_register.sh <migration_id> [env]
# Apply a SQL migration and record it in the ledger — one command.
#
# Usage:
#   ./api/scripts/migrate_apply_and_register.sh 197               # widow (default)
#   ./api/scripts/migrate_apply_and_register.sh 197 widow          # explicit env
#   ./api/scripts/migrate_apply_and_register.sh 197 dev popos      # alternate host
# ──────────────────────────────────────────────────────

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
MIGRATIONS="$ROOT/api/database/migrations"
ID="${1:?Usage: $0 <migration_id> [env]}"
ENV="${2:-widow}"
SQL_FILE="$MIGRATIONS/$ID.sql"

# ── Validate file exists ───────────────────────────────
if ! [ -f "$SQL_FILE" ]; then
    echo "❌ Migration file not found: $SQL_FILE" >&2
    exit 1
fi

echo "📄 File:   $(basename "$SQL_FILE")"
echo "🔧 Env:    $ENV"
echo ""

# ── Pick host based on env ─────────────────────────────
HOST_PORT="5432"
DB_NAME="news_intel"
case "$ENV" in
    widow)
        DB_HOST="192.168.93.101"
        ;;
    dev|popos|local)
        DB_HOST="localhost"
        DB_NAME="news_intelligence"
        ;;
    *)
        echo "❌ Unknown env: $ENV (use widow, dev, popos)" >&2
        exit 1
        ;;
esac

# ── Source credentials from authoritative configs/.env ────────────
if [ -f "$ROOT/configs/.env" ]; then
    _PW="$(grep -m1 '^DB_PASSWORD=' "$ROOT/configs/.env" | cut -d= -f2-)"
    export DB_PASSWORD="$_PW" PGPASSWORD="$_PW"
else
    echo "⚠️  No $ROOT/configs/.env found — credentials not set for env=$ENV" >&2
fi

# ── Apply the migration SQL ────────────────────────────
echo "🚀 Applying migration..."
if ! psql -h "$DB_HOST" -p "$HOST_PORT" -U newsapp -d "$DB_NAME" -f "$SQL_FILE" 2>&1; then
    echo "" >&2
    echo "❌ Migration FAILED — rolling back ledger (nothing recorded)" >&2
    exit 1
fi
echo "   ✅ SQL applied."
echo ""

# ── Register in the ledger ─────────────────────────────
echo "📝 Recording in public.applied_migrations..."
PYTHONPATH=api python3 "$ROOT/api/scripts/register_applied_migration.py" \
    "$ID" \
    --env "$ENV" \
    --notes "auto via migrate_apply_and_register.sh" \
    --file "$SQL_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration $ID applied and registered (env=$ENV)."
else
    echo "" >&2
    echo "❌ Ledger registration failed — SQL was applied but not recorded." >&2
    exit 1
fi
