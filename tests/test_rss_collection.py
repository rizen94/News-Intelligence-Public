#!/usr/bin/env python3
"""
Test RSS Collection
Simple script to test RSS feed collection and verify it works
"""

import requests


def test_rss_collection():
    """Test RSS collection functionality"""
    api_base = "http://localhost:8000"

    print("🧪 Testing RSS Collection System")
    print("=" * 50)

    # Get current feeds
    print("📰 Current RSS Feeds:")
    feeds_response = requests.get(f"{api_base}/api/rss/feeds/")
    if feeds_response.status_code == 200:
        feeds_data = feeds_response.json()
        feeds = feeds_data.get("data", {}).get("feeds", [])
        print(f"   Total feeds: {len(feeds)}")
        for feed in feeds:
            print(f"   - {feed['id']}: {feed['name']} ({feed['url']})")
    else:
        print(f"   ❌ Failed to get feeds: {feeds_response.status_code}")
        return

    # Get current article count
    print("\n📊 Current Articles:")
    articles_response = requests.get(f"{api_base}/api/articles/?limit=10")
    if articles_response.status_code == 200:
        articles_data = articles_response.json()
        articles = articles_data.get("data", {}).get("articles", [])
        print(f"   Total articles: {len(articles)}")
        if articles:
            print("   Recent articles:")
            for article in articles[:3]:
                print(f"   - {article.get('title', 'No title')[:60]}...")
    else:
        print(f"   ❌ Failed to get articles: {articles_response.status_code}")

    # Test RSS collection by trying to refresh a feed
    print("\n🔄 Testing RSS Collection:")
    test_feed_id = 2  # Fox News Politics
    print(f"   Testing feed {test_feed_id} (Fox News Politics)...")

    refresh_response = requests.post(f"{api_base}/api/rss/feeds/{test_feed_id}/refresh")
    if refresh_response.status_code == 200:
        refresh_data = refresh_response.json()
        print(f"   ✅ Refresh successful: {refresh_data.get('message')}")
        print(f"   📈 Articles fetched: {refresh_data.get('data', {}).get('articles_fetched', 0)}")
    else:
        print(f"   ❌ Refresh failed: {refresh_response.status_code}")

    # Check if articles were added
    print("\n📊 Checking for new articles:")
    articles_response_after = requests.get(f"{api_base}/api/articles/?limit=10")
    if articles_response_after.status_code == 200:
        articles_data_after = articles_response_after.json()
        articles_after = articles_data_after.get("data", {}).get("articles", [])
        print(f"   Total articles after: {len(articles_after)}")

        if len(articles_after) > len(articles):
            print("   ✅ New articles detected!")
        else:
            print("   ℹ️ No new articles found (this is normal if feed was recently refreshed)")

    # Test ML processing
    print("\n🤖 Testing ML Processing:")
    if articles_after:
        # Try to process the first article
        first_article = articles_after[0]
        article_id = first_article.get("id")

        if article_id:
            ml_response = requests.post(f"{api_base}/api/storylines/1/process-ml")
            if ml_response.status_code == 200:
                ml_data = ml_response.json()
                print(f"   ✅ ML processing successful: {ml_data.get('message')}")
            else:
                print(f"   ❌ ML processing failed: {ml_response.status_code}")

    print("\n" + "=" * 50)
    print("🎯 RSS Collection Test Complete")


if __name__ == "__main__":
    test_rss_collection()
