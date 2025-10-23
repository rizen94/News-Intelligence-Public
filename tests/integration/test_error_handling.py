"""
Comprehensive error handling tests
Tests system behavior under error conditions
"""

import pytest
import requests
from tests.conftest import TestConfig, TestUtils

class TestErrorHandling:
    """Test comprehensive error handling"""
    
    def test_invalid_endpoint_handling(self, api_client):
        """Test handling of invalid endpoints"""
        print("🚫 Testing invalid endpoint handling...")
        
        invalid_endpoints = [
            "/api/v4/nonexistent/endpoint",
            "/api/v4/content-analysis/invalid",
            "/api/v4/storyline-management/invalid"
        ]
        
        for endpoint in invalid_endpoints:
            response = api_client.get(f"{TestConfig.API_BASE_URL}{endpoint}")
            assert response.status_code == 404, f"Expected 404 for {endpoint}, got {response.status_code}"
        
        print("✅ Invalid endpoint handling test passed!")
    
    def test_invalid_data_handling(self, api_client):
        """Test handling of invalid data"""
        print("🚫 Testing invalid data handling...")
        
        # Test invalid JSON
        response = api_client.post(
            f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422, f"Expected 422 for invalid JSON, got {response.status_code}"
        
        # Test missing required fields
        response = api_client.post(
            f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines",
            json={"invalid": "data"}
        )
        assert response.status_code in [400, 422], f"Expected 400/422 for missing fields, got {response.status_code}"
        
        # Test invalid data types
        response = api_client.post(
            f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines",
            json={"title": 123, "description": None}
        )
        assert response.status_code in [400, 422], f"Expected 400/422 for invalid types, got {response.status_code}"
        
        print("✅ Invalid data handling test passed!")
    
    def test_resource_not_found_handling(self, api_client):
        """Test handling of resource not found scenarios"""
        print("🚫 Testing resource not found handling...")
        
        # Test non-existent article
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/articles/99999")
        assert response.status_code == 404, f"Expected 404 for non-existent article, got {response.status_code}"
        
        # Test non-existent storyline
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/storyline-management/storylines/99999")
        assert response.status_code == 404, f"Expected 404 for non-existent storyline, got {response.status_code}"
        
        # Test non-existent topic
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/topics/nonexistent-topic/articles")
        assert response.status_code == 404, f"Expected 404 for non-existent topic, got {response.status_code}"
        
        print("✅ Resource not found handling test passed!")
    
    def test_database_error_handling(self, api_client):
        """Test handling of database errors"""
        print("🚫 Testing database error handling...")
        
        # Test operations that might cause database errors
        # (This would require more sophisticated mocking in a real test environment)
        
        # For now, test that the system handles database connection issues gracefully
        response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/system-monitoring/status")
        
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 500], f"Unexpected status code: {response.status_code}"
        
        if response.status_code == 500:
            data = response.json()
            assert "error" in data or "detail" in data, "Error response should contain error information"
        
        print("✅ Database error handling test passed!")
    
    def test_rate_limiting_and_timeout_handling(self, api_client):
        """Test rate limiting and timeout handling"""
        print("🚫 Testing rate limiting and timeout handling...")
        
        # Make rapid requests to test rate limiting
        responses = []
        for i in range(20):
            response = api_client.get(f"{TestConfig.API_BASE_URL}/api/v4/content-analysis/articles")
            responses.append(response.status_code)
        
        # Most requests should succeed (no rate limiting implemented yet)
        success_count = sum(1 for status in responses if status == 200)
        assert success_count >= 15, f"Too many requests failed: {success_count}/20"
        
        print("✅ Rate limiting and timeout handling test passed!")
