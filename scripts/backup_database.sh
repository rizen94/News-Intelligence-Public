#!/bin/bash

# Database Backup Script
# Creates a full backup of the database before cleanup

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Error handling function
error_exit() {
    echo -e "${RED}❌ ERROR: $1${NC}" >&2
    exit 1
}

# Get timestamp for backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/Documents/projects/Projects/News Intelligence/backups"
BACKUP_FILE="$BACKUP_DIR/news_intelligence_backup_$TIMESTAMP.sql.gz"

echo "💾 DATABASE BACKUP"
echo "================="
echo ""

# Set environment variables
export PGPASSWORD=newsapp_password

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "📂 Backup directory: $BACKUP_DIR"
echo "📄 Backup file: $(basename $BACKUP_FILE)"
echo ""
echo "🔄 Creating backup using Python..."
cd "$(dirname "$0")/../api"

if python3 << PYEOF
import sys
import gzip
from datetime import datetime
from config.database import get_db_connection
import psycopg2

try:
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cur.fetchall()]
    
    backup_file = "$BACKUP_FILE"
    
    with open(backup_file, 'w') as f:
        f.write(f"-- News Intelligence Database Backup\\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\\n")
        f.write(f"-- Total Tables: {len(tables)}\\n\\n")
        
        # Backup each table
        for table_name in tables:
            try:
                # Get table structure
                cur.execute(f"SELECT * FROM {table_name} LIMIT 0")
                columns = [desc[0] for desc in cur.description]
                
                # Get all data
                cur.execute(f"SELECT * FROM {table_name}")
                rows = cur.fetchall()
                
                f.write(f"\\n-- Table: {table_name}\\n")
                f.write(f"-- Rows: {len(rows)}\\n\\n")
                
                # Write data (basic format)
                for row in rows:
                    values = []
                    for val in row:
                        if val is None:
                            values.append("NULL")
                        elif isinstance(val, str):
                            values.append(f"'{val.replace(chr(39), chr(39)+chr(39))}'")
                        else:
                            values.append(str(val))
                    
                    f.write(f"INSERT INTO {table_name} VALUES ({','.join(values)});\\n")
                
                f.write(f"\\n")
                
            except Exception as e:
                f.write(f"-- Error backing up {table_name}: {e}\\n")
    
    conn.close()
    print(f"Backup completed: {backup_file}")
    sys.exit(0)
    
except Exception as e:
    print(f"Backup failed: {e}")
    sys.exit(1)
PYEOF
then
    # Get backup file size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo ""
    echo -e "${GREEN}✅ Backup created successfully!${NC}"
    echo "   File: $BACKUP_FILE"
    echo "   Size: $BACKUP_SIZE"
    
    # Verify backup integrity
    echo ""
    echo "🔍 Verifying backup integrity..."
    if gunzip -t "$BACKUP_FILE" 2>/dev/null; then
        echo -e "${GREEN}   ✅ Backup file is valid${NC}"
    else
        error_exit "Backup file is corrupt!"
    fi
    
    # Count tables in backup
    TABLE_COUNT=$(gunzip -c "$BACKUP_FILE" | grep -c "^CREATE TABLE" || true)
    echo "   Tables in backup: $TABLE_COUNT"
    
    echo ""
    echo -e "${GREEN}✅ BACKUP COMPLETE${NC}"
    echo "=================="
    echo ""
    echo "Backup is ready at:"
    echo "  $BACKUP_FILE"
    echo ""
    echo "You can restore this backup with:"
    echo "  gunzip -c $BACKUP_FILE | psql -h localhost -U newsapp -d news_intelligence"
    
    exit 0
else
    error_exit "Backup failed!"
fi

