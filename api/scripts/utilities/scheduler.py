#!/usr/bin/env python3
"""
Simple Scheduler for News Intelligence System v2.0.0
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

def _get_db_config() -> Dict[str, str]:
    """Database config from shared source (DB_* env). Run with api as cwd or PYTHONPATH=api."""
    import sys
    _api = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _api not in sys.path:
        sys.path.insert(0, _api)
    from shared.database.connection import get_db_config
    return get_db_config()

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
        db_config = _get_db_config()
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
                    logger.warning("⚠️  RSS collection failed, will retry next cycle")
            
            # Check if pruning is due
            if (current_time - last_pruning_run) >= (pruning_interval * 3600):
                if run_article_pruning():
                    last_pruning_run = current_time
                else:
                    logger.warning("⚠️  Article pruning failed, will retry next cycle")
            
            # Sleep for 1 minute before next check
            time.sleep(60)
            
            # Log status every hour
            if int(current_time - start_time) % 3600 < 60:
                elapsed_hours = (current_time - start_time) / 3600
                logger.info(f"📊 Service running for {elapsed_hours:.1f} hours")
                
    except KeyboardInterrupt:
        logger.info("🛑 Service stopped by user")
    except Exception as e:
        logger.error(f"💥 Service error: {e}")
    finally:
        logger.info("🔄 Service stopped")

def run_test_mode():
    """Run in test mode (single execution)"""
    logger.info("🧪 Running in test mode (single execution)")
    
    # Test RSS collection
    logger.info("🔄 Running scheduled RSS collection...")
    if run_rss_collection():
        logger.info("✅ RSS collection completed")
    else:
        logger.error("❌ RSS collection failed")
    
    # Test article pruning
    logger.info("🧹 Running scheduled article pruning...")
    if run_article_pruning():
        logger.info("✅ Article pruning completed")
    else:
        logger.error("❌ Article pruning failed")
    
    logger.info("🎉 Test completed successfully!")

def show_status():
    """Show service status"""
    print("📊 News Intelligence System v2.0.0 Scheduler Status")
    print("=" * 60)
    
    # Check module availability
    print(f"RSS Collector: {'✅ Available' if RSS_AVAILABLE else '❌ Not Available'}")
    print(f"Article Pruner: {'✅ Available' if PRUNER_AVAILABLE else '❌ Not Available'}")
    
    # Check database connection
    try:
        from shared.database.connection import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get basic stats
        cur.execute("SELECT COUNT(*) FROM articles")
        article_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM rss_feeds WHERE is_active = true")
        active_feeds = cur.fetchone()[0]
        
        print(f"Database: ✅ Connected")
        print(f"Articles: {article_count}")
        print(f"Active Feeds: {active_feeds}")
        
        conn.close()
    except Exception as e:
        print(f"Database: ❌ Connection Failed - {e}")
    
    # Show configuration
    print(f"\nConfiguration:")
    print(f"RSS Interval: {os.getenv('RSS_INTERVAL_MINUTES', 60)} minutes")
    print(f"Pruning Interval: {os.getenv('PRUNING_INTERVAL_HOURS', 12)} hours")
    print(f"Max Runtime: {os.getenv('MAX_RUNTIME_HOURS', 24)} hours")
    
    print("\nAvailable Commands:")
    print("  start     - Start scheduled service")
    print("  test      - Run test mode (single execution)")
    print("  status    - Show service status")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 scheduler.py [command]")
        print("Commands:")
        print("  start     - Start scheduled service")
        print("  test      - Run test mode (single execution)")
        print("  status    - Show service status")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "start":
        run_scheduled_service()
    elif command == "test":
        run_test_mode()
    elif command == "status":
        show_status()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: start, test, status")
        sys.exit(1)

if __name__ == "__main__":
    main()
