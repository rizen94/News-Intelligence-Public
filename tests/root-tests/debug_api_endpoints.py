#!/usr/bin/env python3
"""
Debug API endpoints to identify specific issues
"""

import requests
import json

def test_endpoint(endpoint, expected_fields=None):
    """Test a specific endpoint and analyze the response"""
    print(f"\n🔍 Testing {endpoint}")
    print("-" * 50)
    
    try:
        response = requests.get(f"http://localhost:8001{endpoint}", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response Type: {type(data)}")
                print(f"Response Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                
                if isinstance(data, dict) and 'data' in data:
                    print(f"Data Keys: {list(data['data'].keys())}")
                    if 'articles' in data['data']:
                        print(f"Articles Count: {len(data['data']['articles'])}")
                        if len(data['data']['articles']) > 0:
                            article = data['data']['articles'][0]
                            print(f"Sample Article Keys: {list(article.keys())}")
                    elif 'feeds' in data['data']:
                        print(f"Feeds Count: {len(data['data']['feeds'])}")
                        if len(data['data']['feeds']) > 0:
                            feed = data['data']['feeds'][0]
                            print(f"Sample Feed Keys: {list(feed.keys())}")
                    elif 'storylines' in data['data']:
                        print(f"Storylines Count: {len(data['data']['storylines'])}")
                        if len(data['data']['storylines']) > 0:
                            storyline = data['data']['storylines'][0]
                            print(f"Sample Storyline Keys: {list(storyline.keys())}")
                
                print("✅ Endpoint working correctly")
                return True
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                print(f"Raw response: {response.text[:200]}...")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Request error: {e}")
        return False

# Test all endpoints
endpoints = [
    "/api/v4/system-monitoring/health",
    "/api/v4/news-aggregation/articles/recent",
    "/api/v4/news-aggregation/rss-feeds",
    "/api/v4/storyline-management/storylines"
]

for endpoint in endpoints:
    test_endpoint(endpoint)
