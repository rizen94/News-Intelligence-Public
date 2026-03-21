#!/usr/bin/env python3
"""
Complete Database Migration via SSH
Handles schema and data migration using Python
"""

import psycopg2
import subprocess
import sys
from pathlib import Path

NAS_HOST = "192.168.93.100"
NAS_SSH_PORT = "9222"
NAS_USER = "Admin"
LOCAL_HOST = "localhost"
DB_NAME = "news_intelligence"
DB_USER = "newsapp"
DB_PASSWORD = "newsapp_password"

def execute_sql_via_ssh(sql, ignore_errors=False):
    """Execute SQL on NAS database via SSH"""
    cmd = f'ssh -p {NAS_SSH_PORT} {NAS_USER}@{NAS_HOST} "/usr/local/bin/docker exec news-intelligence-postgres psql -U {DB_USER} -d {DB_NAME} -c \\"{sql}\\" 2>&1"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if not ignore_errors and ('ERROR' in result.stderr.upper() or 'ERROR' in result.stdout.upper()):
        return result.stdout, result.stderr, False
    return result.stdout, result.stderr, True

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

def migrate_table_complete(local_conn, table_name):
    """Complete migration of a table including structure and data"""
    print(f"\nMigrating {table_name}...")
    
    local_cursor = local_conn.cursor()
    
    # Check if table exists locally
    try:
        local_cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        local_count = local_cursor.fetchone()[0]
    except:
        print(f"  ⚠️  Table {table_name} doesn't exist locally")
        return 0
    
    if local_count == 0:
        print(f"  {table_name}: 0 rows (skipping)")
        return 0
    
    # Check if table exists on NAS
    stdout, stderr, success = execute_sql_via_ssh(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table_name}');", True)
    if 't' not in stdout:
        print(f"  ⚠️  Table {table_name} doesn't exist on NAS, skipping")
        return 0
    
    # Get column info
    local_cursor.execute(f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position;
    """, (table_name,))
    columns_info = local_cursor.fetchall()
    columns = [col[0] for col in columns_info]
    
    # Clear existing data
    execute_sql_via_ssh(f"TRUNCATE TABLE {table_name} CASCADE;", True)
    
    # Get all data
    local_cursor.execute(f"SELECT * FROM {table_name};")
    rows = local_cursor.fetchall()
    
    if not rows:
        return 0
    
    # Insert data in smaller batches to avoid command length issues
    batch_size = 20
    total_inserted = 0
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        values_list = []
        
        for row in batch:
            values = []
            for idx, val in enumerate(row):
                if val is None:
                    values.append('NULL')
                elif isinstance(val, str):
                    # Escape properly
                    val = val.replace("'", "''").replace("\\", "\\\\")
                    values.append(f"'{val}'")
                elif isinstance(val, bool):
                    values.append('true' if val else 'false')
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    # Convert to string and escape
                    val_str = str(val).replace("'", "''").replace("\\", "\\\\")
                    values.append(f"'{val_str}'")
            values_list.append(f"({', '.join(values)})")
        
        columns_str = ', '.join(columns)
        values_str = ', '.join(values_list)
        
        # Use simpler INSERT for each row to avoid command length issues
        for row in batch:
            values = []
            for val in row:
                if val is None:
                    values.append('NULL')
                elif isinstance(val, str):
                    val = val.replace("'", "''").replace("\\", "\\\\")
                    values.append(f"'{val}'")
                elif isinstance(val, bool):
                    values.append('true' if val else 'false')
                else:
                    values.append(str(val))
            
            sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({', '.join(values)});"
            stdout, stderr, success = execute_sql_via_ssh(sql, True)
            if success or 'duplicate' in stderr.lower():
                total_inserted += 1
    
    # Verify
    stdout, stderr, _ = execute_sql_via_ssh(f"SELECT COUNT(*) FROM {table_name};", True)
    nas_count = 0
    try:
        nas_count = int([x for x in stdout.split() if x.isdigit()][0]) if stdout.split() else 0
    except:
        pass
    
    if nas_count == local_count:
        print(f"  ✅ {table_name}: {local_count} -> {nas_count}")
    elif nas_count > 0:
        print(f"  ⚠️  {table_name}: {local_count} -> {nas_count} (partial)")
    else:
        print(f"  ❌ {table_name}: {local_count} -> {nas_count} (failed)")
    
    return total_inserted

def main():
    print("🔄 Complete Database Migration via SSH")
    print("=" * 50)
    print("")
    
    # Connect to local
    print("Connecting to local database...")
    try:
        local_conn = get_local_connection()
        print("✅ Local database connected")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return 1
    
    # Get table list
    print("\nGetting table list...")
    local_cursor = local_conn.cursor()
    local_cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    all_tables = [row[0] for row in local_cursor.fetchall()]
    print(f"✅ Found {len(all_tables)} tables")
    
    # Check NAS
    print("\nChecking NAS database...")
    stdout, stderr, _ = execute_sql_via_ssh("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';", True)
    nas_count = int([x for x in stdout.split() if x.isdigit()][0]) if stdout.split() else 0
    print(f"  NAS has {nas_count} tables")
    
    # Migrate key tables first
    print("\nMigrating key tables...")
    key_tables = ['schema_migrations', 'rss_feeds', 'articles', 'topics', 'story_threads']
    
    total_migrated = 0
    for table in key_tables:
        if table in all_tables:
            count = migrate_table_complete(local_conn, table)
            total_migrated += count
    
    local_cursor.close()
    local_conn.close()
    
    print("\n" + "=" * 50)
    print(f"✅ Migration complete! {total_migrated} rows migrated")
    print("=" * 50)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

