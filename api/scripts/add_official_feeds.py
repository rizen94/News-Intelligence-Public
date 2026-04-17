#!/usr/bin/env python3
"""
Add official government and SEC RSS feeds to appropriate domains
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use same DB config as RSS collector
try:
    from config.database import get_db_config

    DB_CONFIG = get_db_config()
    # Add timeouts/options
    DB_CONFIG.update({"connect_timeout": 10, "options": "-c statement_timeout=30000"})
except Exception as e:
    logger.warning(f"Failed to load database config: {e}")
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "192.168.93.101"),
        "database": os.getenv("DB_NAME", "news_intel"),
        "user": os.getenv("DB_USER", "newsapp"),
        "password": os.getenv("DB_PASSWORD", ""),
        "port": int(os.getenv("DB_PORT", "5432")),
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000",
    }


def get_db_connection():
    """Get database connection from shared pool. Raises if DB unreachable."""
    from shared.database.connection import get_db_connection as _get_conn

    return _get_conn()


# Official government and SEC feeds by domain
OFFICIAL_FEEDS = {
    "finance": [
        {
            "feed_name": "SEC Press Releases",
            "feed_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom",
            "description": "SEC official press releases and announcements",
        },
        {
            "feed_name": "SEC EDGAR Filings",
            "feed_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom",
            "description": "SEC EDGAR company filings feed",
        },
        {
            "feed_name": "Federal Reserve Press Releases",
            "feed_url": "https://www.federalreserve.gov/feeds/press_all.xml",
            "description": "Federal Reserve Board official press releases",
        },
        {
            "feed_name": "Treasury Direct Announcements",
            "feed_url": "https://www.treasurydirect.gov/rss/announcements.xml",
            "description": "Treasury offering announcements and updates",
        },
        {
            "feed_name": "FDIC News Releases",
            "feed_url": "https://www.fdic.gov/news/news/press/feed.xml",
            "description": "FDIC official news releases",
        },
        {
            "feed_name": "CFTC News Releases",
            "feed_url": "https://www.cftc.gov/PressRoom/PressReleases/index.htm",
            "description": "Commodity Futures Trading Commission news releases",
        },
    ],
    "politics": [
        {
            "feed_name": "White House Briefings",
            "feed_url": "https://www.whitehouse.gov/briefing-room/feed/",
            "description": "White House official briefings and statements",
        },
        {
            "feed_name": "Department of State Press Releases",
            "feed_url": "https://www.state.gov/rss-feed/press-releases/feed/",
            "description": "U.S. Department of State official press releases",
        },
        {
            "feed_name": "Department of Justice Press Releases",
            "feed_url": "https://www.justice.gov/opa/rss/doj-press-releases.xml",
            "description": "DOJ official press releases and announcements",
        },
        {
            "feed_name": "Department of Defense News",
            "feed_url": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=944&max=20",
            "description": "DOD official news and press releases",
        },
        {
            "feed_name": "Congressional Research Service",
            "feed_url": "https://crsreports.congress.gov/rss",
            "description": "Congressional Research Service reports and analysis",
        },
        {
            "feed_name": "GAO Reports",
            "feed_url": "https://www.gao.gov/rss/reports.xml",
            "description": "Government Accountability Office reports",
        },
        {
            "feed_name": "CBO Publications",
            "feed_url": "https://www.cbo.gov/rss/publications.xml",
            "description": "Congressional Budget Office publications",
        },
    ],
    "artificial_intelligence": [
        {
            "feed_name": "NASA News",
            "feed_url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
            "description": "NASA official news and press releases",
        },
        {
            "feed_name": "NSF News",
            "feed_url": "https://www.nsf.gov/news/news_summ.jsp?cntn_id=&org=NSF&from=news",
            "description": "National Science Foundation news",
        },
        {
            "feed_name": "NIST News",
            "feed_url": "https://www.nist.gov/news-events/news/feed",
            "description": "National Institute of Standards and Technology news",
        },
        {
            "feed_name": "Department of Energy News",
            "feed_url": "https://www.energy.gov/feeds/all",
            "description": "DOE official news and press releases",
        },
        {
            "feed_name": "NIH News Releases",
            "feed_url": "https://www.nih.gov/news-events/news-releases/rss",
            "description": "National Institutes of Health news releases",
        },
    ],
}


def add_feeds_to_domain(domain_key: str, schema_name: str, feeds: list):
    """Add feeds to a specific domain schema"""
    conn = get_db_connection()
    if not conn:
        print(f"❌ Failed to connect to database for {domain_key}")
        return 0, 0

    added_count = 0
    skipped_count = 0

    try:
        cur = conn.cursor()

        for feed in feeds:
            feed_name = feed["feed_name"]
            feed_url = feed["feed_url"]
            feed.get("description", "")

            # Check if feed already exists
            cur.execute(
                f"""
                SELECT id FROM {schema_name}.rss_feeds
                WHERE feed_url = %s
            """,
                (feed_url,),
            )

            if cur.fetchone():
                print(f"⏭️  Skipping {feed_name} (already exists)")
                skipped_count += 1
                continue

            # Insert feed
            try:
                cur.execute(
                    f"""
                    INSERT INTO {schema_name}.rss_feeds
                    (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """,
                    (
                        feed_name,
                        feed_url,
                        True,  # is_active
                        3600,  # 1 hour default fetch interval
                        datetime.now(),
                    ),
                )

                feed_id = cur.fetchone()[0]
                conn.commit()
                print(f"✅ Added {feed_name} to {domain_key} (ID: {feed_id})")
                added_count += 1

            except Exception as e:
                print(f"❌ Error adding {feed_name}: {e}")
                conn.rollback()
                continue

        return added_count, skipped_count

    finally:
        conn.close()


def main():
    """Add all official feeds to their respective domains"""
    print("📰 Adding Official Government and SEC RSS Feeds")
    print("=" * 60)

    total_added = 0
    total_skipped = 0

    for domain_key, feeds in OFFICIAL_FEEDS.items():
        schema_name = {
            "finance": "finance",
            "politics": "politics",
            "artificial_intelligence": "artificial_intelligence",
        }.get(domain_key, domain_key)

        print(f"\n📂 Processing {domain_key.upper()} domain ({len(feeds)} feeds)...")
        added, skipped = add_feeds_to_domain(domain_key, schema_name, feeds)
        total_added += added
        total_skipped += skipped

    print("\n" + "=" * 60)
    print("✅ Summary:")
    print(f"   Added: {total_added} feeds")
    print(f"   Skipped: {total_skipped} feeds (already exist)")
    print("=" * 60)


if __name__ == "__main__":
    main()
