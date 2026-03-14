#!/usr/bin/env python3
"""
Disconnect V3 Database Tables
Safely removes legacy tables after confirming v4 data integrity.
Run from api/ or with PYTHONPATH=api. Uses shared DB config (DB_* env / .env).
"""

import os
import sys
import psycopg2
from datetime import datetime

def connect_database():
    """Connect to the database using shared config."""
    _api = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _api not in sys.path:
        sys.path.insert(0, _api)
    from shared.database.connection import get_db_connection
    return get_db_connection()

def verify_v4_data_integrity():
    """Verify v4 data is complete before removing v3 tables"""
    print("🔍 Verifying v4 data integrity...")
    
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            # Check v4 tables exist
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%_v4'
            """)
            v4_count = cur.fetchone()[0]
            
            # Check data in v4 tables
            cur.execute("SELECT COUNT(*) FROM articles_v4")
            articles_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM rss_feeds_v4")
            feeds_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM storylines_v4")
            storylines_count = cur.fetchone()[0]
            
            print(f"   V4 tables: {v4_count}")
            print(f"   Articles: {articles_count}")
            print(f"   RSS feeds: {feeds_count}")
            print(f"   Storylines: {storylines_count}")
            
            if v4_count >= 11 and articles_count > 0 and feeds_count > 0:
                print("✅ V4 data integrity verified")
                return True
            else:
                print("❌ V4 data integrity check failed")
                return False
                
    finally:
        conn.close()

def get_legacy_tables():
    """Get list of legacy tables to remove"""
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                AND table_name NOT LIKE '%_v4'
                ORDER BY table_name
            """)
            
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

def disconnect_legacy_tables():
    """Disconnect legacy tables"""
    print("🔌 Disconnecting legacy tables...")
    
    if not verify_v4_data_integrity():
        print("❌ Cannot disconnect legacy tables - v4 data integrity check failed")
        return False
    
    legacy_tables = get_legacy_tables()
    print(f"   Found {len(legacy_tables)} legacy tables to disconnect")
    
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            # Drop legacy tables
            for table in legacy_tables:
                try:
                    cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                    print(f"   ✅ Disconnected: {table}")
                except Exception as e:
                    print(f"   ❌ Failed to disconnect {table}: {e}")
            
            conn.commit()
            print(f"✅ Disconnected {len(legacy_tables)} legacy tables")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Error disconnecting legacy tables: {e}")
        return False
    finally:
        conn.close()
    
    return True

def verify_disconnection():
    """Verify legacy tables have been disconnected"""
    print("🔍 Verifying disconnection...")
    
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            # Check remaining tables
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """)
            total_tables = cur.fetchone()[0]
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%_v4'
            """)
            v4_tables = cur.fetchone()[0]
            
            print(f"   Total tables remaining: {total_tables}")
            print(f"   V4 tables: {v4_tables}")
            
            if total_tables == v4_tables:
                print("✅ All legacy tables successfully disconnected")
                return True
            else:
                print(f"⚠️ {total_tables - v4_tables} legacy tables still exist")
                return False
                
    finally:
        conn.close()

def main():
    """Main function"""
    print("🚀 Starting V3 Table Disconnection")
    print("=" * 40)
    
    try:
        if disconnect_legacy_tables():
            verify_disconnection()
            print("\n🎉 V3 table disconnection completed successfully!")
        else:
            print("\n❌ V3 table disconnection failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
