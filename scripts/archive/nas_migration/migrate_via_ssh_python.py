#!/usr/bin/env python3
"""
Database Migration via SSH
Uses Python to migrate data since direct connection is blocked by firewall
"""

import psycopg2
import subprocess
import sys
import os
from pathlib import Path

# Configuration
NAS_HOST = "192.168.93.100"
NAS_SSH_PORT = "9222"
NAS_USER = "Admin"
LOCAL_HOST = "localhost"
DB_NAME = "news_intelligence"
DB_USER = "newsapp"
DB_PASSWORD = "newsapp_password"

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKUP_DIR = PROJECT_ROOT / "backups" / f"ssh_migration_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def execute_sql_via_ssh(sql):
    """Execute SQL on NAS database via SSH"""
    cmd = f'ssh -p {NAS_SSH_PORT} {NAS_USER}@{NAS_HOST} "/usr/local/bin/docker exec news-intelligence-postgres psql -U {DB_USER} -d {DB_NAME} -c \\"{sql}\\" 2>&1"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr

def get_local_connection():
    """Get connection to local database"""
    return psycopg2.connect(
        host=LOCAL_HOST,
        port=5432,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=5
    )

def get_table_list(conn):
    """Get list of tables from database"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    return [row[0] for row in cursor.fetchall()]

def get_record_count(conn, table):
    """Get record count for a table"""
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        return cursor.fetchone()[0]
    except:
        return 0

def migrate_table_data(local_conn, table_name):
    """Migrate data from local to NAS for a specific table"""
    print(f"  Migrating {table_name}...")
    
    # Get data from local
    local_cursor = local_conn.cursor()
    local_cursor.execute(f"SELECT * FROM {table_name};")
    columns = [desc[0] for desc in local_cursor.description]
    rows = local_cursor.fetchall()
    
    if not rows:
        print(f"    {table_name}: 0 rows (skipping)")
        return 0
    
    # Get column info for INSERT
    local_cursor.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position;
    """, (table_name,))
    col_info = local_cursor.fetchall()
    
    # Check if table exists on NAS
    stdout, stderr = execute_sql_via_ssh(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table_name}');")
    if 't' not in stdout:
        print(f"    ⚠️  Table {table_name} doesn't exist on NAS, skipping data migration")
        return 0
    
    # Clear existing data
    execute_sql_via_ssh(f"TRUNCATE TABLE {table_name} CASCADE;")
    
    # Insert data in batches
    batch_size = 100
    total_inserted = 0
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        values_list = []
        
        for row in batch:
            values = []
            for val in row:
                if val is None:
                    values.append('NULL')
                elif isinstance(val, str):
                    # Escape single quotes
                    val = val.replace("'", "''")
                    values.append(f"'{val}'")
                else:
                    values.append(str(val))
            values_list.append(f"({', '.join(values)})")
        
        columns_str = ', '.join(columns)
        values_str = ', '.join(values_list)
        
        sql = f"INSERT INTO {table_name} ({columns_str}) VALUES {values_str};"
        stdout, stderr = execute_sql_via_ssh(sql)
        
        if 'ERROR' in stderr.upper() or 'ERROR' in stdout.upper():
            print(f"    ⚠️  Error inserting batch: {stderr[:100]}")
        else:
            total_inserted += len(batch)
    
    print(f"    ✅ {table_name}: {total_inserted} rows migrated")
    return total_inserted

def main():
    print("🔄 Database Migration via SSH (Python)")
    print("=" * 50)
    print("")
    
    # Step 1: Connect to local database
    print("Step 1: Connecting to local database...")
    try:
        local_conn = get_local_connection()
        print("✅ Local database connected")
    except Exception as e:
        print(f"❌ Failed to connect to local database: {e}")
        return 1
    
    # Step 2: Get table list
    print("\nStep 2: Getting table list...")
    tables = get_table_list(local_conn)
    print(f"✅ Found {len(tables)} tables")
    
    # Step 3: Check NAS database
    print("\nStep 3: Checking NAS database...")
    stdout, stderr = execute_sql_via_ssh("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")
    nas_table_count = int(stdout.strip().split()[0]) if stdout.strip().split()[0].isdigit() else 0
    print(f"  NAS has {nas_table_count} tables")
    
    if nas_table_count == 0:
        print("\n⚠️  NAS database has no tables. Schema migrations may be needed first.")
        print("   Run: ./scripts/migrate_schema_to_nas.sh")
        response = input("   Continue with data migration anyway? (y/N): ")
        if response.lower() != 'y':
            return 1
    
    # Step 4: Migrate data for key tables
    print("\nStep 4: Migrating data...")
    key_tables = ['articles', 'rss_feeds', 'topics', 'story_threads', 'schema_migrations']
    
    total_migrated = 0
    for table in key_tables:
        if table in tables:
            count = migrate_table_data(local_conn, table)
            total_migrated += count
    
    # Step 5: Verify
    print("\nStep 5: Verifying migration...")
    print("")
    for table in key_tables:
        if table in tables:
            local_count = get_record_count(local_conn, table)
            stdout, stderr = execute_sql_via_ssh(f"SELECT COUNT(*) FROM {table};")
            nas_count = int(stdout.strip().split()[0]) if stdout.strip().split()[0].isdigit() else 0
            
            if nas_count == local_count:
                print(f"  ✅ {table}: {local_count} -> {nas_count}")
            else:
                print(f"  ⚠️  {table}: {local_count} -> {nas_count} (differs)")
    
    local_conn.close()
    
    print("\n" + "=" * 50)
    print("✅ Migration complete!")
    print(f"   Total rows migrated: {total_migrated}")
    print("=" * 50)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

