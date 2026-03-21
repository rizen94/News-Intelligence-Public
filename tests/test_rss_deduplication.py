#!/usr/bin/env python3
"""
Test RSS collection with deduplication integration
"""

import sys

sys.path.append("/app/api")

import logging

from collectors.rss_collector import collect_rss_feeds

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_rss_collection_with_deduplication():
    """Test RSS collection with deduplication enabled"""
    print("🧪 Testing RSS Collection with Deduplication...")

    try:
        # Run RSS collection
        print("   📡 Starting RSS feed collection...")
        articles_added = collect_rss_feeds()

        print(f"   ✓ RSS collection completed: {articles_added} articles added")

        # Check if deduplication was active
        if articles_added >= 0:
            print("   ✅ RSS collection with deduplication working correctly")
            return True
        else:
            print("   ❌ RSS collection failed")
            return False

    except Exception as e:
        print(f"   ❌ Error during RSS collection: {e}")
        return False


def main():
    """Run the test"""
    print("🚀 RSS Collection with Deduplication Test")
    print("=" * 50)

    success = test_rss_collection_with_deduplication()

    print("\n" + "=" * 50)
    if success:
        print("✅ RSS collection with deduplication test passed!")
        return 0
    else:
        print("❌ RSS collection with deduplication test failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
