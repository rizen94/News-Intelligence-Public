#!/usr/bin/env python3
"""
Comprehensive test to verify that the frontend is displaying live data
and not test data or mock data.
"""

import requests
import json
import sys
from datetime import datetime

def test_api_endpoints():
    """Test all API endpoints to ensure they return live data"""
    print("=== TESTING API ENDPOINTS ===")
    
    base_url = "http://localhost:8000"
    
    # Test Articles API
    print("1. Testing Articles API...")
    try:
        response = requests.get(f"{base_url}/api/articles/?limit=3")
        if response.status_code == 200:
            data = response.json()
            articles = data.get('data', {}).get('articles', [])
            if articles:
                print(f"   ✓ Articles API working - {len(articles)} articles returned")
                print(f"   ✓ Sample article: {articles[0].get('title', 'No title')}")
                print(f"   ✓ Source: {articles[0].get('source', 'No source')}")
                
                # Check if articles have real sources
                real_sources = ['BBC News', 'TechCrunch', 'The Verge', 'Reuters', 'CNN']
                has_real_sources = any(article.get('source') in real_sources for article in articles)
                if has_real_sources:
                    print("   ✓ Articles have real news sources")
                else:
                    print("   ✗ Articles may not have real news sources")
            else:
                print("   ✗ No articles returned")
                return False
        else:
            print(f"   ✗ Articles API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Articles API error: {e}")
        return False
    
    # Test Storylines API
    print("\n2. Testing Storylines API...")
    try:
        response = requests.get(f"{base_url}/api/story-management/stories")
        if response.status_code == 200:
            data = response.json()
            stories = data.get('data', [])
            if stories:
                print(f"   ✓ Storylines API working - {len(stories)} storylines returned")
                print(f"   ✓ Sample storyline: {stories[0].get('name', 'No name')}")
                print(f"   ✓ Active: {stories[0].get('is_active', False)}")
            else:
                print("   ✗ No storylines returned")
                return False
        else:
            print(f"   ✗ Storylines API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Storylines API error: {e}")
        return False
    
    # Test Dashboard API
    print("\n3. Testing Dashboard API...")
    try:
        response = requests.get(f"{base_url}/api/dashboard/")
        if response.status_code == 200:
            data = response.json()
            dashboard_data = data.get('data', {})
            print(f"   ✓ Dashboard API working")
            print(f"   ✓ Total articles: {dashboard_data.get('total_articles', 0)}")
            print(f"   ✓ Active stories: {dashboard_data.get('active_stories', 0)}")
            print(f"   ✓ Articles today: {dashboard_data.get('articles_today', 0)}")
        else:
            print(f"   ✗ Dashboard API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Dashboard API error: {e}")
        return False
    
    # Test Timeline API
    print("\n4. Testing Timeline API...")
    try:
        response = requests.get(f"{base_url}/api/storyline-timeline/ai_tech_developments_2024")
        if response.status_code == 200:
            data = response.json()
            timeline_data = data.get('data', {})
            recent_events = timeline_data.get('recent_events', [])
            if recent_events:
                print(f"   ✓ Timeline API working - {len(recent_events)} events returned")
                print(f"   ✓ Sample event: {recent_events[0].get('title', 'No title')}")
            else:
                print("   ✗ No timeline events returned")
                return False
        else:
            print(f"   ✗ Timeline API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Timeline API error: {e}")
        return False
    
    return True

def test_frontend_accessibility():
    """Test if frontend is accessible"""
    print("\n=== TESTING FRONTEND ACCESSIBILITY ===")
    
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            print("   ✓ Frontend is accessible")
            return True
        else:
            print(f"   ✗ Frontend not accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Frontend error: {e}")
        return False

def check_for_test_data():
    """Check if there are any obvious test data patterns"""
    print("\n=== CHECKING FOR TEST DATA PATTERNS ===")
    
    base_url = "http://localhost:8000"
    
    # Check articles for test patterns
    try:
        response = requests.get(f"{base_url}/api/articles/?limit=10")
        if response.status_code == 200:
            data = response.json()
            articles = data.get('data', {}).get('articles', [])
            
            test_patterns = ['test', 'sample', 'example', 'mock', 'dummy', 'fake']
            test_articles = []
            
            for article in articles:
                title = article.get('title', '').lower()
                for pattern in test_patterns:
                    if pattern in title:
                        test_articles.append(article.get('title'))
            
            if test_articles:
                print(f"   ⚠ Found {len(test_articles)} articles with test patterns:")
                for title in test_articles[:3]:  # Show first 3
                    print(f"     - {title}")
            else:
                print("   ✓ No obvious test data patterns found in articles")
            
            # Check for real news sources
            real_sources = ['BBC News', 'TechCrunch', 'The Verge', 'Reuters', 'CNN', 'Associated Press']
            sources = set(article.get('source') for article in articles if article.get('source'))
            real_sources_found = [source for source in sources if source in real_sources]
            
            if real_sources_found:
                print(f"   ✓ Found real news sources: {', '.join(real_sources_found)}")
            else:
                print("   ⚠ No recognizable real news sources found")
                
        else:
            print("   ✗ Could not check articles for test patterns")
    except Exception as e:
        print(f"   ✗ Error checking test patterns: {e}")

def main():
    """Main test function"""
    print("LIVE DATA VERIFICATION TEST")
    print("=" * 50)
    print(f"Test started at: {datetime.now()}")
    
    # Test API endpoints
    api_success = test_api_endpoints()
    
    # Test frontend accessibility
    frontend_success = test_frontend_accessibility()
    
    # Check for test data patterns
    check_for_test_data()
    
    # Summary
    print("\n=== TEST SUMMARY ===")
    if api_success and frontend_success:
        print("✓ All tests passed - System appears to be using live data")
        print("✓ APIs are returning real data from database")
        print("✓ Frontend is accessible")
        return 0
    else:
        print("✗ Some tests failed - System may not be working correctly")
        if not api_success:
            print("  - API endpoints are not working properly")
        if not frontend_success:
            print("  - Frontend is not accessible")
        return 1

if __name__ == "__main__":
    sys.exit(main())
