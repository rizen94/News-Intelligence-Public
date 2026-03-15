"""
Performance and load tests
Tests system performance under various loads
"""

import pytest
import requests
import time
import concurrent.futures
from tests.conftest import TestConfig, TestUtils

class TestPerformanceAndLoad:
    """Test system performance and load handling"""
    
    def test_concurrent_requests(self, api_client):
        """Test system handling of concurrent requests"""
        print("⚡ Testing concurrent request handling...")
        
        def make_request():
            response = api_client.get(f"{TestConfig.API_BASE_URL}/api/articles")
            return response.status_code == 200
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(results), "Some concurrent requests failed"
        print("✅ Concurrent request handling test passed!")
    
    def test_response_times(self, api_client):
        """Test API response times"""
        print("⏱️ Testing API response times...")
        
        endpoints_to_test = [
            "/api/system_monitoring/status",
            "/api/articles",
            "/api/politics/storylines",
            "/api/politics/content_analysis/topics/word_cloud"
        ]
        
        max_response_time = 2.0  # 2 seconds max
        
        for endpoint in endpoints_to_test:
            start_time = time.time()
            response = api_client.get(f"{TestConfig.API_BASE_URL}{endpoint}")
            end_time = time.time()
            
            response_time = end_time - start_time
            assert response_time < max_response_time, f"Response time too slow for {endpoint}: {response_time:.2f}s"
            assert response.status_code == 200, f"Request failed for {endpoint}: {response.status_code}"
        
        print("✅ Response time test passed!")
    
    def test_large_data_handling(self, api_client, test_data_manager):
        """Test system handling of large data sets"""
        print("📊 Testing large data handling...")
        
        # Create multiple articles
        article_ids = []
        for i in range(20):
            article_data = {
                "title": f"Large Dataset Test Article {i}",
                "url": f"https://example.com/large-dataset-article-{i}",
                "content": f"This is a test article {i} for testing large dataset handling. " * 10,  # Long content
                "source_domain": "example.com",
                "published_at": TestConfig.SAMPLE_ARTICLE["published_at"]
            }
            article_id = test_data_manager.create_article(article_data)
            if article_id:
                article_ids.append(article_id)
        
        # Test retrieving all articles
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/articles")
        TestUtils.assert_response_success(response)
        
        data = response.json()["data"]
        assert len(data["articles"]) >= len(article_ids), "Should retrieve all created articles"
        
        # Test pagination
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/articles", 
                                params={"limit": 10, "page": 1})
        TestUtils.assert_response_success(response)
        
        data = response.json()["data"]
        assert len(data["articles"]) <= 10, "Pagination should limit results"
        
        print("✅ Large data handling test passed!")
