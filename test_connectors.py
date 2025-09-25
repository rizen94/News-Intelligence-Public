#!/usr/bin/env python3
"""
Comprehensive connector test for News Intelligence System
Tests all API endpoints and frontend functionality
"""

import requests
import json
import time
from datetime import datetime

API_BASE = "http://localhost:8002"
FRONTEND_BASE = "http://localhost:3000"

def test_endpoint(method, url, expected_status=200, data=None):
    """Test a single endpoint"""
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return False, f"Unsupported method: {method}"
        
        success = response.status_code == expected_status
        return success, f"{response.status_code} - {response.text[:100]}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def test_api_connectors():
    """Test all API endpoints"""
    print("🔍 TESTING API CONNECTORS")
    print("=" * 50)
    
    tests = [
        # Health endpoints
        ("GET", f"{API_BASE}/api/health/", 200),
        ("GET", f"{API_BASE}/api/health/database", 200),
        ("GET", f"{API_BASE}/api/health/ready", 200),
        ("GET", f"{API_BASE}/api/health/live", 200),
        
        # Dashboard endpoints
        ("GET", f"{API_BASE}/api/dashboard/stats", 200),
        
        # Articles endpoints
        ("GET", f"{API_BASE}/api/articles/", 200),
        ("GET", f"{API_BASE}/api/articles/sources", 200),
        ("GET", f"{API_BASE}/api/articles/categories", 200),
        ("GET", f"{API_BASE}/api/articles/stats/overview", 200),
        
        # Storylines endpoints
        ("GET", f"{API_BASE}/api/storylines/", 200),
        
        # RSS endpoints
        ("GET", f"{API_BASE}/api/rss/feeds/", 200),
        ("GET", f"{API_BASE}/api/rss/feeds/stats/overview", 200),
        
        # Intelligence endpoints
        ("GET", f"{API_BASE}/api/intelligence/trending-topics?time_period=24h&limit=3", 200),
        ("GET", f"{API_BASE}/api/intelligence/topic-clusters?time_period=7d&min_articles=2", 200),
        ("GET", f"{API_BASE}/api/intelligence/discovery?limit=5", 200),
        ("GET", f"{API_BASE}/api/intelligence/morning-briefing", 200),
        
        # Monitoring endpoints
        ("GET", f"{API_BASE}/api/monitoring/dashboard", 200),
        ("GET", f"{API_BASE}/api/monitoring/alerts", 200),
        ("GET", f"{API_BASE}/api/monitoring/metrics/system", 200),
        
        # Pipeline monitoring endpoints
        ("GET", f"{API_BASE}/api/pipeline-monitoring/traces", 200),
        ("GET", f"{API_BASE}/api/pipeline-monitoring/performance", 200),
        ("GET", f"{API_BASE}/api/pipeline-monitoring/live-status", 200),
    ]
    
    results = []
    for method, url, expected_status in tests:
        success, message = test_endpoint(method, url, expected_status)
        status = "✅" if success else "❌"
        print(f"{status} {method} {url.split('/')[-1] or url.split('/')[-2]}")
        if not success:
            print(f"   Error: {message}")
        results.append((success, url, message))
    
    return results

def test_data_consistency():
    """Test data consistency across endpoints"""
    print("\n🔍 TESTING DATA CONSISTENCY")
    print("=" * 50)
    
    try:
        # Test dashboard stats
        dashboard_response = requests.get(f"{API_BASE}/api/dashboard/stats", timeout=10)
        if dashboard_response.status_code == 200:
            dashboard_data = dashboard_response.json()
            print(f"✅ Dashboard Stats: {dashboard_data.get('data', {}).get('article_stats', {}).get('total_articles', 0)} articles")
            print(f"✅ RSS Stats: {dashboard_data.get('data', {}).get('rss_stats', {}).get('total_feeds', 0)} feeds")
        else:
            print("❌ Dashboard stats failed")
        
        # Test articles endpoint
        articles_response = requests.get(f"{API_BASE}/api/articles/", timeout=10)
        if articles_response.status_code == 200:
            articles_data = articles_response.json()
            article_count = len(articles_data.get('data', {}).get('articles', []))
            print(f"✅ Articles Endpoint: {article_count} articles returned")
        else:
            print("❌ Articles endpoint failed")
        
        # Test storylines endpoint
        storylines_response = requests.get(f"{API_BASE}/api/storylines/", timeout=10)
        if storylines_response.status_code == 200:
            storylines_data = storylines_response.json()
            storyline_count = len(storylines_data.get('data', {}).get('storylines', []))
            print(f"✅ Storylines Endpoint: {storyline_count} storylines returned")
        else:
            print("❌ Storylines endpoint failed")
        
        # Test intelligence endpoints
        trending_response = requests.get(f"{API_BASE}/api/intelligence/trending-topics?time_period=24h&limit=3", timeout=10)
        if trending_response.status_code == 200:
            trending_data = trending_response.json()
            trending_count = len(trending_data.get('data', {}).get('trending_topics', []))
            print(f"✅ Trending Topics: {trending_count} topics returned")
        else:
            print("❌ Trending topics failed")
        
    except Exception as e:
        print(f"❌ Data consistency test failed: {e}")

