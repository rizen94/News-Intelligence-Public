#!/usr/bin/env python3
"""
Create Storylines for Top 5 Major International Markets
Creates storylines for US, European, China, Japan, and India markets
with automation for daily summaries
"""

import sys
import os
import requests
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# API Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')
DOMAIN = 'finance'

# Top 5 Major International Markets
MARKET_STORYLINES = [
    {
        'title': 'United States Stock Market',
        'description': 'Comprehensive tracking of US stock market developments including NYSE, NASDAQ, and major indices (S&P 500, Dow Jones, NASDAQ Composite). Daily summaries of market movements, corporate earnings, economic indicators, and policy impacts.',
        'keywords': ['US stock market', 'NYSE', 'NASDAQ', 'S&P 500', 'Dow Jones', 'US markets', 'Wall Street', 'US economy', 'Federal Reserve', 'US corporate earnings'],
        'automation': {
            'enabled': True,
            'auto_approve': False,
            'min_relevance_score': 0.7,
            'min_quality_score': 0.6,
            'min_semantic_score': 0.75,
            'daily_summary': True,
            'summary_time': '18:00',  # 6 PM ET
        }
    },
    {
        'title': 'European Markets (Eurozone)',
        'description': 'Tracking developments across European stock markets including Germany (DAX), France (CAC 40), UK (FTSE 100), and broader Eurozone markets. Daily summaries of European economic indicators, ECB policy, corporate news, and cross-market movements.',
        'keywords': ['European markets', 'Eurozone', 'DAX', 'CAC 40', 'FTSE 100', 'European Central Bank', 'ECB', 'European economy', 'EU markets', 'London Stock Exchange', 'Frankfurt Stock Exchange'],
        'automation': {
            'enabled': True,
            'auto_approve': False,
            'min_relevance_score': 0.7,
            'min_quality_score': 0.6,
            'min_semantic_score': 0.75,
            'daily_summary': True,
            'summary_time': '18:00',  # 6 PM CET
        }
    },
    {
        'title': 'China Stock Market',
        'description': 'Comprehensive coverage of Chinese stock markets including Shanghai Stock Exchange (SSE), Shenzhen Stock Exchange, and Hong Kong markets. Daily summaries of market movements, policy changes, economic data, and corporate developments in China.',
        'keywords': ['China stock market', 'Shanghai Stock Exchange', 'Shenzhen Stock Exchange', 'Hong Kong markets', 'Hang Seng', 'SSE Composite', 'China economy', 'Chinese markets', 'PBOC', 'China policy'],
        'automation': {
            'enabled': True,
            'auto_approve': False,
            'min_relevance_score': 0.7,
            'min_quality_score': 0.6,
            'min_semantic_score': 0.75,
            'daily_summary': True,
            'summary_time': '18:00',  # 6 PM CST
        }
    },
    {
        'title': 'Japan Stock Market',
        'description': 'Tracking developments in Japanese stock markets including Tokyo Stock Exchange (TSE) and Nikkei 225. Daily summaries of market performance, Bank of Japan policy, economic indicators, corporate earnings, and yen movements.',
        'keywords': ['Japan stock market', 'Tokyo Stock Exchange', 'Nikkei 225', 'TSE', 'Japan economy', 'Bank of Japan', 'BOJ', 'Japanese markets', 'yen', 'Japan corporate earnings'],
        'automation': {
            'enabled': True,
            'auto_approve': False,
            'min_relevance_score': 0.7,
            'min_quality_score': 0.6,
            'min_semantic_score': 0.75,
            'daily_summary': True,
            'summary_time': '18:00',  # 6 PM JST
        }
    },
    {
        'title': 'India Stock Market',
        'description': 'Comprehensive tracking of Indian stock markets including BSE (Bombay Stock Exchange) and NSE (National Stock Exchange). Daily summaries of market movements, RBI policy, economic indicators, corporate news, and rupee movements.',
        'keywords': ['India stock market', 'BSE', 'NSE', 'Bombay Stock Exchange', 'National Stock Exchange', 'Sensex', 'Nifty', 'India economy', 'Reserve Bank of India', 'RBI', 'Indian markets', 'rupee'],
        'automation': {
            'enabled': True,
            'auto_approve': False,
            'min_relevance_score': 0.7,
            'min_quality_score': 0.6,
            'min_semantic_score': 0.75,
            'daily_summary': True,
            'summary_time': '18:00',  # 6 PM IST
        }
    },
]


def create_storyline(market_data):
    """Create a storyline via API"""
    url = f"{API_BASE_URL}/api/v4/{DOMAIN}/storyline-management/storylines"
    
    payload = {
        'title': market_data['title'],
        'description': market_data['description']
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            storyline_id = result['data']['storyline_id']
            print(f"  ✅ Created: {market_data['title']} (ID: {storyline_id})")
            return storyline_id
        else:
            print(f"  ❌ Failed: {market_data['title']} - {result.get('error', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error creating {market_data['title']}: {e}")
        return None


def setup_automation(storyline_id, automation_config):
    """Set up automation settings for a storyline"""
    url = f"{API_BASE_URL}/api/v4/{DOMAIN}/storyline-management/storylines/{storyline_id}/automation/settings"
    
    try:
        response = requests.put(url, json=automation_config, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            print(f"    ✅ Automation configured")
            return True
        else:
            print(f"    ⚠️  Automation setup failed: {result.get('error', 'Unknown error')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"    ⚠️  Error setting up automation: {e}")
        return False


def main():
    """Main function"""
    print("🚀 Creating Market Storylines for Top 5 International Markets")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Domain: {DOMAIN}")
    print(f"API Base URL: {API_BASE_URL}")
    print()
    
    created_storylines = []
    failed_storylines = []
    
    for i, market in enumerate(MARKET_STORYLINES, 1):
        print(f"\n[{i}/5] Creating storyline: {market['title']}")
        print("-" * 70)
        
        storyline_id = create_storyline(market)
        
        if storyline_id:
            created_storylines.append({
                'id': storyline_id,
                'title': market['title'],
                'automation': market['automation']
            })
            
            # Set up automation
            print(f"  Setting up automation...")
            setup_automation(storyline_id, market['automation'])
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
            print(f"    - Automation: {'Enabled' if sl['automation']['enabled'] else 'Disabled'}")
            print(f"    - Daily Summary: {'Yes' if sl['automation']['daily_summary'] else 'No'}")
    
    if failed_storylines:
        print(f"\n❌ Failed Storylines:")
        for title in failed_storylines:
            print(f"  • {title}")
    
    print("\n" + "=" * 70)
    print("🎯 Next Steps:")
    print("  1. Review storylines in the Finance domain")
    print("  2. Run article discovery for each storyline")
    print("  3. Daily summaries will be generated automatically")
    print("=" * 70)
    
    return 0 if len(failed_storylines) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())



