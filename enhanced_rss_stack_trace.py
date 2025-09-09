#!/usr/bin/env python3
"""
News Intelligence System v3.3.0 - Enhanced RSS Processing Stack Trace
Traces a new RSS feed through the entire system processing pipeline with comprehensive error handling
"""

import requests
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import sys
import os
import signal
import traceback
from contextlib import contextmanager
import logging

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('rss_stack_trace.log')
    ]
)
logger = logging.getLogger(__name__)

# Add API path
sys.path.append('api')
from database.connection import get_db_config

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

@contextmanager
def timeout(seconds):
    """Context manager for timeouts"""
    def signal_handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Restore the old signal handler
        signal.signal(signal.SIGALRM, old_handler)
        signal.alarm(0)

def get_db_connection(timeout_seconds=30):
    """Get database connection with timeout"""
    try:
        with timeout(timeout_seconds):
            config = get_db_config()
            logger.info(f"🔗 Connecting to database: {config['host']}:{config['port']}")
            conn = psycopg2.connect(**config)
            logger.info("✅ Database connection established")
            return conn
    except TimeoutError as e:
        logger.error(f"❌ Database connection timeout: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Error details: {str(e)}")
        raise

def safe_request(url, method='GET', data=None, timeout_seconds=30, retries=3):
    """Make HTTP request with timeout and retries"""
    for attempt in range(retries):
        try:
            logger.info(f"🌐 {method} {url} (attempt {attempt + 1}/{retries})")
            
            with timeout(timeout_seconds):
                if method == 'GET':
                    response = requests.get(url, timeout=timeout_seconds)
                elif method == 'POST':
                    response = requests.post(url, json=data, timeout=timeout_seconds)
                else:
                    raise ValueError(f"Unsupported method: {method}")
            
            logger.info(f"✅ {method} {url} - Status: {response.status_code}")
            return response
            
        except TimeoutError as e:
            logger.warning(f"⏰ {method} {url} timeout (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"🌐 {method} {url} request failed (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
            
        except Exception as e:
            logger.error(f"❌ {method} {url} unexpected error (attempt {attempt + 1}): {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)

def safe_db_query(conn, query, params=None, timeout_seconds=30):
    """Execute database query with timeout and error handling"""
    try:
        with timeout(timeout_seconds):
            logger.info(f"🗄️ Executing query: {query[:100]}...")
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params)
            result = cursor.fetchall()
            cursor.close()
            logger.info(f"✅ Query executed successfully - {len(result)} rows returned")
            return result
    except TimeoutError as e:
        logger.error(f"⏰ Database query timeout: {e}")
        raise
    except psycopg2.Error as e:
        logger.error(f"❌ Database query failed: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params: {params}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected database error: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
        raise

def trace_rss_processing():
    """Trace RSS feed processing through the entire system with comprehensive error handling"""
    logger.info("🔍 ENHANCED RSS PROCESSING STACK TRACE")
    logger.info("=" * 80)
    
    base_url = "http://localhost:8000"
    start_time = datetime.now()
    
    try:
        # Step 1: Verify the new feed exists
        logger.info("\n1️⃣ VERIFYING NEW RSS FEED")
        logger.info("-" * 50)
        
        try:
            response = safe_request(f"{base_url}/api/rss/feeds/", timeout_seconds=15)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"📊 API Response: {json.dumps(data, indent=2)}")
                
                feeds = data.get("data", {}).get("feeds", [])
                logger.info(f"📰 Found {len(feeds)} total feeds")
                
                new_feed = next((f for f in feeds if f["name"] == "Hacker News Test Feed"), None)
                
                if new_feed:
                    logger.info(f"✅ Feed found: {new_feed['name']} (ID: {new_feed['id']})")
                    logger.info(f"   URL: {new_feed['url']}")
                    logger.info(f"   Status: {new_feed.get('status', 'unknown')}")
                    logger.info(f"   Last Fetched: {new_feed.get('last_fetched', 'Never')}")
                    logger.info(f"   Active: {new_feed.get('is_active', 'unknown')}")
                    feed_id = new_feed['id']
                else:
                    logger.error("❌ New feed not found in API response")
                    logger.error(f"   Available feeds: {[f['name'] for f in feeds]}")
                    return False
            else:
                logger.error(f"❌ Failed to get feeds: HTTP {response.status_code}")
                logger.error(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error verifying feed: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False
        
        # Step 2: Check current article count
        logger.info("\n2️⃣ CHECKING CURRENT ARTICLE COUNT")
        logger.info("-" * 50)
        
        try:
            conn = get_db_connection(timeout_seconds=30)
            
            # Get total article count
            total_result = safe_db_query(conn, "SELECT COUNT(*) as total FROM articles")
            total_articles = total_result[0]['total']
            logger.info(f"📊 Total articles in system: {total_articles}")
            
            # Get articles from our test feed
            feed_result = safe_db_query(conn, """
                SELECT COUNT(*) as count, MAX(created_at) as latest
                FROM articles 
                WHERE source = %s
            """, (new_feed['name'],))
            
            feed_articles = feed_result[0]
            feed_count = feed_articles['count']
            latest_article = feed_articles['latest']
            
            logger.info(f"📊 Articles from test feed: {feed_count}")
            logger.info(f"📊 Latest article from test feed: {latest_article}")
            
            # Get processing status breakdown
            status_result = safe_db_query(conn, """
                SELECT processing_status, COUNT(*) as count
                FROM articles 
                WHERE source = %s
                GROUP BY processing_status
            """, (new_feed['name'],))
            
            logger.info(f"📊 Processing status breakdown:")
            for status in status_result:
                logger.info(f"   {status['processing_status']}: {status['count']} articles")
            
            conn.close()
            logger.info("✅ Database connection closed")
            
        except Exception as e:
            logger.error(f"❌ Error checking article count: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False
        
        # Step 3: Trigger RSS processing manually
        logger.info("\n3️⃣ TRIGGERING RSS PROCESSING")
        logger.info("-" * 50)
        
        try:
            # Check if there's a manual RSS processing endpoint
            response = safe_request(f"{base_url}/api/rss/process/", method='POST', timeout_seconds=60)
            
            if response.status_code == 200:
                logger.info("✅ RSS processing triggered successfully")
                processing_result = response.json()
                logger.info(f"   Result: {json.dumps(processing_result, indent=2)}")
            else:
                logger.warning(f"⚠️ Manual processing not available (status: {response.status_code})")
                logger.warning(f"   Response: {response.text}")
                logger.info("   Will monitor for automatic processing...")
                
        except Exception as e:
            logger.warning(f"⚠️ Manual processing failed: {e}")
            logger.warning(f"   Error type: {type(e).__name__}")
            logger.info("   Will monitor for automatic processing...")
        
        # Step 4: Monitor article processing in real-time
        logger.info("\n4️⃣ MONITORING ARTICLE PROCESSING")
        logger.info("-" * 50)
        
        initial_count = total_articles
        max_wait_time = 300  # 5 minutes
        check_interval = 10  # 10 seconds
        
        logger.info(f"⏰ Starting monitoring at {start_time.strftime('%H:%M:%S')}")
        logger.info(f"⏰ Will monitor for up to {max_wait_time} seconds")
        logger.info(f"⏰ Check interval: {check_interval} seconds")
        
        monitoring_start = datetime.now()
        last_count = initial_count
        
        while (datetime.now() - monitoring_start).total_seconds() < max_wait_time:
            try:
                elapsed = (datetime.now() - monitoring_start).total_seconds()
                
                # Check database for new articles
                conn = get_db_connection(timeout_seconds=15)
                
                # Get current article count
                current_result = safe_db_query(conn, "SELECT COUNT(*) as total FROM articles")
                current_total = current_result[0]['total']
                
                # Get articles from our test feed
                feed_result = safe_db_query(conn, """
                    SELECT COUNT(*) as count, MAX(created_at) as latest, 
                           MIN(created_at) as earliest
                    FROM articles 
                    WHERE source = %s
                """, (new_feed['name'],))
                
                feed_data = feed_result[0]
                current_feed_count = feed_data['count']
                latest_article = feed_data['latest']
                earliest_article = feed_data['earliest']
                
                # Get recent articles for analysis
                recent_result = safe_db_query(conn, """
                    SELECT id, title, created_at, processing_status, 
                           word_count, reading_time, language
                    FROM articles 
                    WHERE source = %s
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (new_feed['name'],))
                
                recent_articles = recent_result
                
                conn.close()
                
                # Check for changes
                new_articles = current_total - initial_count
                new_feed_articles = current_feed_count - feed_count
                total_change = current_total - last_count
                
                logger.info(f"⏰ [{elapsed:6.1f}s] Articles: Total={current_total} (+{new_articles}), Feed={current_feed_count} (+{new_feed_articles}), Change={total_change}")
                
                if new_feed_articles > 0:
                    logger.info(f"   🎉 NEW ARTICLES DETECTED!")
                    logger.info(f"   📰 Latest: {latest_article}")
                    logger.info(f"   📰 Earliest: {earliest_article}")
                    
                    # Show recent articles
                    for i, article in enumerate(recent_articles, 1):
                        logger.info(f"   📄 Article {i}: ID={article['id']} | {article['title'][:50]}...")
                        logger.info(f"      Created: {article['created_at']} | Status: {article['processing_status']}")
                        logger.info(f"      Words: {article['word_count']} | Reading: {article['reading_time']}min | Lang: {article['language']}")
                    
                    break
                elif total_change > 0:
                    logger.info(f"   📈 System processing: {total_change} new articles (not from test feed)")
                else:
                    logger.info(f"   ⏳ Waiting for new articles...")
                
                last_count = current_total
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"❌ Error during monitoring: {e}")
                logger.error(f"   Error type: {type(e).__name__}")
                logger.error(f"   Traceback: {traceback.format_exc()}")
                time.sleep(check_interval)
        
        # Step 5: Analyze processing pipeline
        logger.info("\n5️⃣ ANALYZING PROCESSING PIPELINE")
        logger.info("-" * 50)
        
        try:
            conn = get_db_connection(timeout_seconds=30)
            
            # Get detailed article analysis
            analysis_result = safe_db_query(conn, """
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(CASE WHEN processing_status = 'processed' THEN 1 END) as processed,
                    COUNT(CASE WHEN processing_status = 'pending_processing' THEN 1 END) as pending,
                    COUNT(CASE WHEN processing_status = 'processing' THEN 1 END) as processing,
                    AVG(word_count) as avg_word_count,
                    AVG(reading_time) as avg_reading_time,
                    COUNT(DISTINCT language) as languages
                FROM articles 
                WHERE source = %s
            """, (new_feed['name'],))
            
            analysis = analysis_result[0]
            
            logger.info(f"📊 PROCESSING ANALYSIS:")
            logger.info(f"   Total Articles: {analysis['total_articles']}")
            logger.info(f"   Processed: {analysis['processed']}")
            logger.info(f"   Pending: {analysis['pending']}")
            logger.info(f"   Processing: {analysis['processing']}")
            logger.info(f"   Avg Word Count: {analysis['avg_word_count']:.1f}" if analysis['avg_word_count'] else "   Avg Word Count: N/A")
            logger.info(f"   Avg Reading Time: {analysis['avg_reading_time']:.1f} min" if analysis['avg_reading_time'] else "   Avg Reading Time: N/A")
            logger.info(f"   Languages: {analysis['languages']}")
            
            # Get processing timeline
            timeline_result = safe_db_query(conn, """
                SELECT 
                    DATE_TRUNC('minute', created_at) as minute,
                    COUNT(*) as articles_per_minute
                FROM articles 
                WHERE source = %s
                GROUP BY DATE_TRUNC('minute', created_at)
                ORDER BY minute DESC
                LIMIT 10
            """, (new_feed['name'],))
            
            logger.info(f"\n📈 PROCESSING TIMELINE:")
            for entry in timeline_result:
                logger.info(f"   {entry['minute']}: {entry['articles_per_minute']} articles")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Error analyzing pipeline: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
        
        # Step 6: Test API endpoints with new data
        logger.info("\n6️⃣ TESTING API ENDPOINTS")
        logger.info("-" * 50)
        
        try:
            # Test articles endpoint
            response = safe_request(f"{base_url}/api/articles/?source={new_feed['name']}", timeout_seconds=15)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get("data", {}).get("articles", [])
                logger.info(f"✅ Articles API: {len(articles)} articles retrieved")
                
                if articles:
                    sample = articles[0]
                    logger.info(f"   Sample Article: {sample['title'][:50]}...")
                    logger.info(f"   ID: {sample['id']} | Source: {sample['source']}")
                    logger.info(f"   Created: {sample['created_at']} | Status: {sample.get('processing_status', 'unknown')}")
                else:
                    logger.warning("   No articles found in API response")
            else:
                logger.error(f"❌ Articles API failed: HTTP {response.status_code}")
                logger.error(f"   Response: {response.text}")
            
            # Test health endpoint
            response = safe_request(f"{base_url}/api/health/", timeout_seconds=15)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Health API: {data.get('data', {}).get('status', 'unknown')}")
            else:
                logger.error(f"❌ Health API failed: HTTP {response.status_code}")
                logger.error(f"   Response: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Error testing API endpoints: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
        
        # Final summary
        total_time = (datetime.now() - start_time).total_seconds()
        logger.info("\n" + "=" * 80)
        logger.info("🎯 ENHANCED STACK TRACE COMPLETE")
        logger.info("=" * 80)
        logger.info(f"⏰ Total execution time: {total_time:.1f} seconds")
        logger.info(f"📊 Final article count: {current_total if 'current_total' in locals() else 'unknown'}")
        logger.info(f"📊 Test feed articles: {current_feed_count if 'current_feed_count' in locals() else 'unknown'}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in stack trace: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = trace_rss_processing()
    exit(0 if success else 1)

