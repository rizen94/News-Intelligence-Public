#!/usr/bin/env python3
"""
Automated RSS Collection and ML Processing Script
Runs RSS collection and immediately processes articles through ML pipeline
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from collectors.rss_collector import collect_rss_feeds

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class AutomatedCollection:
    def __init__(self):
        self.api_base_url = "http://localhost:8000"

    def collect_rss_feeds(self):
        """Collect articles from all active RSS feeds"""
        logger.info("Starting RSS collection...")

        try:
            # Use the existing collect_rss_feeds function
            articles_collected = collect_rss_feeds()
            logger.info(f"RSS collection completed. Total articles collected: {articles_collected}")
            return articles_collected

        except Exception as e:
            logger.error(f"Error during RSS collection: {str(e)}")
            return 0

    def trigger_ml_processing(self):
        """Trigger ML processing for raw articles"""
        logger.info("Triggering ML processing...")

        try:
            # Get count of raw articles using direct database connection
            import psycopg2

            conn = psycopg2.connect(
                host="postgres", database="news_system", user="newsapp", password="newsapp_password"
            )
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles WHERE processing_status = 'raw'")
            raw_count = cursor.fetchone()[0]
            conn.close()

            if raw_count == 0:
                logger.info("No raw articles to process")
                return 0

            logger.info(f"Found {raw_count} raw articles to process")

            # Trigger ML processing via API
            response = requests.post(
                f"{self.api_base_url}/api/ml-management/process",
                json={"article_ids": [], "job_type": "full_processing"},
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"ML processing triggered successfully: {result}")
                return raw_count
            else:
                logger.error(
                    f"Failed to trigger ML processing: {response.status_code} - {response.text}"
                )
                return 0

        except Exception as e:
            logger.error(f"Error triggering ML processing: {str(e)}")
            return 0

    def run_collection_cycle(self):
        """Run a complete collection and processing cycle"""
        logger.info("=" * 50)
        logger.info(f"Starting automated collection cycle at {datetime.now()}")
        logger.info("=" * 50)

        # Step 1: Collect RSS feeds
        articles_collected = self.collect_rss_feeds()

        # Step 2: Trigger ML processing if articles were collected
        if articles_collected > 0:
            self.trigger_ml_processing()
        else:
            logger.info("No new articles collected, skipping ML processing")

        logger.info(f"Collection cycle completed at {datetime.now()}")
        logger.info("=" * 50)

        return articles_collected


def main():
    """Main entry point"""
    collection = AutomatedCollection()

    try:
        articles_collected = collection.run_collection_cycle()
        print(f"Collection completed. Articles collected: {articles_collected}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Collection failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
