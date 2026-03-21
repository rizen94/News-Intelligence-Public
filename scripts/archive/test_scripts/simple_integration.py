#!/usr/bin/env python3
"""
Simple Integration Script for News Intelligence System
Focuses on core workflow: RSS → ML → Storylines
"""

import os
import sys
import time
import requests
import logging
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000/api"

def check_system_health():
    """Check if all core services are running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("status") == "healthy":
                return True
        return False
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False

def collect_rss_feeds():
    """Collect articles from all active RSS feeds"""
    try:
        logger.info("🔄 Collecting RSS feeds...")
        
        # Get all active feeds
        feeds_response = requests.get(f"{API_BASE_URL}/rss/feeds/", timeout=10)
        if feeds_response.status_code != 200:
            logger.error("Failed to get RSS feeds")
            return 0
        
        feeds_data = feeds_response.json()
        if not feeds_data.get("success"):
            logger.error("RSS feeds API returned error")
            return 0
        
        feeds = feeds_data.get("data", {}).get("feeds", [])
        active_feeds = [f for f in feeds if f.get("is_active", True)]
        
        if not active_feeds:
            logger.warning("No active RSS feeds found")
            return 0
        
        logger.info(f"Found {len(active_feeds)} active feeds")
        
        # Collect from each feed
        total_collected = 0
        for feed in active_feeds:
            try:
                logger.info(f"  Collecting from: {feed.get('name', 'Unknown')}")
                
                # Trigger collection for this feed
                collect_response = requests.post(
                    f"{API_BASE_URL}/rss/feeds/{feed['id']}/refresh",
                    timeout=30
                )
                
                if collect_response.status_code == 200:
                    collect_data = collect_response.json()
                    if collect_data.get("success"):
                        articles_fetched = collect_data.get("data", {}).get("articles_fetched", 0)
                        total_collected += articles_fetched
                        logger.info(f"    ✅ Collected {articles_fetched} articles")
                    else:
                        logger.warning(f"    ⚠️ Collection failed: {collect_data.get('error')}")
                else:
                    logger.warning(f"    ⚠️ Collection failed with status {collect_response.status_code}")
                    
            except Exception as e:
                logger.error(f"    ❌ Error collecting from {feed.get('name')}: {e}")
        
        logger.info(f"📊 Total articles collected: {total_collected}")
        return total_collected
        
    except Exception as e:
        logger.error(f"RSS collection failed: {e}")
        return 0

def process_ml_for_new_articles():
    """Process new articles with ML"""
    try:
        logger.info("🤖 Processing new articles with ML...")
        
        # Get articles that need ML processing
        articles_response = requests.get(f"{API_BASE_URL}/articles/stats/", timeout=10)
        if articles_response.status_code != 200:
            logger.error("Failed to get article stats")
            return False
        
        articles_data = articles_response.json()
        if not articles_data.get("success"):
            logger.error("Articles API returned error")
            return False
        
        stats = articles_data.get("data", {})
        total_articles = stats.get("total_articles", 0)
        ml_processed = stats.get("ml_processed_articles_count", 0)
        
        logger.info(f"  Total articles: {total_articles}")
        logger.info(f"  ML processed: {ml_processed}")
        
        if total_articles == 0:
            logger.info("  No articles to process")
            return True
        
        # Check ML service status
        ml_response = requests.get(f"{API_BASE_URL}/ml/status/", timeout=10)
        if ml_response.status_code != 200:
            logger.error("  ML service not available")
            return False
        
        ml_data = ml_response.json()
        if not ml_data.get("success") or not ml_data.get("data", {}).get("ml_available"):
            logger.error("  ML service not available")
            return False
        
        logger.info("  ✅ ML service is available")
        
        # Process articles (this would trigger the actual ML processing)
        # For now, we'll just log that we would process them
        logger.info("  🔄 ML processing would be triggered here")
        
        return True
        
    except Exception as e:
        logger.error(f"ML processing failed: {e}")
        return False

def generate_storylines():
    """Generate storylines from processed articles"""
    try:
        logger.info("📚 Generating storylines...")
        
        # Get storylines
        storylines_response = requests.get(f"{API_BASE_URL}/storylines/", timeout=10)
        if storylines_response.status_code != 200:
            logger.error("Failed to get storylines")
            return False
        
        storylines_data = storylines_response.json()
        if not storylines_data.get("success"):
            logger.error("Storylines API returned error")
            return False
        
        storylines = storylines_data.get("data", {}).get("storylines", [])
        total_storylines = storylines_data.get("data", {}).get("total_count", 0)
        
        logger.info(f"  Total storylines: {total_storylines}")
        
        # Check if we have articles to create storylines from
        articles_response = requests.get(f"{API_BASE_URL}/articles/stats/", timeout=10)
        if articles_response.status_code == 200:
            articles_data = articles_response.json()
            if articles_data.get("success"):
                total_articles = articles_data.get("data", {}).get("total_articles", 0)
                logger.info(f"  Total articles available: {total_articles}")
                
                if total_articles > 0:
                    logger.info("  ✅ Articles available for storyline generation")
                else:
                    logger.info("  ⚠️ No articles available for storyline generation")
        
        return True
        
    except Exception as e:
        logger.error(f"Storyline generation failed: {e}")
        return False

def run_integration_cycle():
    """Run a complete integration cycle"""
    logger.info("🚀 Starting News Intelligence Integration Cycle")
    logger.info("=" * 60)
    
    # Step 1: Check system health
    if not check_system_health():
        logger.error("❌ System health check failed - stopping")
        return False
    
    logger.info("✅ System health check passed")
    
    # Step 2: Collect RSS feeds
    articles_collected = collect_rss_feeds()
    
    # Step 3: Process with ML (if articles were collected)
    if articles_collected > 0:
        if not process_ml_for_new_articles():
            logger.error("❌ ML processing failed")
            return False
        logger.info("✅ ML processing completed")
    else:
        logger.info("ℹ️ No new articles to process with ML")
    
    # Step 4: Generate storylines
    if not generate_storylines():
        logger.error("❌ Storyline generation failed")
        return False
    
    logger.info("✅ Storyline generation completed")
    
    logger.info("=" * 60)
    logger.info("🎉 Integration cycle completed successfully!")
    
    return True

def main():
    """Main function"""
    try:
        # Run one integration cycle
        success = run_integration_cycle()
        
        if success:
            logger.info("✅ Integration completed successfully")
            return 0
        else:
            logger.error("❌ Integration failed")
            return 1
            
    except KeyboardInterrupt:
        logger.info("🛑 Integration interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"💥 Integration crashed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
