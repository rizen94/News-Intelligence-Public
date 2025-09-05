#!/usr/bin/env python3
"""
Test script for articles refresh functionality
Tests database calls, API responses, and refresh behavior
"""

import requests
import json
import time
from datetime import datetime

def test_articles_api():
    """Test articles API functionality"""
    print("=== Testing Articles API ===")
    
    base_url = "http://localhost:8000/api"
    
    # Test 1: Basic articles endpoint
    print("1. Testing basic articles endpoint...")
    response = requests.get(f"{base_url}/articles/?limit=5")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Articles count: {len(data['data']['articles'])}")
        print(f"   📄 First article: {data['data']['articles'][0]['title'][:50]}...")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False
    
    # Test 2: Articles with different parameters
    print("\n2. Testing articles with different parameters...")
    params = {
        'page': 1,
        'per_page': 10,
        'sort_by': 'created_at',
        'sort_order': 'desc'
    }
    response = requests.get(f"{base_url}/articles/", params=params)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Articles count: {len(data['data']['articles'])}")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False
    
    # Test 3: Articles stats
    print("\n3. Testing articles stats...")
    response = requests.get(f"{base_url}/articles/stats/overview")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Total articles: {data['data']['total_articles']}")
        print(f"   📊 By status: {data['data']['by_status']}")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False
    
    # Test 4: Sources endpoint
    print("\n4. Testing sources endpoint...")
    response = requests.get(f"{base_url}/articles/sources")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Sources count: {len(data['data'])}")
        if data['data']:
            print(f"   📄 Top source: {data['data'][0]['name']} ({data['data'][0]['count']} articles)")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False
    
    # Test 5: Categories endpoint
    print("\n5. Testing categories endpoint...")
    response = requests.get(f"{base_url}/articles/categories")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Categories count: {len(data['data'])}")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False
    
    return True

def test_refresh_behavior():
    """Test refresh behavior by making multiple requests"""
    print("\n=== Testing Refresh Behavior ===")
    
    base_url = "http://localhost:8000/api"
    
    # Make multiple requests to simulate refresh
    print("1. Making multiple requests to simulate refresh...")
    
    for i in range(3):
        print(f"   Request {i+1}...")
        response = requests.get(f"{base_url}/articles/?limit=3")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {len(data['data']['articles'])} articles")
            # Check if we get fresh data (different timestamps)
            if data['data']['articles']:
                first_article = data['data']['articles'][0]
                print(f"   📄 First article created: {first_article['created_at']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            return False
        
        time.sleep(1)  # Wait 1 second between requests
    
    return True

def test_database_connection_health():
    """Test database connection health"""
    print("\n=== Testing Database Connection Health ===")
    
    base_url = "http://localhost:8000/api"
    
    # Test health endpoint
    print("1. Testing database health...")
    response = requests.get(f"{base_url}/health/")
    if response.status_code == 200:
        data = response.json()
        db_health = data['services']['database']
        print(f"   ✅ Database status: {db_health['status']}")
        print(f"   📊 Response time: {db_health['response_time_ms']}ms")
        print(f"   🔗 Pool status: {db_health.get('pool_status', {}).get('status', 'unknown')}")
    else:
        print(f"   ❌ Health check failed: {response.status_code}")
        return False
    
    return True

def test_frontend_integration():
    """Test frontend integration"""
    print("\n=== Testing Frontend Integration ===")
    
    # Test frontend articles page
    print("1. Testing frontend articles page...")
    response = requests.get("http://localhost:3001/articles")
    if response.status_code == 200:
        print("   ✅ Frontend articles page accessible")
        # Check if it contains expected content
        if "Articles" in response.text:
            print("   ✅ Frontend contains expected content")
        else:
            print("   ⚠️  Frontend may not be loading articles properly")
    else:
        print(f"   ❌ Frontend not accessible: {response.status_code}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🔧 Testing Articles Refresh Functionality")
    print("=" * 50)
    
    tests = [
        ("Articles API", test_articles_api),
        ("Refresh Behavior", test_refresh_behavior),
        ("Database Health", test_database_connection_health),
        ("Frontend Integration", test_frontend_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Articles refresh functionality is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
