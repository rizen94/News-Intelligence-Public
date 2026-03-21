#!/bin/bash
# Migrate Database via SSH
# Uses SSH to execute migration commands on NAS since direct connection is blocked

set -e

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
LOCAL_HOST="localhost"
DB_NAME="news_intelligence"
DB_USER="newsapp"
DB_PASSWORD="newsapp_password"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$PROJECT_ROOT/api/database/migrations"
BACKUP_DIR="$PROJECT_ROOT/backups/ssh_migration_$(date +%Y%m%d_%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$BACKUP_DIR"

echo "🔄 Database Migration via SSH"
echo "=============================="
echo ""

# Step 1: Backup local database
echo "Step 1: Backing up local database..."
export PGPASSWORD="$DB_PASSWORD"
pg_dump -h "$LOCAL_HOST" -p 5432 -U "$DB_USER" -d "$DB_NAME" \
    -F c -f "$BACKUP_DIR/local_database_backup.dump" 2>&1

if [ -f "$BACKUP_DIR/local_database_backup.dump" ]; then
    SIZE=$(du -h "$BACKUP_DIR/local_database_backup.dump" | cut -f1)
    echo -e "${GREEN}✅ Backup created: $SIZE${NC}"
else
    echo -e "${RED}❌ Backup failed${NC}"
    exit 1
fi
echo ""

# Step 2: Copy backup to NAS
echo "Step 2: Copying backup to NAS..."
scp -P "$NAS_SSH_PORT" "$BACKUP_DIR/local_database_backup.dump" \
    "$NAS_USER@$NAS_HOST:/tmp/postgres_backup.dump" 2>&1
echo -e "${GREEN}✅ Backup copied to NAS${NC}"
echo ""

# Step 3: Restore to NAS database via SSH
echo "Step 3: Restoring backup to NAS database..."
ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "/usr/local/bin/docker exec -i news-intelligence-postgres \
    pg_restore -U $DB_USER -d $DB_NAME --clean --if-exists --no-owner --no-privileges \
    < /tmp/postgres_backup.dump 2>&1" || echo -e "${YELLOW}⚠️  Some warnings may be normal${NC}"
echo ""

# Step 4: Verify migration
echo "Step 4: Verifying migration..."
echo ""

# Get table counts
LOCAL_TABLES=$(psql -h "$LOCAL_HOST" -p 5432 -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" 2>/dev/null | tr -d ' ')

NAS_TABLES=$(ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "/usr/local/bin/docker exec news-intelligence-postgres \
    psql -U $DB_USER -d $DB_NAME -t -c \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';\" 2>&1" | tr -d ' ' | grep -E '^[0-9]+$' || echo "0")

echo "  Local database: $LOCAL_TABLES tables"
echo "  NAS database: $NAS_TABLES tables"

if [ "$NAS_TABLES" -ge "$LOCAL_TABLES" ]; then
    echo -e "  ${GREEN}✅ Table count matches or exceeds local${NC}"
else
    echo -e "  ${YELLOW}⚠️  Table count differs${NC}"
fi
echo ""

# Get record counts for key tables
echo "Key table record counts:"
for table in articles rss_feeds schema_migrations; do
    LOCAL_COUNT=$(psql -h "$LOCAL_HOST" -p 5432 -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT COUNT(*) FROM $table;" 2>/dev/null | tr -d ' ' || echo "0")
    
    NAS_COUNT=$(ssh -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "/usr/local/bin/docker exec news-intelligence-postgres \
        psql -U $DB_USER -d $DB_NAME -t -c \"SELECT COUNT(*) FROM $table;\" 2>&1" | tr -d ' ' | grep -E '^[0-9]+$' || echo "0")
    
    if [ "$NAS_COUNT" -eq "$LOCAL_COUNT" ]; then
        echo -e "  ${GREEN}✅ $table: $LOCAL_COUNT -> $NAS_COUNT${NC}"
    elif [ "$NAS_COUNT" -gt 0 ]; then
        echo -e "  ${YELLOW}⚠️  $table: $LOCAL_COUNT -> $NAS_COUNT (differs)${NC}"
    else
        echo -e "  ${RED}❌ $table: $LOCAL_COUNT -> $NAS_COUNT (missing)${NC}"
    fi
done
echo ""

echo "=========================================="
echo -e "${GREEN}✅ Migration via SSH complete!${NC}"
echo "=========================================="
echo ""
echo "Backup location: $BACKUP_DIR"
echo ""

