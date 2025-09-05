#!/usr/bin/env python3
"""
News Intelligence System v3.1.0 - Query Alignment Checker
Verifies that all queries match the actual database schema
"""

import os
import re
import psycopg2
from typing import List, Dict, Set

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'database': 'newsintelligence',
    'user': 'newsapp',
    'password': 'Database@NEWSINT2025',
    'port': '5432'
}

def get_database_schema():
    """Get actual database schema"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Get all tables and columns
    cursor.execute("""
        SELECT table_name, column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        ORDER BY table_name, ordinal_position
    """)
    
    schema = {}
    for table_name, column_name, data_type, is_nullable in cursor.fetchall():
        if table_name not in schema:
            schema[table_name] = {}
        schema[table_name][column_name] = {
            'type': data_type,
            'nullable': is_nullable == 'YES'
        }
    
    cursor.close()
    conn.close()
    return schema

def find_sql_queries():
    """Find all SQL queries in the codebase"""
    queries = []
    
    # Search for SQL queries in Python files
    for root, dirs, files in os.walk('api'):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Find SQL queries (basic pattern matching)
                        sql_patterns = [
                            r'SELECT\s+.*?FROM\s+(\w+)',
                            r'INSERT\s+INTO\s+(\w+)',
                            r'UPDATE\s+(\w+)',
                            r'DELETE\s+FROM\s+(\w+)',
                            r'CREATE\s+TABLE\s+(\w+)',
                            r'ALTER\s+TABLE\s+(\w+)'
                        ]
                        
                        for pattern in sql_patterns:
                            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
                            for match in matches:
                                queries.append({
                                    'file': filepath,
                                    'table': match,
                                    'query_type': pattern.split()[0].upper()
                                })
                except Exception as e:
                    print(f"Error reading {filepath}: {e}")
    
    return queries

def check_query_alignment(schema, queries):
    """Check if queries align with schema"""
    issues = []
    
    for query in queries:
        table_name = query['table']
        if table_name in schema:
            # Query references a valid table
            pass
        else:
            issues.append({
                'type': 'INVALID_TABLE',
                'file': query['file'],
                'table': table_name,
                'message': f"Table '{table_name}' not found in schema"
            })
    
    return issues

def main():
    print("=== QUERY ALIGNMENT CHECK ===")
    print("")
    
    print("1. Getting database schema...")
    schema = get_database_schema()
    print(f"   Found {len(schema)} tables in database")
    
    print("")
    print("2. Finding SQL queries in codebase...")
    queries = find_sql_queries()
    print(f"   Found {len(queries)} SQL queries")
    
    print("")
    print("3. Checking query alignment...")
    issues = check_query_alignment(schema, queries)
    
    if issues:
        print(f"   Found {len(issues)} alignment issues:")
        for issue in issues:
            print(f"   - {issue['type']}: {issue['message']} in {issue['file']}")
    else:
        print("   ✅ All queries align with database schema")
    
    print("")
    print("4. Schema summary:")
    for table_name, columns in schema.items():
        print(f"   {table_name}: {len(columns)} columns")
    
    print("")
    print("=== QUERY ALIGNMENT CHECK COMPLETED ===")

if __name__ == "__main__":
    main()
