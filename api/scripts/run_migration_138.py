#!/usr/bin/env python3
"""Run migration 138 (article entities) using project DB config."""

import os
import sys

# Add api to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from shared.database.connection import get_db_connection, get_db_config
    
    config = get_db_config()
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "database", "migrations", "138_article_entities_full_system.sql"
    )
    
    if not os.path.exists(migration_path):
        print(f"ERROR: Migration file not found: {migration_path}")
        sys.exit(1)
    
    with open(migration_path) as f:
        sql = f.read()
    
    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database")
        sys.exit(1)
    
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(sql)
        conn.commit()
        print("✅ Migration 138 applied successfully")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
