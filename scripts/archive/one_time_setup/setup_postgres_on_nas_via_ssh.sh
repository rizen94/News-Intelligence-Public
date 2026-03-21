#!/bin/bash
# Setup PostgreSQL on NAS via SSH
# This script connects to NAS and sets up PostgreSQL container with schema

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_MOUNT="/mnt/nas"
DB_NAME="news_intelligence"
DB_USER="newsapp"
DB_PASSWORD="newsapp_password"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
}

# Test SSH connection
test_ssh() {
    header "Testing SSH Connection"
    log "Connecting to ${NAS_USER}@${NAS_HOST}:${NAS_SSH_PORT}..."
    
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "echo 'SSH connection successful' && whoami && hostname" 2>&1; then
        success "SSH connection successful"
        return 0
    else
        error "Cannot connect to NAS via SSH"
        return 1
    fi
}

# Execute command on NAS
ssh_exec() {
    local cmd="$1"
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "$cmd"
}

# Copy file to NAS
ssh_copy() {
    local local_file="$1"
    local remote_path="$2"
    scp -o StrictHostKeyChecking=no -P "$NAS_SSH_PORT" \
        "$local_file" "${NAS_USER}@${NAS_HOST}:${remote_path}"
}

# Check Docker on NAS
check_docker() {
    header "Checking Docker on NAS"
    log "Checking if Docker is available..."
    
    if ssh_exec "command -v docker" > /dev/null 2>&1; then
        success "Docker is available"
        ssh_exec "docker --version"
        return 0
    else
        error "Docker is not available on NAS"
        return 1
    fi
}

# Start PostgreSQL container
start_postgres_container() {
    header "Starting PostgreSQL Container"
    log "Setting up PostgreSQL container on NAS..."
    
    # Check if container already exists
    if ssh_exec "docker ps -a --format '{{.Names}}' | grep -q 'news-intelligence-postgres-nas'" 2>/dev/null; then
        warning "PostgreSQL container already exists"
        read -p "Remove existing container and create new one? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Stopping and removing existing container..."
            ssh_exec "docker stop news-intelligence-postgres-nas 2>/dev/null || true"
            ssh_exec "docker rm news-intelligence-postgres-nas 2>/dev/null || true"
        else
            log "Using existing container"
            ssh_exec "docker start news-intelligence-postgres-nas 2>/dev/null || true"
            return 0
        fi
    fi
    
    # Check if docker-compose file exists on NAS
    if ssh_exec "test -f ${NAS_MOUNT}/docker-compose-postgres-nas.yml" 2>/dev/null; then
        log "Using docker-compose file from NAS..."
        ssh_exec "cd ${NAS_MOUNT} && docker-compose -f docker-compose-postgres-nas.yml up -d"
    else
        # Create docker-compose file on NAS
        log "Creating docker-compose file on NAS..."
        ssh_exec "cat > /tmp/docker-compose-postgres-nas.yml << 'EOF'
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
      - \"5432:5432\"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: [\"CMD-SHELL\", \"pg_isready -U ${DB_USER} -d ${DB_NAME}\"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    driver: local
EOF
"
        ssh_exec "cd /tmp && docker-compose -f docker-compose-postgres-nas.yml up -d"
    fi
    
    # Wait for container to be ready
    log "Waiting for PostgreSQL to be ready..."
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

# Apply schema migrations
apply_schema_migrations() {
    header "Applying Schema Migrations"
    log "Applying database schema to NAS PostgreSQL..."
    
    # Check if migrations are on NAS
    if ssh_exec "test -f ${NAS_MOUNT}/migrations.tar.gz" 2>/dev/null; then
        log "Extracting migrations from NAS..."
        ssh_exec "tar -xzf ${NAS_MOUNT}/migrations.tar.gz -C /tmp/ 2>/dev/null || true"
        ssh_exec "mkdir -p /tmp/news_intelligence_migrations"
        ssh_exec "mv /tmp/api/database/migrations/* /tmp/news_intelligence_migrations/ 2>/dev/null || true"
    else
        error "Migrations file not found on NAS: ${NAS_MOUNT}/migrations.tar.gz"
    fi
    
    # Install postgresql-client in container
    log "Installing postgresql-client in container..."
    ssh_exec "docker exec news-intelligence-postgres-nas apk add --no-cache postgresql-client > /dev/null 2>&1"
    
    # Create migration tracking table
    log "Creating migration tracking table..."
    ssh_exec "docker exec news-intelligence-postgres-nas psql -U ${DB_USER} -d ${DB_NAME} <<EOF
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);
EOF
"
    
    # Apply migrations
    log "Applying schema migrations..."
    ssh_exec "docker exec news-intelligence-postgres-nas sh -c '
        export PGPASSWORD=${DB_PASSWORD}
        for migration in \$(ls /tmp/news_intelligence_migrations/*.sql 2>/dev/null | sort); do
            migration_name=\$(basename \$migration .sql)
            echo \"  Applying: \$migration_name\"
            
            # Check if already applied
            if psql -h localhost -U ${DB_USER} -d ${DB_NAME} -t -c \"SELECT COUNT(*) FROM schema_migrations WHERE migration_name = '\$migration_name';\" | grep -q \"1\"; then
                echo \"    Already applied, skipping\"
                continue
            fi
            
            # Apply migration
            if psql -h localhost -U ${DB_USER} -d ${DB_NAME} -f \$migration > /dev/null 2>&1; then
                psql -h localhost -U ${DB_USER} -d ${DB_NAME} -c \"INSERT INTO schema_migrations (migration_name) VALUES ('\$migration_name') ON CONFLICT DO NOTHING;\" > /dev/null 2>&1
                echo \"    ✅ Applied\"
            else
                echo \"    ❌ Failed\"
            fi
        done
    '"
    
    success "Schema migrations applied"
}

# Verify setup
verify_setup() {
    header "Verifying Setup"
    log "Verifying NAS PostgreSQL setup..."
    
    # Test connection
    export PGPASSWORD="$DB_PASSWORD"
    if psql -h "$NAS_HOST" -p "$NAS_DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        success "NAS database connection successful"
        
        # Get table count
        local table_count=$(psql -h "$NAS_HOST" -p "$NAS_DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
        
        log "NAS database has $table_count tables"
        
        if [ "$table_count" -gt 0 ]; then
            success "Schema is ready for data migration"
            return 0
        else
            warning "Database is empty - migrations may have failed"
            return 1
        fi
    else
        error "Cannot connect to NAS database"
        return 1
    fi
}

# Main execution
main() {
    header "PostgreSQL Setup on NAS via SSH"
    log "Setting up PostgreSQL on NAS..."
    echo ""
    
    # Pre-flight checks
    test_ssh
    check_docker
    
    # Start PostgreSQL container
    start_postgres_container
    
    # Apply schema migrations
    apply_schema_migrations
    
    # Verify setup
    verify_setup
    
    header "Setup Complete"
    success "PostgreSQL is set up on NAS and ready for data migration!"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Run data migration: ./scripts/migrate_postgres_to_nas.sh"
    echo "   2. Update system configuration to use NAS database"
    echo "   3. Test system with NAS database"
    echo ""
    echo "🔗 Connection details:"
    echo "   Host: $NAS_HOST"
    echo "   Port: 5432"
    echo "   Database: $DB_NAME"
    echo "   User: $DB_USER"
    echo ""
}

main "$@"

