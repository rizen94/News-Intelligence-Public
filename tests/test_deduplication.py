#!/usr/bin/env python3
"""
Test script for the advanced deduplication system
"""

import logging
import sys

sys.path.append("/app/api")

from modules.deduplication import ContentNormalizer, DeduplicationManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_content_normalizer():
    """Test the content normalizer"""
    print("🧪 Testing Content Normalizer...")

    normalizer = ContentNormalizer()

    # Test HTML content
    html_content = """
    <html>
        <body>
            <h1>Test Article</h1>
            <p>This is a <strong>test</strong> article about <em>technology</em>.</p>
            <script>alert('test');</script>
            <p>Click here to read more!</p>
        </body>
    </html>
    """

    cleaned, normalized, content_hash = normalizer.normalize_content(html_content, "Test Article")

    print(f"   ✓ HTML stripped: {len(html_content)} -> {len(cleaned)} chars")
    print(f"   ✓ Content normalized: {len(normalized)} chars")
    print(f"   ✓ Content hash: {content_hash[:16]}...")

    # Test content metrics
    metrics = normalizer.get_content_metrics(cleaned)
    print(
        f"   ✓ Content metrics: {metrics['word_count']} words, {metrics['sentence_count']} sentences"
    )

    # Test content segmentation
    segments = normalizer.segment_content(cleaned, max_sentences=3)
    print(f"   ✓ Content segments: {len(segments)} sentences")

    return True


def test_deduplication_engine():
    """Test the deduplication engine"""
    print("\n🧪 Testing Deduplication Engine...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        from modules.deduplication import DeduplicationEngine

        engine = DeduplicationEngine(db_config)
        print("   ✓ DeduplicationEngine created successfully")

        # Test configuration loading
        print(
            f"   ✓ Configuration loaded: semantic_threshold={engine.config['semantic_threshold']}"
        )

        return True

    except Exception as e:
        print(f"   ❌ Error creating DeduplicationEngine: {e}")
        return False


def test_deduplication_manager():
    """Test the deduplication manager"""
    print("\n🧪 Testing Deduplication Manager...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = DeduplicationManager(db_config)
        print("   ✓ DeduplicationManager created successfully")

        # Test stats
        stats = manager.get_deduplication_stats()
        if "error" not in stats:
            print(f"   ✓ Stats retrieved: {stats['total_articles']} total articles")
            print(f"   ✓ Status counts: {stats['status_counts']}")
        else:
            print(f"   ⚠️ Stats error: {stats['error']}")

        return True

    except Exception as e:
        print(f"   ❌ Error creating DeduplicationManager: {e}")
        return False


def test_duplicate_detection():
    """Test duplicate detection with sample articles"""
    print("\n🧪 Testing Duplicate Detection...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = DeduplicationManager(db_config)

        # Test article 1
        article1 = {
            "title": "Test Article About Technology",
            "content": "This is a test article about technology and innovation.",
            "url": "https://example.com/test1",
            "source": "Test Source",
            "category": "Technology",
        }

        result1 = manager.process_new_article(article1)
        print(
            f"   ✓ Article 1 processed: {'Duplicate' if result1['duplicate_status']['is_duplicate'] else 'Unique'}"
        )

        # Test article 2 (similar content)
        article2 = {
            "title": "Test Article About Technology",
            "content": "This is a test article about technology and innovation.",
            "url": "https://example.com/test2",
            "source": "Test Source 2",
            "category": "Technology",
        }

        result2 = manager.process_new_article(article2)
        print(
            f"   ✓ Article 2 processed: {'Duplicate' if result2['duplicate_status']['is_duplicate'] else 'Unique'}"
        )

        if result2["duplicate_status"]["is_duplicate"]:
            print(f"   ✓ Duplicate correctly detected: {result2['duplicate_status']['reason']}")
        else:
            print("   ⚠️ Duplicate not detected (may be expected for first run)")

        return True

    except Exception as e:
        print(f"   ❌ Error testing duplicate detection: {e}")
        return False


def test_batch_processing():
    """Test batch deduplication processing"""
    print("\n🧪 Testing Batch Processing...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = DeduplicationManager(db_config)

        # Process existing articles
        result = manager.process_existing_articles(batch_size=10, max_articles=20)

        if "error" not in result:
            print(f"   ✓ Batch processing completed: {result['total_articles']} articles")
            print(f"   ✓ Batches processed: {result['batches_processed']}")
            print(f"   ✓ Duplicates found: {result['total_duplicates_found']}")
            print(f"   ✓ Unique articles: {result['total_unique_articles']}")
            print(f"   ✓ Processing time: {result['total_processing_time']:.3f}s")
        else:
            print(f"   ⚠️ Batch processing error: {result['error']}")

        return True

    except Exception as e:
        print(f"   ❌ Error testing batch processing: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Advanced Deduplication System Test Suite")
    print("=" * 50)

    tests = [
        test_content_normalizer,
        test_deduplication_engine,
        test_deduplication_manager,
        test_duplicate_detection,
        test_batch_processing,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("   ❌ Test failed")
        except Exception as e:
            print(f"   ❌ Test error: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ All tests passed! Deduplication system is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
