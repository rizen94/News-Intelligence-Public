#!/usr/bin/env python3
"""
Comprehensive System Verification Script
Tests all major system components and endpoints
"""

import requests
import json
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

def test_endpoint(endpoint, method="GET", data=None, expected_status=200):
    """Test a single endpoint"""
    try:
        url = f"{API_BASE}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == expected_status:
            try:
                result = response.json()
                return True, result
            except:
                return True, response.text
        else:
            return False, f"Status {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

def main():
    print("🔍 News Intelligence System Verification")
    print("=" * 50)
    print(f"Testing at: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test results
    results = {
        "passed": 0,
        "failed": 0,
        "total": 0
    }
    
    # Core API Endpoints
    endpoints = [
        ("/health/", "Health Check"),
        ("/articles/", "Articles List"),
        ("/articles/sources", "Article Sources"),
        ("/rss/feeds/", "RSS Feeds"),
        ("/rss/feeds/", "RSS Feeds (POST)", "POST", {
            "name": "Test Feed",
            "url": "https://example.com/feed.xml",
            "category": "test",
            "tier": 3,
            "priority": 5,
            "language": "en"
        }),
    ]
    
    print("📡 Testing Core API Endpoints")
    print("-" * 30)
    
    for endpoint, description, *args in endpoints:
        method = args[0] if args else "GET"
        data = args[1] if len(args) > 1 else None
        expected_status = 200
        
        if method == "POST" and "Test Feed" in description:
            expected_status = 200  # Should succeed or fail gracefully
        
        results["total"] += 1
        success, response = test_endpoint(endpoint, method, data, expected_status)
        
        if success:
            print(f"✅ {description}")
            if isinstance(response, dict) and "data" in response:
                data_info = response["data"]
                if isinstance(data_info, dict):
                    if "articles" in data_info:
                        print(f"   📄 {len(data_info['articles'])} articles")
                    elif "feeds" in data_info:
                        print(f"   📡 {len(data_info['feeds'])} feeds")
                    elif "sources" in data_info:
                        print(f"   🏢 {len(data_info['sources'])} sources")
            results["passed"] += 1
        else:
            print(f"❌ {description}: {response}")
            results["failed"] += 1
        print()
    
    # Database Connectivity Tests
    print("🗄️  Testing Database Connectivity")
    print("-" * 30)
    
    # Test articles endpoint for database connectivity
    success, response = test_endpoint("/articles/")
    if success and isinstance(response, dict):
        data = response.get("data", {})
        total_articles = data.get("total_count", 0)
        print(f"✅ Database Connection: {total_articles} articles in database")
        results["passed"] += 1
    else:
        print(f"❌ Database Connection: {response}")
        results["failed"] += 1
    results["total"] += 1
    print()
    
    # RSS Collection Test
    print("📡 Testing RSS Collection")
    print("-" * 30)
    
    success, response = test_endpoint("/rss/feeds/")
    if success and isinstance(response, dict):
        feeds = response.get("data", {}).get("feeds", [])
        active_feeds = [f for f in feeds if f.get("is_active", False)]
        print(f"✅ RSS Feeds: {len(feeds)} total, {len(active_feeds)} active")
        results["passed"] += 1
    else:
        print(f"❌ RSS Feeds: {response}")
        results["failed"] += 1
    results["total"] += 1
    print()
    
    # System Health Check
    print("🏥 Testing System Health")
    print("-" * 30)
    
    success, response = test_endpoint("/health/")
    if success and isinstance(response, dict):
        health_data = response.get("data", {})
        status = health_data.get("status", "unknown")
        services = health_data.get("services", {})
        
        print(f"✅ System Status: {status}")
        for service, service_data in services.items():
            service_status = service_data.get("status", "unknown")
            print(f"   {service}: {service_status}")
        results["passed"] += 1
    else:
        print(f"❌ Health Check: {response}")
        results["failed"] += 1
    results["total"] += 1
    print()
    
    # Performance Test
    print("⚡ Testing Performance")
    print("-" * 30)
    
    start_time = time.time()
    success, response = test_endpoint("/articles/")
    end_time = time.time()
    
    if success:
        response_time = (end_time - start_time) * 1000
        print(f"✅ Articles API Response Time: {response_time:.2f}ms")
        if response_time < 1000:
            print("   🚀 Excellent performance")
        elif response_time < 2000:
            print("   ✅ Good performance")
        else:
            print("   ⚠️  Slow performance")
        results["passed"] += 1
    else:
        print(f"❌ Performance Test: {response}")
        results["failed"] += 1
    results["total"] += 1
    print()
    
    # Summary
    print("📊 Verification Summary")
    print("=" * 50)
    print(f"Total Tests: {results['total']}")
    print(f"Passed: {results['passed']} ✅")
    print(f"Failed: {results['failed']} ❌")
    print(f"Success Rate: {(results['passed']/results['total']*100):.1f}%")
    print()
    
    if results["failed"] == 0:
        print("🎉 All tests passed! System is fully operational.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
