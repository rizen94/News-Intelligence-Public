#!/usr/bin/env python3
"""
Create Storylines for Top 5 Major International Markets (Direct DB)
Creates storylines directly in the database for US, European, China, Japan, and India markets
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.shared.database.connection import get_db_connection

# Top 5 Major International Markets
MARKET_STORYLINES = [
    {
        'title': 'United States Stock Market',
        'description': 'Comprehensive tracking of US stock market developments including NYSE, NASDAQ, and major indices (S&P 500, Dow Jones, NASDAQ Composite). Daily summaries of market movements, corporate earnings, economic indicators, and policy impacts.',
        'keywords': ['US stock market', 'NYSE', 'NASDAQ', 'S&P 500', 'Dow Jones', 'US markets', 'Wall Street', 'US economy', 'Federal Reserve', 'US corporate earnings'],
    },
    {
        'title': 'European Markets (Eurozone)',
        'description': 'Tracking developments across European stock markets including Germany (DAX), France (CAC 40), UK (FTSE 100), and broader Eurozone markets. Daily summaries of European economic indicators, ECB policy, corporate news, and cross-market movements.',
        'keywords': ['European markets', 'Eurozone', 'DAX', 'CAC 40', 'FTSE 100', 'European Central Bank', 'ECB', 'European economy', 'EU markets', 'London Stock Exchange', 'Frankfurt Stock Exchange'],
    },
    {
        'title': 'China Stock Market',
        'description': 'Comprehensive coverage of Chinese stock markets including Shanghai Stock Exchange (SSE), Shenzhen Stock Exchange, and Hong Kong markets. Daily summaries of market movements, policy changes, economic data, and corporate developments in China.',
        'keywords': ['China stock market', 'Shanghai Stock Exchange', 'Shenzhen Stock Exchange', 'Hong Kong markets', 'Hang Seng', 'SSE Composite', 'China economy', 'Chinese markets', 'PBOC', 'China policy'],
    },
    {
        'title': 'Japan Stock Market',
        'description': 'Tracking developments in Japanese stock markets including Tokyo Stock Exchange (TSE) and Nikkei 225. Daily summaries of market performance, Bank of Japan policy, economic indicators, corporate earnings, and yen movements.',
        'keywords': ['Japan stock market', 'Tokyo Stock Exchange', 'Nikkei 225', 'TSE', 'Japan economy', 'Bank of Japan', 'BOJ', 'Japanese markets', 'yen', 'Japan corporate earnings'],
    },
    {
        'title': 'India Stock Market',
        'description': 'Comprehensive tracking of Indian stock markets including BSE (Bombay Stock Exchange) and NSE (National Stock Exchange). Daily summaries of market movements, RBI policy, economic indicators, corporate news, and rupee movements.',
        'keywords': ['India stock market', 'BSE', 'NSE', 'Bombay Stock Exchange', 'National Stock Exchange', 'Sensex', 'Nifty', 'India economy', 'Reserve Bank of India', 'RBI', 'Indian markets', 'rupee'],
    },
]


def create_storyline(conn, market_data):
    """Create a storyline directly in the database"""
    cur = conn.cursor()
    
    try:
        # Check if storyline already exists
        cur.execute("""
            SELECT id FROM finance.storylines 
            WHERE title = %s
        """, (market_data['title'],))
        
        existing = cur.fetchone()
        if existing:
            print(f"  ⚠️  Storyline already exists: {market_data['title']} (ID: {existing[0]})")
            return existing[0]
        
        # Insert new storyline
        cur.execute("""
            INSERT INTO finance.storylines (
                title, description, status, created_at, updated_at
            ) VALUES (
                %s, %s, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING id
        """, (
            market_data['title'],
            market_data['description']
        ))
        
        storyline_id = cur.fetchone()[0]
        conn.commit()
        print(f"  ✅ Created: {market_data['title']} (ID: {storyline_id})")
        return storyline_id
        
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Error creating {market_data['title']}: {e}")
        return None
    finally:
        cur.close()


def main():
    """Main function"""
    print("🚀 Creating Market Storylines for Top 5 International Markets")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Domain: finance")
    print()
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return 1
    
    try:
        created_storylines = []
        failed_storylines = []
        
        for i, market in enumerate(MARKET_STORYLINES, 1):
            print(f"\n[{i}/5] Creating storyline: {market['title']}")
            print("-" * 70)
            
            storyline_id = create_storyline(conn, market)
            
            if storyline_id:
                created_storylines.append({
                    'id': storyline_id,
                    'title': market['title'],
                    'keywords': market['keywords']
                })
            else:
                failed_storylines.append(market['title'])
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ Storyline Creation Complete!")
        print("=" * 70)
        print(f"\n📊 Summary:")
        print(f"  ✅ Successfully created: {len(created_storylines)} storylines")
        print(f"  ❌ Failed: {len(failed_storylines)} storylines")
        
        if created_storylines:
            print(f"\n📋 Created Storylines:")
            for sl in created_storylines:
                print(f"  • {sl['title']} (ID: {sl['id']})")
                print(f"    Keywords: {', '.join(sl['keywords'][:5])}...")
        
        if failed_storylines:
            print(f"\n❌ Failed Storylines:")
            for title in failed_storylines:
                print(f"  • {title}")
        
        print("\n" + "=" * 70)
        print("🎯 Next Steps:")
        print("  1. Review storylines in the Finance domain")
        print("  2. Configure automation settings for daily summaries")
        print("  3. Run article discovery for each storyline")
        print("  4. Daily summaries will track market developments")
        print("=" * 70)
        
        return 0 if len(failed_storylines) == 0 else 1
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())



