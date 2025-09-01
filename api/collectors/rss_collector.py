#!/usr/bin/env python3
"""
RSS Feed Collector for News Intelligence System v3.0.0
Collects articles from RSS feeds with advanced deduplication.
"""

import os
import logging
import signal
import feedparser
import psycopg2
from datetime import datetime
from typing import Dict, List, Optional

# Import deduplication system
try:
    from modules.deduplication import DeduplicationManager
    DEDUPLICATION_AVAILABLE = True
except ImportError:
    DEDUPLICATION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Deduplication system not available - falling back to basic collection")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import configuration
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
try:
    from database import get_database_config
    DB_CONFIG = get_database_config()
    DB_CONFIG.update({
        'connect_timeout': 10,      # 10 second connection timeout
        'options': '-c statement_timeout=30000'  # 30 second query timeout
    })
except ImportError:
    # Fallback configuration if config module not available
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'postgres'),
        'database': os.getenv('DB_NAME', 'news_system'),
        'user': os.getenv('DB_USER', 'newsapp'),
        'password': os.getenv('DB_PASSWORD', ''),
        'connect_timeout': 10,      # 10 second connection timeout
        'options': '-c statement_timeout=30000'  # 30 second query timeout
    }

def get_db_connection():
    """Get database connection with timeout protection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def collect_rss_feeds() -> int:
    """
    Collect articles from all active RSS feeds with deduplication
    Returns: Number of articles added
    """
    logger.info("Starting RSS feed collection with deduplication...")
    
    # Initialize deduplication manager if available
    dedup_manager = None
    if DEDUPLICATION_AVAILABLE:
        try:
            dedup_manager = DeduplicationManager(DB_CONFIG)
            logger.info("Deduplication system initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize deduplication system: {e}")
            dedup_manager = None
    
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to database")
        return 0
    
    try:
        cur = conn.cursor()
        
        # Get all active RSS feeds
        cur.execute("""
            SELECT id, name, url, category 
            FROM rss_feeds 
            WHERE is_active = true
        """)
        feeds = cur.fetchall()
        
        total_articles_added = 0
        total_duplicates_rejected = 0
        
        for feed_id, feed_name, feed_url, feed_category in feeds:
            logger.info(f"Processing feed: {feed_name} ({feed_url})")
            
            try:
                # Set timeout for RSS parsing
                def timeout_handler(signum, frame):
                    raise TimeoutError("RSS parsing timeout")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(30)  # 30 second timeout
                
                # Parse RSS feed
                feed = feedparser.parse(feed_url)
                signal.alarm(0)  # Cancel timeout
                
                articles_added = 0
                
                for entry in feed.entries:
                    try:
                        # Extract article data
                        title = entry.get('title', '')[:500]  # Limit title length
                        url = entry.get('link', '')[:500]    # Limit URL length
                        content = entry.get('summary', '') or entry.get('description', '')
                        
                        # Parse published date
                        published_date = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            published_date = datetime(*entry.published_parsed[:6])
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            published_date = datetime(*entry.updated_parsed[:6])
                        else:
                            published_date = datetime.now()
                        
                        # Insert article if it doesn't exist
                        cur.execute("""
                            INSERT INTO articles
                            (title, url, content, summary, published_date, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (url) DO NOTHING
                        """, (
                            title,
                            url,
                            content,
                            None,
                            published_date,
                            datetime.now()
                        ))
                        
                        if cur.rowcount > 0:
                            articles_added += 1
                            
                    except Exception as e:
                        logger.warning(f"Error processing article from {feed_name}: {e}")
                        continue
                
                # Update last fetched timestamp
                cur.execute("""
                    UPDATE rss_feeds 
                    SET last_fetched = NOW() 
                    WHERE id = %s
                """, (feed_id,))
                
                total_articles_added += articles_added
                logger.info(f"Added {articles_added} articles from {feed_name}")
                
            except TimeoutError:
                logger.error(f"Timeout processing feed: {feed_name}")
                continue
            except Exception as e:
                logger.error(f"Error processing feed {feed_name}: {e}")
                continue
        
        conn.commit()
        
        # Log final results
        if dedup_manager and total_duplicates_rejected > 0:
            logger.info(f"RSS collection completed with deduplication. "
                       f"Articles added: {total_articles_added}, "
                       f"Duplicates rejected: {total_duplicates_rejected}")
        else:
            logger.info(f"RSS collection completed. Total articles added: {total_articles_added}")
        
        return total_articles_added
        
    except Exception as e:
        logger.error(f"Error during RSS collection: {e}")
        conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

def collect_rss_feed(feed_url: str, feed_name: str = "Unknown") -> int:
    """
    Collect articles from a specific RSS feed
    Args:
        feed_url: URL of the RSS feed
        feed_name: Name of the feed for logging
    Returns:
        Number of articles added
    """
    logger.info(f"Collecting from single feed: {feed_name}")
    
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        cur = conn.cursor()
        
        # Parse RSS feed with timeout
        def timeout_handler(signum, frame):
            raise TimeoutError("RSS parsing timeout")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)
        
        feed = feedparser.parse(feed_url)
        signal.alarm(0)
        
        articles_added = 0
        
        for entry in feed.entries:
            try:
                title = entry.get('title', '')[:500]
                url = entry.get('link', '')[:500]
                content = entry.get('summary', '') or entry.get('description', '')
                
                published_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_date = datetime(*entry.updated_parsed[:6])
                else:
                    published_date = datetime.now()
                
                cur.execute("""
                    INSERT INTO articles
                    (title, url, content, summary, published_date, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO NOTHING
                """, (
                    title, url, content, None, published_date, datetime.now()
                ))
                
                if cur.rowcount > 0:
                    articles_added += 1
                    
            except Exception as e:
                logger.warning(f"Error processing article: {e}")
                continue
        
        conn.commit()
        logger.info(f"Added {articles_added} articles from {feed_name}")
        return articles_added
        
    except TimeoutError:
        logger.error(f"Timeout processing feed: {feed_name}")
        return 0
    except Exception as e:
        logger.error(f"Error processing feed {feed_name}: {e}")
        conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Test RSS collection
    print("Testing RSS collection...")
    result = collect_rss_feeds()
    print(f"Collection completed. Articles added: {result}")
