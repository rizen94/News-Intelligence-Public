#!/usr/bin/env python3
"""
Test database connection and verify tables exist
"""

import psycopg2
import os

# Database configuration
DATABASE_URL = "postgresql://newsapp:newsapp_password@localhost:5432/news_intelligence"

try:
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if articles table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'articles'
        );
    """)
    
    articles_exists = cursor.fetchone()[0]
    print(f"Articles table exists: {articles_exists}")
    
    if articles_exists:
        # Count articles
        cursor.execute("SELECT COUNT(*) FROM articles;")
        count = cursor.fetchone()[0]
        print(f"Number of articles: {count}")
        
        # Show sample articles
        cursor.execute("SELECT id, title, source FROM articles LIMIT 3;")
        articles = cursor.fetchall()
        print("Sample articles:")
        for article in articles:
            print(f"  {article[0]}: {article[1]} ({article[2]})")
    
    # Check other tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    print(f"\nAll tables: {[table[0] for table in tables]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Database connection error: {e}")
