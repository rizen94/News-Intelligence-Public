#!/usr/bin/env python3
"""
Database Migration with Progress Bar
Migrates data from local to NAS database with visual progress tracking
"""

import psycopg2
import sys
import time
from datetime import datetime

LOCAL_HOST = "localhost"
LOCAL_PORT = 5432
NAS_HOST = "localhost"  # Using SSH tunnel
NAS_PORT = 5433  # SSH tunnel port (forwards to NAS:5432)
DB_NAME = "news_intelligence"
DB_USER = "newsapp"
DB_PASSWORD = "newsapp_password"

def print_progress_bar(current, total, table_name="", bar_length=50):
    """Print a progress bar"""
    if total == 0:
        return
    
    percent = float(current) / float(total) * 100
    filled = int(bar_length * current / total)
    bar = '█' * filled + '░' * (bar_length - filled)
    
    sys.stdout.write(f'\r  {table_name:<20} [{bar}] {current:>5}/{total:<5} ({percent:>5.1f}%)')
    sys.stdout.flush()
    
    if current == total:
        sys.stdout.write('\n')

def migrate_table_with_progress(local_conn, nas_conn, table_name):
    """Migrate a table with progress tracking"""
    local_cursor = local_conn.cursor()
    nas_cursor = nas_conn.cursor()
    
    try:
        # Get local count
        local_cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        local_count = local_cursor.fetchone()[0]
        
        if local_count == 0:
            print(f"  {table_name:<20} [{'░' * 50}]     0/0     (0.0%) - No data")
            return 0, 0
        
        # Get column info from both databases
        local_cursor.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position;
        """, (table_name,))
        local_cols = {row[0]: row[1] for row in local_cursor.fetchall()}
        
        nas_cursor.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position;
        """, (table_name,))
        nas_cols = {row[0]: row[1] for row in nas_cursor.fetchall()}
        
        # Find common columns (columns that exist in both)
        common_columns = sorted(set(local_cols.keys()) & set(nas_cols.keys()))
        
        if not common_columns:
            print(f"  ⚠️  No common columns between local and NAS for {table_name}")
            return 0, 0
        
        # Column name mappings (for renamed columns)
        column_mapping = {
            'feed_id': 'rss_feed_id',  # articles table
        }
        
        # Use mapped column names for NAS, original for local
        local_columns = []
        nas_columns = []
        for col in common_columns:
            local_columns.append(col)
            nas_columns.append(column_mapping.get(col, col))
        
        # Verify mapped columns exist in NAS
        final_columns = []
        for local_col, nas_col in zip(local_columns, nas_columns):
            if nas_col in nas_cols:
                final_columns.append((local_col, nas_col))
            else:
                print(f"  ⚠️  Skipping {local_col} (mapped to {nas_col} which doesn't exist in NAS)")
        
        if not final_columns:
            print(f"  ⚠️  No valid columns to migrate for {table_name}")
            return 0, 0
        
        local_col_names = [col[0] for col in final_columns]
        nas_col_names = [col[1] for col in final_columns]
        col_info = {col[0]: local_cols[col[0]] for col in final_columns}
        columns = local_col_names
        
        # Clear NAS table
        nas_cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
        nas_conn.commit()
        
        # Get all data (only common columns)
        print(f"\n  Fetching data from {table_name} (migrating {len(columns)} common columns)...")
        columns_str = ', '.join(columns)
        local_cursor.execute(f"SELECT {columns_str} FROM {table_name};")
        rows = local_cursor.fetchall()
        
        print(f"  Migrating {len(rows)} rows...")
        
        # Insert in batches with progress using parameterized queries
        batch_size = 100
        total_inserted = 0
        errors = 0
        
        # Handle required columns that don't exist in local
        # Add default values for required NAS columns
        required_nas_columns = {}
        if table_name == 'rss_feeds':
            # category is required but doesn't exist in local
            if 'category' in nas_cols and 'category' not in local_cols:
                required_nas_columns['category'] = 'general'  # Default category
        elif table_name == 'articles':
            # Map processing_status values
            # Local uses 'raw', NAS requires: pending, ingesting, analyzing, summarizing, clustering, completed, failed, archived
            pass  # Will handle in row transformation
        
        # Build final column list including required NAS columns
        final_nas_cols = nas_col_names.copy()
        final_local_cols = local_col_names.copy()
        final_values_template = [None] * len(local_col_names)
        
        for req_col, default_val in required_nas_columns.items():
            if req_col not in final_nas_cols:
                final_nas_cols.append(req_col)
                final_values_template.append(default_val)
        
        # Use NAS column names for INSERT
        nas_columns_str = ', '.join(final_nas_cols)
        placeholders = ', '.join(['%s'] * len(final_nas_cols))
        insert_query = f"INSERT INTO {table_name} ({nas_columns_str}) VALUES ({placeholders})"
        
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            
            # Transform rows to include required columns and map values
            transformed_batch = []
            for row in batch:
                row_list = list(row)
                
                # Add required NAS column values
                for req_col, default_val in required_nas_columns.items():
                    if req_col not in nas_col_names:  # Only add if not already in row
                        row_list.append(default_val)
                
                # Map processing_status for articles
                if table_name == 'articles' and 'processing_status' in local_col_names:
                    status_idx = local_col_names.index('processing_status')
                    if status_idx < len(row_list):
                        status = row_list[status_idx]
                        # Map 'raw' to 'pending' (valid NAS value)
                        if status == 'raw':
                            row_list[status_idx] = 'pending'
                        elif status not in ['pending', 'ingesting', 'analyzing', 'summarizing', 'clustering', 'completed', 'failed', 'archived']:
                            row_list[status_idx] = 'pending'  # Default to pending for unknown values
                
                transformed_batch.append(tuple(row_list))
            
            try:
                # Use executemany for batch insert (psycopg2 handles all type conversions)
                nas_cursor.executemany(insert_query, transformed_batch)
                nas_conn.commit()
                total_inserted += len(transformed_batch)
            except Exception as e:
                nas_conn.rollback()
                print(f"\n    ⚠️  Batch insert failed: {str(e)[:100]}")
                # Try inserting one by one to identify problematic rows
                for row in transformed_batch:
                    try:
                        nas_cursor.execute(insert_query, row)
                        nas_conn.commit()
                        total_inserted += 1
                    except Exception as row_e:
                        errors += 1
                        nas_conn.rollback()
                        if errors <= 3:  # Only print first few errors
                            print(f"\n      Row error: {str(row_e)[:80]}")
            
            # Update progress
            current = min(i + batch_size, len(rows))
            print_progress_bar(current, len(rows), table_name)
        
        # Verify
        nas_cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        nas_count = nas_cursor.fetchone()[0]
        
        return nas_count, errors
        
    except Exception as e:
        print(f"\n    ❌ Error: {str(e)[:80]}")
        return 0, 0

