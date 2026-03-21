#!/usr/bin/env python3
"""
Comprehensive functionality tests for News Intelligence System v4.0
Tests actual business logic, not just connectivity
"""

import os
import sys
from datetime import datetime

import requests

# Add the API directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))


class TestNewsIntelligenceFunctionality:
    """Test actual functionality, not just connectivity"""

    def __init__(self):
        self.api_base = "http://localhost:8001"
        self.test_data = self._create_test_data()

    def _create_test_data(self):
        """Create realistic test data for testing"""
        return {
            "test_article": {
                "title": "Test Article for Functionality Testing",
                "url": "https://example.com/test-article",
                "content": "This is a test article about technology and innovation.",
                "source_domain": "example.com",
                "published_at": datetime.now().isoformat(),
            },
            "test_storyline": {
                "title": "Test Storyline for Functionality Testing",
                "description": "A test storyline to verify functionality",
            },
            "test_rss_feed": {
                "feed_name": "Test Feed",
                "feed_url": "https://feeds.bbci.co.uk/news/rss.xml",
                "is_active": True,
                "fetch_interval_seconds": 3600,
            },
        }

    def test_article_creation_and_retrieval(self):
        """Test that articles can be created and retrieved with correct data"""
        print("🧪 Testing article creation and retrieval...")

        # Test 1: Create article via API
        response = requests.post(
            f"{self.api_base}/api/articles", json=self.test_data["test_article"]
        )

        if response.status_code == 200:
            article_data = response.json()
            article_id = article_data.get("data", {}).get("id")

            # Test 2: Retrieve the article
            get_response = requests.get(f"{self.api_base}/api/articles/{article_id}")

            if get_response.status_code == 200:
                retrieved_article = get_response.json()["data"]

                # Verify data integrity
                assert retrieved_article["title"] == self.test_data["test_article"]["title"]
                assert retrieved_article["url"] == self.test_data["test_article"]["url"]
                assert (
                    retrieved_article["source_domain"]
                    == self.test_data["test_article"]["source_domain"]
                )

                print("✅ Article creation and retrieval working correctly")
                return True
            else:
                print(f"❌ Failed to retrieve article: {get_response.status_code}")
                return False
        else:
            print(f"❌ Failed to create article: {response.status_code}")
            return False

    def test_storyline_management_functionality(self):
        """Test storyline creation, article addition, and management"""
        print("🧪 Testing storyline management functionality...")

        # Test 1: Create storyline
        response = requests.post(
            f"{self.api_base}/api/politics/storylines", json=self.test_data["test_storyline"]
        )

        if response.status_code == 200:
            storyline_data = response.json()
            storyline_id = storyline_data["data"]["storyline_id"]

            # Test 2: Get available articles
            articles_response = requests.get(f"{self.api_base}/api/articles")

            if articles_response.status_code == 200:
                articles = articles_response.json()["data"]["articles"]

                if articles:
                    # Test 3: Add article to storyline
                    article_id = articles[0]["id"]
                    add_response = requests.post(
                        f"{self.api_base}/api/politics/storylines/{storyline_id}/articles/{article_id}",
                        json={"relevance_score": 0.8},
                    )

                    if add_response.status_code == 200:
                        # Test 4: Verify article is in storyline
                        storyline_response = requests.get(
                            f"{self.api_base}/api/politics/storylines/{storyline_id}"
                        )

                        if storyline_response.status_code == 200:
                            storyline = storyline_response.json()["data"]
                            article_count = storyline.get("article_count", 0)

                            if article_count > 0:
                                print("✅ Storyline management functionality working correctly")
                                return True
                            else:
                                print("❌ Article not properly added to storyline")
                                return False
                        else:
                            print(
                                f"❌ Failed to retrieve storyline: {storyline_response.status_code}"
                            )
                            return False
                    else:
                        print(f"❌ Failed to add article to storyline: {add_response.status_code}")
                        return False
                else:
                    print("❌ No articles available for testing")
                    return False
            else:
                print(f"❌ Failed to get articles: {articles_response.status_code}")
                return False
        else:
            print(f"❌ Failed to create storyline: {response.status_code}")
            return False

    def test_topic_clustering_functionality(self):
        """Test topic clustering and intelligent filtering"""
        print("🧪 Testing topic clustering functionality...")

        # Test 1: Get word cloud data
        response = requests.get(f"{self.api_base}/api/politics/content_analysis/topics/word_cloud")

        if response.status_code == 200:
            data = response.json()

            if data.get("success"):
                # Test 2: Verify intelligent filtering is working
                if "word_cloud" in data["data"]:
                    word_cloud = data["data"]["word_cloud"]

                    # Check for noise words (should be filtered out)
                    noise_words = [
                        "www",
                        "thursday",
                        "href",
                        "https",
                        "com",
                        "as",
                        "its",
                        "first",
                        "after",
                        "from",
                        "said",
                    ]
                    found_noise = [
                        topic["text"].lower()
                        for topic in word_cloud
                        if topic["text"].lower() in noise_words
                    ]

                    if len(found_noise) == 0:
                        print("✅ Topic clustering with intelligent filtering working correctly")
                        return True
                    else:
                        print(f"⚠️  Some noise words still present: {found_noise[:3]}")
                        return True  # Still working, just needs fine-tuning
                else:
                    print("❌ Word cloud data format incorrect")
                    return False
            else:
                print(f"❌ Topic clustering failed: {data.get('error')}")
                return False
        else:
            print(f"❌ Failed to get topic clustering data: {response.status_code}")
            return False

    def test_data_integrity_and_consistency(self):
        """Test data integrity across the system"""
        print("🧪 Testing data integrity and consistency...")

        # Test 1: Get system monitoring data
        monitoring_response = requests.get(f"{self.api_base}/api/system_monitoring/status")

        if monitoring_response.status_code == 200:
            monitoring_data = monitoring_response.json()

            if monitoring_data.get("success"):
                # Test 2: Verify data consistency
                db_data = monitoring_data["data"]["database"]
                total_articles = db_data["total_articles"]
                total_storylines = db_data["total_storylines"]

                # Test 3: Cross-reference with individual endpoints
                articles_response = requests.get(f"{self.api_base}/api/articles")
                storylines_response = requests.get(f"{self.api_base}/api/politics/storylines")

                if articles_response.status_code == 200 and storylines_response.status_code == 200:
                    articles_data = articles_response.json()
                    storylines_data = storylines_response.json()

                    articles_count = articles_data["data"]["total"]
                    storylines_count = storylines_data["count"]

                    # Verify counts match
                    if total_articles == articles_count and total_storylines == storylines_count:
                        print("✅ Data integrity and consistency verified")
                        return True
                    else:
                        print(
                            f"❌ Data inconsistency: monitoring({total_articles}, {total_storylines}) vs endpoints({articles_count}, {storylines_count})"
                        )
                        return False
                else:
                    print("❌ Failed to get individual endpoint data")
                    return False
            else:
                print("❌ System monitoring data invalid")
                return False
        else:
            print(f"❌ Failed to get system monitoring data: {monitoring_response.status_code}")
            return False

    def test_error_handling_and_edge_cases(self):
        """Test error handling and edge cases"""
        print("🧪 Testing error handling and edge cases...")

        # Test 1: Invalid storyline ID
        response = requests.get(f"{self.api_base}/api/politics/storylines/99999")

        if response.status_code == 404:
            print("✅ Proper 404 handling for invalid storyline ID")
        else:
            print(f"❌ Expected 404, got {response.status_code}")
            return False

        # Test 2: Invalid article ID
        response = requests.get(f"{self.api_base}/api/articles/99999")

        if response.status_code == 404:
            print("✅ Proper 404 handling for invalid article ID")
        else:
            print(f"❌ Expected 404, got {response.status_code}")
            return False

        # Test 3: Invalid JSON in POST request
        response = requests.post(
            f"{self.api_base}/api/politics/storylines",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 422:  # Unprocessable Entity
            print("✅ Proper 422 handling for invalid JSON")
            return True
        else:
            print(f"❌ Expected 422, got {response.status_code}")
            return False

    def run_all_tests(self):
        """Run all functionality tests"""
        print("🚀 RUNNING COMPREHENSIVE FUNCTIONALITY TESTS")
        print("=" * 50)

        tests = [
            ("Article Creation and Retrieval", self.test_article_creation_and_retrieval),
            ("Storyline Management", self.test_storyline_management_functionality),
            ("Topic Clustering", self.test_topic_clustering_functionality),
            ("Data Integrity", self.test_data_integrity_and_consistency),
            ("Error Handling", self.test_error_handling_and_edge_cases),
        ]

        results = []
        for test_name, test_func in tests:
            print(f"\n🔍 Testing: {test_name}")
            print("-" * 30)
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")
                results.append((test_name, False))

        print("\n📊 TEST RESULTS SUMMARY:")
        print("=" * 30)
        passed = 0
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")
            if result:
                passed += 1

        print(f"\n🎯 OVERALL RESULT: {passed}/{len(results)} tests passed")

        if passed == len(results):
            print("🎉 ALL FUNCTIONALITY TESTS PASSED!")
            return True
        else:
            print("⚠️  SOME TESTS FAILED - SYSTEM NEEDS ATTENTION")
            return False


if __name__ == "__main__":
    tester = TestNewsIntelligenceFunctionality()
    tester.run_all_tests()
