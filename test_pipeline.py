#!/usr/bin/env python3
"""
News Intelligence System v3.3.0 - End-to-End Pipeline Test
Tests complete front-to-back pipeline continuity
"""

import requests
import json
import time
from datetime import datetime

def test_pipeline():
    """Test complete pipeline from API to data flow"""
    print("🧪 Testing News Intelligence System v3.3.0 Pipeline")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    results = {
        "health_check": False,
        "articles_endpoint": False,
        "rss_feeds_endpoint": False,
        "rss_processing": False,
        "data_flow": False
    }
    
    # Test 1: Health Check
    print("\n1️⃣ Testing Health Check...")
    try:
        response = requests.get(f"{base_url}/api/health/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("status") == "healthy":
                results["health_check"] = True
                print("✅ Health check passed")
            else:
                print("❌ Health check failed - unhealthy status")
        else:
            print(f"❌ Health check failed - status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check failed - error: {e}")
    
    # Test 2: Articles Endpoint
    print("\n2️⃣ Testing Articles Endpoint...")
    try:
        response = requests.get(f"{base_url}/api/articles/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "articles" in data.get("data", {}):
                articles = data["data"]["articles"]
                results["articles_endpoint"] = True
                print(f"✅ Articles endpoint passed - {len(articles)} articles retrieved")
            else:
                print("❌ Articles endpoint failed - no articles data")
        else:
            print(f"❌ Articles endpoint failed - status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Articles endpoint failed - error: {e}")
    
    # Test 3: RSS Feeds Endpoint
    print("\n3️⃣ Testing RSS Feeds Endpoint...")
    try:
        response = requests.get(f"{base_url}/api/rss/feeds/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "feeds" in data.get("data", {}):
                feeds = data["data"]["feeds"]
                results["rss_feeds_endpoint"] = True
                print(f"✅ RSS feeds endpoint passed - {len(feeds)} feeds retrieved")
            else:
                print("❌ RSS feeds endpoint failed - no feeds data")
        else:
            print(f"❌ RSS feeds endpoint failed - status code: {response.status_code}")
    except Exception as e:
        print(f"❌ RSS feeds endpoint failed - error: {e}")
    
    # Test 4: RSS Processing (if automation is running)
    print("\n4️⃣ Testing RSS Processing...")
    try:
        # Check if articles are being processed by looking at recent articles
        response = requests.get(f"{base_url}/api/articles/?limit=5", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "articles" in data.get("data", {}):
                articles = data["data"]["articles"]
                recent_articles = [a for a in articles if a.get("created_at")]
                if recent_articles:
                    results["rss_processing"] = True
                    print(f"✅ RSS processing working - recent articles found")
                else:
                    print("⚠️ RSS processing - no recent articles found")
            else:
                print("❌ RSS processing failed - no articles data")
        else:
            print(f"❌ RSS processing failed - status code: {response.status_code}")
    except Exception as e:
        print(f"❌ RSS processing failed - error: {e}")
    
    # Test 5: Data Flow Continuity
    print("\n5️⃣ Testing Data Flow Continuity...")
    try:
        # Test that data flows from RSS feeds to articles
        feeds_response = requests.get(f"{base_url}/api/rss/feeds/", timeout=10)
        articles_response = requests.get(f"{base_url}/api/articles/?limit=10", timeout=10)
        
        if (feeds_response.status_code == 200 and articles_response.status_code == 200):
            feeds_data = feeds_response.json()
            articles_data = articles_response.json()
            
            if (feeds_data.get("success") and articles_data.get("success")):
                feeds = feeds_data["data"]["feeds"]
                articles = articles_data["data"]["articles"]
                
                # Check if articles have sources that match feed names
                feed_names = [feed["name"] for feed in feeds]
                article_sources = [article["source"] for article in articles if article.get("source")]
                
                matching_sources = set(article_sources) & set(feed_names)
                if matching_sources:
                    results["data_flow"] = True
                    print(f"✅ Data flow continuity confirmed - {len(matching_sources)} matching sources")
                else:
                    print("⚠️ Data flow - no matching sources between feeds and articles")
            else:
                print("❌ Data flow failed - API responses not successful")
        else:
            print("❌ Data flow failed - API requests failed")
    except Exception as e:
        print(f"❌ Data flow failed - error: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 PIPELINE TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED - Pipeline is working correctly!")
        return True
    else:
        print("⚠️ Some tests failed - Pipeline needs attention")
        return False

if __name__ == "__main__":
    success = test_pipeline()
    exit(0 if success else 1)

