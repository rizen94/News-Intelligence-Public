#!/usr/bin/env python3
"""
News Intelligence System v3.1.0 - Production API Test
Comprehensive testing of all production endpoints
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_endpoint(method: str, endpoint: str, data: Dict[Any, Any] = None) -> Dict[str, Any]:
    """Test a single API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, timeout=10)
        elif method.upper() == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        return {
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
    except Exception as e:
        return {"error": str(e), "success": False}

def main():
    print("=== PRODUCTION API TESTING ===")
    print("")
    
    # Test endpoints
    endpoints = [
        ("GET", "/"),
        ("GET", "/health/"),
        ("GET", "/health/database"),
        ("GET", "/health/ready"),
        ("GET", "/health/live"),
        ("GET", "/articles/"),
        ("GET", "/articles/sources"),
        ("GET", "/articles/categories"),
        ("GET", "/articles/stats/overview"),
        ("GET", "/rss/feeds/"),
        ("GET", "/rss/feeds/stats/overview"),
    ]
    
    results = []
    
    for method, endpoint in endpoints:
        print(f"Testing {method} {endpoint}...")
        result = test_endpoint(method, endpoint)
        results.append({
            "endpoint": f"{method} {endpoint}",
            "result": result
        })
        
        if result.get("success"):
            print(f"   ✅ Success: {result.get('status_code', 'N/A')}")
        else:
            print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
    
    print("")
    print("=== TEST RESULTS SUMMARY ===")
    successful = sum(1 for r in results if r["result"].get("success"))
    total = len(results)
    
    print(f"Successful: {successful}/{total}")
    print(f"Success Rate: {(successful/total)*100:.1f}%")
    
    if successful == total:
        print("🎉 All endpoints are working correctly!")
    else:
        print("⚠️  Some endpoints need attention")
    
    print("")
    print("=== PRODUCTION API TEST COMPLETED ===")

if __name__ == "__main__":
    main()
