#!/usr/bin/env python3
"""
News Intelligence System v3.3.0 - RSS Processing Stack Trace
Traces a new RSS feed through the entire system processing pipeline
"""

import requests
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import sys
import os

# Add API path
sys.path.append('api')
from database.connection import get_db_config

def get_db_connection():
    """Get database connection"""
    config = get_db_config()
    return psycopg2.connect(**config)

def trace_rss_processing():
    """Trace RSS feed processing through the entire system"""
    print("🔍 RSS PROCESSING STACK TRACE")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Step 1: Verify the new feed exists
    print("\n1️⃣ VERIFYING NEW RSS FEED")
    print("-" * 40)
    
    try:
        response = requests.get(f"{base_url}/api/rss/feeds/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            feeds = data["data"]["feeds"]
            new_feed = next((f for f in feeds if f["name"] == "Hacker News Test Feed"), None)
            
            if new_feed:
                print(f"✅ Feed found: {new_feed['name']} (ID: {new_feed['id']})")
                print(f"   URL: {new_feed['url']}")
                print(f"   Status: {new_feed.get('status', 'unknown')}")
                print(f"   Last Fetched: {new_feed.get('last_fetched', 'Never')}")
                feed_id = new_feed['id']
            else:
                print("❌ New feed not found")
                return False
        else:
            print(f"❌ Failed to get feeds: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error getting feeds: {e}")
        return False
    
    # Step 2: Check current article count
    print("\n2️⃣ CHECKING CURRENT ARTICLE COUNT")
    print("-" * 40)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get total article count
        cursor.execute("SELECT COUNT(*) as total FROM articles")
        total_articles = cursor.fetchone()['total']
        
        # Get articles from our test feed
        cursor.execute("""
            SELECT COUNT(*) as count, MAX(created_at) as latest
            FROM articles 
            WHERE source = %s
        """, (new_feed['name'],))
        
        feed_articles = cursor.fetchone()
        feed_count = feed_articles['count']
        latest_article = feed_articles['latest']
        
        print(f"📊 Total articles in system: {total_articles}")
        print(f"📊 Articles from test feed: {feed_count}")
        print(f"📊 Latest article from test feed: {latest_article}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking article count: {e}")
        return False
    
    # Step 3: Trigger RSS processing manually
    print("\n3️⃣ TRIGGERING RSS PROCESSING")
    print("-" * 40)
    
    try:
        # Check if there's a manual RSS processing endpoint
        response = requests.post(f"{base_url}/api/rss/process/", timeout=30)
        if response.status_code == 200:
            print("✅ RSS processing triggered successfully")
            processing_result = response.json()
            print(f"   Result: {processing_result}")
        else:
            print(f"⚠️ Manual processing not available (status: {response.status_code})")
            print("   Will monitor for automatic processing...")
    except Exception as e:
        print(f"⚠️ Manual processing failed: {e}")
        print("   Will monitor for automatic processing...")
    
    # Step 4: Monitor article processing in real-time
    print("\n4️⃣ MONITORING ARTICLE PROCESSING")
    print("-" * 40)
    
    initial_count = total_articles
    start_time = datetime.now()
    max_wait_time = 300  # 5 minutes
    check_interval = 10  # 10 seconds
    
    print(f"⏰ Starting monitoring at {start_time.strftime('%H:%M:%S')}")
    print(f"⏰ Will monitor for up to {max_wait_time} seconds")
    
    while (datetime.now() - start_time).total_seconds() < max_wait_time:
        try:
            # Check database for new articles
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get current article count
            cursor.execute("SELECT COUNT(*) as total FROM articles")
            current_total = cursor.fetchone()['total']
            
            # Get articles from our test feed
            cursor.execute("""
                SELECT COUNT(*) as count, MAX(created_at) as latest, 
                       MIN(created_at) as earliest
                FROM articles 
                WHERE source = %s
            """, (new_feed['name'],))
            
            feed_data = cursor.fetchone()
            current_feed_count = feed_data['count']
            latest_article = feed_data['latest']
            earliest_article = feed_data['earliest']
            
            # Get recent articles for analysis
            cursor.execute("""
                SELECT id, title, created_at, processing_status, 
                       word_count, reading_time, language
                FROM articles 
                WHERE source = %s
                ORDER BY created_at DESC
                LIMIT 5
            """, (new_feed['name'],))
            
            recent_articles = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            # Check for changes
            new_articles = current_total - initial_count
            new_feed_articles = current_feed_count - feed_count
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            print(f"\n⏰ [{elapsed:6.1f}s] Articles: Total={current_total} (+{new_articles}), Feed={current_feed_count} (+{new_feed_articles})")
            
            if new_feed_articles > 0:
                print(f"   🎉 NEW ARTICLES DETECTED!")
                print(f"   📰 Latest: {latest_article}")
                print(f"   📰 Earliest: {earliest_article}")
                
                # Show recent articles
                for article in recent_articles:
                    print(f"   📄 ID: {article['id']} | {article['title'][:50]}...")
                    print(f"      Created: {article['created_at']} | Status: {article['processing_status']}")
                    print(f"      Words: {article['word_count']} | Reading: {article['reading_time']}min | Lang: {article['language']}")
                
                break
            else:
                print(f"   ⏳ Waiting for new articles...")
            
            time.sleep(check_interval)
            
        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
            time.sleep(check_interval)
    
    # Step 5: Analyze processing pipeline
    print("\n5️⃣ ANALYZING PROCESSING PIPELINE")
    print("-" * 40)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get detailed article analysis
        cursor.execute("""
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
        
        analysis = cursor.fetchone()
        
        print(f"📊 PROCESSING ANALYSIS:")
        print(f"   Total Articles: {analysis['total_articles']}")
        print(f"   Processed: {analysis['processed']}")
        print(f"   Pending: {analysis['pending']}")
        print(f"   Processing: {analysis['processing']}")
        print(f"   Avg Word Count: {analysis['avg_word_count']:.1f}")
        print(f"   Avg Reading Time: {analysis['avg_reading_time']:.1f} min")
        print(f"   Languages: {analysis['languages']}")
        
        # Get processing timeline
        cursor.execute("""
            SELECT 
                DATE_TRUNC('minute', created_at) as minute,
                COUNT(*) as articles_per_minute
            FROM articles 
            WHERE source = %s
            GROUP BY DATE_TRUNC('minute', created_at)
            ORDER BY minute DESC
            LIMIT 10
        """, (new_feed['name'],))
        
        timeline = cursor.fetchall()
        
        print(f"\n📈 PROCESSING TIMELINE:")
        for entry in timeline:
            print(f"   {entry['minute']}: {entry['articles_per_minute']} articles")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error analyzing pipeline: {e}")
    
    # Step 6: Test API endpoints with new data
    print("\n6️⃣ TESTING API ENDPOINTS")
    print("-" * 40)
    
    try:
        # Test articles endpoint
        response = requests.get(f"{base_url}/api/articles/?source={new_feed['name']}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            articles = data["data"]["articles"]
            print(f"✅ Articles API: {len(articles)} articles retrieved")
            
            if articles:
                sample = articles[0]
                print(f"   Sample Article: {sample['title'][:50]}...")
                print(f"   ID: {sample['id']} | Source: {sample['source']}")
                print(f"   Created: {sample['created_at']} | Status: {sample.get('processing_status', 'unknown')}")
        else:
            print(f"❌ Articles API failed: {response.status_code}")
        
        # Test health endpoint
        response = requests.get(f"{base_url}/api/health/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health API: {data['data']['status']}")
        else:
            print(f"❌ Health API failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 STACK TRACE COMPLETE")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = trace_rss_processing()
    exit(0 if success else 1)

