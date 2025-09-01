#!/usr/bin/env python3
"""
Simple Scheduler for News Intelligence System v2.7.0
Automates RSS collection and article pruning operations.
"""

import os
import sys
import time
import logging
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import working modules
try:
    from collectors.rss_collector import collect_rss_feeds
    RSS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RSS collector not available: {e}")
    RSS_AVAILABLE = False

try:
    from modules.ingestion.article_pruner import ArticlePruner
    PRUNER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Article pruner not available: {e}")
    PRUNER_AVAILABLE = False

def get_db_config() -> Dict[str, str]:
    """Get database configuration from environment"""
    return {
        'host': os.getenv('DB_HOST', 'postgres'),
        'database': os.getenv('DB_NAME', 'news_system'),
        'user': os.getenv('DB_USER', 'newsapp'),
        'password': os.getenv('DB_PASSWORD', '')
    }

def run_rss_collection() -> bool:
    """Run RSS collection from all active feeds"""
    if not RSS_AVAILABLE:
        logger.error("RSS collector not available")
        return False
    
    try:
        logger.info("🔄 Running scheduled RSS collection...")
        articles_added = collect_rss_feeds()
        logger.info("✅ RSS collection completed")
        return True
    except Exception as e:
        logger.error(f"❌ RSS collection failed: {e}")
        return False

def run_article_pruning() -> bool:
    """Run article pruning pipeline"""
    if not PRUNER_AVAILABLE:
        logger.error("Article pruner not available")
        return False
    
    try:
        logger.info("🧹 Running scheduled article pruning...")
        db_config = get_db_config()
        pruner = ArticlePruner(db_config)
        
        # Run pruning
        results = pruner.run_pruning_pipeline(dry_run=False)
        
        logger.info(f"✅ Article pruning completed: {results['total_articles_removed']} articles removed")
        return True
    except Exception as e:
        logger.error(f"❌ Article pruning failed: {e}")
        return False

def run_scheduled_service():
    """Run the scheduled service with configurable intervals"""
    # Configuration
    rss_interval = int(os.getenv('RSS_INTERVAL_MINUTES', 60))      # RSS collection every X minutes
    pruning_interval = int(os.getenv('PRUNING_INTERVAL_HOURS', 12)) # Pruning every X hours
    max_runtime = int(os.getenv('MAX_RUNTIME_HOURS', 24))          # Maximum runtime in hours
    
    logger.info(f"🚀 Starting scheduled service...")
    logger.info(f"📡 RSS Collection: Every {rss_interval} minutes")
    logger.info(f"🧹 Article Pruning: Every {pruning_interval} hours")
    logger.info(f"⏱️  Max Runtime: {max_runtime} hours")
    
    # Initialize timestamps
    start_time = time.time()
    last_rss_run = start_time - (rss_interval * 60)  # Allow immediate RSS run
    last_pruning_run = start_time - (pruning_interval * 3600)  # Allow immediate pruning run
    
    try:
        while (time.time() - start_time) < (max_runtime * 3600):
            current_time = time.time()
            
            # Check if RSS collection is due
            if (current_time - last_rss_run) >= (rss_interval * 60):
                if run_rss_collection():
                    last_rss_run = current_time
                else:
                    logger.warning("RSS collection failed, will retry on next cycle")
            
            # Check if article pruning is due
            if (current_time - last_pruning_run) >= (pruning_interval * 3600):
                if run_article_pruning():
                    last_pruning_run = current_time
                else:
                    logger.warning("Article pruning failed, will retry on next cycle")
            
            # Sleep for a short interval
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        logger.info("🛑 Scheduled service interrupted by user")
    except Exception as e:
        logger.error(f"❌ Scheduled service failed: {e}")
        raise

def test_components():
    """Test individual components"""
    logger.info("🧪 Testing system components...")
    
    # Test RSS collector
    if RSS_AVAILABLE:
        logger.info("Testing RSS collector...")
        try:
            articles_added = collect_rss_feeds()
            logger.info(f"✅ RSS collector test passed: {articles_added} articles")
        except Exception as e:
            logger.error(f"❌ RSS collector test failed: {e}")
    else:
        logger.warning("⚠️ RSS collector not available for testing")
    
    # Test article pruner
    if PRUNER_AVAILABLE:
        logger.info("Testing article pruner...")
        try:
            db_config = get_db_config()
            pruner = ArticlePruner(db_config)
            results = pruner.run_pruning_pipeline(dry_run=True)
            logger.info(f"✅ Article pruner test passed: {results}")
        except Exception as e:
            logger.error(f"❌ Article pruner test failed: {e}")
    else:
        logger.warning("⚠️ Article pruner not available for testing")
    
    logger.info("🧪 Component testing completed")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 simple_scheduler.py {start|test}")
        print("  start - Run the scheduled service")
        print("  test  - Test individual components")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "start":
        run_scheduled_service()
    elif command == "test":
        test_components()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: start, test")
        sys.exit(1)

if __name__ == "__main__":
    main()
