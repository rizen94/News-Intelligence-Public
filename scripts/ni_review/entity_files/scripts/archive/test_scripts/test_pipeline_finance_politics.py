#!/usr/bin/env python3
"""
Test Pipeline Run for Finance and Politics Domains
Runs RSS collection and processing, monitoring for errors
"""

import sys
import os
import logging
import traceback
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'api'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Track errors
errors = []
warnings = []

def log_error(step, error, exc_info=False):
    """Log an error and track it"""
    error_msg = f"{step}: {error}"
    logger.error(error_msg)
    if exc_info:
        logger.error(traceback.format_exc())
    errors.append({
        'step': step,
        'error': str(error),
        'timestamp': datetime.now().isoformat()
    })

def log_warning(step, warning):
    """Log a warning and track it"""
    warning_msg = f"{step}: {warning}"
    logger.warning(warning_msg)
    warnings.append({
        'step': step,
        'warning': str(warning),
        'timestamp': datetime.now().isoformat()
    })

def check_database_connection():
    """Check database connection"""
    logger.info("=" * 80)
    logger.info("STEP 1: Database Connection Check")
    logger.info("=" * 80)
    
    try:
        from api.shared.database.connection import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            log_error("Database Connection", "Failed to connect to database")
            return False
        
        # Test query
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM politics.articles")
        politics_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM finance.articles")
        finance_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        logger.info(f"✅ Database connected")
        logger.info(f"  Politics articles: {politics_count}")
        logger.info(f"  Finance articles: {finance_count}")
        return True
        
    except Exception as e:
        log_error("Database Connection", e, exc_info=True)
        return False

def check_rss_feeds():
    """Check RSS feeds for both domains"""
    logger.info("=" * 80)
    logger.info("STEP 2: RSS Feed Check")
    logger.info("=" * 80)
    
    try:
        from api.shared.database.connection import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            log_error("RSS Feed Check", "Database connection failed")
            return False
        
        cur = conn.cursor()
        
        for domain, schema in [('politics', 'politics'), ('finance', 'finance')]:
            try:
                cur.execute(f"""
                    SELECT COUNT(*) FROM {schema}.rss_feeds WHERE is_active = true
                """)
                count = cur.fetchone()[0]
                logger.info(f"✅ {domain}: {count} active RSS feeds")
            except Exception as e:
                log_error(f"RSS Feed Check ({domain})", e)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        log_error("RSS Feed Check", e, exc_info=True)
        return False

def run_rss_collection():
    """Run RSS collection for both domains"""
    logger.info("=" * 80)
    logger.info("STEP 3: RSS Feed Collection")
    logger.info("=" * 80)
    
    try:
        # Import RSS collector
        from api.collectors.rss_collector import collect_rss_feeds
        
        logger.info("Starting RSS collection for all active domains...")
        articles_added = collect_rss_feeds()
        
        logger.info(f"✅ RSS Collection Complete: {articles_added} articles added")
        return True
        
    except Exception as e:
        log_error("RSS Collection", e, exc_info=True)
        return False

def check_article_processing():
    """Check for articles that need processing"""
    logger.info("=" * 80)
    logger.info("STEP 4: Article Processing Status Check")
    logger.info("=" * 80)
    
    try:
        from api.shared.database.connection import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            log_error("Article Processing Check", "Database connection failed")
            return False
        
        cur = conn.cursor()
        
        for domain, schema in [('politics', 'politics'), ('finance', 'finance')]:
            try:
                # Check processing status
                cur.execute(f"""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE processing_status IS NULL OR processing_status = 'raw') as unprocessed,
                        COUNT(*) FILTER (WHERE processing_status = 'processed') as processed,
                        COUNT(*) FILTER (WHERE processing_status = 'error') as errors
                    FROM {schema}.articles
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """)
                
                result = cur.fetchone()
                total, unprocessed, processed, error_count = result
                
                logger.info(f"✅ {domain} articles (last 24h):")
                logger.info(f"  Total: {total}")
                logger.info(f"  Unprocessed: {unprocessed}")
                logger.info(f"  Processed: {processed}")
                if error_count > 0:
                    log_warning(f"{domain} Processing", f"{error_count} articles with errors")
                
            except Exception as e:
                log_error(f"Article Processing Check ({domain})", e)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        log_error("Article Processing Check", e, exc_info=True)
        return False

