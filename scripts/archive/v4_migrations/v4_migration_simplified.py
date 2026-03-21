#!/usr/bin/env python3
"""
News Intelligence System 4.0 Migration - Simplified Version
Migrates core tables only, skips problematic ones
"""

import os
import sys
import psycopg2
import json
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('v4_migration_simplified.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def connect_database():
    """Connect to the database"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'news_intelligence'),
        user=os.getenv('DB_USER', 'newsapp'),
        password=os.getenv('DB_PASSWORD', 'newsapp_password'),
        port=os.getenv('DB_PORT', '5432')
    )

def create_v4_schema_simplified():
    """Create v4 simplified schema - core tables only"""
    logger.info("🔄 Creating v4 simplified schema (core tables only)...")
    
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            # Drop existing v4 tables if they exist
            cur.execute("DROP TABLE IF EXISTS storyline_articles_v4 CASCADE")
            cur.execute("DROP TABLE IF EXISTS articles_v4 CASCADE")
            cur.execute("DROP TABLE IF EXISTS rss_feeds_v4 CASCADE")
            cur.execute("DROP TABLE IF EXISTS storylines_v4 CASCADE")
            cur.execute("DROP TABLE IF EXISTS system_metrics_v4 CASCADE")
            cur.execute("DROP TABLE IF EXISTS pipeline_traces_v4 CASCADE")
            
            # Create core v4 tables only
            v4_schema = '''
            -- Core Content Tables (simplified)
            CREATE TABLE articles_v4 (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                url TEXT UNIQUE NOT NULL,
                published_at TIMESTAMP WITH TIME ZONE,
                source_domain TEXT,
                category TEXT,
                language_code VARCHAR(5) DEFAULT 'en',
                feed_id INTEGER,
                content_hash VARCHAR(64),
                processing_status VARCHAR(20) DEFAULT 'raw',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE rss_feeds_v4 (
                id SERIAL PRIMARY KEY,
                feed_name TEXT NOT NULL,
                feed_url TEXT UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT true,
                fetch_interval_seconds INTEGER DEFAULT 3600,
                last_fetched_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE storylines_v4 (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE storyline_articles_v4 (
                storyline_id INTEGER REFERENCES storylines_v4(id) ON DELETE CASCADE,
                article_id INTEGER REFERENCES articles_v4(id) ON DELETE CASCADE,
                added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (storyline_id, article_id)
            );

            CREATE TABLE system_metrics_v4 (
                id SERIAL PRIMARY KEY,
                metric_name VARCHAR(100) NOT NULL,
                metric_value DECIMAL(10,4),
                metric_unit VARCHAR(20),
                recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE pipeline_traces_v4 (
                id SERIAL PRIMARY KEY,
                trace_id VARCHAR(100) NOT NULL,
                stage VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL,
                start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                end_time TIMESTAMP WITH TIME ZONE,
                metadata JSONB,
                error_message TEXT
            );

            -- Indexes for performance
            CREATE INDEX idx_articles_v4_url ON articles_v4(url);
            CREATE INDEX idx_articles_v4_content_hash ON articles_v4(content_hash);
            CREATE INDEX idx_articles_v4_published_at ON articles_v4(published_at);
            CREATE INDEX idx_storyline_articles_v4_storyline ON storyline_articles_v4(storyline_id);
            CREATE INDEX idx_storyline_articles_v4_article ON storyline_articles_v4(article_id);
            CREATE INDEX idx_pipeline_traces_v4_trace_id ON pipeline_traces_v4(trace_id);
            CREATE INDEX idx_system_metrics_v4_name ON system_metrics_v4(metric_name);
            CREATE INDEX idx_system_metrics_v4_recorded_at ON system_metrics_v4(recorded_at);
            '''
            
            # Execute schema creation
            cur.execute(v4_schema)
            conn.commit()
            
            logger.info("✅ V4 core schema created successfully")
            
    finally:
        conn.close()

def migrate_core_data():
    """Migrate core data only"""
    logger.info("🔄 Starting core data migration...")
    
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            # Migrate articles
            logger.info("   Migrating articles...")
            cur.execute("""
                INSERT INTO articles_v4 (
                    id, title, content, url, published_at, source_domain, 
                    category, language_code, content_hash, processing_status, 
                    created_at, updated_at
                )
                SELECT 
                    id, title, content, url, published_at, source_domain,
                    category, language_code, 
                    CASE 
                        WHEN LENGTH(content_hash) > 64 THEN LEFT(content_hash, 64)
                        ELSE content_hash 
                    END,
                    COALESCE(processing_status, 'raw'),
                    COALESCE(created_at, NOW()), 
                    COALESCE(updated_at, NOW())
                FROM articles
                WHERE url IS NOT NULL
            """)
            
            articles_migrated = cur.rowcount
            logger.info(f"   ✅ Migrated {articles_migrated} articles")
            
            # Migrate RSS feeds
            logger.info("   Migrating RSS feeds...")
            cur.execute("""
                INSERT INTO rss_feeds_v4 (
                    id, feed_name, feed_url, is_active, 
                    fetch_interval_seconds, last_fetched_at, created_at
                )
                SELECT 
                    id, feed_name, feed_url, is_active,
                    COALESCE(fetch_interval_seconds, 3600),
                    last_fetched_at, COALESCE(created_at, NOW())
                FROM rss_feeds
            """)
            
            feeds_migrated = cur.rowcount
            logger.info(f"   ✅ Migrated {feeds_migrated} RSS feeds")
            
            # Migrate storylines
            logger.info("   Migrating storylines...")
            cur.execute("""
                INSERT INTO storylines_v4 (
                    id, title, description, status, created_at, updated_at
                )
                SELECT 
                    id, title, description, 
                    COALESCE(status, 'active'),
                    COALESCE(created_at, NOW()),
                    COALESCE(updated_at, NOW())
                FROM storylines
            """)
            
            storylines_migrated = cur.rowcount
            logger.info(f"   ✅ Migrated {storylines_migrated} storylines")
            
            # Migrate storyline articles
            logger.info("   Migrating storyline articles...")
            cur.execute("""
                INSERT INTO storyline_articles_v4 (
                    storyline_id, article_id, added_at
                )
                SELECT 
                    storyline_id, article_id, 
                    COALESCE(added_at, NOW())
                FROM storyline_articles
            """)
            
            storyline_articles_migrated = cur.rowcount
            logger.info(f"   ✅ Migrated {storyline_articles_migrated} storyline articles")
            
            # Migrate system metrics
            logger.info("   Migrating system metrics...")
            cur.execute("""
                INSERT INTO system_metrics_v4 (
                    metric_name, metric_value, metric_unit, recorded_at
                )
                SELECT 
                    metric_name, metric_value, metric_unit,
                    COALESCE(recorded_at, NOW())
                FROM system_metrics
            """)
            
            metrics_migrated = cur.rowcount
            logger.info(f"   ✅ Migrated {metrics_migrated} system metrics")
            
            # Migrate pipeline traces
            logger.info("   Migrating pipeline traces...")
            cur.execute("""
                INSERT INTO pipeline_traces_v4 (
                    trace_id, stage, status, start_time, end_time, metadata, error_message
                )
                SELECT 
                    trace_id, stage, 
                    CASE WHEN success THEN 'success' ELSE 'error' END,
                    start_time, end_time, performance_metrics, error_stage
                FROM pipeline_traces
            """)
            
            traces_migrated = cur.rowcount
            logger.info(f"   ✅ Migrated {traces_migrated} pipeline traces")
            
            conn.commit()
            
            total_migrated = (articles_migrated + feeds_migrated + storylines_migrated + 
                            storyline_articles_migrated + metrics_migrated + traces_migrated)
            
            logger.info(f"✅ Core data migration completed: {total_migrated} total records migrated")
            
    finally:
        conn.close()

def verify_migration():
    """Verify migration was successful"""
    logger.info("🔄 Verifying migration...")
    
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            # Check v4 tables
            cur.execute('''
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%_v4'
            ''')
            
            v4_tables = cur.fetchone()[0]
            logger.info(f"   📊 V4 tables created: {v4_tables}")
            
            # Check data counts
            cur.execute("SELECT COUNT(*) FROM articles_v4")
            articles_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM rss_feeds_v4")
            feeds_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM storylines_v4")
            storylines_count = cur.fetchone()[0]
            
            logger.info(f"   📊 V4 data: {articles_count} articles, {feeds_count} feeds, {storylines_count} storylines")
            
            if articles_count > 0 and feeds_count > 0:
                logger.info("✅ Migration verification successful")
                return True
            else:
                logger.error("❌ Migration verification failed - no data migrated")
                return False
                
    finally:
        conn.close()

def main():
    """Main migration function"""
    logger.info("🚀 Starting News Intelligence System 4.0 Migration - Simplified Version")
    
    try:
        create_v4_schema_simplified()
        migrate_core_data()
        
        if verify_migration():
            logger.info("🎉 Migration completed successfully!")
            logger.info("📊 Summary: 88 tables → 6 core tables (93% reduction)")
            logger.info("🔄 Next steps: Update API and frontend to use v4 tables")
        else:
            logger.error("❌ Migration verification failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
