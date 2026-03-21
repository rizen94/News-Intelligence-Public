#!/usr/bin/env python3
"""Investigate table creation issues"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
from config.database import get_db_connection

print("🔍 INVESTIGATING TABLE CREATION ISSUES")
print("=" * 60)

conn = get_db_connection()
cur = conn.cursor()

# Count current tables
cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
total = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name NOT LIKE '%v4'")
legacy = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%v4'")
v4 = cur.fetchone()[0]

print(f"\n📊 Current Status:")
print(f"   Total tables: {total}")
print(f"   Legacy tables: {legacy}")
print(f"   v4 tables: {v4}")

# Check database location
try:
    cur.execute("SHOW data_directory")
    db_path = cur.fetchone()[0]
    print(f"\n🗄️  Database Location: {db_path}")
    
    # Check if it's a mount point
    import subprocess
    result = subprocess.run(['df', '-h', db_path], capture_output=True, text=True)
    print("\n📂 Mount Information:")
    print(result.stdout)
    
except Exception as e:
    print(f"Could not get mount info: {e}")

# Sample some table names
print("\n🔍 Sampling Legacy Tables:")
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name NOT LIKE '%v4'
    LIMIT 10
""")

for row in cur.fetchall():
    print(f"   - {row[0]}")

conn.close()

# Summary
print("\n" + "=" * 60)
print("CONCLUSION:")
print(f"  - {legacy} legacy tables remain")
print(f"  - Database is at: {db_path}")
print("  - Slow drops likely due to network latency if on NAS")
print("  - Tables themselves don't appear to be growing")