def main():
    print("🔄 Database Migration with Progress Tracking")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    # Connect to databases
    print("Step 1: Connecting to databases...")
    try:
        local_conn = psycopg2.connect(host=LOCAL_HOST, port=LOCAL_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        # Verify it's actually local
        cursor = local_conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        if 'aarch64' in version:
            print(f"  ⚠️  WARNING: Port {LOCAL_PORT} connected to NAS, not local!")
            print(f"     Version: {version[:60]}")
        else:
            print(f"  ✅ Local database connected (x86_64)")
    except Exception as e:
        print(f"  ❌ Local database failed: {e}")
        return 1
    
    try:
        nas_conn = psycopg2.connect(host=NAS_HOST, port=NAS_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, connect_timeout=10)
        # Verify it's actually NAS
        cursor = nas_conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        if 'aarch64' in version:
            print(f"  ✅ NAS database connected (ARM - through SSH tunnel on port {NAS_PORT})")
        else:
            print(f"  ⚠️  WARNING: Port {NAS_PORT} may not be NAS!")
            print(f"     Version: {version[:60]}")
    except Exception as e:
        print(f"  ❌ NAS database failed: {e}")
        print(f"     Make sure SSH tunnel is running: ssh -L {NAS_PORT}:localhost:5432 -N -f -p 9222 Admin@192.168.93.100")
        return 1
    
    print("")
    
    # Get table information
    print("Step 2: Analyzing databases...")
    local_cursor = local_conn.cursor()
    local_cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    all_tables = [row[0] for row in local_cursor.fetchall()]
    
    nas_cursor = nas_conn.cursor()
    nas_cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    nas_tables = [row[0] for row in nas_cursor.fetchall()]
    
    print(f"  Local database: {len(all_tables)} tables")
    print(f"  NAS database: {len(nas_tables)} tables")
    print("")
    
    # Migrate key tables
    print("Step 3: Migrating data...")
    print("")
    
    key_tables = ['schema_migrations', 'rss_feeds', 'articles', 'topics', 'story_threads']
    
    migration_results = {}
    total_rows = 0
    total_migrated = 0
    total_errors = 0
    
    for table in key_tables:
        if table not in all_tables:
            print(f"  ⚠️  {table:<20} Not in local database")
            continue
        
        if table not in nas_tables:
            print(f"  ⚠️  {table:<20} Not in NAS database, skipping")
            continue
        
        nas_count, errors = migrate_table_with_progress(local_conn, nas_conn, table)
        
        # Get local count for comparison
        local_cursor.execute(f"SELECT COUNT(*) FROM {table};")
        local_count = local_cursor.fetchone()[0]
        
        migration_results[table] = {
            'local': local_count,
            'nas': nas_count,
            'errors': errors
        }
        
        total_rows += local_count
        total_migrated += nas_count
        total_errors += errors
        
        if nas_count == local_count:
            print(f"    ✅ {table}: {local_count} rows migrated successfully")
        elif nas_count > 0:
            print(f"    ⚠️  {table}: {nas_count}/{local_count} rows migrated ({errors} errors)")
        else:
            print(f"    ❌ {table}: Migration failed")
        print("")
    
    local_cursor.close()
    local_conn.close()
    nas_cursor.close()
    nas_conn.close()
    
    # Summary
    print("=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"{'Table':<20} {'Local':<10} {'NAS':<10} {'Status'}")
    print("-" * 70)
    
    for table, results in migration_results.items():
        local = results['local']
        nas = results['nas']
        errors = results['errors']
        
        if nas == local:
            status = "✅ Complete"
        elif nas > 0:
            status = f"⚠️  Partial ({errors} errors)"
        else:
            status = "❌ Failed"
        
        print(f"{table:<20} {local:<10} {nas:<10} {status}")
    
    print("-" * 70)
    print(f"{'TOTAL':<20} {total_rows:<10} {total_migrated:<10} {total_errors} errors")
    print("=" * 70)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    if total_migrated == total_rows:
        print("✅ Migration 100% complete!")
        return 0
    elif total_migrated > 0:
        print(f"⚠️  Migration {total_migrated}/{total_rows} rows ({total_migrated/total_rows*100:.1f}%)")
        return 0
    else:
        print("❌ Migration failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

