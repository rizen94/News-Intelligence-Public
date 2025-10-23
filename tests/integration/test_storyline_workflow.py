"""
Integration tests for storyline workflow
Tests complete storyline management pipeline
"""

import pytest
import requests
from tests.conftest import TestConfig, TestUtils

class TestStorylineWorkflow:
    """Test complete storyline workflow"""
    
    def test_create_and_manage_storyline(self, api_client, sample_storyline, test_data_manager):
        """Test creating and managing a storyline"""
        # Step 1: Create storyline
        storyline_id = test_data_manager.create_storyline(sample_storyline)
        assert storyline_id is not None, "Failed to create storyline"
        
        # Step 2: Verify storyline was created
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}")
        TestUtils.assert_response_success(response)
        
        storyline_data = response.json()["data"]
        assert storyline_data["title"] == sample_storyline["title"]
        assert storyline_data["description"] == sample_storyline["description"]
        
        # Step 3: Create test articles
        articles = []
        for i in range(3):
            article_data = {
                "title": f"Test Article {i} for Storyline",
                "url": f"https://example.com/storyline-article-{i}",
                "content": f"This is test article {i} for the storyline.",
                "source_domain": "example.com",
                "published_at": TestConfig.SAMPLE_ARTICLE["published_at"]
            }
            article_id = test_data_manager.create_article(article_data)
            if article_id:
                articles.append(article_id)
        
        # Step 4: Add articles to storyline
        for article_id in articles:
            response = api_client.post(
                f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}/articles/{article_id}",
                json={"relevance_score": 0.8}
            )
            TestUtils.assert_response_success(response)
        
        # Step 5: Verify articles are in storyline
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}")
        TestUtils.assert_response_success(response)
        
        storyline_data = response.json()["data"]
        assert storyline_data["article_count"] == len(articles)
        
        # Step 6: Test timeline generation
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}/timeline")
        TestUtils.assert_response_success(response)
        
        timeline_data = response.json()["data"]
        assert "timeline_events" in timeline_data
    
    def test_storyline_article_management(self, api_client, test_data_manager):
        """Test adding and removing articles from storylines"""
        # Create storyline and articles
        storyline_id = test_data_manager.create_storyline(TestConfig.SAMPLE_STORYLINE)
        article_id = test_data_manager.create_article(TestConfig.SAMPLE_ARTICLE)
        
        assert storyline_id is not None and article_id is not None
        
        # Add article to storyline
        response = api_client.post(
            f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}/articles/{article_id}",
            json={"relevance_score": 0.9}
        )
        TestUtils.assert_response_success(response)
        
        # Verify article is in storyline
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}")
        TestUtils.assert_response_success(response)
        
        storyline_data = response.json()["data"]
        assert storyline_data["article_count"] == 1
        
        # Remove article from storyline
        response = api_client.delete(
            f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}/articles/{article_id}"
        )
        TestUtils.assert_response_success(response)
        
        # Verify article is removed
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}")
        TestUtils.assert_response_success(response)
        
        storyline_data = response.json()["data"]
        assert storyline_data["article_count"] == 0
    
    def test_storyline_timeline_generation(self, api_client, test_data_manager):
        """Test storyline timeline generation"""
        # Create storyline with articles
        storyline_id = test_data_manager.create_storyline(TestConfig.SAMPLE_STORYLINE)
        
        # Add multiple articles with different dates
        articles = []
        for i in range(3):
            article_data = {
                "title": f"Timeline Test Article {i}",
                "url": f"https://example.com/timeline-article-{i}",
                "content": f"This is timeline test article {i}.",
                "source_domain": "example.com",
                "published_at": (TestConfig.SAMPLE_ARTICLE["published_at"] + f"+0{i}:00:00")
            }
            article_id = test_data_manager.create_article(article_data)
            if article_id:
                articles.append(article_id)
                
                # Add to storyline
                response = api_client.post(
                    f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}/articles/{article_id}",
                    json={"relevance_score": 0.7}
                )
                TestUtils.assert_response_success(response)
        
        # Generate timeline
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/{storyline_id}/timeline")
        TestUtils.assert_response_success(response)
        
        timeline_data = response.json()["data"]
        assert "timeline_events" in timeline_data
        assert len(timeline_data["timeline_events"]) > 0
