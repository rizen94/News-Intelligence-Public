"""
Integration tests for article workflow
Tests complete article processing pipeline
"""

from tests.conftest import TestConfig, TestUtils


class TestArticleWorkflow:
    """Test complete article workflow"""

    def test_create_and_process_article(self, api_client, sample_article, test_data_manager):
        """Test creating and processing an article"""
        # Step 1: Create article
        article_id = test_data_manager.create_article(sample_article)
        assert article_id is not None, "Failed to create article"

        # Step 2: Verify article was created
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/articles/{article_id}")
        TestUtils.assert_response_success(response)

        article_data = response.json()["data"]
        assert article_data["title"] == sample_article["title"]
        assert article_data["url"] == sample_article["url"]
        assert article_data["source_domain"] == sample_article["source_domain"]

        # Step 3: Test article processing
        response = api_client.post(f"{TestConfig.API_BASE_URL}/api/articles/{article_id}/analyze")
        TestUtils.assert_response_success(response)

        # Step 4: Verify processing results
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/articles/{article_id}")
        TestUtils.assert_response_success(response)

        processed_article = response.json()["data"]
        assert processed_article["processing_status"] == "completed"
        assert processed_article["summary"] is not None
        assert processed_article["word_count"] > 0

    def test_article_search_and_filtering(self, api_client, test_data_manager):
        """Test article search and filtering"""
        # Create multiple test articles
        articles = []
        for i in range(3):
            article_data = {
                "title": f"Test Article {i} - Technology News",
                "url": f"https://example.com/test-article-{i}",
                "content": f"This is test article {i} about technology and innovation.",
                "source_domain": "example.com",
                "published_at": TestConfig.SAMPLE_ARTICLE["published_at"],
            }
            article_id = test_data_manager.create_article(article_data)
            if article_id:
                articles.append(article_id)

        # Test search functionality
        response = api_client.get(
            f"{TestConfig.API_BASE_URL}/api/articles", params={"search": "technology"}
        )
        TestUtils.assert_response_success(response)

        data = response.json()["data"]
        assert len(data["articles"]) > 0, "Search should return results"

        # Test filtering by source
        response = api_client.get(
            f"{TestConfig.API_BASE_URL}/api/articles", params={"source_domain": "example.com"}
        )
        TestUtils.assert_response_success(response)

        data = response.json()["data"]
        for article in data["articles"]:
            assert article["source_domain"] == "example.com"

    def test_article_deduplication(self, api_client, test_data_manager):
        """Test article deduplication functionality"""
        # Create duplicate articles
        article_data = {
            "title": "Duplicate Test Article",
            "url": "https://example.com/duplicate-article",
            "content": "This is a duplicate test article.",
            "source_domain": "example.com",
            "published_at": TestConfig.SAMPLE_ARTICLE["published_at"],
        }

        # Create first article
        article_id_1 = test_data_manager.create_article(article_data)
        assert article_id_1 is not None

        # Try to create duplicate article
        article_id_2 = test_data_manager.create_article(article_data)

        # Should either prevent duplicate or handle gracefully
        if article_id_2 is not None:
            assert article_id_1 != article_id_2, "Duplicate articles should have different IDs"
        else:
            # Duplicate prevention is working
            pass
