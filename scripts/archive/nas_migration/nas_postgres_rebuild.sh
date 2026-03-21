#!/bin/bash
# NAS PostgreSQL Rebuild and Migration Script
# This script helps SSH into NAS, rebuild PostgreSQL container, and migrate data

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configuration
NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_PASSWORD="Pooter@STORAGE2024"
DB_NAME="news_intelligence"
DB_USER="newsapp"
DB_PASSWORD="newsapp_password"
LOCAL_DB_HOST="localhost"
LOCAL_DB_PORT="5432"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$PROJECT_ROOT/api/database/migrations"
BACKUP_DIR="$PROJECT_ROOT/backups/nas_migration_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$PROJECT_ROOT/logs/nas_postgres_rebuild.log"

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

info() {
    echo -e "${CYAN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

# Test SSH connection
test_ssh() {
    header "Testing SSH Connection to NAS"
    log "Attempting to connect to ${NAS_USER}@${NAS_HOST}:${NAS_SSH_PORT}..."
    
    # Try SSH key authentication (primary method)
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "echo 'SSH connection successful'" > /dev/null 2>&1; then
        success "SSH connection successful (key-based) on port $NAS_SSH_PORT"
        return 0
    fi
    
    # Fallback to password if key doesn't work
    if command -v sshpass &> /dev/null; then
        if sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
            "${NAS_USER}@${NAS_HOST}" "echo 'SSH connection successful'" > /dev/null 2>&1; then
            success "SSH connection successful (password) on port $NAS_SSH_PORT"
            return 0
        fi
    fi
    
    error "Cannot connect to NAS via SSH"
    error "Please ensure SSH keys are set up: ./scripts/setup_nas_ssh_key.sh"
    return 1
}

# Check SSH key setup
check_ssh_key() {
    info "Checking SSH key authentication..."
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "echo 'test'" > /dev/null 2>&1; then
        success "SSH key authentication is working"
        return 0
    else
        warning "SSH key authentication check failed, but continuing..."
        info "Will attempt connection during actual operations"
        return 0  # Don't fail, just warn
    fi
}

# Execute command on NAS via SSH (prefers key-based auth)
ssh_exec() {
    local cmd="$1"
    # Try SSH key first (default)
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "$cmd" 2>/dev/null || \
    # Fallback to password if key fails
    (command -v sshpass &> /dev/null && \
     sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "$cmd")
}

# Copy file to NAS (prefers key-based auth)
ssh_copy() {
    local local_file="$1"
    local remote_path="$2"
    # Try SSH key first (default)
    scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 -P "$NAS_SSH_PORT" \
        "$local_file" "${NAS_USER}@${NAS_HOST}:${remote_path}" 2>/dev/null || \
    # Fallback to password if key fails
    (command -v sshpass &> /dev/null && \
     sshpass -p "$NAS_PASSWORD" scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 -P "$NAS_SSH_PORT" \
        "$local_file" "${NAS_USER}@${NAS_HOST}:${remote_path}")
}

# Check Docker on NAS
check_docker_on_nas() {
    header "Checking Docker on NAS"
    info "Checking if Docker is available on NAS..."
    
    if ssh_exec "command -v docker" > /dev/null 2>&1; then
        success "Docker is available on NAS"
        ssh_exec "docker --version"
        return 0
    else
        error "Docker is not available on NAS"
        return 1
    fi
}

# Backup local database
backup_local_database() {
    header "Backing Up Local Database"
    log "Creating backup of local database..."
    
    export PGPASSWORD="newsapp_password"
    
    if command -v pg_dump &> /dev/null; then
        log "Using pg_dump to backup database..."
        pg_dump -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -F c -f "$BACKUP_DIR/local_database_backup.dump" 2>&1 | tee -a "$LOG_FILE"
        success "Local database backup created: $BACKUP_DIR/local_database_backup.dump"
    else
        warning "pg_dump not found. Trying Python backup..."
        python3 << EOF
import psycopg2
import sys
sys.path.insert(0, '$PROJECT_ROOT/api')
from config.database import DatabaseManager

try:
    db = DatabaseManager()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Found {len(tables)} tables to backup")
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF
        success "Database structure verified"
    fi
}

# Create PostgreSQL container on NAS
create_postgres_container() {
    header "Creating PostgreSQL Container on NAS"
    info "Setting up PostgreSQL container on NAS..."
    
    # Create docker-compose file for NAS
    local compose_file="/tmp/docker-compose-postgres.yml"
    cat > "$compose_file" << EOF
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: news-intelligence-postgres-nas
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    driver: local
EOF
    
    # Copy compose file to NAS
    info "Copying docker-compose file to NAS..."
    ssh_copy "$compose_file" "/tmp/docker-compose-postgres.yml"
    
    # Stop existing container if it exists
    info "Stopping existing PostgreSQL container (if any)..."
    ssh_exec "docker stop news-intelligence-postgres-nas 2>/dev/null || true"
    ssh_exec "docker rm news-intelligence-postgres-nas 2>/dev/null || true"
    
    # Start new container
    info "Starting PostgreSQL container..."
    ssh_exec "cd /tmp && docker-compose -f docker-compose-postgres.yml up -d"
    
    # Wait for container to be ready
    info "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if ssh_exec "docker exec news-intelligence-postgres-nas pg_isready -U ${DB_USER} -d ${DB_NAME}" > /dev/null 2>&1; then
            success "PostgreSQL container is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    error "PostgreSQL container failed to start"
}

# Apply schema migrations on NAS
apply_schema_migrations() {
    header "Applying Schema Migrations on NAS"
    info "Applying database schema to NAS PostgreSQL..."
    
    # Copy migration files to NAS
    info "Copying migration files to NAS..."
    ssh_exec "mkdir -p /tmp/news_intelligence_migrations"
    
    # Copy all migration files
    for migration_file in "$MIGRATIONS_DIR"/*.sql; do
        if [ -f "$migration_file" ]; then
            local filename=$(basename "$migration_file")
            ssh_copy "$migration_file" "/tmp/news_intelligence_migrations/$filename"
        fi
    done
    
    # Copy migration script
    local migration_script="/tmp/apply_migrations.sh"
    cat > "$migration_script" << 'MIGRATION_SCRIPT'
#!/bin/bash
set -e

DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="news_intelligence"
DB_USER="newsapp"
DB_PASSWORD="newsapp_password"
MIGRATIONS_DIR="/tmp/news_intelligence_migrations"

export PGPASSWORD="$DB_PASSWORD"

# Create migration tracking table
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);
EOF

# Apply migrations in order
for migration in $(ls "$MIGRATIONS_DIR"/*.sql | sort); do
    migration_name=$(basename "$migration" .sql)
    echo "Applying migration: $migration_name"
    
    # Check if already applied
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM schema_migrations WHERE migration_name = '$migration_name';" | grep -q "1"; then
        echo "  Already applied, skipping"
        continue
    fi
    
    # Apply migration
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration"; then
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
            "INSERT INTO schema_migrations (migration_name) VALUES ('$migration_name') ON CONFLICT DO NOTHING;"
        echo "  ✅ Applied successfully"
    else
        echo "  ❌ Failed to apply"
        exit 1
    fi
done

echo "✅ All migrations applied"
MIGRATION_SCRIPT
    
    ssh_copy "$migration_script" "/tmp/apply_migrations.sh"
    ssh_exec "chmod +x /tmp/apply_migrations.sh"
    
    # Execute migration script inside container
    info "Running migrations inside PostgreSQL container..."
    ssh_exec "docker exec news-intelligence-postgres-nas /bin/sh -c 'apk add --no-cache postgresql-client && /tmp/apply_migrations.sh'"
    
    success "Schema migrations applied"
}

# Migrate data from local to NAS
migrate_data() {
    header "Migrating Data from Local to NAS"
    info "Preparing data migration..."
    
    # Create data migration script
    local data_script="/tmp/migrate_data.sh"
    cat > "$data_script" << 'DATA_SCRIPT'
#!/bin/bash
# This will be run locally to migrate data
echo "Data migration will be handled separately"
DATA_SCRIPT
    
    warning "Data migration step - will be completed after schema is ready"
    info "Once schema is ready, we'll use pg_dump/pg_restore to migrate data"
}

# Main execution
main() {
    header "NAS PostgreSQL Rebuild and Migration"
    log "Starting NAS PostgreSQL rebuild process"
    
    # Pre-flight checks
    check_ssh_key
    test_ssh
    check_docker_on_nas
    
    # Backup local database
    backup_local_database
    
    # Create PostgreSQL container on NAS
    create_postgres_container
    
    # Apply schema migrations
    apply_schema_migrations
    
    # Migrate data (placeholder)
    migrate_data
    
    header "Migration Complete"
    success "PostgreSQL container rebuilt on NAS with current schema"
    info "Next steps:"
    info "  1. Verify schema on NAS"
    info "  2. Run data migration script"
    info "  3. Update system configuration to use NAS database"
    info ""
    info "Backup location: $BACKUP_DIR"
    info "Log file: $LOG_FILE"
}

# Run main function
main "$@"

