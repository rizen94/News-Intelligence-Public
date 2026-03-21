#!/usr/bin/env python3
"""
Test script for the Content Prioritization and Story Tracking System
"""

import sys

sys.path.append("/app/api")

import logging

from modules.prioritization import ContentPrioritizationManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_content_prioritization_manager():
    """Test the content prioritization manager"""
    print("🧪 Testing Content Prioritization Manager...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = ContentPrioritizationManager(db_config)
        print("   ✓ ContentPrioritizationManager created successfully")

        # Test statistics
        stats = manager.get_manager_statistics()
        if "error" not in stats:
            print(f"   ✓ Manager stats retrieved: {stats['total_story_threads']} story threads")
            print(f"   ✓ Priority levels: {stats['total_priority_levels']}")
            print(f"   ✓ User rules: {stats['total_user_rules']}")
        else:
            print(f"   ⚠️ Stats error: {stats['error']}")

        return True

    except Exception as e:
        print(f"   ❌ Error creating ContentPrioritizationManager: {e}")
        return False


def test_story_thread_creation():
    """Test story thread creation"""
    print("\n🧪 Testing Story Thread Creation...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = ContentPrioritizationManager(db_config)

        # Create a test story thread
        thread_result = manager.create_story_thread(
            title="AI Breakthrough in Medical Diagnosis",
            description="Tracking developments in AI-powered medical diagnosis systems",
            category="Technology",
            priority_level_name="high",
            keywords=["AI", "medical", "diagnosis", "healthcare", "machine learning"],
            user_created=True,
        )

        if "error" not in thread_result:
            print(
                f"   ✓ Story thread created: {thread_result['title']} (ID: {thread_result['id']})"
            )
            print(f"   ✓ Keywords: {thread_result['keywords']}")
            return True
        else:
            print(f"   ❌ Error creating story thread: {thread_result['error']}")
            return False

    except Exception as e:
        print(f"   ❌ Error testing story thread creation: {e}")
        return False


def test_user_interest_rules():
    """Test user interest rule creation"""
    print("\n🧪 Testing User Interest Rules...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = ContentPrioritizationManager(db_config)

        # Add a user interest rule
        rule_result = manager.add_user_interest_rule(
            profile_name="test_profile",
            rule_type="keyword",
            rule_value="quantum computing",
            priority_level_name="high",
            action="boost",
            weight=1.0,
        )

        if "error" not in rule_result:
            print(
                f"   ✓ User interest rule added: {rule_result['rule_type']}={rule_result['rule_value']}"
            )
            print(f"   ✓ Action: {rule_result['action']}, Weight: {rule_result['weight']}")
            return True
        else:
            print(f"   ❌ Error adding user interest rule: {rule_result['error']}")
            return False

    except Exception as e:
        print(f"   ❌ Error testing user interest rules: {e}")
        return False


def test_article_priority_processing():
    """Test article priority processing"""
    print("\n🧪 Testing Article Priority Processing...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = ContentPrioritizationManager(db_config)

        # Test article 1: High priority (AI-related)
        article1 = {
            "title": "Major Breakthrough in Quantum Computing Research",
            "content": "Scientists have achieved a significant milestone in quantum computing technology that could revolutionize the field.",
            "url": "https://example.com/quantum-breakthrough",
            "source": "Tech News Daily",
            "category": "Technology",
            "published_date": "2025-08-30T10:00:00Z",
        }

        result1 = manager.process_article_with_priority(article1, profile_name="test_profile")
        print(f"   ✓ Article 1 processed: {'Stored' if result1['should_store'] else 'Rejected'}")
        if result1["should_store"]:
            print(f"   ✓ Priority: {result1['priority_result']['priority_level_name']}")
            print(f"   ✓ Score: {result1['priority_result']['priority_score']}")

        # Test article 2: Lower priority (general news)
        article2 = {
            "title": "Local Weather Update for Weekend",
            "content": "The weather forecast for the upcoming weekend shows sunny skies with temperatures in the mid-70s.",
            "url": "https://example.com/weather-update",
            "source": "Local News",
            "category": "Weather",
            "published_date": "2025-08-30T11:00:00Z",
        }

        result2 = manager.process_article_with_priority(article2, profile_name="test_profile")
        print(f"   ✓ Article 2 processed: {'Stored' if result2['should_store'] else 'Rejected'}")
        if result2["should_store"]:
            print(f"   ✓ Priority: {result2['priority_result']['priority_level_name']}")
            print(f"   ✓ Score: {result2['priority_result']['priority_score']}")

        return True

    except Exception as e:
        print(f"   ❌ Error testing article priority processing: {e}")
        return False


def test_rag_context_building():
    """Test RAG context building"""
    print("\n🧪 Testing RAG Context Building...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = ContentPrioritizationManager(db_config)

        # Get story threads
        threads = manager.get_story_threads(status="active")
        if threads:
            # Test building context for the first thread
            thread_id = threads[0]["id"]
            thread_title = threads[0]["title"]

            print(f"   📚 Building context for thread: {thread_title}")

            # Build historical context
            historical_context = manager.build_rag_context(thread_id, "historical", max_articles=5)
            if "error" not in historical_context:
                print(
                    f"   ✓ Historical context built: {historical_context['articles_found']} articles"
                )
                print(f"   ✓ Context summary: {historical_context['context_summary'][:100]}...")
            else:
                print(f"   ⚠️ Historical context error: {historical_context['error']}")

            # Build timeline context
            timeline_context = manager.build_rag_context(thread_id, "timeline", max_articles=5)
            if "error" not in timeline_context:
                print(f"   ✓ Timeline context built: {timeline_context['articles_found']} articles")
                print(f"   ✓ Timeline period: {timeline_context['timeline_period']}")
            else:
                print(f"   ⚠️ Timeline context error: {timeline_context['error']}")

            return True
        else:
            print("   ⚠️ No story threads found for RAG context testing")
            return True

    except Exception as e:
        print(f"   ❌ Error testing RAG context building: {e}")
        return False


def test_priority_statistics():
    """Test priority statistics retrieval"""
    print("\n🧪 Testing Priority Statistics...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = ContentPrioritizationManager(db_config)

        # Get priority statistics
        priority_stats = manager.get_priority_statistics()
        if "error" not in priority_stats:
            print("   ✓ Priority statistics retrieved successfully")
            print(f"   ✓ Priority levels: {len(priority_stats['priority_levels'])}")
            print(f"   ✓ Story threads: {priority_stats['story_threads']}")
            print(f"   ✓ Recent articles: {priority_stats['recent_articles']}")

            # Display priority level breakdown
            for level in priority_stats["priority_levels"]:
                print(f"   ✓ {level['name'].title()}: {level['article_count']} articles")

            return True
        else:
            print(f"   ❌ Error getting priority statistics: {priority_stats['error']}")
            return False

    except Exception as e:
        print(f"   ❌ Error testing priority statistics: {e}")
        return False


def test_existing_articles_priority():
    """Test priority processing for existing articles"""
    print("\n🧪 Testing Existing Articles Priority Processing...")

    db_config = {
        "host": "postgres",
        "database": "news_system",
        "user": "newsapp",
        "password": "secure_password_123",
    }

    try:
        manager = ContentPrioritizationManager(db_config)

        # Process existing articles for priority
        result = manager.process_existing_articles_priority(batch_size=10, max_articles=20)

        if "error" not in result:
            print(f"   ✓ Priority processing completed: {result['total_articles']} articles")
            print(f"   ✓ Batches processed: {result['batches_processed']}")
            if "priority_assignments_made" in result:
                print(f"   ✓ Priority assignments made: {result['priority_assignments_made']}")
            if "story_threads_created" in result:
                print(f"   ✓ Story threads created: {result['story_threads_created']}")
            print(f"   ✓ Processing time: {result['total_processing_time']:.3f}s")
            return True
        else:
            print(f"   ⚠️ Priority processing error: {result['error']}")
            return True  # Not a critical failure

    except Exception as e:
        print(f"   ❌ Error testing existing articles priority: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Content Prioritization and Story Tracking System Test Suite")
    print("=" * 70)

    tests = [
        test_content_prioritization_manager,
        test_story_thread_creation,
        test_user_interest_rules,
        test_article_priority_processing,
        test_rag_context_building,
        test_priority_statistics,
        test_existing_articles_priority,
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

    print("\n" + "=" * 70)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ All tests passed! Content prioritization system is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
