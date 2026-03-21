#!/usr/bin/env python3
"""
RSS Feed Restoration Script
Restores politics feeds and adds finance feeds for v4.0 domain silos
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.shared.database.connection import get_db_connection

# Politics RSS Feeds (from RSS_FEEDS_USA_POLITICS_ADDED.md)
POLITICS_FEEDS = [
    # USA National Politics
    {
        'feed_name': 'CNN Politics',
        'feed_url': 'https://rss.cnn.com/rss/edition_politics.rss',
        'description': 'CNN Politics - Latest political news and analysis',
        'country': 'US',
        'language_code': 'en',
    },
    {
        'feed_name': 'BBC US Politics',
        'feed_url': 'https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml',
        'description': 'BBC News - US and Canada politics coverage',
        'country': 'US',
        'language_code': 'en',
    },
    {
        'feed_name': 'Reuters US Politics',
        'feed_url': 'https://feeds.reuters.com/Reuters/PoliticsNews',
        'description': 'Reuters - US Politics news and analysis',
        'country': 'US',
        'language_code': 'en',
    },
    {
        'feed_name': 'Associated Press Politics',
        'feed_url': 'https://feeds.apnews.com/rss/apf-politics',
        'description': 'Associated Press - US Politics coverage',
        'country': 'US',
        'language_code': 'en',
    },
    {
        'feed_name': 'Politico',
        'feed_url': 'https://www.politico.com/rss/politicopicks.xml',
        'description': 'Politico - Political news and analysis',
        'country': 'US',
        'language_code': 'en',
    },
    {
        'feed_name': 'The Hill',
        'feed_url': 'https://thehill.com/rss/syndicator/19110',
        'description': 'The Hill - Congressional and political news',
        'country': 'US',
        'language_code': 'en',
    },
    {
        'feed_name': 'Roll Call',
        'feed_url': 'https://rollcall.com/feed/',
        'description': 'Roll Call - Congressional news and analysis',
        'country': 'US',
        'language_code': 'en',
    },
    {
        'feed_name': 'C-SPAN',
        'feed_url': 'https://www.c-span.org/rss/cspan.xml',
        'description': 'C-SPAN - Congressional and political coverage',
        'country': 'US',
        'language_code': 'en',
    },
    # International US Politics
    {
        'feed_name': 'Guardian US Politics',
        'feed_url': 'https://www.theguardian.com/us-news/us-politics/rss',
        'description': 'The Guardian - US Politics from UK perspective',
        'country': 'UK',
        'language_code': 'en',
    },
    {
        'feed_name': 'Financial Times US Politics',
        'feed_url': 'https://www.ft.com/rss/home/us',
        'description': 'Financial Times - US Politics and policy',
        'country': 'UK',
        'language_code': 'en',
    },
    {
        'feed_name': 'Deutsche Welle US Politics',
        'feed_url': 'https://rss.dw.com/xml/rss-en-all',
        'description': 'Deutsche Welle - US Politics from German perspective',
        'country': 'Germany',
        'language_code': 'en',
    },
    {
        'feed_name': 'France 24 US Politics',
        'feed_url': 'https://www.france24.com/en/rss',
        'description': 'France 24 - US Politics from French perspective',
        'country': 'France',
        'language_code': 'en',
    },
    {
        'feed_name': 'Al Jazeera US Politics',
        'feed_url': 'https://www.aljazeera.com/xml/rss/all.xml',
        'description': 'Al Jazeera - US Politics from Middle East perspective',
        'country': 'Qatar',
        'language_code': 'en',
    },
    {
        'feed_name': 'CBC US Politics',
        'feed_url': 'https://rss.cbc.ca/rss/cbcworldnews.xml',
        'description': 'CBC - US Politics from Canadian perspective',
        'country': 'Canada',
        'language_code': 'en',
    },
    {
        'feed_name': 'ABC News Australia US Politics',
        'feed_url': 'https://www.abc.net.au/news/feed/45910/rss.xml',
        'description': 'ABC News Australia - US Politics coverage',
        'country': 'Australia',
        'language_code': 'en',
    },
    {
        'feed_name': 'Japan Times US Politics',
        'feed_url': 'https://www.japantimes.co.jp/rss/news/',
        'description': 'Japan Times - US Politics from Japanese perspective',
        'country': 'Japan',
        'language_code': 'en',
    },
]

# Finance RSS Feeds - Market Research & Corporate News
FINANCE_FEEDS = [
    # Major Financial News Sources
    {
        'feed_name': 'Bloomberg Markets',
        'feed_url': 'https://feeds.bloomberg.com/markets/news.rss',
        'description': 'Bloomberg - Market news and analysis',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Bloomberg Business',
        'feed_url': 'https://feeds.bloomberg.com/business/news.rss',
        'description': 'Bloomberg - Business news and corporate updates',
        'country': 'US',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Financial Times Markets',
        'feed_url': 'https://www.ft.com/markets?format=rss',
        'description': 'Financial Times - Global markets coverage',
        'country': 'UK',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Financial Times Companies',
        'feed_url': 'https://www.ft.com/companies?format=rss',
        'description': 'Financial Times - Corporate news and announcements',
        'country': 'UK',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'CNBC Markets',
        'feed_url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
        'description': 'CNBC - Market news and analysis',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'CNBC Business',
        'feed_url': 'https://www.cnbc.com/id/10001147/device/rss/rss.html',
        'description': 'CNBC - Business news and corporate updates',
        'country': 'US',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Wall Street Journal Markets',
        'feed_url': 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',
        'description': 'Wall Street Journal - Markets and trading',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Wall Street Journal Business',
        'feed_url': 'https://feeds.a.dj.com/rss/RSSBusiness.xml',
        'description': 'Wall Street Journal - Business and corporate news',
        'country': 'US',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Reuters Business',
        'feed_url': 'https://feeds.reuters.com/reuters/businessNews',
        'description': 'Reuters - Business news and corporate announcements',
        'country': 'US',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Reuters Markets',
        'feed_url': 'https://feeds.reuters.com/reuters/marketsNews',
        'description': 'Reuters - Market news and analysis',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Yahoo Finance',
        'feed_url': 'https://finance.yahoo.com/news/rssindex',
        'description': 'Yahoo Finance - Financial news and market updates',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'MarketWatch',
        'feed_url': 'https://www.marketwatch.com/rss/topstories',
        'description': 'MarketWatch - Market news and analysis',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Forbes Business',
        'feed_url': 'https://www.forbes.com/business/feed/',
        'description': 'Forbes - Business news and corporate insights',
        'country': 'US',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Barron\'s',
        'feed_url': 'https://www.barrons.com/feed',
        'description': 'Barron\'s - Financial markets and investment news',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Financial Times Lex',
        'feed_url': 'https://www.ft.com/lex?format=rss',
        'description': 'Financial Times Lex - Financial analysis and commentary',
        'country': 'UK',
        'language_code': 'en',
        'category': 'market_patterns',
    },
    {
        'feed_name': 'Seeking Alpha',
        'feed_url': 'https://seekingalpha.com/feed.xml',
        'description': 'Seeking Alpha - Market analysis and investment research',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_patterns',
    },
]

# International Finance RSS Feeds - Global Markets Coverage
INTERNATIONAL_FINANCE_FEEDS = [
    # European Markets
    {
        'feed_name': 'Financial Times Europe Markets',
        'feed_url': 'https://www.ft.com/europe?format=rss',
        'description': 'Financial Times - European markets and financial news',
        'country': 'UK',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Bloomberg Europe',
        'feed_url': 'https://feeds.bloomberg.com/markets/news.rss',
        'description': 'Bloomberg - European markets coverage',
        'country': 'UK',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Reuters Europe Business',
        'feed_url': 'https://feeds.reuters.com/reuters/europeBusiness',
        'description': 'Reuters - European business and markets',
        'country': 'UK',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'The Guardian Business',
        'feed_url': 'https://www.theguardian.com/business/rss',
        'description': 'The Guardian - UK and European business news',
        'country': 'UK',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'BBC Business',
        'feed_url': 'https://feeds.bbci.co.uk/news/business/rss.xml',
        'description': 'BBC - UK and international business news',
        'country': 'UK',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Deutsche Welle Business',
        'feed_url': 'https://rss.dw.com/xml/rss-en-business',
        'description': 'Deutsche Welle - German and European business news (English)',
        'country': 'Germany',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Euronews Business',
        'feed_url': 'https://www.euronews.com/rss?format=mrss',
        'description': 'Euronews - European business and markets (English)',
        'country': 'France',
        'language_code': 'en',
        'category': 'market_research',
    },
    
    # Asian Markets
    {
        'feed_name': 'Financial Times Asia',
        'feed_url': 'https://www.ft.com/asia-pacific?format=rss',
        'description': 'Financial Times - Asian markets and financial news',
        'country': 'UK',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Bloomberg Asia',
        'feed_url': 'https://feeds.bloomberg.com/markets/news.rss',
        'description': 'Bloomberg - Asian markets coverage',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Reuters Asia Business',
        'feed_url': 'https://feeds.reuters.com/reuters/asiaBusiness',
        'description': 'Reuters - Asian business and markets',
        'country': 'US',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Nikkei Asian Review',
        'feed_url': 'https://asia.nikkei.com/rss/feed/nar',
        'description': 'Nikkei - Asian business and markets (English)',
        'country': 'Japan',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'South China Morning Post Business',
        'feed_url': 'https://www.scmp.com/rss/2/feed',
        'description': 'SCMP - Asian business news, China focus (English)',
        'country': 'Hong Kong',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Straits Times Business',
        'feed_url': 'https://www.straitstimes.com/rss',
        'description': 'Straits Times - Singapore and Southeast Asia business (English)',
        'country': 'Singapore',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'The Australian Financial Review',
        'feed_url': 'https://www.afr.com/rss.xml',
        'description': 'AFR - Australian and Asia-Pacific financial news',
        'country': 'Australia',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Business Times Singapore',
        'feed_url': 'https://www.businesstimes.com.sg/rss',
        'description': 'Business Times - Singapore financial markets (English)',
        'country': 'Singapore',
        'language_code': 'en',
        'category': 'market_research',
    },
    
    # Global/International
    {
        'feed_name': 'Financial Times Global Economy',
        'feed_url': 'https://www.ft.com/global-economy?format=rss',
        'description': 'Financial Times - Global economy and markets',
        'country': 'UK',
        'language_code': 'en',
        'category': 'market_patterns',
    },
    {
        'feed_name': 'Reuters World Business',
        'feed_url': 'https://feeds.reuters.com/reuters/businessNews',
        'description': 'Reuters - Global business and markets',
        'country': 'US',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Bloomberg World Markets',
        'feed_url': 'https://feeds.bloomberg.com/markets/news.rss',
        'description': 'Bloomberg - Global markets and financial news',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Al Jazeera Business',
        'feed_url': 'https://www.aljazeera.com/xml/rss/all.xml',
        'description': 'Al Jazeera - Global business news (English)',
        'country': 'Qatar',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'CBC Business',
        'feed_url': 'https://rss.cbc.ca/rss/cbcbusiness.xml',
        'description': 'CBC - Canadian and North American business news',
        'country': 'Canada',
        'language_code': 'en',
        'category': 'corporate_announcements',
    },
    {
        'feed_name': 'Globe and Mail Business',
        'feed_url': 'https://www.theglobeandmail.com/business/rss.xml',
        'description': 'Globe and Mail - Canadian business and markets',
        'country': 'Canada',
        'language_code': 'en',
        'category': 'market_research',
    },
    {
        'feed_name': 'Financial Times Emerging Markets',
        'feed_url': 'https://www.ft.com/emerging-markets?format=rss',
        'description': 'Financial Times - Emerging markets coverage',
        'country': 'UK',
        'language_code': 'en',
        'category': 'market_patterns',
    },
    {
        'feed_name': 'Reuters Emerging Markets',
        'feed_url': 'https://feeds.reuters.com/reuters/emergingMarketsNews',
        'description': 'Reuters - Emerging markets business and finance',
        'country': 'US',
        'language_code': 'en',
        'category': 'market_research',
    },
]


def insert_feed(conn, schema, feed_data):
    """Insert a single RSS feed into the specified schema"""
    cur = conn.cursor()
    
    try:
        # Check if feed already exists
        cur.execute(f"""
            SELECT id FROM {schema}.rss_feeds 
            WHERE feed_url = %s
        """, (feed_data['feed_url'],))
        
        existing = cur.fetchone()
        if existing:
            print(f"  ⚠️  Feed already exists: {feed_data['feed_name']}")
            return False
        
        # Insert new feed - check which columns exist
        # First, get column names
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = %s AND table_name = 'rss_feeds'
            ORDER BY ordinal_position
        """, (schema,))
        columns = [row[0] for row in cur.fetchall()]
        
        # Build INSERT based on available columns
        if 'feed_description' in columns:
            # Has description column
            cur.execute(f"""
                INSERT INTO {schema}.rss_feeds (
                    feed_name, feed_url, feed_description, 
                    is_active, fetch_interval_seconds,
                    language_code, country, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, 
                    TRUE, 1800,
                    %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                ) RETURNING id
            """, (
                feed_data['feed_name'],
                feed_data['feed_url'],
                feed_data.get('description', ''),
                feed_data.get('language_code', 'en'),
                feed_data.get('country', 'US'),
            ))
        else:
            # No description column, use metadata JSONB if available
            if 'metadata' in columns:
                import json
                metadata = {'description': feed_data.get('description', '')}
                cur.execute(f"""
                    INSERT INTO {schema}.rss_feeds (
                        feed_name, feed_url, 
                        is_active, fetch_interval_seconds,
                        language_code, country, metadata, created_at, updated_at
                    ) VALUES (
                        %s, %s, 
                        TRUE, 1800,
                        %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    ) RETURNING id
                """, (
                    feed_data['feed_name'],
                    feed_data['feed_url'],
                    feed_data.get('language_code', 'en'),
                    feed_data.get('country', 'US'),
                    json.dumps(metadata),
                ))
            else:
                # Minimal insert
                cur.execute(f"""
                    INSERT INTO {schema}.rss_feeds (
                        feed_name, feed_url, 
                        is_active, fetch_interval_seconds,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, 
                        TRUE, 1800,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    ) RETURNING id
                """, (
                    feed_data['feed_name'],
                    feed_data['feed_url'],
                ))
        
        feed_id = cur.fetchone()[0]
        conn.commit()
        print(f"  ✅ Added: {feed_data['feed_name']}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Error adding {feed_data['feed_name']}: {e}")
        return False
    finally:
        cur.close()


