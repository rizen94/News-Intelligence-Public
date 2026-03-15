"""
Unit tests for API endpoints
Tests individual endpoint functionality
"""

import pytest
import requests
from tests.conftest import TestConfig, TestUtils

class TestAPIEndpoints:
    """Test individual API endpoints"""
    
    def test_health_endpoint(self, api_client):
        """Test system health endpoint"""
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/system_monitoring/status")
        TestUtils.assert_response_success(response)
        
        data = response.json()
        assert "data" in data
        assert "overall_status" in data["data"]
        assert data["data"]["overall_status"] in ["healthy", "degraded", "error"]
    
    def test_articles_endpoint(self, api_client):
        """Test articles endpoint"""
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/articles")
        TestUtils.assert_response_success(response)
        
        data = response.json()
        TestUtils.assert_data_integrity(data["data"], ["articles", "total", "page", "limit"])
        
        # Verify article structure
        if data["data"]["articles"]:
            article = data["data"]["articles"][0]
            TestUtils.assert_data_integrity(article, ["id", "title", "url", "source_domain"])
    
    def test_storylines_endpoint(self, api_client):
        """Test storylines endpoint"""
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/politics/storylines")
        TestUtils.assert_response_success(response)
        
        data = response.json()
        TestUtils.assert_data_integrity(data["data"], ["storylines", "total"])
        
        # Verify storyline structure
        if data["data"]["storylines"]:
            storyline = data["data"]["storylines"][0]
            TestUtils.assert_data_integrity(storyline, ["id", "title", "description"])
    
    def test_topics_endpoint(self, api_client):
        """Test topics endpoint"""
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/politics/content_analysis/topics")
        TestUtils.assert_response_success(response)
        
        data = response.json()
        TestUtils.assert_data_integrity(data["data"], ["topics", "total"])
    
    def test_word_cloud_endpoint(self, api_client):
        """Test word cloud endpoint"""
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/politics/content_analysis/topics/word_cloud")
        TestUtils.assert_response_success(response)
        
        data = response.json()
        TestUtils.assert_data_integrity(data["data"], ["word_cloud", "total_topics"])
        
        # Test intelligent filtering
        TestUtils.assert_no_noise_words(data["data"])
    
    def test_rss_feeds_endpoint(self, api_client):
        """Test RSS feeds endpoint"""
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/politics/rss_feeds")
        TestUtils.assert_response_success(response)
        
        data = response.json()
        TestUtils.assert_data_integrity(data["data"], ["feeds", "total"])
        
        # Verify RSS feed structure
        if data["data"]["feeds"]:
            feed = data["data"]["feeds"][0]
            TestUtils.assert_data_integrity(feed, ["id", "feed_name", "feed_url", "is_active"])
