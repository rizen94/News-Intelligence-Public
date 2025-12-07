#!/usr/bin/env python3
"""
Check for duplicate data between v4 tables and legacy tables
Ensures no data loss before cleanup
"""

import sys
from config.database import get_db_connection

def check_table_exists(cur, table_name):
    """Check if a table exists"""
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        )
    """, (table_name,))
    return cur.fetchone()[0]

def compare_table_data(cur, v4_table, legacy_table):
    """Compare data between v4 and legacy tables"""
    if not check_table_exists(cur, legacy_table):
        print(f"   ➖ Legacy table '{legacy_table}' doesn't exist")
        return True
    
    if not check_table_exists(cur, v4_table):
        print(f"   ⚠️  V4 table '{v4_table}' doesn't exist!")
        return False
    
    # Count rows in both tables
    try:
        cur.execute(f"SELECT COUNT(*) FROM {v4_table}")
        v4_count = cur.fetchone()[0]
        
        cur.execute(f"SELECT COUNT(*) FROM {legacy_table}")
        legacy_count = cur.fetchone()[0]
        
        print(f"   {legacy_table:<30} -> {v4_table:<30}")
        print(f"   {'Legacy:':<30} {legacy_count:>6} rows")
        print(f"   {'V4:':<30} {v4_count:>6} rows")
        
        # Check if v4 has more or equal rows
        if v4_count >= legacy_count:
            print(f"   ✅ Data appears migrated")
            return True
        else:
            print(f"   ⚠️  V4 has fewer rows ({v4_count} < {legacy_count})")
            print(f"   ❌ Possible data loss detected!")
            return False
            
    except Exception as e:
        print(f"   ❌ Error comparing tables: {e}")
        return False

def main():
    print("🔍 CHECKING FOR DUPLICATES AND DATA LOSS")
    print("=" * 60)
    print("")
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        print("Comparing v4 tables with legacy tables:")
        print("-" * 60)
        
        checks_passed = True
        
        # Compare articles
        print("\n1. Articles:")
        if not compare_table_data(cur, "articles_v4", "articles"):
            checks_passed = False
        
        # Compare RSS feeds
        print("\n2. RSS Feeds:")
        if not compare_table_data(cur, "rss_feeds_v4", "rss_feeds"):
            checks_passed = False
        
        # Compare storylines
        print("\n3. Storylines:")
        if not compare_table_data(cur, "storylines_v4", "storylines"):
            checks_passed = False
        
        # Compare storyline articles
        print("\n4. Storyline Articles:")
        if not compare_table_data(cur, "storyline_articles_v4", "storyline_articles"):
            checks_passed = False
        
        # Summary
        print("\n" + "=" * 60)
        if checks_passed:
            print("✅ All data checks passed!")
            print("   It's safe to proceed with cleanup.")
            conn.close()
            sys.exit(0)
        else:
            print("❌ Data loss detected!")
            print("   DO NOT proceed with cleanup until data is migrated.")
            conn.close()
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.close()
        sys.exit(1)

if __name__ == "__main__":
    main()

