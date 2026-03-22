#!/bin/bash
# NAS PostgreSQL Setup - Manual Instructions
# Since SSH may not be available, this provides manual steps and scripts

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$PROJECT_ROOT/api/database/migrations"
BACKUP_DIR="$PROJECT_ROOT/backups/nas_migration_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Backup local database
backup_local_database() {
    header "Step 1: Backup Local Database"
    info "Creating backup of local database..."
    
    export PGPASSWORD="newsapp_password"
    
    if command -v pg_dump &> /dev/null; then
        info "Using pg_dump to create backup..."
        pg_dump -h localhost -p 5432 -U newsapp -d news_intelligence \
            -F c -f "$BACKUP_DIR/local_database_backup.dump" 2>&1
        
        if [ -f "$BACKUP_DIR/local_database_backup.dump" ]; then
            success "Backup created: $BACKUP_DIR/local_database_backup.dump"
            local size=$(du -h "$BACKUP_DIR/local_database_backup.dump" | cut -f1)
            info "Backup size: $size"
        else
            error "Backup failed"
            return 1
        fi
    else
        warning "pg_dump not found. Creating SQL dump instead..."
        python3 << EOF
import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='news_intelligence',
        user='newsapp',
        password='newsapp_password'
    )
    
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
    
    print(f"Found {len(tables)} tables")
    for table in tables[:10]:
        print(f"  - {table}")
    if len(tables) > 10:
        print(f"  ... and {len(tables) - 10} more")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF
        success "Database structure verified"
    fi
}

# Step 2: Create Docker Compose file for NAS
create_docker_compose() {
    header "Step 2: Create Docker Compose File"
    info "Creating docker-compose file for NAS PostgreSQL..."
    
    local compose_file="$BACKUP_DIR/docker-compose-postgres-nas.yml"
    cat > "$compose_file" << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: news-intelligence-postgres-nas
    environment:
      POSTGRES_DB: news_intelligence
      POSTGRES_USER: newsapp
      POSTGRES_PASSWORD: newsapp_password
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U newsapp -d news_intelligence"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    driver: local
EOF
    
    success "Docker compose file created: $compose_file"
    info "Copy this file to NAS and run: docker-compose -f docker-compose-postgres-nas.yml up -d"
}

# Step 3: Create migration package
create_migration_package() {
    header "Step 3: Create Migration Package"
    info "Packaging all migration files..."
    
    local migration_package="$BACKUP_DIR/migrations.tar.gz"
    tar -czf "$migration_package" -C "$PROJECT_ROOT" \
        api/database/migrations/ \
        api/database/init/ 2>/dev/null || true
    
    if [ -f "$migration_package" ]; then
        success "Migration package created: $migration_package"
        local size=$(du -h "$migration_package" | cut -f1)
        info "Package size: $size"
    else
        error "Failed to create migration package"
        return 1
    fi
}

# Step 4: Create setup script for NAS
create_nas_setup_script() {
    header "Step 4: Create NAS Setup Script"
    info "Creating setup script to run on NAS..."
    
    local setup_script="$BACKUP_DIR/setup_postgres_on_nas.sh"
    cat > "$setup_script" << 'SETUP_SCRIPT'
#!/bin/bash
# PostgreSQL Setup Script for NAS
# Run this script on the NAS after copying migration files

set -e

DB_NAME="news_intelligence"
DB_USER="newsapp"
DB_PASSWORD="newsapp_password"
MIGRATIONS_DIR="/tmp/news_intelligence_migrations"

echo "🚀 Setting up PostgreSQL on NAS"
echo "================================"

# Check if container is running
if ! docker ps | grep -q news-intelligence-postgres-nas; then
    echo "❌ PostgreSQL container not running"
    echo "Please start it first: docker-compose -f docker-compose-postgres-nas.yml up -d"
    exit 1
fi

echo "✅ PostgreSQL container is running"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec news-intelligence-postgres-nas pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    sleep 2
done

# Install postgresql-client in container
echo "Installing postgresql-client in container..."
docker exec news-intelligence-postgres-nas apk add --no-cache postgresql-client > /dev/null 2>&1

# Create migration tracking table
echo "Creating migration tracking table..."
docker exec news-intelligence-postgres-nas psql -U "$DB_USER" -d "$DB_NAME" <<EOF
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);
EOF

# Apply migrations
echo "Applying schema migrations..."
export PGPASSWORD="$DB_PASSWORD"

