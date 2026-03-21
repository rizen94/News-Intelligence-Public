#!/bin/bash
# Migrate Database Schema to NAS Database
# This script applies all necessary migrations to prepare the NAS database for data transfer

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$PROJECT_ROOT/api/database/migrations"
INIT_DIR="$PROJECT_ROOT/api/database/init"
LOG_FILE="$PROJECT_ROOT/logs/nas_schema_migration.log"

# NAS Database Configuration (REQUIRED)
DB_HOST="${DB_HOST:-192.168.93.100}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-news_intelligence}"
DB_USER="${DB_USER:-newsapp}"
DB_PASSWORD="${DB_PASSWORD:-newsapp_password}"

# Create logs directory
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$PROJECT_ROOT/backups"

# Logging functions
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${CYAN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

# Validate NAS database requirement
if [[ "${DB_HOST}" == "localhost" ]] || [[ "${DB_HOST}" == "127.0.0.1" ]]; then
    if [[ "${ALLOW_LOCAL_DB}" != "true" ]]; then
        error "Local database connection is BLOCKED. System requires NAS database (192.168.93.100)"
    else
        warn "Using local database (EMERGENCY MODE - NOT RECOMMENDED)"
    fi
fi

header "NAS Database Schema Migration"
log "Starting schema migration to NAS database"
log "Target: ${DB_HOST}:${DB_PORT}/${DB_NAME}"

# Test database connection
info "Testing NAS database connection..."
export PGPASSWORD="$DB_PASSWORD"
if ! psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "SELECT 1;" > /dev/null 2>&1; then
    error "Cannot connect to NAS database at ${DB_HOST}:${DB_PORT}"
    error "Please verify:"
    error "  1. NAS PostgreSQL is running"
    error "  2. Database credentials are correct"
    error "  3. Network connectivity to NAS"
    error "  4. Database '${DB_NAME}' exists"
fi
success "Database connection successful"

# Check if database is empty
info "Checking database state..."
TABLE_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -t -c "
    SELECT COUNT(*) 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
" | tr -d ' ')

if [ "$TABLE_COUNT" -gt 0 ]; then
    warn "Database already has $TABLE_COUNT tables"
    read -p "Continue with migration? This may modify existing schema. (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "Migration cancelled by user"
    fi
else
    info "Database is empty - ready for initial schema"
fi

# Create migration tracking table
info "Creating migration tracking table..."
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" <<EOF > /dev/null 2>&1
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64),
    applied_by VARCHAR(100) DEFAULT CURRENT_USER
);
EOF
success "Migration tracking table ready"

# Function to check if migration was already applied
is_migration_applied() {
    local migration_name="$1"
    local count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -t -c "
        SELECT COUNT(*) FROM schema_migrations WHERE migration_name = '$migration_name';
    " 2>/dev/null | tr -d ' ')
    [ "$count" = "1" ]
}

# Function to apply migration
apply_migration() {
    local migration_file="$1"
    local migration_name=$(basename "$migration_file" .sql)
    
    if [ ! -f "$migration_file" ]; then
        warn "Migration file not found: $migration_file (skipping)"
        return 0
    fi
    
    if is_migration_applied "$migration_name"; then
        info "Migration $migration_name already applied, skipping"
        return 0
    fi
    
    log "Applying migration: $migration_name"
    
    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -f "$migration_file" >> "$LOG_FILE" 2>&1; then
        # Record migration as applied
        psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "
            INSERT INTO schema_migrations (migration_name) VALUES ('$migration_name')
            ON CONFLICT (migration_name) DO NOTHING;
        " > /dev/null 2>&1
        success "Migration $migration_name applied successfully"
        return 0
    else
        error "Failed to apply migration $migration_name (check logs: $LOG_FILE)"
    fi
}

