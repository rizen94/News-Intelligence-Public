#!/usr/bin/env python3
"""
Script to process raw articles through the ML pipeline
"""

import sys
import os
import logging
from datetime import datetime

# Add the API directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from modules.ml.ml_pipeline import MLPipeline
from config.database import get_db_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_raw_articles():
    """Process raw articles through the ML pipeline"""
    try:
        # Get database config
        db_config = get_db_config()
        
        # Initialize ML pipeline
        ml_pipeline = MLPipeline(db_config)
        
        # Get raw articles
        import psycopg2
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, title, content, source, published_date 
            FROM articles 
            WHERE processing_status = 'raw' 
            ORDER BY published_date DESC 
            LIMIT 10
        """)
        
        raw_articles = cur.fetchall()
        cur.close()
        conn.close()
        
        if not raw_articles:
            logger.info("No raw articles found to process")
            return
        
        logger.info(f"Found {len(raw_articles)} raw articles to process")
        
        # Process each article
        processed_count = 0
        for article_id, title, content, source, published_date in raw_articles:
            logger.info(f"Processing article {article_id}: {title[:50]}...")
            
            result = ml_pipeline.process_article(article_id)
            
            if result.get("status") == "success":
                processed_count += 1
                logger.info(f"✅ Successfully processed article {article_id}")
            else:
                logger.error(f"❌ Failed to process article {article_id}: {result.get('error', 'Unknown error')}")
        
        logger.info(f"Processing complete: {processed_count}/{len(raw_articles)} articles processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing articles: {e}")

if __name__ == "__main__":
    process_raw_articles()
