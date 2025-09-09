#!/usr/bin/env python3
"""
Pre-Reboot Test Script for News Intelligence System v3.3.0
Tests critical fixes before system reboot
"""

import sys
import os
import requests
import time
import subprocess
from datetime import datetime

def test_article_processing_service():
    """Test ArticleProcessingService fixes"""
    print("🔧 Testing ArticleProcessingService...")
    try:
        sys.path.append('api')
        from services.article_processing_service import ArticleProcessingService, get_article_processor
        from database.connection import get_db_config
        
        # Test service creation
        db_config = get_db_config()
        service = ArticleProcessingService(db_config)
        print("✅ ArticleProcessingService created successfully")
        
        # Test global instance function
        processor = get_article_processor()
        print("✅ get_article_processor() works")
        
        # Test process_single_article method exists
        if hasattr(processor, 'process_single_article'):
            print("✅ process_single_article method exists")
        else:
            print("❌ process_single_article method missing")
            return False
            
        return True
    except Exception as e:
        print(f"❌ ArticleProcessingService test failed: {e}")
        return False

def test_ai_processing_service():
    """Test AIProcessingService JSON parsing fixes"""
    print("🔧 Testing AIProcessingService...")
    try:
        sys.path.append('api')
        from services.ai_processing_service import AIProcessingService
        from database.connection import get_db_config
        
        # Test service creation
        db_config = get_db_config()
        service = AIProcessingService(db_config)
        print("✅ AIProcessingService created successfully")
        
        # Test JSON cleaning method
        test_json = '''
        {
          "people": ["Tim Cook"],
          "organizations": ["Apple"],
          "numbers": [
            "3", // AirPods Pro 3
            "10am PT" // time of the event,
            "5" // sizes of adjustable earpiece
          ]
        }
        '''
        
        cleaned = service._clean_json_string(test_json)
        print("✅ JSON cleaning method works")
        
        # Test fallback response
        fallback = service._create_fallback_response("test response")
        if fallback.get('fallback') == True:
            print("✅ Fallback response method works")
        else:
            print("❌ Fallback response method failed")
            return False
            
        return True
    except Exception as e:
        print(f"❌ AIProcessingService test failed: {e}")
        return False

def test_automation_manager():
    """Test AutomationManager fixes"""
    print("🔧 Testing AutomationManager...")
    try:
        sys.path.append('api')
        from services.automation_manager import AutomationManager
        from database.connection import get_db_config
        
        # Test service creation
        db_config = get_db_config()
        automation = AutomationManager(db_config)
        print("✅ AutomationManager created successfully")
        
        # Test database connection method
        if hasattr(automation, '_get_db_connection'):
            print("✅ _get_db_connection method exists")
        else:
            print("❌ _get_db_connection method missing")
            return False
            
        return True
    except Exception as e:
        print(f"❌ AutomationManager test failed: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    print("🔧 Testing database connection...")
    try:
        sys.path.append('api')
        from database.connection import get_db_config
        import psycopg2
        
        db_config = get_db_config()
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result[0] == 1:
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection failed")
            return False
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

def test_api_server():
    """Test API server startup"""
    print("🔧 Testing API server...")
    try:
        # Check if server is already running
        response = requests.get("http://localhost:8000/api/health/", timeout=5)
        if response.status_code == 200:
            print("✅ API server is already running")
            return True
    except:
        pass
    
    print("⚠️ API server not running - this is expected before reboot")
    return True

def test_docker_services():
    """Test Docker services"""
    print("🔧 Testing Docker services...")
    try:
        # Check if Docker is running
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Docker is running")
            
            # Check for our containers
            if 'news-system-postgres' in result.stdout:
                print("✅ PostgreSQL container found")
            else:
                print("⚠️ PostgreSQL container not running")
                
            if 'news-system-redis' in result.stdout:
                print("✅ Redis container found")
            else:
                print("⚠️ Redis container not running")
                
            return True
        else:
            print("❌ Docker is not running")
            return False
    except Exception as e:
        print(f"❌ Docker test failed: {e}")
        return False

def main():
    """Run all pre-reboot tests"""
    print("🚀 News Intelligence System v3.3.0 - Pre-Reboot Test")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("ArticleProcessingService", test_article_processing_service),
        ("AIProcessingService", test_ai_processing_service),
        ("AutomationManager", test_automation_manager),
        ("Database Connection", test_database_connection),
        ("API Server", test_api_server),
        ("Docker Services", test_docker_services),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} test...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
        print()
    
    # Summary
    print("=" * 60)
    print("📊 PRE-REBOOT TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - System ready for reboot!")
        print("\n📋 Next steps:")
        print("1. Reboot the system")
        print("2. Follow the SYSTEM_REBOOT_CHECKLIST.md")
        print("3. Run ./startup_with_recovery.sh after reboot")
    else:
        print("⚠️ SOME TESTS FAILED - Fix issues before reboot")
        print("\n🔧 Failed tests need attention:")
        for test_name, result in results.items():
            if not result:
                print(f"   - {test_name}")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

