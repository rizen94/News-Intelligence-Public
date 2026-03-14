#!/usr/bin/env python3
"""
Simple Ingestion Manager for News Intelligence System v2.0.0
Orchestrates RSS collection and article pruning operations.
"""

import os
import sys
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
    from collectors.enhanced_rss_collector import collect_enhanced_rss
    RSS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"RSS collectors not available: {e}")
    RSS_AVAILABLE = False

try:
    from modules.ingestion.article_pruner import ArticlePruner
    PRUNER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Article pruner not available: {e}")
    PRUNER_AVAILABLE = False

def _get_db_config() -> Dict[str, str]:
    """Database config from shared source. Run from api/ or with PYTHONPATH=api."""
    _api = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _api not in sys.path:
        sys.path.insert(0, _api)
    from shared.database.connection import get_db_config
    return get_db_config()

def run_rss_collection() -> bool:
    """Run RSS collection from all active feeds"""
    if not RSS_AVAILABLE:
        logger.error("RSS collectors not available")
        return False
    
    try:
        logger.info("Starting RSS feed collection...")
        articles_added = collect_rss_feeds()
        logger.info(f"RSS collection completed successfully")
        return True
    except Exception as e:
        logger.error(f"RSS collection failed: {e}")
        return False

def run_enhanced_rss_collection() -> bool:
    """Run enhanced RSS collection with full content extraction"""
    if not RSS_AVAILABLE:
        logger.error("RSS collectors not available")
        return False
    
    try:
        logger.info("Starting enhanced RSS collection...")
        articles_processed = collect_enhanced_rss()
        logger.info(f"Enhanced RSS collection completed successfully")
        return True
    except Exception as e:
        logger.error(f"Enhanced RSS collection failed: {e}")
        return False

def run_article_pruning() -> bool:
    """Run article pruning pipeline"""
    if not PRUNER_AVAILABLE:
        logger.error("Article pruner not available")
        return False
    
    try:
        logger.info("Starting article pruning pipeline...")
        db_config = _get_db_config()
        pruner = ArticlePruner(db_config)
        
        # Run pruning with dry run first to show what would be done
        logger.info("Running pruning analysis...")
        results = pruner.run_pruning_pipeline(dry_run=True)
        
        # Show results
        logger.info(f"Pruning analysis completed: {results['total_articles_removed']} articles would be removed")
        
        # Run actual pruning
        logger.info("Running actual pruning...")
        results = pruner.run_pruning_pipeline(dry_run=False)
        
        logger.info(f"Article pruning completed successfully: {results['total_articles_removed']} articles removed")
        return True
    except Exception as e:
        logger.error(f"Article pruning failed: {e}")
        return False

def run_basic_pipeline() -> bool:
    """Run basic pipeline (RSS collection + pruning)"""
    logger.info("Starting basic pipeline (RSS + Pruning)...")
    
    # Run RSS collection
    if not run_rss_collection():
        logger.error("RSS collection failed, stopping pipeline")
        return False
    
    # Run article pruning
    if not run_article_pruning():
        logger.error("Article pruning failed, stopping pipeline")
        return False
    
    logger.info("Basic pipeline completed successfully")
    return True

def show_status() -> None:
    """Show system status"""
    print("📊 News Intelligence System v2.0.0 Status")
    print("=" * 50)
    
    # Check module availability
    print(f"RSS Collectors: {'✅ Available' if RSS_AVAILABLE else '❌ Not Available'}")
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
    
    print("\nAvailable Commands:")
    print("  rss       - Run RSS collection")
    print("  enhanced  - Run enhanced RSS collection")
    print("  prune     - Run article pruning")
    print("  basic     - Run basic pipeline (RSS + Pruning)")
    print("  status    - Show system status")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 manage_ingestion_simple.py [command]")
        print("Commands:")
        print("  rss       - Run RSS collection once")
        print("  enhanced  - Run enhanced RSS collection once")
        print("  prune     - Run article pruning once")
        print("  basic     - Run basic pipeline (RSS + Pruning)")
        print("  status    - Show system status")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "rss":
        if not RSS_AVAILABLE:
            logger.error("RSS collectors not available")
            sys.exit(1)
        success = run_rss_collection()
        sys.exit(0 if success else 1)
    
    elif command == "enhanced":
        if not RSS_AVAILABLE:
            logger.error("RSS collectors not available")
            sys.exit(1)
        success = run_enhanced_rss_collection()
        sys.exit(0 if success else 1)
    
    elif command == "prune":
        if not PRUNER_AVAILABLE:
            logger.error("Article pruner not available")
            sys.exit(1)
        success = run_article_pruning()
        sys.exit(0 if success else 1)
    
    elif command == "basic":
        success = run_basic_pipeline()
        sys.exit(0 if success else 1)
    
    elif command == "status":
        show_status()
        sys.exit(0)
    
    else:
        print(f"Unknown command: {command}")
        print("Available commands: rss, enhanced, prune, basic, status")
        sys.exit(1)

if __name__ == "__main__":
    main()
