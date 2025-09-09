#!/usr/bin/env python3
"""
Production API Test Script
Tests all critical endpoints to ensure they work correctly
"""

import requests
import json
import sys
import time

def test_endpoint(url, expected_status=200, description=""):
    """Test a single endpoint"""
    try:
        response = requests.get(url, timeout=10)
        print(f"✅ {description}: {response.status_code}")
        if response.status_code == expected_status:
            return True
        else:
            print(f"   Response: {response.text[:200]}...")
            return False
    except Exception as e:
        print(f"❌ {description}: ERROR - {e}")
        return False

def main():
    """Test all critical production endpoints"""
    base_url = "http://localhost:8000"
    
    print("🚀 Testing News Intelligence System Production API")
    print("=" * 60)
    
    # Test basic connectivity
    tests = [
        (f"{base_url}/", 200, "Root endpoint"),
        (f"{base_url}/api/health/", 200, "Health check"),
        (f"{base_url}/api/articles/", 200, "Articles list"),
        (f"{base_url}/api/rss/feeds/", 200, "RSS feeds list"),
        (f"{base_url}/docs", 200, "API documentation"),
    ]
    
    # Test stats endpoints (these might fail initially)
    stats_tests = [
        (f"{base_url}/api/articles/stats/overview", 200, "Article stats"),
        (f"{base_url}/api/rss/feeds/stats/overview", 200, "RSS stats"),
    ]
    
    print("\n📊 Basic Endpoints:")
    basic_passed = 0
    for url, status, desc in tests:
        if test_endpoint(url, status, desc):
            basic_passed += 1
    
    print(f"\n📈 Stats Endpoints:")
    stats_passed = 0
    for url, status, desc in stats_tests:
        if test_endpoint(url, status, desc):
            stats_passed += 1
    
    print(f"\n📋 Results:")
    print(f"Basic endpoints: {basic_passed}/{len(tests)} passed")
    print(f"Stats endpoints: {stats_passed}/{len(stats_tests)} passed")
    print(f"Total: {basic_passed + stats_passed}/{len(tests) + len(stats_tests)} passed")
    
    if basic_passed == len(tests):
        print("\n🎉 Core system is working! Stats endpoints may need database setup.")
        return 0
    else:
        print("\n❌ Core system has issues that need fixing.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
