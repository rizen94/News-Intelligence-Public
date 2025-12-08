#!/bin/bash
# Run v4.0 Domain Silo Infrastructure Migration
# Creates domain schemas and tables for multi-domain architecture

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATION_FILE="$PROJECT_ROOT/api/database/migrations/122_domain_silo_infrastructure.sql"

cd "$PROJECT_ROOT"

echo "🚀 Starting v4.0 Database Migration: Domain Silo Infrastructure"
echo "=============================================================="
echo ""
echo "Migration File: $MIGRATION_FILE"
echo ""

# Check if migration file exists
if [ ! -f "$MIGRATION_FILE" ]; then
    echo "❌ Error: Migration file not found: $MIGRATION_FILE"
    exit 1
fi

# Database connection parameters
DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-news_intelligence}"
DB_USER="${DB_USER:-newsapp}"
DB_PASSWORD="${DB_PASSWORD:-newsapp_password}"
DB_PORT="${DB_PORT:-5432}"

echo "📊 Database Configuration:"
echo "  Host: $DB_HOST"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Port: $DB_PORT"
echo ""

# Test database connection
echo "🔍 Testing database connection..."
export PGPASSWORD="$DB_PASSWORD"
if ! psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to database"
    echo "   Please check your database configuration"
    exit 1
fi
echo "✅ Database connection successful"
echo ""

# Create backup before migration
BACKUP_FILE="$PROJECT_ROOT/backups/pre_v4_migration_$(date +%Y%m%d_%H%M%S).sql"
echo "💾 Creating database backup..."
mkdir -p "$PROJECT_ROOT/backups"
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" > "$BACKUP_FILE" 2>/dev/null || {
    echo "⚠️  Warning: Could not create backup (continuing anyway)"
    BACKUP_FILE=""
}
if [ -n "$BACKUP_FILE" ]; then
    echo "✅ Backup created: $BACKUP_FILE"
fi
echo ""

# Run migration
echo "🔄 Running migration..."
echo ""

psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -f "$MIGRATION_FILE" 2>&1 | tee /tmp/v4_migration_output.log

MIGRATION_EXIT_CODE=${PIPESTATUS[0]}

if [ $MIGRATION_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Migration completed successfully!"
    echo ""
    echo "📊 Verification:"
    echo "  Checking domains table..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "
        SELECT domain_key, name, schema_name, is_active 
        FROM domains 
        ORDER BY display_order;
    " || echo "⚠️  Could not verify domains table"
    
    echo ""
    echo "  Checking schemas..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name IN ('politics', 'finance', 'science_tech')
        ORDER BY schema_name;
    " || echo "⚠️  Could not verify schemas"
    
    echo ""
    echo "  Checking finance-specific tables..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'finance' 
        AND table_name IN ('market_patterns', 'corporate_announcements', 'financial_indicators')
        ORDER BY table_name;
    " || echo "⚠️  Could not verify finance tables"
    
    echo ""
    echo "✅ v4.0 Database Infrastructure Ready!"
    echo ""
    echo "Next Steps:"
    echo "  1. Review migration results"
    echo "  2. Run data migration (Migration 123) to move existing data"
    echo "  3. Update API services for domain awareness"
    echo ""
    
    if [ -n "$BACKUP_FILE" ]; then
        echo "💾 Backup available at: $BACKUP_FILE"
        echo "   Use this to rollback if needed"
    fi
else
    echo ""
    echo "❌ Migration failed with exit code: $MIGRATION_EXIT_CODE"
    echo ""
    echo "📋 Migration output saved to: /tmp/v4_migration_output.log"
    echo ""
    
    if [ -n "$BACKUP_FILE" ]; then
        echo "💾 Backup available at: $BACKUP_FILE"
        echo "   You can restore from backup if needed"
    fi
    
    exit $MIGRATION_EXIT_CODE
fi

