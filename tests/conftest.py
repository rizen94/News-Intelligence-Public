"""
Pytest configuration and fixtures for News Intelligence System v4.0
"""

import pytest
import os
import sys
import json
import requests
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add API directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))

class TestConfig:
    """Test configuration and constants"""
    
    API_BASE_URL = "http://localhost:8001"
    DB_CONFIG = {
        "host": "localhost",
        "database": "news_intelligence",
        "user": "newsapp",
        "password": "newsapp_password",
        "port": "5432"
    }
    
    TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')
    
    # Test data templates
    SAMPLE_ARTICLE = {
        "title": "Test Article for Comprehensive Testing",
        "url": "https://example.com/test-article",
        "content": "This is a comprehensive test article about technology, innovation, and artificial intelligence. It contains multiple paragraphs with various topics and entities.",
        "summary": "A test article about technology and AI",
        "source_domain": "example.com",
        "published_at": datetime.now().isoformat(),
        "word_count": 25,
        "processing_status": "pending"
    }
    
    SAMPLE_STORYLINE = {
        "title": "Test Storyline for Comprehensive Testing",
        "description": "A comprehensive test storyline to verify all functionality",
        "processing_status": "active"
    }
    
    SAMPLE_RSS_FEED = {
        "feed_name": "Test RSS Feed",
        "feed_url": "https://feeds.bbci.co.uk/news/rss.xml",
        "is_active": True,
        "fetch_interval_seconds": 3600
    }

@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration"""
    return TestConfig()

@pytest.fixture(scope="session")
def api_client():
    """Provide API client for testing"""
    return requests.Session()

@pytest.fixture(scope="session")
def db_connection():
    """Provide database connection for testing"""
    try:
        conn = psycopg2.connect(**TestConfig.DB_CONFIG)
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Database connection failed: {e}")

@pytest.fixture(scope="function")
def clean_test_data(db_connection):
    """Clean up test data before and after each test"""
    with db_connection.cursor() as cur:
        # Clean up test data
        cur.execute("DELETE FROM storyline_articles WHERE storyline_id IN (SELECT id FROM storylines WHERE title LIKE 'Test%')")
        cur.execute("DELETE FROM storylines WHERE title LIKE 'Test%'")
        cur.execute("DELETE FROM articles WHERE title LIKE 'Test%'")
        cur.execute("DELETE FROM rss_feeds WHERE feed_name LIKE 'Test%'")
        db_connection.commit()
    
    yield
    
    # Clean up after test
    with db_connection.cursor() as cur:
        cur.execute("DELETE FROM storyline_articles WHERE storyline_id IN (SELECT id FROM storylines WHERE title LIKE 'Test%')")
        cur.execute("DELETE FROM storylines WHERE title LIKE 'Test%'")
        cur.execute("DELETE FROM articles WHERE title LIKE 'Test%'")
        cur.execute("DELETE FROM rss_feeds WHERE feed_name LIKE 'Test%'")
        db_connection.commit()

@pytest.fixture(scope="function")
def sample_article(test_config):
    """Provide sample article data"""
    return test_config.SAMPLE_ARTICLE.copy()

@pytest.fixture(scope="function")
def sample_storyline(test_config):
    """Provide sample storyline data"""
    return test_config.SAMPLE_STORYLINE.copy()

@pytest.fixture(scope="function")
def sample_rss_feed(test_config):
    """Provide sample RSS feed data"""
    return test_config.SAMPLE_RSS_FEED.copy()

class TestDataManager:
    """Manage test data creation and cleanup"""
    
    def __init__(self, api_client, db_connection):
        self.api = api_client
        self.db = db_connection
        self.created_resources = []
    
    def create_article(self, article_data):
        """Create a test article"""
        response = self.api.post(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/articles", 
                                json=article_data)
        if response.status_code == 200:
            article_id = response.json()["data"]["id"]
            self.created_resources.append(("article", article_id))
            return article_id
        return None
    
    def create_storyline(self, storyline_data):
        """Create a test storyline"""
        response = self.api.post(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines",
                                json=storyline_data)
        if response.status_code == 200:
            storyline_id = response.json()["data"]["storyline_id"]
            self.created_resources.append(("storyline", storyline_id))
            return storyline_id
        return None
    
    def create_rss_feed(self, feed_data):
        """Create a test RSS feed"""
        response = self.api.post(f"{TestConfig.API_BASE_URL}/api/v4/news-aggregation/rss-feeds",
                                json=feed_data)
        if response.status_code == 200:
            feed_id = response.json()["data"]["id"]
            self.created_resources.append(("rss_feed", feed_id))
            return feed_id
        return None
    
    def cleanup(self):
        """Clean up all created resources"""
        for resource_type, resource_id in self.created_resources:
            if resource_type == "article":
                self.api.delete(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/articles/{resource_id}")
            elif resource_type == "storyline":
                self.api.delete(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{resource_id}")
            elif resource_type == "rss_feed":
                self.api.delete(f"{TestConfig.API_BASE_URL}/api/v4/news-aggregation/rss-feeds/{resource_id}")

@pytest.fixture(scope="function")
def test_data_manager(api_client, db_connection):
    """Provide test data manager"""
    manager = TestDataManager(api_client, db_connection)
    yield manager
    manager.cleanup()

# Test utilities
class TestUtils:
    """Utility functions for testing"""
    
    @staticmethod
    def assert_response_success(response, expected_status=200):
        """Assert API response is successful"""
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success", True), f"Response indicates failure: {data}"
        return data
    
    @staticmethod
    def assert_data_integrity(data, expected_fields):
        """Assert data contains expected fields"""
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
            assert data[field] is not None, f"Field {field} is None"
    
    @staticmethod
    def assert_no_noise_words(word_cloud_data, noise_words=None):
        """Assert word cloud doesn't contain noise words"""
        if noise_words is None:
            noise_words = ["www", "thursday", "href", "https", "com", "as", "its", "first", "after", "from", "said"]
        
        if "word_cloud" in word_cloud_data:
            word_cloud = word_cloud_data["word_cloud"]
            found_noise = [topic["text"].lower() for topic in word_cloud if topic["text"].lower() in noise_words]
            assert len(found_noise) == 0, f"Found noise words: {found_noise}"

@pytest.fixture(scope="session")
def test_utils():
    """Provide test utilities"""
    return TestUtils
