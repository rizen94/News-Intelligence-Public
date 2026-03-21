#!/usr/bin/env python3
"""
Test script for article processing pipeline
"""

import sys

from modules.intelligence.article_processor import ArticleProcessor
from modules.intelligence.content_clusterer import ContentClusterer
from modules.intelligence.enhanced_entity_extractor import EnhancedEntityExtractor


def test_article_processing():
    """Test the article processing pipeline"""
    print("Testing article processing pipeline...")

    # Database configuration
    db_config = {"host": "postgres", "database": "news_system", "user": "newsapp", "password": ""}

    try:
        # Test article processor
        print("1. Testing ArticleProcessor...")
        ArticleProcessor(db_config)
        print("   ✓ ArticleProcessor created successfully")

        # Test content clusterer
        print("2. Testing ContentClusterer...")
        ContentClusterer(db_config)
        print("   ✓ ContentClusterer created successfully")

        # Test entity extractor
        print("3. Testing EnhancedEntityExtractor...")
        EnhancedEntityExtractor(db_config)
        print("   ✓ EnhancedEntityExtractor created successfully")

        print("\n✅ All modules imported successfully!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = test_article_processing()
    sys.exit(0 if success else 1)