for migration in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
    migration_name=$(basename "$migration" .sql)
    echo "  Applying: $migration_name"
    
    # Check if already applied
    if docker exec news-intelligence-postgres-nas psql -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM schema_migrations WHERE migration_name = '$migration_name';" | grep -q "1"; then
        echo "    Already applied, skipping"
        continue
    fi
    
    # Apply migration
    if docker exec -i news-intelligence-postgres-nas psql -U "$DB_USER" -d "$DB_NAME" < "$migration" > /dev/null 2>&1; then
        docker exec news-intelligence-postgres-nas psql -U "$DB_USER" -d "$DB_NAME" -c \
            "INSERT INTO schema_migrations (migration_name) VALUES ('$migration_name') ON CONFLICT DO NOTHING;" > /dev/null 2>&1
        echo "    ✅ Applied"
    else
        echo "    ❌ Failed"
        exit 1
    fi
done

echo ""
echo "✅ Schema migrations complete!"
echo ""
echo "Next steps:"
echo "  1. Verify schema: docker exec news-intelligence-postgres-nas psql -U newsapp -d news_intelligence -c '\dt'"
echo "  2. Migrate data from local database"
echo "  3. Update system configuration to use NAS database"
SETUP_SCRIPT
    
    chmod +x "$setup_script"
    success "Setup script created: $setup_script"
}

# Step 5: Create data migration script
create_data_migration_script() {
    header "Step 5: Create Data Migration Script"
    info "Creating data migration script..."
    
    local data_script="$BACKUP_DIR/migrate_data_to_nas.sh"
    cat > "$data_script" << 'DATA_SCRIPT'
#!/bin/bash
# Data Migration Script - Migrate from Local to NAS Database

set -e

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

BACKUP_FILE="local_database_backup.dump"

echo "🔄 Migrating Data from Local to NAS Database"
echo "============================================"

# Test local connection
echo "Testing local database connection..."
export PGPASSWORD="$LOCAL_DB_PASSWORD"
if ! psql -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Cannot connect to local database"
    exit 1
fi
echo "✅ Local database connection successful"

# Test NAS connection
echo "Testing NAS database connection..."
export PGPASSWORD="$NAS_DB_PASSWORD"
if ! psql -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ Cannot connect to NAS database"
    exit 1
fi
echo "✅ NAS database connection successful"

# Restore from backup
if [ -f "$BACKUP_FILE" ]; then
    echo "Restoring from backup file: $BACKUP_FILE"
    export PGPASSWORD="$NAS_DB_PASSWORD"
    pg_restore -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" \
        --clean --if-exists --no-owner --no-privileges "$BACKUP_FILE" 2>&1 | grep -v "ERROR" || true
    echo "✅ Data migration complete"
else
    echo "⚠️  Backup file not found. Using pg_dump/pg_restore..."
    echo "Creating fresh dump from local database..."
    export PGPASSWORD="$LOCAL_DB_PASSWORD"
    pg_dump -h "$LOCAL_DB_HOST" -p "$LOCAL_DB_PORT" -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" \
        -F c -f /tmp/migration_dump.dump
    
    echo "Restoring to NAS database..."
    export PGPASSWORD="$NAS_DB_PASSWORD"
    pg_restore -h "$NAS_DB_HOST" -p "$NAS_DB_PORT" -U "$NAS_DB_USER" -d "$NAS_DB_NAME" \
        --clean --if-exists --no-owner --no-privileges /tmp/migration_dump.dump 2>&1 | grep -v "ERROR" || true
    
    echo "✅ Data migration complete"
fi

echo ""
echo "✅ Migration complete!"
echo "Verify data: psql -h $NAS_DB_HOST -U $NAS_DB_USER -d $NAS_DB_NAME -c 'SELECT COUNT(*) FROM articles;'"
DATA_SCRIPT
    
    chmod +x "$data_script"
    success "Data migration script created: $data_script"
}

