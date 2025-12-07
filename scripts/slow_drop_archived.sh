#!/bin/bash

# Slow background script to drop archived tables over time
# This avoids locking and network issues

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_DIR/api"
LOG_FILE="$PROJECT_DIR/logs/slow_drop.log"

cd "$API_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

echo "$(date): Starting slow drop of archived tables" >> "$LOG_FILE"

while true; do
    echo "$(date): Checking for archived tables to drop..." >> "$LOG_FILE"
    
    # Drop archived tables 5 at a time
    python3 << PYEOF
import sys
import os
import time

sys.path.insert(0, '$API_DIR')

try:
    from config.database import get_db_connection
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get up to 5 archived tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'archived_%'
        LIMIT 5
    """)
    
    tables = [row[0] for row in cur.fetchall()]
    
    if not tables:
        print("No archived tables found")
        sys.exit(0)
    
    print(f"Dropping {len(tables)} archived tables...")
    
    for table in tables:
        try:
            cur.execute(f'DROP TABLE IF EXISTS {table} CASCADE')
            conn.commit()
            print(f"  Dropped {table}")
        except Exception as e:
            print(f"  Error dropping {table}: {e}")
            conn.rollback()
        
        time.sleep(2)  # 2 second delay between drops
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
PYEOF
    
    echo "$(date): Completed batch, waiting 5 minutes..." >> "$LOG_FILE"
    sleep 300  # Wait 5 minutes
done

