#!/usr/bin/env python3
"""
Test script to verify TopicClusteringService database connection patterns.
This will help us understand the current implementation before refactoring.
"""

import sys
import os
sys.path.insert(0, '/home/pete/Documents/projects/news_intelligence')

from api.domains.content_analysis.services.topic_clustering_service import TopicClusteringService

def test_connection_pattern():
    """Test the current database connection pattern"""
    print("Testing current TopicClusteringService connection pattern...")
    
    # Create a mock db_config
    db_config = {
        'host': 'localhost',
        'port': '5432',
        'database': 'news_intel',
        'user': 'test_user',
        'password': 'test_password'
    }
    
    try:
        service = TopicClusteringService(db_config, domain='politics')
        print("✓ Service created successfully")
        
        # Check if the connection method exists
        if hasattr(service, '_get_db_connection'):
            print("✓ _get_db_connection method exists")
        else:
            print("✗ _get_db_connection method missing")
            
        # Look at the method definition
        import inspect
        try:
            source = inspect.getsource(service._get_db_connection)
            print("Current _get_db_connection implementation:")
            print(source[:500] + "..." if len(source) > 500 else source)
        except Exception as e:
            print(f"Could not get source: {e}")
            
    except Exception as e:
        print(f"Error creating service: {e}")

if __name__ == "__main__":
    test_connection_pattern()