#!/usr/bin/env python3
"""Non-interactive script to rename all legacy tables - FAST!"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
from config.database import get_db_connection

print("🗑️  RENAMING LEGACY TABLES TO 'archived_' PREFIX")
print("=" * 60)

conn = get_db_connection()
cur = conn.cursor()

# Get all non-v4 tables that aren't already archived
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name NOT LIKE '%v4'
    AND table_name NOT LIKE 'archived_%'
""")

tables = [row[0] for row in cur.fetchall()]
print(f"\nFound {len(tables)} tables to rename\n")

if not tables:
    print("✅ No tables to rename!")
    sys.exit(0)

renamed = 0
failed = 0

for i, table in enumerate(tables):
    try:
        new_name = f"archived_{table}"
        cur.execute(f'ALTER TABLE {table} RENAME TO {new_name}')
        conn.commit()
        renamed += 1
        
        if (i + 1) % 20 == 0 or (i + 1) == len(tables):
            print(f"  Renamed: {i + 1}/{len(tables)}")
            
    except Exception as e:
        print(f"  ⚠️  Error renaming {table}: {e}")
        failed += 1
        conn.rollback()

# Verify
cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name NOT LIKE '%v4' AND table_name NOT LIKE 'archived_%'")
remaining = cur.fetchone()[0]

print(f"\n✅ Results:")
print(f"   Renamed: {renamed}")
print(f"   Failed: {failed}")
print(f"   Remaining non-archived tables: {remaining}")

conn.close()

if remaining == 0:
    print("\n🎉 SUCCESS! All legacy tables renamed to archived_ prefix!")
    print("   System is now using only v4 tables")
    sys.exit(0)
else:
    print(f"\n⚠️  {remaining} tables still need renaming")
    sys.exit(1)