# Define migration order (critical for dependencies)
# Start with base schema, then apply migrations in order
MIGRATIONS=(
    # Base schema (if exists)
    "$INIT_DIR/01_schema.sql"
    
    # Core migrations
    "$MIGRATIONS_DIR/003_create_metrics_tables.sql"
    "$MIGRATIONS_DIR/007_iterative_rag_system.sql"
    "$MIGRATIONS_DIR/007_timeline_features.sql"
    "$MIGRATIONS_DIR/008_ml_queue_system.sql"
    "$MIGRATIONS_DIR/008_restored_routes_tables.sql"
    "$MIGRATIONS_DIR/008_rss_deduplication_tables.sql"
    "$MIGRATIONS_DIR/009_multi_perspective_analysis.sql"
    "$MIGRATIONS_DIR/009_scaling_optimizations.sql"
    "$MIGRATIONS_DIR/009_sources_table.sql"
    "$MIGRATIONS_DIR/010_expert_analysis_tables.sql"
    "$MIGRATIONS_DIR/010_rag_context.sql"
    "$MIGRATIONS_DIR/010_search_ml_tables.sql"
    "$MIGRATIONS_DIR/011_api_cache.sql"
    "$MIGRATIONS_DIR/011_automation_tables.sql"
    "$MIGRATIONS_DIR/011_pipeline_tracking_tables.sql"
    "$MIGRATIONS_DIR/012_add_created_by_column.sql"
    "$MIGRATIONS_DIR/013_enhanced_rss_feed_registry.sql"
    "$MIGRATIONS_DIR/020_advanced_deduplication.sql"
    "$MIGRATIONS_DIR/030_schema_alignment.sql"
    "$MIGRATIONS_DIR/040_enhanced_storyline_system.sql"
    "$MIGRATIONS_DIR/050_ml_processing_enhancement.sql"
    "$MIGRATIONS_DIR/050_v4_0_schema_compatibility.sql"
    "$MIGRATIONS_DIR/051_fix_ml_queue_function.sql"
    "$MIGRATIONS_DIR/060_enhanced_timeline_system.sql"
    
    # V4.0 Schema Overhaul
    "$MIGRATIONS_DIR/100_v4_0_complete_schema_overhaul.sql"
    "$MIGRATIONS_DIR/101_v4_0_schema_enhancement.sql"
    "$MIGRATIONS_DIR/102_v4_0_schema_enhancement_corrected.sql"
    "$MIGRATIONS_DIR/103_naming_consistency_fix.sql"
    
    # Recent features
    "$MIGRATIONS_DIR/120_storyline_automation_settings.sql"
    "$MIGRATIONS_DIR/121_topic_clustering_system.sql"
    "$MIGRATIONS_DIR/122_domain_silo_infrastructure.sql"
    "$MIGRATIONS_DIR/123_fix_domain_foreign_keys.sql"
    "$MIGRATIONS_DIR/124_fix_missing_timestamps.sql"
    "$MIGRATIONS_DIR/126_storyline_quality_metrics.sql"
    
    # Note: 125_data_migration_to_domains.sql is for data migration, not schema
)

# Apply migrations in order
header "Applying Database Migrations"
MIGRATION_COUNT=0
APPLIED_COUNT=0
SKIPPED_COUNT=0

for migration in "${MIGRATIONS[@]}"; do
    if [ -f "$migration" ]; then
        MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
        if apply_migration "$migration"; then
            APPLIED_COUNT=$((APPLIED_COUNT + 1))
        else
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        fi
    fi
done

# Verify schema
header "Verifying Schema"
info "Checking database schema..."

TABLE_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -t -c "
    SELECT COUNT(*) 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
" | tr -d ' ')

success "Database now has $TABLE_COUNT tables"

# List key tables
info "Key tables in database:"
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT" -c "
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name
    LIMIT 20;
" | tee -a "$LOG_FILE"

# Summary
header "Migration Summary"
success "Migration completed!"
log "Migrations processed: $MIGRATION_COUNT"
log "Migrations applied: $APPLIED_COUNT"
log "Migrations skipped: $SKIPPED_COUNT"
log "Total tables: $TABLE_COUNT"
log ""
log "Database is ready for data migration!"
log "Log file: $LOG_FILE"

echo ""
success "✅ NAS database schema migration complete!"
echo ""
echo "Next steps:"
echo "  1. Verify schema matches local database"
echo "  2. Run data migration script to transfer data"
echo "  3. Update system to use NAS database"
echo ""

