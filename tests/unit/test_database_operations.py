"""
Unit tests for database operations
Tests database connectivity and basic operations
"""

import pytest
import psycopg2
from tests.conftest import TestConfig, TestUtils

class TestDatabaseOperations:
    """Test database operations"""
    
    def test_database_connection(self, db_connection):
        """Test database connection"""
        assert db_connection is not None
        assert not db_connection.closed
    
    def test_basic_query(self, db_connection):
        """Test basic database query"""
        with db_connection.cursor() as cur:
            cur.execute("SELECT 1 as test")
            result = cur.fetchone()
            assert result[0] == 1
    
    def test_tables_exist(self, db_connection):
        """Test that all required tables exist"""
        required_tables = [
            "articles", "storylines", "storyline_articles", "rss_feeds",
            "timeline_events", "topic_clusters", "article_topic_clusters"
        ]
        
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            existing_tables = [row[0] for row in cur.fetchall()]
            
            for table in required_tables:
                assert table in existing_tables, f"Table {table} does not exist"
    
    def test_articles_table_structure(self, db_connection):
        """Test articles table structure"""
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'articles'
            """)
            columns = {row[0]: row[1] for row in cur.fetchall()}
            
            required_columns = ["id", "title", "url", "content", "source_domain", "published_at"]
            for column in required_columns:
                assert column in columns, f"Column {column} missing from articles table"
    
    def test_storylines_table_structure(self, db_connection):
        """Test storylines table structure"""
        with db_connection.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'storylines'
            """)
            columns = {row[0]: row[1] for row in cur.fetchall()}
            
            required_columns = ["id", "title", "description", "processing_status"]
            for column in required_columns:
                assert column in columns, f"Column {column} missing from storylines table"
    
    def test_data_integrity_constraints(self, db_connection):
        """Test data integrity constraints"""
        with db_connection.cursor() as cur:
            # Test foreign key constraints
            cur.execute("""
                SELECT constraint_name, constraint_type 
                FROM information_schema.table_constraints 
                WHERE table_name IN ('storyline_articles', 'timeline_events')
            """)
            constraints = cur.fetchall()
            
            # Should have foreign key constraints
            fk_constraints = [c for c in constraints if c[1] == 'FOREIGN KEY']
            assert len(fk_constraints) > 0, "Missing foreign key constraints"
