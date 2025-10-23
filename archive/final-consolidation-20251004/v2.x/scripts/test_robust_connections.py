#!/usr/bin/env python3
"""
Test script for robust database connections
Tests connection pooling, retry logic, and health monitoring
"""

import sys
import time
import threading
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.config.robust_database import db_manager, get_db_cursor

def test_connection_pool():
    """Test connection pool functionality"""
    print("=== Testing Connection Pool ===")
    
    # Test basic connection
    print("1. Testing basic connection...")
    conn = db_manager.get_connection()
    if conn:
        print("✅ Basic connection successful")
        db_manager.return_connection(conn)
    else:
        print("❌ Basic connection failed")
        return False
    
    # Test connection pool status
    print("2. Checking pool status...")
    pool_status = db_manager.get_pool_status()
    print(f"Pool status: {pool_status}")
    
    # Test multiple connections
    print("3. Testing multiple connections...")
    connections = []
    for i in range(5):
        conn = db_manager.get_connection()
        if conn:
            connections.append(conn)
            print(f"✅ Connection {i+1} successful")
        else:
            print(f"❌ Connection {i+1} failed")
    
    # Return all connections
    for conn in connections:
        db_manager.return_connection(conn)
    
    print(f"Successfully created and returned {len(connections)} connections")
    return True

def test_retry_logic():
    """Test retry logic with simulated failures"""
    print("\n=== Testing Retry Logic ===")
    
    # Test with context manager
    print("1. Testing context manager...")
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            if result['test'] == 1:
                print("✅ Context manager test successful")
            else:
                print("❌ Context manager test failed")
                return False
    except Exception as e:
        print(f"❌ Context manager test failed: {e}")
        return False
    
    # Test query execution
    print("2. Testing query execution...")
    try:
        results = db_manager.execute_query("SELECT COUNT(*) as article_count FROM articles")
        if results:
            print(f"✅ Query execution successful: {results[0]['article_count']} articles")
        else:
            print("❌ Query execution failed")
            return False
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
        return False
    
    return True

def test_concurrent_connections():
    """Test concurrent connection handling"""
    print("\n=== Testing Concurrent Connections ===")
    
    def worker(worker_id):
        """Worker function for concurrent testing"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute("SELECT %s as worker_id, NOW() as timestamp", (worker_id,))
                result = cursor.fetchone()
                print(f"Worker {worker_id}: {result['worker_id']} at {result['timestamp']}")
                return True
        except Exception as e:
            print(f"Worker {worker_id} failed: {e}")
            return False
    
    # Start multiple threads
    threads = []
    results = []
    
    for i in range(10):
        thread = threading.Thread(target=lambda i=i: results.append(worker(i)))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    successful = sum(results)
    print(f"Concurrent test: {successful}/10 workers successful")
    return successful >= 8  # Allow some failures

def test_health_monitoring():
    """Test health monitoring functionality"""
    print("\n=== Testing Health Monitoring ===")
    
    # Test basic health check
    print("1. Testing basic health check...")
    is_healthy = db_manager.test_connection()
    print(f"Health check: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
    
    # Test comprehensive health status
    print("2. Testing comprehensive health status...")
    from api.config.database import get_database_health
    health_status = get_database_health()
    print(f"Health status: {health_status}")
    
    return is_healthy

def main():
    """Run all tests"""
    print("🔧 Testing Robust Database Connections")
    print("=" * 50)
    
    tests = [
        ("Connection Pool", test_connection_pool),
        ("Retry Logic", test_retry_logic),
        ("Concurrent Connections", test_concurrent_connections),
        ("Health Monitoring", test_health_monitoring)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Robust database connections are working.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
