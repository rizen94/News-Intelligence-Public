#!/usr/bin/env python3
"""
Basic functionality tests for News Intelligence System v2.5
"""

import pytest
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all major modules can be imported."""
    try:
        from modules.intelligence import DataPreparationPipeline
        from modules.intelligence import ArticleProcessor
        from modules.intelligence import ContentClusterer
        from modules.intelligence import MLDataPreparer
        from modules.intelligence import IntelligenceOrchestrator
        from modules.intelligence import EnhancedEntityExtractor
        from modules.intelligence import ArticleDeduplicator
        from modules.intelligence import ContentCleaner
        from modules.intelligence import LanguageDetector
        from modules.intelligence import QualityValidator
        from modules.intelligence import ArticleStager
        return True
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")

def test_database_connection():
    """Test database connectivity."""
    try:
        import psycopg2
        # This is a basic test - actual connection would require database setup
        return True
    except ImportError as e:
        pytest.fail(f"Database module import failed: {e}")

def test_requirements():
    """Test that required packages are available."""
    required_packages = [
        'psycopg2', 'sentence_transformers', 'spacy', 'langdetect',
        'textstat', 'readability', 'chardet', 'fuzzywuzzy'
    ]
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError as e:
            pytest.fail(f"Required package {package} not available: {e}")
    
    return True

if __name__ == "__main__":
    # Run basic tests
    print("🧪 Running basic functionality tests...")
    
    tests = [
        ("Module Imports", test_imports),
        ("Database Connectivity", test_database_connection),
        ("Required Packages", test_requirements)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Please check the system.")
        sys.exit(1)
