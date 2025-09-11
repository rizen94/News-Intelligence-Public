#!/usr/bin/env python3
"""
Debug script to test database connection issues
"""

import sys
import os
sys.path.append('api')

from api.config.database import get_db, get_db_connection
from sqlalchemy.orm import Session
from sqlalchemy import text

def test_get_db():
    """Test what get_db() returns"""
    print("Testing get_db()...")
    try:
        db_gen = get_db()
        print(f"get_db() returns: {type(db_gen)}")
        print(f"Has __next__: {hasattr(db_gen, '__next__')}")
        print(f"Has execute: {hasattr(db_gen, 'execute')}")
        
        # Try to get the actual session
        db = next(db_gen)
        print(f"next(db_gen) returns: {type(db)}")
        print(f"Has execute: {hasattr(db, 'execute')}")
        
        # Try to execute a query
        result = db.execute(text("SELECT COUNT(*) FROM articles")).scalar()
        print(f"Query result: {result}")
        
        db.close()
        print("✅ get_db() works correctly")
        
    except Exception as e:
        print(f"❌ Error with get_db(): {e}")

def test_get_db_connection():
    """Test what get_db_connection() returns"""
    print("\nTesting get_db_connection()...")
    try:
        conn = get_db_connection()
        print(f"get_db_connection() returns: {type(conn)}")
        print(f"Has execute: {hasattr(conn, 'execute')}")
        
        # Try to execute a query
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM articles")
            result = cur.fetchone()[0]
            print(f"Query result: {result}")
        
        conn.close()
        print("✅ get_db_connection() works correctly")
        
    except Exception as e:
        print(f"❌ Error with get_db_connection(): {e}")

if __name__ == "__main__":
    test_get_db()
    test_get_db_connection()