def check_topic_clustering():
    """Check topic clustering status"""
    logger.info("=" * 80)
    logger.info("STEP 5: Topic Clustering Status Check")
    logger.info("=" * 80)
    
    try:
        from api.shared.database.connection import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            log_error("Topic Clustering Check", "Database connection failed")
            return False
        
        cur = conn.cursor()
        
        for domain, schema in [('politics', 'politics'), ('finance', 'finance')]:
            try:
                # Check topics
                cur.execute(f"SELECT COUNT(*) FROM {schema}.topics")
                topic_count = cur.fetchone()[0]
                
                # Check article-topic assignments
                cur.execute(f"""
                    SELECT COUNT(DISTINCT article_id) 
                    FROM {schema}.article_topic_assignments
                """)
                assigned_count = cur.fetchone()[0]
                
                logger.info(f"✅ {domain} topics:")
                logger.info(f"  Topics: {topic_count}")
                logger.info(f"  Articles with topics: {assigned_count}")
                
            except Exception as e:
                log_error(f"Topic Clustering Check ({domain})", e)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        log_error("Topic Clustering Check", e, exc_info=True)
        return False

def check_storylines():
    """Check storylines status"""
    logger.info("=" * 80)
    logger.info("STEP 6: Storylines Status Check")
    logger.info("=" * 80)
    
    try:
        from api.shared.database.connection import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            log_error("Storylines Check", "Database connection failed")
            return False
        
        cur = conn.cursor()
        
        for domain, schema in [('politics', 'politics'), ('finance', 'finance')]:
            try:
                # Check storylines
                cur.execute(f"SELECT COUNT(*) FROM {schema}.storylines WHERE status = 'active'")
                storyline_count = cur.fetchone()[0]
                
                # Check storyline articles
                cur.execute(f"""
                    SELECT COUNT(DISTINCT article_id) 
                    FROM {schema}.storyline_articles
                """)
                article_count = cur.fetchone()[0]
                
                logger.info(f"✅ {domain} storylines:")
                logger.info(f"  Active storylines: {storyline_count}")
                logger.info(f"  Articles in storylines: {article_count}")
                
            except Exception as e:
                log_error(f"Storylines Check ({domain})", e)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        log_error("Storylines Check", e, exc_info=True)
        return False

def print_summary():
    """Print test summary"""
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    logger.info(f"\n✅ Steps Completed: 6")
    logger.info(f"❌ Errors: {len(errors)}")
    logger.info(f"⚠️  Warnings: {len(warnings)}")
    
    if errors:
        logger.info("\n❌ ERRORS FOUND:")
        for i, error in enumerate(errors, 1):
            logger.info(f"  {i}. [{error['step']}] {error['error']}")
            logger.info(f"     Time: {error['timestamp']}")
    
    if warnings:
        logger.info("\n⚠️  WARNINGS:")
        for i, warning in enumerate(warnings, 1):
            logger.info(f"  {i}. [{warning['step']}] {warning['warning']}")
            logger.info(f"     Time: {warning['timestamp']}")
    
    if not errors and not warnings:
        logger.info("\n🎉 All checks passed! Pipeline is working correctly.")
    elif not errors:
        logger.info("\n✅ Pipeline completed with warnings (non-critical).")
    else:
        logger.info("\n❌ Pipeline completed with errors. Review and fix issues above.")

def main():
    """Main test function"""
    logger.info("🚀 Starting Pipeline Test for Finance and Politics Domains")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # Run all checks
    check_database_connection()
    check_rss_feeds()
    run_rss_collection()
    check_article_processing()
    check_topic_clustering()
    check_storylines()
    
    # Print summary
    print_summary()
    
    logger.info("=" * 80)
    logger.info(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    return 0 if len(errors) == 0 else 1

if __name__ == '__main__':
    sys.exit(main())