def restore_politics_feeds(conn):
    """Restore politics RSS feeds"""
    print("\n📰 Restoring Politics RSS Feeds...")
    print("=" * 60)
    
    added_count = 0
    skipped_count = 0
    
    for feed in POLITICS_FEEDS:
        if insert_feed(conn, 'politics', feed):
            added_count += 1
        else:
            skipped_count += 1
    
    print(f"\n✅ Politics Feeds: {added_count} added, {skipped_count} skipped")
    return added_count


def add_finance_feeds(conn):
    """Add finance RSS feeds"""
    print("\n💰 Adding Finance RSS Feeds...")
    print("=" * 60)
    
    added_count = 0
    skipped_count = 0
    
    for feed in FINANCE_FEEDS:
        if insert_feed(conn, 'finance', feed):
            added_count += 1
        else:
            skipped_count += 1
    
    print(f"\n✅ Finance Feeds: {added_count} added, {skipped_count} skipped")
    return added_count


def add_international_finance_feeds(conn):
    """Add international finance RSS feeds"""
    print("\n🌍 Adding International Finance RSS Feeds...")
    print("=" * 60)
    
    added_count = 0
    skipped_count = 0
    
    for feed in INTERNATIONAL_FINANCE_FEEDS:
        if insert_feed(conn, 'finance', feed):
            added_count += 1
        else:
            skipped_count += 1
    
    print(f"\n✅ International Finance Feeds: {added_count} added, {skipped_count} skipped")
    return added_count


