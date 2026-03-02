#!/usr/bin/env python3
"""
Analyze existing articles against current filtering criteria.
Identifies articles that would be filtered by current RSS collector logic.
"""

import os
import sys
import logging
import psycopg2
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime

# Add parent directory to path to import filtering functions
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import filtering functions from RSS collector
try:
    from collectors.rss_collector import (
        is_excluded_content,
        is_clickbait_title,
        is_advertisement,
        calculate_article_quality_score,
        calculate_article_impact_score
    )
except ImportError as e:
    print(f"Error importing filtering functions: {e}")
    print("Make sure you're running from the api directory")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
try:
    from config.database import get_db_config
    DB_CONFIG = get_db_config()
except Exception as e:
    logger.warning(f"Failed to load database config: {e}")
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', '192.168.93.101'),
        'database': os.getenv('DB_NAME', 'news_intel'),
        'user': os.getenv('DB_USER', 'newsapp'),
        'password': os.getenv('DB_PASSWORD', ''),
        'port': int(os.getenv('DB_PORT', '5432')),
    }

def get_db_connection():
    """Get database connection"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

def analyze_article(article: Dict, schema_name: str) -> Dict:
    """
    Analyze a single article against all filters.
    
    Returns:
        Dict with filter results and scores
    """
    title = article.get('title', '')
    content = article.get('content', '') or article.get('summary', '')
    url = article.get('url', '')
    source = article.get('source_domain', '') or article.get('source', '')
    feed_name = article.get('feed_name', '')
    
    # Apply all filters
    excluded_content = is_excluded_content(title, content, feed_name, url)
    clickbait = is_clickbait_title(title)
    advertisement = is_advertisement(title, content, url)
    
    # Calculate scores
    quality_score = calculate_article_quality_score(title, content, source)
    impact_score = calculate_article_impact_score(title, content)
    
    # Check score thresholds
    low_quality = quality_score < 0.4
    low_impact = impact_score < 0.4
    
    # Determine if article would be filtered
    would_filter = excluded_content or clickbait or advertisement or low_quality or low_impact
    
    # Determine primary reason
    reasons = []
    if excluded_content:
        reasons.append('excluded_content')
    if clickbait:
        reasons.append('clickbait')
    if advertisement:
        reasons.append('advertisement')
    if low_quality:
        reasons.append(f'low_quality_{quality_score:.2f}')
    if low_impact:
        reasons.append(f'low_impact_{impact_score:.2f}')
    
    return {
        'article_id': article.get('id'),
        'title': title,
        'source': source,
        'feed_name': feed_name,
        'url': url,
        'would_filter': would_filter,
        'reasons': reasons,
        'quality_score': quality_score,
        'impact_score': impact_score,
        'excluded_content': excluded_content,
        'clickbait': clickbait,
        'advertisement': advertisement,
        'low_quality': low_quality,
        'low_impact': low_impact,
        'schema': schema_name
    }

def analyze_domain_articles(conn, schema_name: str, limit: Optional[int] = None, source_filter: Optional[str] = None) -> Tuple[List[Dict], Dict]:
    """
    Analyze articles from a specific domain schema.
    
    Returns:
        Tuple of (filtered_articles, statistics)
    """
    cur = conn.cursor()
    
    # Build query
    query = f"""
        SELECT 
            id, title, url, content, summary, source_domain, source, feed_name,
            created_at, published_at, processing_status
        FROM {schema_name}.articles
        WHERE 1=1
    """
    
    params = []
    if source_filter:
        query += " AND (source_domain ILIKE %s OR source ILIKE %s OR feed_name ILIKE %s)"
        pattern = f"%{source_filter}%"
        params = [pattern, pattern, pattern]
    
    query += " ORDER BY created_at DESC"
    
    if limit:
        query += f" LIMIT %s"
        params.append(limit)
    
    cur.execute(query, params)
    articles = cur.fetchall()
    
    # Convert to dict format
    article_dicts = []
    for row in articles:
        article_dicts.append({
            'id': row[0],
            'title': row[1],
            'url': row[2],
            'content': row[3],
            'summary': row[4],
            'source_domain': row[5],
            'source': row[6],
            'feed_name': row[7],
            'created_at': row[8],
            'published_at': row[9],
            'processing_status': row[10]
        })
    
    # Analyze each article
    filtered_articles = []
    stats = defaultdict(int)
    stats['total'] = len(article_dicts)
    
    for article in article_dicts:
        analysis = analyze_article(article, schema_name)
        
        if analysis['would_filter']:
            filtered_articles.append(analysis)
            stats['filtered'] += 1
            
            # Count by reason
            for reason in analysis['reasons']:
                if reason.startswith('low_quality_'):
                    stats['low_quality'] += 1
                elif reason.startswith('low_impact_'):
                    stats['low_impact'] += 1
                else:
                    stats[reason] += 1
        
        # Track scores for statistics
        if analysis['quality_score'] < 0.4:
            stats['low_quality_score'] += 1
        if analysis['impact_score'] < 0.4:
            stats['low_impact_score'] += 1
    
    return filtered_articles, dict(stats)

def print_summary(all_stats: Dict[str, Dict], all_filtered: List[Dict], source_filter: Optional[str] = None):
    """Print analysis summary"""
    print("\n" + "=" * 80)
    print("ARTICLE FILTERING ANALYSIS SUMMARY")
    print("=" * 80)
    
    if source_filter:
        print(f"\n📊 Filtering by source: {source_filter}")
    
    # Overall statistics
    total_articles = sum(s['total'] for s in all_stats.values())
    total_filtered = sum(s['filtered'] for s in all_stats.values())
    
    print(f"\n📈 Overall Statistics:")
    print(f"   Total articles analyzed: {total_articles:,}")
    print(f"   Articles that would be filtered: {total_filtered:,} ({total_filtered/total_articles*100:.1f}%)")
    print(f"   Articles that would pass: {total_articles - total_filtered:,} ({(total_articles-total_filtered)/total_articles*100:.1f}%)")
    
    # Statistics by domain
    print(f"\n📊 Statistics by Domain:")
    for schema, stats in sorted(all_stats.items()):
        if stats['total'] > 0:
            pct = stats['filtered'] / stats['total'] * 100
            print(f"\n   {schema}:")
            print(f"      Total: {stats['total']:,}")
            print(f"      Would filter: {stats['filtered']:,} ({pct:.1f}%)")
            if stats['filtered'] > 0:
                print(f"      Reasons:")
                if stats.get('excluded_content', 0) > 0:
                    print(f"         - Excluded content (sports/entertainment): {stats['excluded_content']:,}")
                if stats.get('clickbait', 0) > 0:
                    print(f"         - Clickbait: {stats['clickbait']:,}")
                if stats.get('advertisement', 0) > 0:
                    print(f"         - Advertisement: {stats['advertisement']:,}")
                if stats.get('low_quality', 0) > 0:
                    print(f"         - Low quality score (<0.4): {stats['low_quality']:,}")
                if stats.get('low_impact', 0) > 0:
                    print(f"         - Low impact score (<0.4): {stats['low_impact']:,}")
    
    # Statistics by source
    if all_filtered:
        print(f"\n📰 Top Sources with Filtered Articles:")
        source_counts = defaultdict(int)
        for article in all_filtered:
            source = article.get('source') or article.get('feed_name', 'Unknown')
            source_counts[source] += 1
        
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"   {source}: {count:,} articles")
    
    # Sample filtered articles
    if all_filtered:
        print(f"\n🔍 Sample Filtered Articles (first 20):")
        for i, article in enumerate(all_filtered[:20], 1):
            print(f"\n   {i}. [{article['schema']}] {article['title'][:70]}...")
            print(f"      Source: {article.get('source') or article.get('feed_name', 'Unknown')}")
            print(f"      Reasons: {', '.join(article['reasons'])}")
            print(f"      Scores: Quality={article['quality_score']:.2f}, Impact={article['impact_score']:.2f}")

def main():
    """Main analysis function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze existing articles against filtering criteria')
    parser.add_argument('--source', type=str, help='Filter by source name (e.g., "telegraph")')
    parser.add_argument('--limit', type=int, help='Limit articles analyzed per domain (default: all)')
    parser.add_argument('--domains', nargs='+', help='Specific domains to analyze (default: all)')
    parser.add_argument('--export', type=str, help='Export filtered article IDs to file (CSV format)')
    parser.add_argument('--dry-run', action='store_true', help='Only analyze, do not mark for deletion')
    
    args = parser.parse_args()
    
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to database")
        sys.exit(1)
    
    # Get active domain schemas
    cur = conn.cursor()
    if args.domains:
        schemas = args.domains
    else:
        cur.execute("SELECT schema_name FROM domains WHERE is_active = true")
        schemas = [row[0] for row in cur.fetchall()]
    
    logger.info(f"Analyzing articles from schemas: {', '.join(schemas)}")
    
    all_filtered = []
    all_stats = {}
    
    for schema in schemas:
        logger.info(f"Analyzing {schema}...")
        try:
            filtered, stats = analyze_domain_articles(
                conn, schema, 
                limit=args.limit,
                source_filter=args.source
            )
            all_filtered.extend(filtered)
            all_stats[schema] = stats
            logger.info(f"  Found {stats['filtered']} filtered articles out of {stats['total']} total")
        except Exception as e:
            logger.error(f"Error analyzing {schema}: {e}")
            all_stats[schema] = {'total': 0, 'filtered': 0}
    
    # Print summary
    print_summary(all_stats, all_filtered, args.source)
    
    # Export if requested
    if args.export and all_filtered:
        import csv
        with open(args.export, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['schema', 'article_id', 'title', 'source', 'reasons', 'quality_score', 'impact_score'])
            for article in all_filtered:
                writer.writerow([
                    article['schema'],
                    article['article_id'],
                    article['title'],
                    article.get('source') or article.get('feed_name', 'Unknown'),
                    ';'.join(article['reasons']),
                    article['quality_score'],
                    article['impact_score']
                ])
        print(f"\n✅ Exported {len(all_filtered)} filtered articles to {args.export}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("=" * 80)

if __name__ == '__main__':
    main()

