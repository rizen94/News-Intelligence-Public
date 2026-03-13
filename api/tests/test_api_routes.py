#!/usr/bin/env python3
"""
Test script to verify API routes and database data
Tests:
1. Database schemas exist
2. Data exists in schemas
3. API endpoints work correctly
4. Response formats match frontend expectations
"""

import os
import sys
import requests
import json
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from shared.database.connection import get_db_connection
from psycopg2.extras import RealDictCursor

# API base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Domains to test
DOMAINS = ["politics", "finance", "science-tech"]

def print_section(title: str):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_result(name: str, success: bool, details: str = ""):
    """Print a test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"      {details}")

def test_database_connection() -> bool:
    """Test database connection"""
    print_section("1. DATABASE CONNECTION TEST")
    try:
        conn = get_db_connection()
        if not conn:
            print_result("Database Connection", False, "Cannot connect to database")
            return False
        
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            conn.close()
            
            if result:
                print_result("Database Connection", True, "Connected successfully")
                return True
            else:
                print_result("Database Connection", False, "Query returned no result")
                return False
    except Exception as e:
        print_result("Database Connection", False, f"Error: {str(e)}")
        return False

def test_domain_schemas() -> Dict[str, bool]:
    """Test if domain schemas exist"""
    print_section("2. DOMAIN SCHEMAS TEST")
    results = {}
    
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Cannot connect to database")
            return results
        
        with conn.cursor() as cur:
            # Check if domains table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'domains'
                )
            """)
            domains_table_exists = cur.fetchone()[0]
            
            if not domains_table_exists:
                print_result("Domains Table", False, "domains table does not exist")
                conn.close()
                return results
            
            print_result("Domains Table", True)
            
            # Check each domain
            for domain in DOMAINS:
                schema_name = domain.replace('-', '_')
                
                # Check if schema exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.schemata 
                        WHERE schema_name = %s
                    )
                """, (schema_name,))
                schema_exists = cur.fetchone()[0]
                
                if schema_exists:
                    # Check if tables exist in schema
                    cur.execute("""
                        SELECT COUNT(*) FROM information_schema.tables 
                        WHERE table_schema = %s
                        AND table_name IN ('articles', 'storylines', 'rss_feeds')
                    """, (schema_name,))
                    table_count = cur.fetchone()[0]
                    
                    if table_count >= 3:
                        print_result(f"Schema: {schema_name}", True, f"{table_count} tables found")
                        results[domain] = True
                    else:
                        print_result(f"Schema: {schema_name}", False, f"Only {table_count} tables found (expected 3+)")
                        results[domain] = False
                else:
                    print_result(f"Schema: {schema_name}", False, "Schema does not exist")
                    results[domain] = False
        
        conn.close()
        return results
        
    except Exception as e:
        print_result("Domain Schemas Test", False, f"Error: {str(e)}")
        return results

def test_domain_data(domain: str) -> Dict[str, Any]:
    """Test if domain has data"""
    schema_name = domain.replace('-', '_')
    results = {
        "articles": 0,
        "storylines": 0,
        "rss_feeds": 0
    }
    
    try:
        conn = get_db_connection()
        if not conn:
            return results
        
        with conn.cursor() as cur:
            # Count articles
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.articles")
                results["articles"] = cur.fetchone()[0]
            except Exception as e:
                print(f"      ⚠️  Error counting articles: {e}")
            
            # Count storylines
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.storylines")
                results["storylines"] = cur.fetchone()[0]
            except Exception as e:
                print(f"      ⚠️  Error counting storylines: {e}")
            
            # Count RSS feeds
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.rss_feeds")
                results["rss_feeds"] = cur.fetchone()[0]
            except Exception as e:
                print(f"      ⚠️  Error counting RSS feeds: {e}")
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"      ❌ Error testing domain data: {e}")
        return results

def test_all_domain_data() -> Dict[str, Dict[str, int]]:
    """Test data in all domains"""
    print_section("3. DOMAIN DATA TEST")
    all_results = {}
    
    for domain in DOMAINS:
        print(f"\n  Testing domain: {domain}")
        results = test_domain_data(domain)
        all_results[domain] = results
        
        articles = results["articles"]
        storylines = results["storylines"]
        feeds = results["rss_feeds"]
        
        print_result(
            f"{domain} - Articles", 
            articles > 0, 
            f"{articles} articles found"
        )
        print_result(
            f"{domain} - Storylines", 
            storylines > 0, 
            f"{storylines} storylines found"
        )
        print_result(
            f"{domain} - RSS Feeds", 
            feeds > 0, 
            f"{feeds} RSS feeds found"
        )
    
    return all_results

def test_api_endpoint(method: str, url: str, params: Dict = None, data: Dict = None) -> Dict[str, Any]:
    """Test an API endpoint"""
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, params=params, timeout=10)
        else:
            return {"success": False, "error": f"Unsupported method: {method}"}
        
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            "error": None if response.status_code < 400 else response.text
        }
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to API server. Is it running?"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_api_endpoints() -> Dict[str, Any]:
    """Test API endpoints"""
    print_section("4. API ENDPOINTS TEST")
    results = {}
    
    # Test health endpoint
    print("\n  Testing Health Endpoint")
    health_result = test_api_endpoint("GET", f"{API_BASE_URL}/api/system_monitoring/health")
    print_result(
        "Health Check",
        health_result["success"],
        f"Status: {health_result.get('status_code', 'N/A')}"
    )
    results["health"] = health_result
    
    # Test domain endpoints
    for domain in DOMAINS:
        print(f"\n  Testing domain: {domain}")
        
        # Test articles endpoint
        articles_result = test_api_endpoint(
            "GET",
            f"{API_BASE_URL}/api/{domain}/articles",
            params={"limit": 10, "offset": 0}
        )
        print_result(
            f"{domain} - Articles",
            articles_result["success"],
            f"Status: {articles_result.get('status_code', 'N/A')}"
        )
        if articles_result["success"]:
            data = articles_result.get("data", {})
            if isinstance(data, dict):
                articles = data.get("data", {}).get("articles", [])
                total = data.get("data", {}).get("total", 0)
                print(f"      Found {len(articles)} articles (total: {total})")
        results[f"{domain}_articles"] = articles_result
        
        # Test storylines endpoint
        storylines_result = test_api_endpoint(
            "GET",
            f"{API_BASE_URL}/api/{domain}/storylines",
            params={"limit": 10, "offset": 0}
        )
        print_result(
            f"{domain} - Storylines",
            storylines_result["success"],
            f"Status: {storylines_result.get('status_code', 'N/A')}"
        )
        if storylines_result["success"]:
            data = storylines_result.get("data", {})
            if isinstance(data, dict):
                storylines = data.get("data", {}).get("storylines", [])
                total = data.get("data", {}).get("total", 0)
                print(f"      Found {len(storylines)} storylines (total: {total})")
        results[f"{domain}_storylines"] = storylines_result
        
        # Test RSS feeds endpoint
        rss_result = test_api_endpoint(
            "GET",
            f"{API_BASE_URL}/api/{domain}/rss_feeds"
        )
        print_result(
            f"{domain} - RSS Feeds",
            rss_result["success"],
            f"Status: {rss_result.get('status_code', 'N/A')}"
        )
        if rss_result["success"]:
            data = rss_result.get("data", {})
            if isinstance(data, dict):
                feeds = data.get("data", {}).get("feeds", [])
                total = data.get("data", {}).get("total", 0)
                print(f"      Found {len(feeds)} RSS feeds (total: {total})")
        results[f"{domain}_rss"] = rss_result
    
    return results

def test_pagination() -> Dict[str, Any]:
    """Test pagination functionality"""
    print_section("5. PAGINATION TEST")
    results = {}
    
    domain = "politics"  # Test with one domain
    
    # Test page 1
    print(f"\n  Testing pagination for {domain}")
    page1_result = test_api_endpoint(
        "GET",
        f"{API_BASE_URL}/api/{domain}/articles",
        params={"limit": 5, "offset": 0}
    )
    
    if page1_result["success"]:
        data = page1_result.get("data", {})
        if isinstance(data, dict):
            articles1 = data.get("data", {}).get("articles", [])
            total = data.get("data", {}).get("total", 0)
            print_result(
                "Page 1 (offset=0)",
                len(articles1) <= 5,
                f"Got {len(articles1)} articles (total: {total})"
            )
            
            # Test page 2
            if total > 5:
                page2_result = test_api_endpoint(
                    "GET",
                    f"{API_BASE_URL}/api/{domain}/articles",
                    params={"limit": 5, "offset": 5}
                )
                if page2_result["success"]:
                    data2 = page2_result.get("data", {})
                    if isinstance(data2, dict):
                        articles2 = data2.get("data", {}).get("articles", [])
                        print_result(
                            "Page 2 (offset=5)",
                            len(articles2) <= 5,
                            f"Got {len(articles2)} articles"
                        )
                        
                        # Verify different articles
                        if articles1 and articles2:
                            ids1 = {a.get("id") for a in articles1 if a.get("id")}
                            ids2 = {a.get("id") for a in articles2 if a.get("id")}
                            overlap = ids1 & ids2
                            print_result(
                                "No Overlap Between Pages",
                                len(overlap) == 0,
                                f"{len(overlap)} overlapping IDs found"
                            )
    
    return results

def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  API ROUTE VERIFICATION TEST SUITE")
    print("=" * 70)
    
    # Test 1: Database connection
    if not test_database_connection():
        print("\n❌ Database connection failed. Cannot continue tests.")
        return
    
    # Test 2: Domain schemas
    schema_results = test_domain_schemas()
    
    # Test 3: Domain data
    data_results = test_all_domain_data()
    
    # Test 4: API endpoints
    api_results = test_api_endpoints()
    
    # Test 5: Pagination
    pagination_results = test_pagination()
    
    # Summary
    print_section("TEST SUMMARY")
    
    # Count successes
    total_tests = 0
    passed_tests = 0
    
    # Schema tests
    for domain, success in schema_results.items():
        total_tests += 1
        if success:
            passed_tests += 1
    
    # Data tests
    for domain, data in data_results.items():
        total_tests += 3  # articles, storylines, feeds
        if data["articles"] > 0:
            passed_tests += 1
        if data["storylines"] > 0:
            passed_tests += 1
        if data["rss_feeds"] > 0:
            passed_tests += 1
    
    # API tests
    for key, result in api_results.items():
        total_tests += 1
        if result.get("success"):
            passed_tests += 1
    
    print(f"\n  Tests Passed: {passed_tests} / {total_tests}")
    print(f"  Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    if passed_tests == total_tests:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} TESTS FAILED")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()


