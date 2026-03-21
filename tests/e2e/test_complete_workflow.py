"""
End-to-end tests for complete workflows
Tests full user journeys from start to finish
"""

import time

from tests.conftest import TestConfig, TestUtils


class TestCompleteWorkflow:
    """Test complete end-to-end workflows"""

    def test_news_intelligence_complete_workflow(self, api_client, test_data_manager):
        """Test complete news intelligence workflow from RSS to analysis"""
        print("🚀 Testing complete news intelligence workflow...")

        # Step 1: Create RSS feed
        rss_feed_id = test_data_manager.create_rss_feed(TestConfig.SAMPLE_RSS_FEED)
        assert rss_feed_id is not None, "Failed to create RSS feed"

        # Step 2: Fetch articles from RSS feed
        response = api_client.post(f"{TestConfig.API_BASE_URL}/api/fetch_articles")
        TestUtils.assert_response_success(response)

        # Step 3: Wait for articles to be processed
        time.sleep(3)

        # Step 4: Get articles
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/articles")
        TestUtils.assert_response_success(response)

        articles = response.json()["data"]["articles"]
        assert len(articles) > 0, "Should have articles from RSS feed"

        # Step 5: Create storyline
        storyline_id = test_data_manager.create_storyline(TestConfig.SAMPLE_STORYLINE)
        assert storyline_id is not None, "Failed to create storyline"

        # Step 6: Add articles to storyline
        for article in articles[:3]:  # Add first 3 articles
            response = api_client.post(
                f"{TestConfig.API_BASE_URL}/api/politics/storylines/{storyline_id}/articles/{article['id']}",
                json={"relevance_score": 0.8},
            )
            TestUtils.assert_response_success(response)

        # Step 7: Generate timeline
        response = api_client.get(
            f"{TestConfig.API_BASE_URL}/api/politics/storylines/{storyline_id}/timeline"
        )
        TestUtils.assert_response_success(response)

        timeline_data = response.json()["data"]
        assert len(timeline_data["timeline_events"]) > 0, "Should have timeline events"

        # Step 8: Trigger topic clustering
        response = api_client.post(
            f"{TestConfig.API_BASE_URL}/api/politics/content_analysis/topics/cluster"
        )
        TestUtils.assert_response_success(response)

        # Step 9: Get topic analysis
        response = api_client.get(
            f"{TestConfig.API_BASE_URL}/api/politics/content_analysis/topics/word_cloud"
        )
        TestUtils.assert_response_success(response)

        word_cloud_data = response.json()["data"]
        assert len(word_cloud_data["word_cloud"]) > 0, "Should have word cloud data"

        # Step 10: Verify system monitoring
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/system_monitoring/status")
        TestUtils.assert_response_success(response)

        monitoring_data = response.json()["data"]
        assert monitoring_data["database"]["total_articles"] > 0
        assert monitoring_data["database"]["total_storylines"] > 0

        print("✅ Complete workflow test passed!")

    def test_data_consistency_across_operations(self, api_client, test_data_manager):
        """Test data consistency across all operations"""
        print("🔍 Testing data consistency across operations...")

        # Create test data
        article_id = test_data_manager.create_article(TestConfig.SAMPLE_ARTICLE)
        storyline_id = test_data_manager.create_storyline(TestConfig.SAMPLE_STORYLINE)

        assert article_id is not None and storyline_id is not None

        # Add article to storyline
        response = api_client.post(
            f"{TestConfig.API_BASE_URL}/api/politics/storylines/{storyline_id}/articles/{article_id}",
            json={"relevance_score": 0.9},
        )
        TestUtils.assert_response_success(response)

        # Verify consistency across endpoints
        endpoints_to_check = [
            f"/api/articles/{article_id}",
            f"/api/politics/storylines/{storyline_id}",
            "/api/system_monitoring/status",
        ]

        for endpoint in endpoints_to_check:
            response = api_client.get(f"{TestConfig.API_BASE_URL}{endpoint}")
            TestUtils.assert_response_success(response)

            # Verify data structure
            data = response.json()
            assert "success" in data or "data" in data, f"Invalid response structure for {endpoint}"

        print("✅ Data consistency test passed!")

    def test_error_recovery_and_resilience(self, api_client):
        """Test error recovery and system resilience"""
        print("🛡️ Testing error recovery and resilience...")

        # Test invalid requests
        invalid_requests = [
            ("GET", "/api/politics/storylines/99999", None),
            ("GET", "/api/articles/99999", None),
            ("POST", "/api/politics/storylines", {"invalid": "data"}),
            ("POST", "/api/articles", {"invalid": "data"}),
        ]

        for method, endpoint, data in invalid_requests:
            if method == "GET":
                response = api_client.get(f"{TestConfig.API_BASE_URL}{endpoint}")
            else:
                response = api_client.post(f"{TestConfig.API_BASE_URL}{endpoint}", json=data or {})

            # Should handle errors gracefully
            assert response.status_code in [400, 404, 422, 500], (
                f"Unexpected status code for {endpoint}: {response.status_code}"
            )

        # Test system recovery
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/system_monitoring/status")
        TestUtils.assert_response_success(response)

        print("✅ Error recovery test passed!")
