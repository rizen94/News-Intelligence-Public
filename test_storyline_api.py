#!/usr/bin/env python3
"""
Test script for storyline API functionality
"""

import requests
import json
import sys

def test_storyline_api():
    """Test storyline API endpoints"""
    base_url = "http://localhost:8001/api"
    
    print("Testing Storyline API...")
    print("=" * 50)
    
    # Test 1: Get storylines
    print("\n1. Testing GET /storylines")
    try:
        response = requests.get(f"{base_url}/storylines/")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Create a new storyline
    print("\n2. Testing POST /storylines")
    try:
        storyline_data = {
            "title": "Test Storyline",
            "description": "This is a test storyline created via API"
        }
        response = requests.post(f"{base_url}/storylines/", json=storyline_data)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            storyline_id = response.json().get('data', {}).get('storyline', {}).get('id')
            if storyline_id:
                print(f"Created storyline with ID: {storyline_id}")
                
                # Test 3: Get specific storyline
                print(f"\n3. Testing GET /storylines/{storyline_id}")
                try:
                    response = requests.get(f"{base_url}/storylines/{storyline_id}/")
                    print(f"Status: {response.status_code}")
                    print(f"Response: {json.dumps(response.json(), indent=2)}")
                except Exception as e:
                    print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: Health check
    print("\n4. Testing health endpoint")
    try:
        response = requests.get(f"{base_url}/health/")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_storyline_api()
