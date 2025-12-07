#!/usr/bin/env python3
"""
Article Deduplication System
Comprehensive system for detecting and managing duplicate articles using URL and content analysis
"""

import os
import sys
import logging
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import psycopg2
from urllib.parse import urlparse
import requests
from collections import defaultdict
from difflib import SequenceMatcher
import json

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
        logging.FileHandler('logs/article_deduplication.log')
    ]
)
logger = logging.getLogger(__name__)

class ArticleDeduplicationSystem:
    """Comprehensive Article Deduplication System"""
    
    def __init__(self):
        self.conn = None
        self.content_similarity_threshold = 0.85  # 85% similarity threshold
        self.title_similarity_threshold = 0.90    # 90% similarity threshold
        
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
    
    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        try:
            parsed = urlparse(url)
            # Remove common tracking parameters
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                # Keep only essential query parameters
                query_params = []
                for param in parsed.query.split('&'):
                    if param and not any(track in param.lower() for track in ['utm_', 'fbclid', 'gclid', 'ref']):
                        query_params.append(param)
                if query_params:
                    normalized += f"?{'&'.join(query_params)}"
            return normalized.lower()
        except Exception as e:
            logger.warning(f"⚠️ Could not normalize URL {url}: {e}")
            return url.lower()
    
    def generate_content_hash(self, content: str) -> str:
        """Generate hash for article content"""
        if not content:
            return ""
        
        # Clean and normalize content
        cleaned = self.clean_content(content)
        
        # Generate hash
        return hashlib.md5(cleaned.encode('utf-8')).hexdigest()
    
    def clean_content(self, content: str) -> str:
        """Clean and normalize content for comparison"""
        if not content:
            return ""
        
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', ' ', content)
        
        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove common noise words and phrases
        noise_patterns = [
            r'\b(click here|read more|continue reading|more at|source:)\b',
            r'\b(advertisement|sponsored|promoted)\b',
            r'\b(share this|tweet this|like this)\b',
            r'\b(updated:?\s*\d{1,2}:\d{2}|\d{1,2}:\d{2}\s*updated)\b',
            r'\b(by\s+\w+\s+\w+)\b',  # Author bylines
        ]
        
        for pattern in noise_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Remove extra whitespace again
        content = re.sub(r'\s+', ' ', content).strip()
        
        return content.lower()
    
    def detect_url_duplicates(self) -> List[Dict[str, Any]]:
        """Detect articles with duplicate URLs"""
        logger.info("🔍 Detecting URL-based duplicates...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT url, COUNT(*) as count, 
                       STRING_AGG(id::text, ', ') as article_ids,
                       STRING_AGG(title, ' | ') as titles,
                       STRING_AGG(source_domain, ', ') as domains
                FROM articles 
                GROUP BY url 
                HAVING COUNT(*) > 1
                ORDER BY count DESC
            """)
            
            duplicates = []
            for row in cur.fetchall():
                url, count, ids, titles, domains = row
                duplicate_info = {
                    'url': url,
                    'count': count,
                    'article_ids': [int(id) for id in ids.split(', ')],
                    'titles': titles.split(' | '),
                    'domains': domains.split(', '),
                    'type': 'exact_url'
                }
                duplicates.append(duplicate_info)
                
            logger.info(f"📊 Found {len(duplicates)} URL-based duplicates")
            return duplicates
    
    def detect_normalized_url_duplicates(self) -> List[Dict[str, Any]]:
        """Detect articles with similar normalized URLs"""
        logger.info("🔍 Detecting normalized URL duplicates...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, url, title, source_domain, content
                FROM articles 
                ORDER BY created_at DESC
            """)
            
            articles = cur.fetchall()
            
            # Group by normalized URL
            normalized_groups = defaultdict(list)
            for article_id, url, title, domain, content in articles:
                normalized_url = self.normalize_url(url)
                normalized_groups[normalized_url].append({
                    'id': article_id,
                    'url': url,
                    'title': title,
                    'domain': domain,
                    'content': content
                })
            
            # Find groups with multiple articles
            duplicates = []
            for normalized_url, articles_list in normalized_groups.items():
                if len(articles_list) > 1:
                    duplicate_info = {
                        'normalized_url': normalized_url,
                        'count': len(articles_list),
                        'articles': articles_list,
                        'type': 'normalized_url'
                    }
                    duplicates.append(duplicate_info)
            
            logger.info(f"📊 Found {len(duplicates)} normalized URL duplicates")
            return duplicates
    
    def detect_content_duplicates(self) -> List[Dict[str, Any]]:
        """Detect articles with duplicate content using hashes"""
        logger.info("🔍 Detecting content-based duplicates...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content, url, source_domain, created_at
                FROM articles 
                WHERE content IS NOT NULL AND LENGTH(content) > 100
                ORDER BY created_at DESC
            """)
            
            articles = cur.fetchall()
            
            # Generate content hashes
            content_hashes = defaultdict(list)
            for article_id, title, content, url, domain, created_at in articles:
                content_hash = self.generate_content_hash(content)
                if content_hash:
                    content_hashes[content_hash].append({
                        'id': article_id,
                        'title': title,
                        'content': content,
                        'url': url,
                        'domain': domain,
                        'created_at': created_at
                    })
            
            # Find groups with multiple articles
            duplicates = []
            for content_hash, articles_list in content_hashes.items():
                if len(articles_list) > 1:
                    duplicate_info = {
                        'content_hash': content_hash,
                        'count': len(articles_list),
                        'articles': articles_list,
                        'type': 'content_hash'
                    }
                    duplicates.append(duplicate_info)
            
            logger.info(f"📊 Found {len(duplicates)} content-based duplicates")
            return duplicates
    
    def detect_title_similarities(self) -> List[Dict[str, Any]]:
        """Detect articles with similar titles"""
        logger.info("🔍 Detecting title similarities...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, url, source_domain, created_at
                FROM articles 
                WHERE title IS NOT NULL AND LENGTH(title) > 10
                ORDER BY created_at DESC
            """)
            
            articles = cur.fetchall()
            
            # Group articles by cleaned title
            title_groups = defaultdict(list)
            for article_id, title, url, domain, created_at in articles:
                cleaned_title = self.clean_content(title)
                title_groups[cleaned_title].append({
                    'id': article_id,
                    'title': title,
                    'url': url,
                    'domain': domain,
                    'created_at': created_at
                })
            
            # Find groups with multiple articles
            duplicates = []
            for cleaned_title, articles_list in title_groups.items():
                if len(articles_list) > 1:
                    duplicate_info = {
                        'cleaned_title': cleaned_title,
                        'count': len(articles_list),
                        'articles': articles_list,
                        'type': 'title_similarity'
                    }
                    duplicates.append(duplicate_info)
            
            logger.info(f"📊 Found {len(duplicates)} title similarities")
            return duplicates
    
    def detect_content_similarities(self) -> List[Dict[str, Any]]:
        """Detect articles with similar content using text analysis"""
        logger.info("🔍 Detecting content similarities...")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content, url, source_domain, created_at
                FROM articles 
                WHERE content IS NOT NULL AND LENGTH(content) > 200
                ORDER BY created_at DESC
                LIMIT 1000
            """)
            
            articles = cur.fetchall()
            
            similarities = []
            processed = set()
            
            for i, (id1, title1, content1, url1, domain1, created1) in enumerate(articles):
                if id1 in processed:
                    continue
                    
                cleaned_content1 = self.clean_content(content1)
                if len(cleaned_content1) < 100:
                    continue
                
                similar_articles = []
                
                for j, (id2, title2, content2, url2, domain2, created2) in enumerate(articles[i+1:], i+1):
                    if id2 in processed:
                        continue
                    
                    cleaned_content2 = self.clean_content(content2)
                    if len(cleaned_content2) < 100:
                        continue
                    
                    # Calculate content similarity
                    similarity = SequenceMatcher(None, cleaned_content1, cleaned_content2).ratio()
                    
                    if similarity >= self.content_similarity_threshold:
                        similar_articles.append({
                            'id': id2,
                            'title': title2,
                            'url': url2,
                            'domain': domain2,
                            'created_at': created2,
                            'similarity': similarity
                        })
                        processed.add(id2)
                
                if similar_articles:
                    similarities.append({
                        'primary_article': {
                            'id': id1,
                            'title': title1,
                            'url': url1,
                            'domain': domain1,
                            'created_at': created1
                        },
                        'similar_articles': similar_articles,
                        'count': len(similar_articles) + 1,
                        'type': 'content_similarity'
                    })
                    processed.add(id1)
            
            logger.info(f"📊 Found {len(similarities)} content similarity groups")
            return similarities
    
    def generate_deduplication_report(self) -> Dict[str, Any]:
        """Generate comprehensive deduplication report"""
        logger.info("📊 Generating deduplication report...")
        
        url_duplicates = self.detect_url_duplicates()
        normalized_url_duplicates = self.detect_normalized_url_duplicates()
        content_duplicates = self.detect_content_duplicates()
        title_similarities = self.detect_title_similarities()
        content_similarities = self.detect_content_similarities()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'url_duplicates': len(url_duplicates),
                'normalized_url_duplicates': len(normalized_url_duplicates),
                'content_duplicates': len(content_duplicates),
                'title_similarities': len(title_similarities),
                'content_similarities': len(content_similarities),
                'total_issues': len(url_duplicates) + len(normalized_url_duplicates) + 
                               len(content_duplicates) + len(title_similarities) + len(content_similarities)
            },
            'url_duplicates': url_duplicates,
            'normalized_url_duplicates': normalized_url_duplicates,
            'content_duplicates': content_duplicates,
            'title_similarities': title_similarities,
            'content_similarities': content_similarities,
            'recommendations': []
        }
        
        # Generate recommendations
        if url_duplicates:
            report['recommendations'].append({
                'type': 'critical',
                'message': f'Found {len(url_duplicates)} exact URL duplicates that should be merged',
                'action': 'merge_url_duplicates'
            })
        
        if content_duplicates:
            report['recommendations'].append({
                'type': 'high',
                'message': f'Found {len(content_duplicates)} content hash duplicates that should be reviewed',
                'action': 'review_content_duplicates'
            })
        
        if content_similarities:
            report['recommendations'].append({
                'type': 'medium',
                'message': f'Found {len(content_similarities)} content similarity groups that should be reviewed',
                'action': 'review_content_similarities'
            })
        
        logger.info(f"📊 Report generated: {report['summary']['total_issues']} total issues found")
        return report
    
    def merge_duplicates(self, duplicates: List[Dict[str, Any]], dry_run: bool = True) -> Dict[str, Any]:
        """Merge duplicate articles"""
        logger.info(f"🔄 {'DRY RUN: ' if dry_run else ''}Merging duplicates...")
        
        merge_results = {
            'merged': [],
            'errors': [],
            'total_processed': 0
        }
        
        for duplicate in duplicates:
            try:
                if duplicate['type'] == 'exact_url':
                    # Keep the article with the most content or the oldest
                    article_ids = duplicate['article_ids']
                    
                    # Get article details
                    with self.conn.cursor() as cur:
                        cur.execute("""
                            SELECT id, title, content, created_at, source_domain
                            FROM articles 
                            WHERE id = ANY(%s)
                            ORDER BY LENGTH(content) DESC, created_at ASC
                        """, (article_ids,))
                        
                        articles = cur.fetchall()
                    
                    # Keep the first article (most content/oldest)
                    keep_article = articles[0]
                    remove_articles = articles[1:]
                    
                    if not dry_run:
                        with self.conn.cursor() as cur:
                            # Delete duplicate articles
                            remove_ids = [article[0] for article in remove_articles]
                            cur.execute("""
                                DELETE FROM articles 
                                WHERE id = ANY(%s)
                            """, (remove_ids,))
                            
                            self.conn.commit()
                    
                    merge_results['merged'].append({
                        'kept_article_id': keep_article[0],
                        'removed_article_ids': [article[0] for article in remove_articles],
                        'url': duplicate['url'],
                        'titles': duplicate['titles']
                    })
                    
                    merge_results['total_processed'] += len(remove_articles)
                    
                    logger.info(f"{'DRY RUN: ' if dry_run else ''}Merged {len(remove_articles)} duplicates for {duplicate['url']}")
                
            except Exception as e:
                error_msg = f"Error merging duplicates: {e}"
                logger.error(error_msg)
                merge_results['errors'].append(error_msg)
        
        return merge_results
    
    def add_deduplication_constraints(self) -> bool:
        """Add database constraints to prevent future duplicates"""
        logger.info("🔒 Adding deduplication constraints...")
        
        try:
            with self.conn.cursor() as cur:
                # Add unique constraint on URL
                cur.execute("""
                    ALTER TABLE articles 
                    ADD CONSTRAINT unique_article_url UNIQUE (url)
                """)
                
                # Add index for faster duplicate detection
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_articles_url 
                    ON articles (url)
                """)
                
                # Add index for content hash (we'll add this column)
                cur.execute("""
                    ALTER TABLE articles 
                    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(32)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_articles_content_hash 
                    ON articles (content_hash)
                """)
                
                self.conn.commit()
                logger.info("✅ Deduplication constraints added successfully")
                return True
                
        except Exception as e:
            if "already exists" in str(e):
                logger.info("ℹ️ Constraints already exist")
                return True
            else:
                logger.error(f"❌ Error adding constraints: {e}")
                return False
    
    def populate_content_hashes(self) -> int:
        """Populate content_hash column for existing articles"""
        logger.info("🔧 Populating content hashes...")
        
        try:
            with self.conn.cursor() as cur:
                # Get articles without content hash
                cur.execute("""
                    SELECT id, content 
                    FROM articles 
                    WHERE content_hash IS NULL AND content IS NOT NULL
                """)
                
                articles = cur.fetchall()
                updated_count = 0
                
                for article_id, content in articles:
                    content_hash = self.generate_content_hash(content)
                    if content_hash:
                        cur.execute("""
                            UPDATE articles 
                            SET content_hash = %s 
                            WHERE id = %s
                        """, (content_hash, article_id))
                        updated_count += 1
                
                self.conn.commit()
                logger.info(f"✅ Updated {updated_count} articles with content hashes")
                return updated_count
                
        except Exception as e:
            logger.error(f"❌ Error populating content hashes: {e}")
            return 0
    
    def close_connection(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("🔌 Database connection closed")

def main():
    """Main function for article deduplication"""
    print("🔍 Article Deduplication System")
    print("==============================")
    
    deduplicator = ArticleDeduplicationSystem()
    
    if not deduplicator.connect_database():
        sys.exit(1)
    
    try:
        # Add constraints and populate hashes
        deduplicator.add_deduplication_constraints()
        deduplicator.populate_content_hashes()
        
        # Generate comprehensive report
        report = deduplicator.generate_deduplication_report()
        
        print(f"\n📊 DEDUPLICATION REPORT")
        print(f"=======================")
        print(f"Timestamp: {report['timestamp']}")
        print(f"URL duplicates: {report['summary']['url_duplicates']}")
        print(f"Normalized URL duplicates: {report['summary']['normalized_url_duplicates']}")
        print(f"Content duplicates: {report['summary']['content_duplicates']}")
        print(f"Title similarities: {report['summary']['title_similarities']}")
        print(f"Content similarities: {report['summary']['content_similarities']}")
        print(f"Total issues: {report['summary']['total_issues']}")
        
        if report['url_duplicates']:
            print(f"\n❌ URL DUPLICATES FOUND:")
            for dup in report['url_duplicates'][:5]:  # Show first 5
                print(f"  URL: {dup['url']}")
                print(f"  Count: {dup['count']}")
                print(f"  Titles: {', '.join(dup['titles'][:2])}")
                print()
        
        if report['content_duplicates']:
            print(f"\n🔄 CONTENT DUPLICATES FOUND:")
            for dup in report['content_duplicates'][:3]:  # Show first 3
                print(f"  Content Hash: {dup['content_hash']}")
                print(f"  Count: {dup['count']}")
                for article in dup['articles'][:2]:
                    print(f"    - {article['title'][:50]}... ({article['domain']})")
                print()
        
        # Auto-merge URL duplicates (dry run first)
        if report['url_duplicates']:
            print(f"\n🔄 AUTO-MERGE URL DUPLICATES (DRY RUN)")
            print(f"=====================================")
            merge_results = deduplicator.merge_duplicates(report['url_duplicates'], dry_run=True)
            print(f"Would merge: {merge_results['total_processed']} duplicate articles")
            print(f"Would keep: {len(merge_results['merged'])} articles")
            
            # Ask for confirmation to actually merge
            response = input("\nDo you want to proceed with actual merging? (y/N): ")
            if response.lower() == 'y':
                print(f"\n🔄 MERGING DUPLICATES...")
                merge_results = deduplicator.merge_duplicates(report['url_duplicates'], dry_run=False)
                print(f"✅ Merged: {merge_results['total_processed']} duplicate articles")
                if merge_results['errors']:
                    print(f"❌ Errors: {len(merge_results['errors'])}")
        
        print(f"\n✅ Deduplication analysis complete!")
        
    except Exception as e:
        logger.error(f"❌ Error in main execution: {e}")
        sys.exit(1)
    
    finally:
        deduplicator.close_connection()

if __name__ == "__main__":
    main()
