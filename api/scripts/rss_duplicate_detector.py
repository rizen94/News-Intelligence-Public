#!/usr/bin/env python3
"""
RSS Feed Duplicate Detection and Management System
Automatically detects and manages duplicate RSS feeds in the database
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple
import psycopg2
from urllib.parse import urlparse
import requests
from collections import defaultdict

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.database import get_db_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/rss_duplicate_detector.log')
    ]
)
logger = logging.getLogger(__name__)

class RSSDuplicateDetector:
    """RSS Feed Duplicate Detection and Management System"""
    
    def __init__(self):
        self.conn = None
        self.duplicates_found = []
        self.similar_feeds = []
        
    def connect_database(self):
        """Connect to the database"""
        try:
            self.conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'news_intelligence'),
                user=os.getenv('DB_USER', 'newsapp'),
                password=os.getenv('DB_PASSWORD', 'newsapp_password'),
                port=os.getenv('DB_PORT', '5432')
            )
            logger.info("✅ Database connected successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def detect_exact_duplicates(self) -> List[Dict[str, Any]]:
        """Detect feeds with identical URLs"""
        logger.info("🔍 Detecting exact URL duplicates...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT feed_url, COUNT(*) as count, 
                       STRING_AGG(feed_name, ' | ') as names,
                       STRING_AGG(id::text, ', ') as ids,
                       STRING_AGG(is_active::text, ', ') as active_status
                FROM rss_feeds 
                GROUP BY feed_url 
                HAVING COUNT(*) > 1
                ORDER BY count DESC
            """)
            
            duplicates = []
            for row in cur.fetchall():
                url, count, names, ids, active_status = row
                duplicate_info = {
                    'url': url,
                    'count': count,
                    'names': names.split(' | '),
                    'ids': [int(id) for id in ids.split(', ')],
                    'active_status': [status == 'True' for status in active_status.split(', ')],
                    'type': 'exact_url'
                }
                duplicates.append(duplicate_info)
                
            logger.info(f"📊 Found {len(duplicates)} exact URL duplicates")
            return duplicates
    
    def detect_similar_feeds(self) -> List[Dict[str, Any]]:
        """Detect feeds with similar URLs (same domain, different paths)"""
        logger.info("🔍 Detecting similar feeds...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, feed_name, feed_url, is_active
                FROM rss_feeds 
                ORDER BY feed_url
            """)
            
            feeds = cur.fetchall()
            domain_groups = defaultdict(list)
            
            # Group feeds by domain
            for feed_id, name, url, is_active in feeds:
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower()
                    domain_groups[domain].append({
                        'id': feed_id,
                        'name': name,
                        'url': url,
                        'is_active': is_active,
                        'path': parsed.path
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Could not parse URL {url}: {e}")
            
            # Find domains with multiple feeds
            similar_groups = []
            for domain, feed_list in domain_groups.items():
                if len(feed_list) > 1:
                    similar_groups.append({
                        'domain': domain,
                        'feeds': feed_list,
                        'count': len(feed_list),
                        'type': 'similar_domain'
                    })
            
            logger.info(f"📊 Found {len(similar_groups)} domains with multiple feeds")
            return similar_groups
    
    def detect_name_similarities(self) -> List[Dict[str, Any]]:
        """Detect feeds with similar names but different URLs"""
        logger.info("🔍 Detecting name similarities...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, feed_name, feed_url, is_active
                FROM rss_feeds 
                ORDER BY feed_name
            """)
            
            feeds = cur.fetchall()
            name_groups = defaultdict(list)
            
            # Group feeds by normalized name
            for feed_id, name, url, is_active in feeds:
                # Normalize name for comparison
                normalized = name.lower().replace(' ', '').replace('-', '').replace('_', '')
                name_groups[normalized].append({
                    'id': feed_id,
                    'name': name,
                    'url': url,
                    'is_active': is_active
                })
            
            # Find names with multiple feeds
            name_duplicates = []
            for normalized_name, feed_list in name_groups.items():
                if len(feed_list) > 1:
                    name_duplicates.append({
                        'normalized_name': normalized_name,
                        'feeds': feed_list,
                        'count': len(feed_list),
                        'type': 'similar_name'
                    })
            
            logger.info(f"📊 Found {len(name_duplicates)} name similarities")
            return name_duplicates
    
    def analyze_feed_content(self, url: str) -> Dict[str, Any]:
        """Analyze RSS feed content to detect duplicates"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Basic content analysis
            content = response.text.lower()
            
            # Look for common RSS indicators
            rss_indicators = ['<rss', '<feed', '<channel', '<item>']
            has_rss_structure = any(indicator in content for indicator in rss_indicators)
            
            # Extract title if possible
            title = None
            if '<title>' in content:
                try:
                    start = content.find('<title>') + 7
                    end = content.find('</title>', start)
                    if end > start:
                        title = content[start:end].strip()
                except:
                    pass
            
            return {
                'accessible': True,
                'has_rss_structure': has_rss_structure,
                'title': title,
                'content_length': len(content),
                'status_code': response.status_code
            }
            
        except Exception as e:
            return {
                'accessible': False,
                'error': str(e),
                'has_rss_structure': False,
                'title': None,
                'content_length': 0,
                'status_code': None
            }
    
    def generate_duplicate_report(self) -> Dict[str, Any]:
        """Generate comprehensive duplicate detection report"""
        logger.info("📊 Generating duplicate detection report...")
        
        exact_duplicates = self.detect_exact_duplicates()
        similar_feeds = self.detect_similar_feeds()
        name_similarities = self.detect_name_similarities()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'exact_duplicates': len(exact_duplicates),
                'similar_domains': len(similar_feeds),
                'name_similarities': len(name_similarities),
                'total_issues': len(exact_duplicates) + len(similar_feeds) + len(name_similarities)
            },
            'exact_duplicates': exact_duplicates,
            'similar_domains': similar_feeds,
            'name_similarities': name_similarities,
            'recommendations': []
        }
        
        # Generate recommendations
        if exact_duplicates:
            report['recommendations'].append({
                'type': 'critical',
                'message': f'Found {len(exact_duplicates)} exact URL duplicates that should be merged',
                'action': 'merge_duplicates'
            })
        
        if similar_feeds:
            report['recommendations'].append({
                'type': 'warning',
                'message': f'Found {len(similar_feeds)} domains with multiple feeds - review for redundancy',
                'action': 'review_similar_feeds'
            })
        
        if name_similarities:
            report['recommendations'].append({
                'type': 'info',
                'message': f'Found {len(name_similarities)} name similarities - verify these are different feeds',
                'action': 'verify_name_similarities'
            })
        
        logger.info(f"📊 Report generated: {report['summary']['total_issues']} total issues found")
        return report
    
    def auto_merge_duplicates(self, duplicates: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, Any]:
        """Automatically merge duplicate feeds"""
        logger.info(f"🔄 {'DRY RUN: ' if dry_run else ''}Auto-merging duplicates...")
        
        merge_results = {
            'merged': [],
            'errors': [],
            'total_processed': 0
        }
        
        for duplicate in duplicates:
            if duplicate['type'] != 'exact_url':
                continue
                
            try:
                # Keep the feed with articles, or the oldest if tied
                feed_ids = duplicate['ids']
                active_status = duplicate['active_status']
                
                # Get article counts for each feed
                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT feed_id, COUNT(*) as article_count
                        FROM articles 
                        WHERE feed_id = ANY(%s)
                        GROUP BY feed_id
                    """, (feed_ids,))
                    
                    article_counts = {row[0]: row[1] for row in cur.fetchall()}
                
                # Determine which feed to keep
                keep_feed_id = None
                max_articles = -1
                
                for feed_id in feed_ids:
                    article_count = article_counts.get(feed_id, 0)
                    if article_count > max_articles:
                        max_articles = article_count
                        keep_feed_id = feed_id
                
                # If tied, keep the oldest
                if max_articles == 0:
                    with self.conn.cursor() as cur:
                        cur.execute("""
                            SELECT id FROM rss_feeds 
                            WHERE id = ANY(%s) 
                            ORDER BY created_at ASC 
                            LIMIT 1
                        """, (feed_ids,))
                        keep_feed_id = cur.fetchone()[0]
                
                # Remove other feeds
                remove_feed_ids = [fid for fid in feed_ids if fid != keep_feed_id]
                
                if not dry_run:
                    with self.conn.cursor() as cur:
                        # Delete duplicate feeds
                        cur.execute("""
                            DELETE FROM rss_feeds 
                            WHERE id = ANY(%s)
                        """, (remove_feed_ids,))
                        
                        self.conn.commit()
                
                merge_results['merged'].append({
                    'kept_feed_id': keep_feed_id,
                    'removed_feed_ids': remove_feed_ids,
                    'url': duplicate['url'],
                    'names': duplicate['names']
                })
                
                merge_results['total_processed'] += len(remove_feed_ids)
                
                logger.info(f"{'DRY RUN: ' if dry_run else ''}Merged {len(remove_feed_ids)} duplicates for {duplicate['url']}")
                
            except Exception as e:
                error_msg = f"Error merging duplicates for {duplicate['url']}: {e}"
                logger.error(error_msg)
                merge_results['errors'].append(error_msg)
        
        return merge_results
    
    def add_duplicate_prevention_constraints(self) -> bool:
        """Add database constraints to prevent future duplicates"""
        logger.info("🔒 Adding duplicate prevention constraints...")
        
        try:
            with self.conn.cursor() as cur:
                # Add unique constraint on feed_url
                cur.execute("""
                    ALTER TABLE rss_feeds 
                    ADD CONSTRAINT unique_feed_url UNIQUE (feed_url)
                """)
                
                # Add index for faster duplicate detection
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rss_feeds_url 
                    ON rss_feeds (feed_url)
                """)
                
                self.conn.commit()
                logger.info("✅ Duplicate prevention constraints added successfully")
                return True
                
        except Exception as e:
            if "already exists" in str(e):
                logger.info("ℹ️ Unique constraint already exists")
                return True
            else:
                logger.error(f"❌ Error adding constraints: {e}")
                return False
    
    def close_connection(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("🔌 Database connection closed")

def main():
    """Main function for RSS duplicate detection"""
    print("🔍 RSS Feed Duplicate Detection System")
    print("=====================================")
    
    detector = RSSDuplicateDetector()
    
    if not detector.connect_database():
        sys.exit(1)
    
    try:
        # Generate comprehensive report
        report = detector.generate_duplicate_report()
        
        print(f"\n📊 DUPLICATE DETECTION REPORT")
        print(f"=============================")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Exact duplicates: {report['summary']['exact_duplicates']}")
        print(f"Similar domains: {report['summary']['similar_domains']}")
        print(f"Name similarities: {report['summary']['name_similarities']}")
        print(f"Total issues: {report['summary']['total_issues']}")
        
        if report['exact_duplicates']:
            print(f"\n❌ EXACT DUPLICATES FOUND:")
            for dup in report['exact_duplicates']:
                print(f"  URL: {dup['url']}")
                print(f"  Count: {dup['count']}")
                print(f"  Names: {', '.join(dup['names'])}")
                print(f"  IDs: {dup['ids']}")
                print()
        
        if report['similar_domains']:
            print(f"\n⚠️ SIMILAR DOMAINS:")
            for sim in report['similar_domains'][:5]:  # Show first 5
                print(f"  Domain: {sim['domain']}")
                print(f"  Feeds: {sim['count']}")
                for feed in sim['feeds']:
                    print(f"    - {feed['name']}: {feed['url']}")
                print()
        
        # Add duplicate prevention constraints
        detector.add_duplicate_prevention_constraints()
        
        # Auto-merge duplicates (dry run first)
        if report['exact_duplicates']:
            print(f"\n🔄 AUTO-MERGE DUPLICATES (DRY RUN)")
            print(f"==================================")
            merge_results = detector.auto_merge_duplicates(report['exact_duplicates'], dry_run=True)
            print(f"Would merge: {merge_results['total_processed']} duplicate feeds")
            print(f"Would keep: {len(merge_results['merged'])} feeds")
            
            # Ask for confirmation to actually merge
            response = input("\nDo you want to proceed with actual merging? (y/N): ")
            if response.lower() == 'y':
                print(f"\n🔄 MERGING DUPLICATES...")
                merge_results = detector.auto_merge_duplicates(report['exact_duplicates'], dry_run=False)
                print(f"✅ Merged: {merge_results['total_processed']} duplicate feeds")
                if merge_results['errors']:
                    print(f"❌ Errors: {len(merge_results['errors'])}")
        
        print(f"\n✅ Duplicate detection complete!")
        
    except Exception as e:
        logger.error(f"❌ Error in main execution: {e}")
        sys.exit(1)
    
    finally:
        detector.close_connection()

if __name__ == "__main__":
    main()
