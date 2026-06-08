#!/bin/bash
# scripts/backup_database_for_widow_migration.sh
# Creates compressed backup of PostgreSQL database for migration to Widow server

set -e

# ==============================
# CONFIGURATION
# ==============================

BACKUP_DIR="/mnt/nas/Data Lake Storage/news-intelligence/migration-2026-06"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Database connection (Widow — where DB currently runs)
DB_HOST="192.168.93.101"
DB_PORT="5432"
DB_NAME="news_intel"
DB_USER="newsintel_user"

# ==============================
# FUNCTIONS
# ==============================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    log "❌ ERROR: $*"
    exit 1
}

# ==============================
# START
# ==============================

log "=========================================="
log "  News Intelligence — Database Backup"
log "=========================================="
log ""
log "Source:    PostgreSQL on $DB_HOST:$DB_PORT"
log "Database:  $DB_NAME"
log "Backup:    $BACKUP_DIR"
log ""

# Check if NAS mount point exists
if [ ! -d "/mnt/nas" ]; then
    error "NAS mount point not found at /mnt/nas"
fi

# Create backup directory
log "📁 Creating backup directory..."
mkdir -p "$BACKUP_DIR/db-backups"

# Get database stats first
log "📊 Gathering database statistics..."
DB_SIZE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));" 2>/dev/null | tr -d ' ' || echo "Unknown")

SCHEMA_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name != 'information_schema';" 2>/dev/null | tr -d ' ' || echo "Unknown")

log "   Database size: $DB_SIZE"
log "   Schemas: $SCHEMA_COUNT"

# Dump database to SQL file
log "📄 Creating SQL dump..."
SQL_DUMP="$BACKUP_DIR/db-backups/news-intel-database-$TIMESTAMP.sql"

log "   Dumping to: $SQL_DUMP"
log "   This may take several minutes..."

pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -F p \
    -f "$SQL_DUMP" \
    --verbose 2>/dev/null

SQL_SIZE=$(du -h "$SQL_DUMP" | cut -f1)
log "   ✅ SQL dump created: ${SQL_SIZE}"

# Compress SQL dump
log "🗜️  Compressing SQL dump..."
gzip -f "$SQL_DUMP"
COMPRESSED_SIZE=$(du -h "${SQL_DUMP}.gz" | cut -f1)
log "   ✅ Compressed: ${SQL_SIZE} → ${COMPRESSED_SIZE}"

# Create domain inventory (list of active domains)
log "📋 Creating domain inventory..."
DOMAIN_LIST="$BACKUP_DIR/db-backups/domain-inventory-$TIMESTAMP.txt"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT schema_name FROM information_schema.schemata 
     WHERE schema_name NOT LIKE 'pg_%' 
     AND schema_name != 'information_schema'
     AND schema_name != 'public'
     ORDER BY schema_name;" 2>/dev/null | sed 's/^/   - /' > "$DOMAIN_LIST"
log "   Active domains:"
cat "$DOMAIN_LIST"

# Create table count summary
log "📊 Creating table count summary..."
TABLE_SUMMARY="$BACKUP_DIR/db-backups/table-counts-$TIMESTAMP.txt"

cat > "$TABLE_SUMMARY" << EOF
Database Table Counts Report
Generated: $(date)

EOF

for TABLE in articles storylines topics rss_feeds events; do
    for DOMAIN in $(cat "$DOMAIN_LIST" | sed 's/   - //' | tr '\n' ' '); do
        if [ -n "$DOMAIN" ]; then
            COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
                "SELECT COUNT(*) FROM \"$DOMAIN\".\"$TABLE\";" 2>/dev/null | tr -d ' ')
            echo "   ${DOMAIN}.${TABLE}: $COUNT" >> "$TABLE_SUMMARY"
        fi
    done
done

log "   ✅ Table counts saved"

# Create schema definitions (CREATE TABLE statements for reference)
log "📐 Exporting schema definitions..."
SCHEMA_EXPORT="$BACKUP_DIR/db-backups/schema-definitions-$TIMESTAMP.sql"
pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --schema-only \
    -F p \
    -f "$SCHEMA_EXPORT" \
    2>/dev/null
log "   ✅ Schema definitions saved"

# Create manifest
log "📄 Creating database manifest..."
cat > "$BACKUP_DIR/db-backups/MANIFEST-db-$TIMESTAMP.txt" << EOF
Database Backup Manifest
=========================
Timestamp: $TIMESTAMP
Date Created: $(date)
Source Host: $DB_HOST:$DB_PORT (Widow — Current DB Location)
Target Host: 192.168.93.101:$DB_PORT (Widow — Same server, new installation)

Database Information:
  Name: $DB_NAME
  User: $DB_USER
  Port: $DB_PORT
  Size: $DB_SIZE (before compression)

Backup Files:
  1. news-intel-database-$TIMESTAMP.sql.gz
     - Full database dump (compressed)
     - Contains: All schemas, tables, data, indexes, constraints
     - Restore with: gunzip && psql

  2. schema-definitions-$TIMESTAMP.sql
     - Schema-only dump (CREATE TABLE statements)
     - Useful for: Documentation, migration verification

  3. domain-inventory-$TIMESTAMP.txt
     - List of all active domain schemas

  4. table-counts-$TIMESTAMP.txt
     - Row counts per table per domain

Restore Instructions:
  1. Ensure PostgreSQL is running on target
  2. Create database: createdb -h localhost -p 5432 -U newsintel_user news_intel
  3. Restore: gunzip < file.sql.gz | psql -h localhost -p 5432 -U newsintel_user news_intel

Verification:
EOF

# Verify compressed file
if [ -f "${SQL_DUMP}.gz" ]; then
    echo "✅ Compressed dump exists: YES" >> "$BACKUP_DIR/db-backups/MANIFEST-db-$TIMESTAMP.txt"
    echo "📦 Compressed size: $(du -h "${SQL_DUMP}.gz" | cut -f1)" >> "$BACKUP_DIR/db-backups/MANIFEST-db-$TIMESTAMP.txt"
    log "   ✅ Backup files verified"
else
    echo "❌ Compressed dump exists: NO" >> "$BACKUP_DIR/db-backups/MANIFEST-db-$TIMESTAMP.txt"
    error "Backup file not found!"
fi

# Summary
log ""
log "=========================================="
log "  ✅ Database Backup Complete!"
log "=========================================="
log ""
log "📍 Backup Location: $BACKUP_DIR/db-backups"
log ""
log "📋 Files Created:"
ls -lh "$BACKUP_DIR/db-backups"/*"$TIMESTAMP"* 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'
log ""
log "📄 Manifest: $BACKUP_DIR/db-backups/MANIFEST-db-$TIMESTAMP.txt"
log ""
log "📝 Summary:"
log "   Database:     $DB_NAME"
log "   Original Size: $DB_SIZE"
log "   Compressed:   ${COMPRESSED_SIZE}"
log ""
log "📝 Next Steps:"
log "   1. Verify project backup exists: ls $BACKUP_DIR"
log "   2. Test restore on a clean database (optional but recommended)"
log "   3. When ready, run: restore_news_intelligence_on_widow.sh"
log ""