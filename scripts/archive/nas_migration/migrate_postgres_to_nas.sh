#!/bin/bash
# Complete PostgreSQL Migration to NAS
# This script handles the full migration process

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="5432"
LOCAL_DB_NAME="news_intelligence"
LOCAL_DB_USER="newsapp"
LOCAL_DB_PASSWORD="newsapp_password"

NAS_DB_HOST="192.168.93.100"
NAS_DB_PORT="5432"
NAS_DB_NAME="news_intelligence"
NAS_DB_USER="newsapp"
NAS_DB_PASSWORD="newsapp_password"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/backups/postgres_migration_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$PROJECT_ROOT/logs/postgres_migration.log"

mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$BACKUP_DIR"

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
}

# Step 1: Backup local database
backup_local_database() {
    header "Step 1: Backup Local Database"
    log "Creating full backup of local database..."
    
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    
    if command -v pg_dump &> /dev/null; then
        log "Using pg_dump to create backup..."
        pg_dump -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" \
            -F c -f "$BACKUP_DIR/local_database_backup.dump" 2>&1 | tee -a "$LOG_FILE"
        
        if [ -f "$BACKUP_DIR/local_database_backup.dump" ]; then
            local size=$(du -h "$BACKUP_DIR/local_database_backup.dump" | cut -f1)
            success "Backup created: $BACKUP_DIR/local_database_backup.dump ($size)"
            return 0
        else
            error "Backup file not created"
        fi
    else
        warning "pg_dump not found. Creating SQL dump instead..."
        pg_dump -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" \
            -f "$BACKUP_DIR/local_database_backup.sql" 2>&1 | tee -a "$LOG_FILE"
        
        if [ -f "$BACKUP_DIR/local_database_backup.sql" ]; then
            local size=$(du -h "$BACKUP_DIR/local_database_backup.sql" | cut -f1)
            success "SQL backup created: $BACKUP_DIR/local_database_backup.sql ($size)"
            return 0
        else
            error "SQL backup failed"
        fi
    fi
}

# Step 2: Verify NAS database is ready
verify_nas_database() {
    header "Step 2: Verify NAS Database"
    log "Checking NAS database connection..."
    
    export PGPASSWORD="$NAS_DB_PASSWORD"
    
    if psql -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        success "NAS database connection successful"
        
        # Check if schema exists
        local table_count=$(psql -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" -t -c \
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
        
        log "NAS database has $table_count tables"
        
        if [ "$table_count" -eq 0 ]; then
            warning "NAS database is empty - schema migrations needed"
            return 1
        else
            success "NAS database schema exists"
            return 0
        fi
    else
        error "Cannot connect to NAS database"
        error "Please ensure PostgreSQL is running on NAS"
        return 1
    fi
}

# Step 3: Migrate data
migrate_data() {
    header "Step 3: Migrate Data to NAS"
    log "Starting data migration from local to NAS..."
    
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    local backup_file="$BACKUP_DIR/local_database_backup.dump"
    
    if [ ! -f "$backup_file" ]; then
        backup_file="$BACKUP_DIR/local_database_backup.sql"
    fi
    
    if [ ! -f "$backup_file" ]; then
        error "Backup file not found: $backup_file"
    fi
    
    log "Restoring backup to NAS database..."
    export PGPASSWORD="$NAS_DB_PASSWORD"
    
    if [[ "$backup_file" == *.dump ]]; then
        # Custom format backup
        log "Using pg_restore for custom format backup..."
        pg_restore -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" \
            --clean --if-exists --no-owner --no-privileges --verbose \
            "$backup_file" 2>&1 | tee -a "$LOG_FILE" | grep -E "ERROR|WARNING|processing" || true
    else
        # SQL format backup
        log "Using psql for SQL backup..."
        psql -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" \
            -f "$backup_file" 2>&1 | tee -a "$LOG_FILE" | grep -E "ERROR|WARNING" || true
    fi
    
    success "Data migration completed"
}

# Step 4: Verify migration
verify_migration() {
    header "Step 4: Verify Migration"
    log "Verifying data migration..."
    
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    local local_count=$(psql -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -t -c \
        "SELECT COUNT(*) FROM articles;" 2>/dev/null | tr -d ' ')
    
    export PGPASSWORD="$NAS_DB_PASSWORD"
    local nas_count=$(psql -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" -t -c \
        "SELECT COUNT(*) FROM articles;" 2>/dev/null | tr -d ' ')
    
    log "Local database articles: $local_count"
    log "NAS database articles: $nas_count"
    
    if [ "$nas_count" -eq "$local_count" ]; then
        success "Article count matches! ($nas_count articles)"
    else
        warning "Article count mismatch: Local=$local_count, NAS=$nas_count"
    fi
    
    # Check other key tables
    for table in storylines rss_feeds topics; do
        export PGPASSWORD="$LOCAL_DB_PASSWORD"
        local local_tbl=$(psql -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -t -c \
            "SELECT COUNT(*) FROM $table;" 2>/dev/null | tr -d ' ' || echo "0")
        
        export PGPASSWORD="$NAS_DB_PASSWORD"
        local nas_tbl=$(psql -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" -t -c \
            "SELECT COUNT(*) FROM $table;" 2>/dev/null | tr -d ' ' || echo "0")
        
        log "$table: Local=$local_tbl, NAS=$nas_tbl"
    done
    
    success "Migration verification complete"
}

# Main execution
main() {
    header "PostgreSQL Migration to NAS"
    log "Starting PostgreSQL migration process"
    echo ""
    
    # Pre-flight checks
    log "Running pre-flight checks..."
    
    # Check NAS mount
    if ! mountpoint -q /mnt/nas 2>/dev/null; then
        error "NAS not mounted at /mnt/nas"
    fi
    success "NAS mount verified"
    
    # Check local database
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    if ! psql -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        error "Cannot connect to local database"
    fi
    success "Local database connection verified"
    
    # Check NAS database
    if ! verify_nas_database; then
        warning "NAS database may need schema migrations first"
        read -p "Continue with data migration anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "Migration cancelled. Please set up NAS database schema first."
        fi
    fi
    
    # Backup local database
    backup_local_database
    
    # Migrate data
    migrate_data
    
    # Verify migration
    verify_migration
    
    header "Migration Complete"
    success "PostgreSQL migration to NAS completed!"
    echo ""
    log "Summary:"
    log "  • Backup location: $BACKUP_DIR"
    log "  • Log file: $LOG_FILE"
    log "  • NAS database: $NAS_DB_HOST:$NAS_DB_PORT/$NAS_DB_NAME"
    echo ""
    echo "📝 Next steps:"
    echo "  1. Update system configuration to use NAS database"
    echo "  2. Test system with NAS database"
    echo "  3. Verify all functionality works"
    echo "  4. (Optional) Shut down local PostgreSQL"
    echo ""
}

main "$@"