def get_feed_counts(conn):
    """Get current feed counts per domain"""
    cur = conn.cursor()
    
    counts = {}
    for schema in ['politics', 'finance', 'science_tech']:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {schema}.rss_feeds")
            counts[schema] = cur.fetchone()[0]
        except Exception as e:
            counts[schema] = 0
            print(f"Warning: Could not count feeds in {schema}: {e}")
    
    cur.close()
    return counts


def main():
    """Main function"""
    print("🚀 RSS Feed Restoration Script")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return 1
    
    try:
        # Show current counts
        print("\n📊 Current Feed Counts:")
        counts = get_feed_counts(conn)
        for schema, count in counts.items():
            print(f"  {schema}: {count} feeds")
        
        # Restore politics feeds
        politics_added = restore_politics_feeds(conn)
        
        # Add finance feeds
        finance_added = add_finance_feeds(conn)
        
        # Add international finance feeds
        international_finance_added = add_international_finance_feeds(conn)
        
        # Show final counts
        print("\n📊 Final Feed Counts:")
        counts = get_feed_counts(conn)
        for schema, count in counts.items():
            print(f"  {schema}: {count} feeds")
        
        print("\n" + "=" * 60)
        print(f"✅ Restoration Complete!")
        print(f"   Politics: {politics_added} feeds added")
        print(f"   Finance (US): {finance_added} feeds added")
        print(f"   Finance (International): {international_finance_added} feeds added")
        print(f"   Total Finance: {finance_added + international_finance_added} feeds")
        print(f"   Total: {politics_added + finance_added + international_finance_added} feeds added")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())