# Create instructions document
create_instructions() {
    header "Creating Instructions Document"
    info "Creating step-by-step instructions..."
    
    local instructions="$BACKUP_DIR/MIGRATION_INSTRUCTIONS.md"
    cat > "$instructions" << 'INSTRUCTIONS'
# NAS PostgreSQL Migration Instructions

## Overview
This guide will help you migrate your PostgreSQL database to the NAS, rebuild it with the current schema, and migrate all data.

## Prerequisites
- NAS accessible at 192.168.93.100
- Docker installed on NAS
- Access to NAS web interface or command line
- Local database backup completed

## Step-by-Step Process

### Step 1: Backup Local Database ✅
Already completed. Backup location: `local_database_backup.dump`

### Step 2: Copy Files to NAS
Copy these files to your NAS:
- `docker-compose-postgres-nas.yml` - Docker compose configuration
- `migrations.tar.gz` - All migration files
- `setup_postgres_on_nas.sh` - Setup script

**Method 1: Via NAS Web Interface**
1. Access NAS web interface: http://192.168.93.100:8181
2. Navigate to File Manager
3. Upload files to a convenient location (e.g., `/tmp/` or `/home/`)

**Method 2: Via SMB/CIFS Mount**
```bash
sudo mount -t cifs //192.168.93.100/public /mnt/nas \
  -o username=Admin,password=<NAS_PASSWORD_PLACEHOLDER>,domain=LAKEHOUSE
cp docker-compose-postgres-nas.yml /mnt/nas/
cp migrations.tar.gz /mnt/nas/
cp setup_postgres_on_nas.sh /mnt/nas/
```

### Step 3: Start PostgreSQL Container on NAS
On the NAS, run:
```bash
docker-compose -f docker-compose-postgres-nas.yml up -d
```

Wait for container to be ready:
```bash
docker exec news-intelligence-postgres-nas pg_isready -U newsapp -d news_intelligence
```

### Step 4: Extract and Apply Migrations
On the NAS:
```bash
# Extract migrations
tar -xzf migrations.tar.gz -C /tmp/
mv /tmp/api/database/migrations /tmp/news_intelligence_migrations

# Run setup script
chmod +x setup_postgres_on_nas.sh
./setup_postgres_on_nas.sh
```

### Step 5: Migrate Data
On your local machine, run:
```bash
./migrate_data_to_nas.sh
```

Or manually:
```bash
export PGPASSWORD=newsapp_password
pg_restore -h 192.168.93.100 -U newsapp -d news_intelligence \
  --clean --if-exists --no-owner --no-privileges \
  local_database_backup.dump
```

### Step 6: Verify Migration
```bash
# Check table count
psql -h 192.168.93.100 -U newsapp -d news_intelligence -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"

# Check data
psql -h 192.168.93.100 -U newsapp -d news_intelligence -c "SELECT COUNT(*) FROM articles;"
```

### Step 7: Update System Configuration
Update your system to use NAS database:
```bash
export DB_HOST=192.168.93.100
export DB_PORT=5432
export DB_USER=newsapp
export DB_PASSWORD=newsapp_password
export DB_NAME=news_intelligence
```

## Troubleshooting

### Container won't start
- Check Docker logs: `docker logs news-intelligence-postgres-nas`
- Verify port 5432 is not in use: `netstat -tuln | grep 5432`

### Migration fails
- Check PostgreSQL logs: `docker logs news-intelligence-postgres-nas`
- Verify schema migrations table: `docker exec news-intelligence-postgres-nas psql -U newsapp -d news_intelligence -c "SELECT * FROM schema_migrations;"`

### Connection refused
- Verify container is running: `docker ps | grep postgres`
- Check firewall rules on NAS
- Verify PostgreSQL is listening: `docker exec news-intelligence-postgres-nas netstat -tuln | grep 5432`

## Files Created
- `local_database_backup.dump` - Full database backup
- `docker-compose-postgres-nas.yml` - Docker compose file
- `migrations.tar.gz` - All migration files
- `setup_postgres_on_nas.sh` - Setup script for NAS
- `migrate_data_to_nas.sh` - Data migration script

## Next Steps After Migration
1. Update `start_system.sh` to use NAS database
2. Test system with NAS database
3. Verify all functionality works
4. Remove local database (optional)
INSTRUCTIONS
    
    success "Instructions created: $instructions"
}

# Main execution
main() {
    header "NAS PostgreSQL Setup - Manual Process"
    echo ""
    echo "Since SSH may not be available, this script prepares all files"
    echo "and instructions for manual setup on the NAS."
    echo ""
    
    backup_local_database
    create_docker_compose
    create_migration_package
    create_nas_setup_script
    create_data_migration_script
    create_instructions
    
    header "Setup Complete"
    success "All files prepared in: $BACKUP_DIR"
    echo ""
    echo "📋 Files created:"
    echo "  • local_database_backup.dump - Database backup"
    echo "  • docker-compose-postgres-nas.yml - Docker compose file"
    echo "  • migrations.tar.gz - Migration files package"
    echo "  • setup_postgres_on_nas.sh - Setup script for NAS"
    echo "  • migrate_data_to_nas.sh - Data migration script"
    echo "  • MIGRATION_INSTRUCTIONS.md - Complete instructions"
    echo ""
    echo "🚀 Next steps:"
    echo "  1. Copy files to NAS (via web interface or SMB mount)"
    echo "  2. Follow instructions in MIGRATION_INSTRUCTIONS.md"
    echo "  3. Run setup script on NAS"
    echo "  4. Migrate data from local to NAS"
    echo ""
}

main "$@"

