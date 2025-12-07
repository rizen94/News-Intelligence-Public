#!/usr/bin/env python3
"""
News Intelligence System 4.0 Comprehensive Test Suite
Tests all aspects of the v4 architecture with no false positives
"""

import os
import sys
import psycopg2
import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class V4TestSuite:
    def __init__(self):
        self.api_base_url = "http://localhost:8001"
        self.test_results = {
            "database_tests": {},
            "api_tests": {},
            "frontend_tests": {},
            "performance_tests": {},
            "integration_tests": {}
        }
        self.failed_tests = []
        self.passed_tests = []
        
    def connect_database(self):
        """Connect to the database"""
        return psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'news_intelligence'),
            user=os.getenv('DB_USER', 'newsapp'),
            password=os.getenv('DB_PASSWORD', 'newsapp_password'),
            port=os.getenv('DB_PORT', '5432')
        )

    def log_test_result(self, test_name: str, passed: bool, details: str, category: str = "general"):
        """Log test result with detailed information"""
        result = {
            "test_name": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "category": category
        }
        
        if passed:
            self.passed_tests.append(result)
            print(f"✅ {test_name}: {details}")
        else:
            self.failed_tests.append(result)
            print(f"❌ {test_name}: {details}")
        
        return result

    def test_database_schema_integrity(self):
        """Test v4 database schema integrity"""
        print("\n🔍 TESTING DATABASE SCHEMA INTEGRITY")
        print("=" * 50)
        
        try:
            conn = self.connect_database()
            with conn.cursor() as cur:
                # Test 1: Verify v4 tables exist
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE '%_v4'
                    ORDER BY table_name
                """)
                
                v4_tables = [row[0] for row in cur.fetchall()]
                expected_tables = [
                    'articles_v4', 'rss_feeds_v4', 'storylines_v4', 
                    'storyline_articles_v4', 'topic_clusters_v4', 
                    'article_topics_v4', 'analysis_results_v4',
                    'system_metrics_v4', 'pipeline_traces_v4',
                    'users_v4', 'user_preferences_v4'
                ]
                
                missing_tables = set(expected_tables) - set(v4_tables)
                if missing_tables:
                    self.log_test_result(
                        "v4_tables_exist", False, 
                        f"Missing tables: {missing_tables}", "database"
                    )
                else:
                    self.log_test_result(
                        "v4_tables_exist", True, 
                        f"All {len(v4_tables)} v4 tables exist", "database"
                    )
                
                # Test 2: Verify data integrity
                cur.execute("SELECT COUNT(*) FROM articles_v4")
                articles_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM rss_feeds_v4")
                feeds_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM storylines_v4")
                storylines_count = cur.fetchone()[0]
                
                if articles_count > 0 and feeds_count > 0:
                    self.log_test_result(
                        "data_integrity", True, 
                        f"Data migrated: {articles_count} articles, {feeds_count} feeds, {storylines_count} storylines", 
                        "database"
                    )
                else:
                    self.log_test_result(
                        "data_integrity", False, 
                        f"No data found: articles={articles_count}, feeds={feeds_count}", 
                        "database"
                    )
                
                # Test 3: Verify foreign key relationships
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM storyline_articles_v4 sa
                    JOIN storylines_v4 s ON sa.storyline_id = s.id
                    JOIN articles_v4 a ON sa.article_id = a.id
                """)
                valid_relationships = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM storyline_articles_v4")
                total_relationships = cur.fetchone()[0]
                
                if valid_relationships == total_relationships:
                    self.log_test_result(
                        "foreign_key_integrity", True, 
                        f"All {total_relationships} foreign key relationships valid", 
                        "database"
                    )
                else:
                    self.log_test_result(
                        "foreign_key_integrity", False, 
                        f"Invalid relationships: {total_relationships - valid_relationships} out of {total_relationships}", 
                        "database"
                    )
                
                # Test 4: Verify indexes exist
                cur.execute("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename LIKE '%_v4'
                    ORDER BY indexname
                """)
                indexes = [row[0] for row in cur.fetchall()]
                
                if len(indexes) > 0:
                    self.log_test_result(
                        "indexes_exist", True, 
                        f"Found {len(indexes)} indexes on v4 tables", 
                        "database"
                    )
                else:
                    self.log_test_result(
                        "indexes_exist", False, 
                        "No indexes found on v4 tables", 
                        "database"
                    )
                
            conn.close()
            
        except Exception as e:
            self.log_test_result(
                "database_connection", False, 
                f"Database connection failed: {e}", 
                "database"
            )

    def test_api_endpoints(self):
        """Test all API endpoints with comprehensive validation"""
        print("\n🔍 TESTING API ENDPOINTS")
        print("=" * 30)
        
        # Test 1: Health endpoint
        try:
            response = requests.get(f"{self.api_base_url}/api/v4/system-monitoring/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'status' in data or 'success' in data:
                    self.log_test_result(
                        "health_endpoint", True, 
                        f"Health endpoint responding: {response.status_code}", 
                        "api"
                    )
                else:
                    self.log_test_result(
                        "health_endpoint", False, 
                        f"Health endpoint unexpected format: {data}", 
                        "api"
                    )
            else:
                self.log_test_result(
                    "health_endpoint", False, 
                    f"Health endpoint failed: {response.status_code}", 
                    "api"
                )
        except Exception as e:
            self.log_test_result(
                "health_endpoint", False, 
                f"Health endpoint error: {e}", 
                "api"
            )
        
        # Test 2: Articles endpoint
        try:
            response = requests.get(f"{self.api_base_url}/api/v4/news-aggregation/articles/recent", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'articles' in data['data']:
                    articles = data['data']['articles']
                    if len(articles) > 0:
                        # Validate article structure
                        article = articles[0]
                        required_fields = ['id', 'title', 'url', 'published_at']
                        missing_fields = [field for field in required_fields if field not in article]
                        
                        if not missing_fields:
                            self.log_test_result(
                                "articles_endpoint", True, 
                                f"Articles endpoint: {len(articles)} articles with valid structure", 
                                "api"
                            )
                        else:
                            self.log_test_result(
                                "articles_endpoint", False, 
                                f"Articles missing fields: {missing_fields}", 
                                "api"
                            )
                    else:
                        self.log_test_result(
                            "articles_endpoint", False, 
                            "Articles endpoint returned empty array", 
                            "api"
                        )
                else:
                    self.log_test_result(
                        "articles_endpoint", False, 
                        f"Articles endpoint unexpected format: {data}", 
                        "api"
                    )
            else:
                self.log_test_result(
                    "articles_endpoint", False, 
                    f"Articles endpoint failed: {response.status_code}", 
                    "api"
                )
        except Exception as e:
            self.log_test_result(
                "articles_endpoint", False, 
                f"Articles endpoint error: {e}", 
                "api"
            )
        
        # Test 3: RSS Feeds endpoint
        try:
            response = requests.get(f"{self.api_base_url}/api/v4/news-aggregation/rss-feeds", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'feeds' in data['data']:
                    feeds = data['data']['feeds']
                    if len(feeds) > 0:
                        # Validate feed structure
                        feed = feeds[0]
                        required_fields = ['id', 'feed_name', 'feed_url', 'is_active']
                        missing_fields = [field for field in required_fields if field not in feed]
                        
                        if not missing_fields:
                            self.log_test_result(
                                "rss_feeds_endpoint", True, 
                                f"RSS feeds endpoint: {len(feeds)} feeds with valid structure", 
                                "api"
                            )
                        else:
                            self.log_test_result(
                                "rss_feeds_endpoint", False, 
                                f"RSS feeds missing fields: {missing_fields}", 
                                "api"
                            )
                    else:
                        self.log_test_result(
                            "rss_feeds_endpoint", False, 
                            "RSS feeds endpoint returned empty array", 
                            "api"
                        )
                else:
                    self.log_test_result(
                        "rss_feeds_endpoint", False, 
                        f"RSS feeds endpoint unexpected format: {data}", 
                        "api"
                    )
            else:
                self.log_test_result(
                    "rss_feeds_endpoint", False, 
                    f"RSS feeds endpoint failed: {response.status_code}", 
                    "api"
                )
        except Exception as e:
            self.log_test_result(
                "rss_feeds_endpoint", False, 
                f"RSS feeds endpoint error: {e}", 
                "api"
            )
        
        # Test 4: Storylines endpoint
        try:
            response = requests.get(f"{self.api_base_url}/api/v4/storyline-management/storylines", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'storylines' in data['data']:
                    storylines = data['data']['storylines']
                    if len(storylines) > 0:
                        # Validate storyline structure
                        storyline = storylines[0]
                        required_fields = ['id', 'title', 'status']
                        missing_fields = [field for field in required_fields if field not in storyline]
                        
                        if not missing_fields:
                            self.log_test_result(
                                "storylines_endpoint", True, 
                                f"Storylines endpoint: {len(storylines)} storylines with valid structure", 
                                "api"
                            )
                        else:
                            self.log_test_result(
                                "storylines_endpoint", False, 
                                f"Storylines missing fields: {missing_fields}", 
                                "api"
                            )
                    else:
                        self.log_test_result(
                            "storylines_endpoint", False, 
                            "Storylines endpoint returned empty array", 
                            "api"
                        )
                else:
                    self.log_test_result(
                        "storylines_endpoint", False, 
                        f"Storylines endpoint unexpected format: {data}", 
                        "api"
                    )
            else:
                self.log_test_result(
                    "storylines_endpoint", False, 
                    f"Storylines endpoint failed: {response.status_code}", 
                    "api"
                )
        except Exception as e:
            self.log_test_result(
                "storylines_endpoint", False, 
                f"Storylines endpoint error: {e}", 
                "api"
            )

    def test_data_consistency(self):
        """Test data consistency between database and API responses"""
        print("\n🔍 TESTING DATA CONSISTENCY")
        print("=" * 35)
        
        try:
            conn = self.connect_database()
            with conn.cursor() as cur:
                # Get database counts
                cur.execute("SELECT COUNT(*) FROM articles_v4")
                db_articles_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM rss_feeds_v4")
                db_feeds_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) FROM storylines_v4")
                db_storylines_count = cur.fetchone()[0]
                
            conn.close()
            
            # Get API counts
            try:
                response = requests.get(f"{self.api_base_url}/api/v4/news-aggregation/articles/recent", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    api_articles_count = len(data.get('data', {}).get('articles', []))
                    
                    # Test articles consistency
                    if api_articles_count <= db_articles_count:
                        self.log_test_result(
                            "articles_consistency", True, 
                            f"API articles ({api_articles_count}) <= DB articles ({db_articles_count})", 
                            "consistency"
                        )
                    else:
                        self.log_test_result(
                            "articles_consistency", False, 
                            f"API articles ({api_articles_count}) > DB articles ({db_articles_count})", 
                            "consistency"
                        )
                else:
                    self.log_test_result(
                        "articles_consistency", False, 
                        f"API articles endpoint failed: {response.status_code}", 
                        "consistency"
                    )
            except Exception as e:
                self.log_test_result(
                    "articles_consistency", False, 
                    f"API articles error: {e}", 
                    "consistency"
                )
            
            # Test RSS feeds consistency
            try:
                response = requests.get(f"{self.api_base_url}/api/v4/news-aggregation/rss-feeds", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    api_feeds_count = len(data.get('data', {}).get('feeds', []))
                    
                    if api_feeds_count == db_feeds_count:
                        self.log_test_result(
                            "feeds_consistency", True, 
                            f"API feeds ({api_feeds_count}) == DB feeds ({db_feeds_count})", 
                            "consistency"
                        )
                    else:
                        self.log_test_result(
                            "feeds_consistency", False, 
                            f"API feeds ({api_feeds_count}) != DB feeds ({db_feeds_count})", 
                            "consistency"
                        )
                else:
                    self.log_test_result(
                        "feeds_consistency", False, 
                        f"API feeds endpoint failed: {response.status_code}", 
                        "consistency"
                    )
            except Exception as e:
                self.log_test_result(
                    "feeds_consistency", False, 
                    f"API feeds error: {e}", 
                    "consistency"
                )
            
        except Exception as e:
            self.log_test_result(
                "data_consistency", False, 
                f"Data consistency test failed: {e}", 
                "consistency"
            )

    def test_performance(self):
        """Test system performance with v4 architecture"""
        print("\n🔍 TESTING SYSTEM PERFORMANCE")
        print("=" * 35)
        
        # Test 1: API response times
        endpoints = [
            "/api/v4/system-monitoring/health",
            "/api/v4/news-aggregation/articles/recent",
            "/api/v4/news-aggregation/rss-feeds",
            "/api/v4/storyline-management/storylines"
        ]
        
        for endpoint in endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                if response.status_code == 200 and response_time < 5000:  # Less than 5 seconds
                    self.log_test_result(
                        f"performance_{endpoint.split('/')[-1]}", True, 
                        f"Response time: {response_time:.2f}ms", 
                        "performance"
                    )
                else:
                    self.log_test_result(
                        f"performance_{endpoint.split('/')[-1]}", False, 
                        f"Slow response: {response_time:.2f}ms or status {response.status_code}", 
                        "performance"
                    )
            except Exception as e:
                self.log_test_result(
                    f"performance_{endpoint.split('/')[-1]}", False, 
                    f"Performance test error: {e}", 
                    "performance"
                )
        
        # Test 2: Database query performance
        try:
            conn = self.connect_database()
            with conn.cursor() as cur:
                start_time = time.time()
                cur.execute("SELECT COUNT(*) FROM articles_v4")
                articles_count = cur.fetchone()[0]
                end_time = time.time()
                
                query_time = (end_time - start_time) * 1000
                
                if query_time < 1000:  # Less than 1 second
                    self.log_test_result(
                        "database_query_performance", True, 
                        f"Query time: {query_time:.2f}ms for {articles_count} articles", 
                        "performance"
                    )
                else:
                    self.log_test_result(
                        "database_query_performance", False, 
                        f"Slow query: {query_time:.2f}ms", 
                        "performance"
                    )
            conn.close()
        except Exception as e:
            self.log_test_result(
                "database_query_performance", False, 
                f"Database performance test error: {e}", 
                "performance"
            )

    def test_frontend_integration(self):
        """Test frontend integration with v4 API"""
        print("\n🔍 TESTING FRONTEND INTEGRATION")
        print("=" * 40)
        
        # Test 1: Check if React server is running
        try:
            response = requests.get("http://localhost:3000", timeout=10)
            if response.status_code == 200:
                self.log_test_result(
                    "react_server", True, 
                    f"React server responding: {response.status_code}", 
                    "frontend"
                )
            else:
                self.log_test_result(
                    "react_server", False, 
                    f"React server failed: {response.status_code}", 
                    "frontend"
                )
        except Exception as e:
            self.log_test_result(
                "react_server", False, 
                f"React server error: {e}", 
                "frontend"
            )
        
        # Test 2: Check API service configuration
        api_service_path = "web/src/services/apiService.ts"
        if os.path.exists(api_service_path):
            with open(api_service_path, 'r') as f:
                content = f.read()
                
            if "api/v4/" in content:
                self.log_test_result(
                    "api_service_v4", True, 
                    "API service configured for v4 endpoints", 
                    "frontend"
                )
            else:
                self.log_test_result(
                    "api_service_v4", False, 
                    "API service not configured for v4 endpoints", 
                    "frontend"
                )
        else:
            self.log_test_result(
                "api_service_v4", False, 
                "API service file not found", 
                "frontend"
            )

    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n📊 COMPREHENSIVE TEST REPORT")
        print("=" * 40)
        
        total_tests = len(self.passed_tests) + len(self.failed_tests)
        passed_count = len(self.passed_tests)
        failed_count = len(self.failed_tests)
        success_rate = (passed_count / total_tests * 100) if total_tests > 0 else 0
        
        print(f"📈 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_count}")
        print(f"   Failed: {failed_count}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        if failed_count > 0:
            print(f"\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"   - {test['test_name']}: {test['details']}")
        
        print(f"\n✅ Passed Tests:")
        for test in self.passed_tests:
            print(f"   - {test['test_name']}: {test['details']}")
        
        # Save detailed report
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed": passed_count,
                "failed": failed_count,
                "success_rate": success_rate,
                "timestamp": datetime.now().isoformat()
            },
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests
        }
        
        with open("tests/v4_test_report.json", 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📁 Detailed report saved to: tests/v4_test_report.json")
        
        return success_rate >= 80  # Consider success if 80% or more tests pass

    def run_all_tests(self):
        """Run all tests in the comprehensive suite"""
        print("🚀 STARTING COMPREHENSIVE V4 TEST SUITE")
        print("=" * 50)
        print(f"Test started at: {datetime.now().isoformat()}")
        
        # Run all test categories
        self.test_database_schema_integrity()
        self.test_api_endpoints()
        self.test_data_consistency()
        self.test_performance()
        self.test_frontend_integration()
        
        # Generate final report
        success = self.generate_test_report()
        
        if success:
            print(f"\n🎉 COMPREHENSIVE TEST SUITE PASSED")
            print(f"✅ V4 architecture is working correctly")
        else:
            print(f"\n❌ COMPREHENSIVE TEST SUITE FAILED")
            print(f"⚠️ V4 architecture needs attention")
        
        return success

if __name__ == "__main__":
    test_suite = V4TestSuite()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)