def test_frontend_connectivity():
    """Test frontend connectivity"""
    print("\n🔍 TESTING FRONTEND CONNECTIVITY")
    print("=" * 50)
    
    try:
        # Test frontend is serving
        frontend_response = requests.get(FRONTEND_BASE, timeout=10)
        if frontend_response.status_code == 200:
            print("✅ Frontend is serving")
        else:
            print(f"❌ Frontend failed: {frontend_response.status_code}")
        
        # Test static assets
        static_response = requests.get(f"{FRONTEND_BASE}/static/js/main.a268788a.js", timeout=10)
        if static_response.status_code == 200:
            print("✅ Static assets are serving")
        else:
            print(f"❌ Static assets failed: {static_response.status_code}")
        
    except Exception as e:
        print(f"❌ Frontend connectivity test failed: {e}")

def test_button_functionality():
    """Test key button functionality through API calls"""
    print("\n🔍 TESTING BUTTON FUNCTIONALITY")
    print("=" * 50)
    
    # Test refresh functionality
    try:
        refresh_response = requests.get(f"{API_BASE}/api/dashboard/stats", timeout=10)
        if refresh_response.status_code == 200:
            print("✅ Refresh Data button - Dashboard stats working")
        else:
            print("❌ Refresh Data button - Dashboard stats failed")
    except Exception as e:
        print(f"❌ Refresh Data button failed: {e}")
    
    # Test article filtering
    try:
        filter_response = requests.get(f"{API_BASE}/api/articles/?category=politics&limit=5", timeout=10)
        if filter_response.status_code == 200:
            print("✅ Article Filtering - Category filter working")
        else:
            print("❌ Article Filtering - Category filter failed")
    except Exception as e:
        print(f"❌ Article Filtering failed: {e}")
    
    # Test search functionality
    try:
        search_response = requests.get(f"{API_BASE}/api/articles/?search=election&limit=5", timeout=10)
        if search_response.status_code == 200:
            print("✅ Search Functionality - Article search working")
        else:
            print("❌ Search Functionality - Article search failed")
    except Exception as e:
        print(f"❌ Search Functionality failed: {e}")

def main():
    """Run all tests"""
    print("🚀 NEWS INTELLIGENCE SYSTEM - CONNECTOR TEST")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Base: {API_BASE}")
    print(f"Frontend Base: {FRONTEND_BASE}")
    
    # Run all tests
    api_results = test_api_connectors()
    test_data_consistency()
    test_frontend_connectivity()
    test_button_functionality()
    
    # Summary
    print("\n📊 TEST SUMMARY")
    print("=" * 50)
    
    total_tests = len(api_results)
    passed_tests = sum(1 for success, _, _ in api_results if success)
    failed_tests = total_tests - passed_tests
    
    print(f"API Endpoints: {passed_tests}/{total_tests} passed")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests > 0:
        print("\n❌ FAILED ENDPOINTS:")
        for success, url, message in api_results:
            if not success:
                print(f"   - {url}: {message}")
    
    print("\n🎯 RECOMMENDATIONS:")
    if failed_tests == 0:
        print("✅ All connectors are working correctly!")
        print("✅ System is ready for production use")
    else:
        print("⚠️  Some connectors need attention")
        print("⚠️  Review failed endpoints before production deployment")

if __name__ == "__main__":
    main()
