#!/usr/bin/env python3
"""
Test script for Discover page refresh functionality
Tests database calls, API responses, and refresh behavior
"""

import requests
import json
import time
from datetime import datetime

def test_discover_api_calls():
    """Test API calls used by Discover page"""
    print("=== Testing Discover Page API Calls ===")
    
    base_url = "http://localhost:8000/api"
    
    # Test 1: Articles API with Discover parameters
    print("1. Testing articles API with Discover parameters...")
    params = {
        'limit': 20,
        'sort_by': 'created_at',
        'sort_order': 'desc'
    }
    response = requests.get(f"{base_url}/articles/", params=params)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Articles count: {len(data['data']['articles'])}")
        print(f"   📄 First article: {data['data']['articles'][0]['title'][:50]}...")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        print(f"   📄 Error: {response.text}")
        return False
    
    # Test 2: Storylines API
    print("\n2. Testing storylines API...")
    response = requests.get(f"{base_url}/story-management/stories")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Storylines count: {len(data['data'])}")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        print(f"   📄 Error: {response.text}")
        return False
    
    # Test 3: Articles API with cache-busting
    print("\n3. Testing articles API with cache-busting...")
    params['_t'] = int(time.time() * 1000)
    response = requests.get(f"{base_url}/articles/", params=params)
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Success: {data['success']}")
        print(f"   📊 Articles count: {len(data['data']['articles'])}")
    else:
        print(f"   ❌ Failed: {response.status_code}")
        return False
    
    return True

def test_discover_refresh_behavior():
    """Test refresh behavior by making multiple requests"""
    print("\n=== Testing Discover Refresh Behavior ===")
    
    base_url = "http://localhost:8000/api"
    
    # Make multiple requests to simulate refresh
    print("1. Making multiple requests to simulate refresh...")
    
    for i in range(3):
        print(f"   Request {i+1}...")
        params = {
            'limit': 20,
            'sort_by': 'created_at',
            'sort_order': 'desc',
            '_t': int(time.time() * 1000)
        }
        response = requests.get(f"{base_url}/articles/", params=params)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success: {len(data['data']['articles'])} articles")
            # Check if we get fresh data
            if data['data']['articles']:
                first_article = data['data']['articles'][0]
                print(f"   📄 First article created: {first_article['created_at']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
            return False
        
        time.sleep(1)  # Wait 1 second between requests
    
    return True

def test_discover_frontend_integration():
    """Test Discover page frontend integration"""
    print("\n=== Testing Discover Frontend Integration ===")
    
    # Test Discover page accessibility
    print("1. Testing Discover page accessibility...")
    response = requests.get("http://localhost:3001/discover")
    if response.status_code == 200:
        print("   ✅ Discover page accessible")
        # Check if it contains expected content
        if "Discover" in response.text:
            print("   ✅ Discover page contains expected content")
        else:
            print("   ⚠️  Discover page may not be loading properly")
    else:
        print(f"   ❌ Discover page not accessible: {response.status_code}")
        return False
    
    return True

def test_trending_topics_generation():
    """Test trending topics generation logic"""
    print("\n=== Testing Trending Topics Generation ===")
    
    base_url = "http://localhost:8000/api"
    
    # Get articles for trending topics generation
    print("1. Getting articles for trending topics generation...")
    response = requests.get(f"{base_url}/articles/?limit=20&sort_by=created_at&sort_order=desc")
    if response.status_code == 200:
        data = response.json()
        articles = data['data']['articles']
        print(f"   ✅ Retrieved {len(articles)} articles")
        
        # Simulate trending topics generation
        print("2. Simulating trending topics generation...")
        topic_counts = {}
        for article in articles:
            words = article['title'].lower().split()
            for word in words:
                if len(word) > 3:
                    topic_counts[word] = (topic_counts.get(word, 0) + 1)
        
        trending = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"   ✅ Generated {len(trending)} trending topics")
        print(f"   📊 Top topics: {[topic[0] for topic in trending[:5]]}")
    else:
        print(f"   ❌ Failed to get articles: {response.status_code}")
        return False
    
    return True

def test_database_connection_health():
    """Test database connection health for Discover page"""
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

def main():
    """Run all tests"""
    print("🔧 Testing Discover Page Refresh Functionality")
    print("=" * 50)
    
    tests = [
        ("Discover API Calls", test_discover_api_calls),
        ("Refresh Behavior", test_discover_refresh_behavior),
        ("Frontend Integration", test_discover_frontend_integration),
        ("Trending Topics Generation", test_trending_topics_generation),
        ("Database Health", test_database_connection_health)
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
        print("🎉 All tests passed! Discover page refresh functionality is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
