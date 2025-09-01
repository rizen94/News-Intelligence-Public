#!/usr/bin/env python3
"""
Article Deduplicator for News Intelligence System v2.5.0
Handles content hash, URL, and semantic similarity deduplication
"""

import os
import sys
import json
import logging
import hashlib
import psycopg2
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs, urlunparse
from collections import defaultdict

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    print("Warning: sentence-transformers not available. Using basic similarity.")

try:
    from fuzzywuzzy import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("Warning: fuzzywuzzy not available. Using basic string matching.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DuplicateGroup:
    """Represents a group of duplicate articles."""
    group_id: int
    original_article_id: int
    duplicate_article_ids: List[int]
    duplicate_count: int
    similarity_type: str  # 'content_hash', 'url', 'semantic'
    confidence_score: float
    created_at: datetime

@dataclass
class DuplicateCandidate:
    """Represents a potential duplicate article."""
    article_id: int
    title: str
    content: str
    url: str
    content_hash: str
    canonical_url: str
    url_hash: str
    similarity_score: float
    similarity_type: str
    is_duplicate: bool = False
    duplicate_of: Optional[int] = None

class ArticleDeduplicator:
    """
    Comprehensive article deduplication system using multiple strategies:
    1. Content hash-based deduplication
    2. URL-based deduplication with canonicalization
    3. Semantic similarity deduplication
    """
    
    def __init__(self, db_config: Dict = None):
        """Initialize the deduplicator with database configuration."""
        self.db_config = db_config or {
            'host': os.getenv('DB_HOST', 'postgres'),
            'database': os.getenv('DB_NAME', 'news_db'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
            'port': os.getenv('DB_PORT', '5432'),
            'connect_timeout': 10,
            'options': '-c statement_timeout=5000'
        }
        
        # Initialize semantic similarity model if available
        self.semantic_model = None
        if SEMANTIC_AVAILABLE:
            try:
                # Use a lightweight model for efficiency
                self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Loaded semantic similarity model")
            except Exception as e:
                logger.warning(f"Failed to load semantic model: {e}")
                self.semantic_model = None
        
        # Deduplication configuration
        self.config = {
            'content_hash_threshold': 1.0,  # Exact match for content hash
            'url_similarity_threshold': 0.8,  # URL similarity threshold
            'semantic_similarity_threshold': 0.85,  # Semantic similarity threshold
            'title_similarity_threshold': 0.7,  # Title similarity threshold
            'batch_size': 100,  # Process articles in batches
            'max_semantic_comparisons': 1000,  # Limit semantic comparisons for performance
        }
        
        # URL normalization patterns
        self.url_cleanup_patterns = [
            # Remove common tracking parameters
            r'[?&](utm_source|utm_medium|utm_campaign|utm_term|utm_content|fbclid|gclid|msclkid)=[^&]*',
            # Remove social media tracking
            r'[?&](ref|source|via|shared)=[^&]*',
            # Remove analytics parameters
            r'[?&](_ga|_gl|_gac|_gid)=[^&]*',
            # Remove timestamp parameters
            r'[?&](t|time|timestamp)=[^&]*',
        ]
    
    def _get_db_connection(self) -> Optional[psycopg2.extensions.connection]:
        """Get database connection with error handling."""
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.autocommit = True
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            return None
    
    def _close_db_connection(self, conn: psycopg2.extensions.connection):
        """Close database connection safely."""
        if conn and not conn.closed:
            conn.close()
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing tracking parameters and standardizing format."""
        if not url:
            return ""
        
        try:
            # Parse URL
            parsed = urlparse(url)
            
            # Clean query parameters
            query_params = parse_qs(parsed.query)
            
            # Remove tracking parameters
            cleaned_params = {}
            for key, values in query_params.items():
                if not any(re.match(pattern, key) for pattern in self.url_cleanup_patterns):
                    cleaned_params[key] = values
            
            # Rebuild query string
            cleaned_query = '&'.join([f"{k}={v[0]}" for k, v in cleaned_params.items()])
            
            # Normalize protocol
            scheme = parsed.scheme.lower()
            if scheme not in ['http', 'https']:
                scheme = 'http'
            
            # Normalize domain (remove www.)
            netloc = parsed.netloc.lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            # Rebuild URL
            normalized = urlunparse((
                scheme,
                netloc,
                parsed.path,
                parsed.params,
                cleaned_query,
                ''  # Remove fragment
            ))
            
            return normalized
            
        except Exception as e:
            logger.warning(f"URL normalization failed for {url}: {e}")
            return url
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate SHA256 hash of cleaned content."""
        if not content:
            return ""
        
        # Clean content for hashing (remove extra whitespace)
        cleaned_content = re.sub(r'\s+', ' ', content.strip())
        return hashlib.sha256(cleaned_content.encode('utf-8')).hexdigest()
    
    def _generate_url_hash(self, url: str) -> str:
        """Generate hash of normalized URL."""
        normalized_url = self._normalize_url(url)
        return hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles."""
        if not title1 or not title2:
            return 0.0
        
        # Clean titles for comparison
        clean_title1 = re.sub(r'[^\w\s]', '', title1.lower().strip())
        clean_title2 = re.sub(r'[^\w\s]', '', title2.lower().strip())
        
        if FUZZY_AVAILABLE:
            # Use fuzzywuzzy for better similarity calculation
            return fuzz.ratio(clean_title1, clean_title2) / 100.0
        else:
            # Basic string similarity
            words1 = set(clean_title1.split())
            words2 = set(clean_title2.split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            
            return intersection / union if union > 0 else 0.0
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity using sentence transformers."""
        if not self.semantic_model or not text1 or not text2:
            return 0.0
        
        try:
            # Truncate texts to reasonable length for efficiency
            max_length = 512
            truncated_text1 = text1[:max_length]
            truncated_text2 = text2[:max_length]
            
            # Generate embeddings
            embeddings = self.semantic_model.encode([truncated_text1, truncated_text2])
            
            # Calculate cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def _get_articles_for_deduplication(self, limit: int = None) -> List[DuplicateCandidate]:
        """Get articles that need deduplication processing."""
        conn = self._get_db_connection()
        if not conn:
            return []
        
        try:
            limit_clause = f"LIMIT {limit}" if limit else ""
            query = f"""
                SELECT id, title, content, url, content_hash
                FROM articles 
                WHERE processing_status = 'raw'
                  AND (duplicate_of IS NULL OR duplicate_of = 0)
                  AND is_duplicate = FALSE
                ORDER BY created_at DESC
                {limit_clause}
            """
            
            cursor = conn.cursor()
            cursor.execute(query)
            
            candidates = []
            for row in cursor.fetchall():
                candidate = DuplicateCandidate(
                    article_id=row[0],
                    title=row[1] or "",
                    content=row[2] or "",
                    url=row[3] or "",
                    content_hash=row[4] or "",
                    canonical_url=self._normalize_url(row[3] or ""),
                    url_hash=self._generate_url_hash(row[3] or ""),
                    similarity_score=0.0,
                    similarity_type="",
                )
                
                # Generate content hash if not present
                if not candidate.content_hash:
                    candidate.content_hash = self._generate_content_hash(candidate.content)
                
                candidates.append(candidate)
            
            cursor.close()
            return candidates
            
        except psycopg2.Error as e:
            logger.error(f"Database error getting articles: {e}")
            return []
        finally:
            self._close_db_connection(conn)
    
    def _find_content_hash_duplicates(self, candidates: List[DuplicateCandidate]) -> List[DuplicateGroup]:
        """Find duplicates based on content hash."""
        hash_groups = defaultdict(list)
        
        # Group by content hash
        for candidate in candidates:
            if candidate.content_hash:
                hash_groups[candidate.content_hash].append(candidate)
        
        duplicate_groups = []
        
        for content_hash, articles in hash_groups.items():
            if len(articles) > 1:
                # Sort by creation time, oldest first
                sorted_articles = sorted(articles, key=lambda x: x.article_id)
                original = sorted_articles[0]
                duplicates = sorted_articles[1:]
                
                group = DuplicateGroup(
                    group_id=0,  # Will be set when saved to database
                    original_article_id=original.article_id,
                    duplicate_article_ids=[d.article_id for d in duplicates],
                    duplicate_count=len(duplicates),
                    similarity_type='content_hash',
                    confidence_score=1.0,  # Exact match
                    created_at=datetime.now()
                )
                
                duplicate_groups.append(group)
                
                # Mark candidates as duplicates
                for duplicate in duplicates:
                    duplicate.is_duplicate = True
                    duplicate.duplicate_of = original.article_id
                    duplicate.similarity_score = 1.0
                    duplicate.similarity_type = 'content_hash'
        
        return duplicate_groups
    
    def _find_url_duplicates(self, candidates: List[DuplicateCandidate]) -> List[DuplicateGroup]:
        """Find duplicates based on URL similarity."""
        url_groups = defaultdict(list)
        
        # Group by domain first for efficiency
        for candidate in candidates:
            if candidate.canonical_url:
                try:
                    domain = urlparse(candidate.canonical_url).netloc
                    url_groups[domain].append(candidate)
                except:
                    continue
        
        duplicate_groups = []
        
        for domain, articles in url_groups.items():
            if len(articles) < 2:
                continue
            
            # Compare URLs within the same domain
            for i, article1 in enumerate(articles):
                if article1.is_duplicate:
                    continue
                
                for j, article2 in enumerate(articles[i+1:], i+1):
                    if article2.is_duplicate:
                        continue
                    
                    # Calculate URL similarity
                    similarity = self._calculate_title_similarity(article1.title, article2.title)
                    
                    if similarity >= self.config['url_similarity_threshold']:
                        # Mark as duplicate
                        article2.is_duplicate = True
                        article2.duplicate_of = article1.article_id
                        article2.similarity_score = similarity
                        article2.similarity_type = 'url'
                        
                        # Create duplicate group
                        group = DuplicateGroup(
                            group_id=0,
                            original_article_id=article1.article_id,
                            duplicate_article_ids=[article2.article_id],
                            duplicate_count=1,
                            similarity_type='url',
                            confidence_score=similarity,
                            created_at=datetime.now()
                        )
                        
                        duplicate_groups.append(group)
        
        return duplicate_groups
    
    def _find_semantic_duplicates(self, candidates: List[DuplicateCandidate]) -> List[DuplicateGroup]:
        """Find duplicates based on semantic similarity."""
        if not self.semantic_model:
            return []
        
        # Filter out already identified duplicates
        non_duplicates = [c for c in candidates if not c.is_duplicate]
        
        if len(non_duplicates) < 2:
            return []
        
        duplicate_groups = []
        processed_pairs = set()
        
        # Limit comparisons for performance
        max_comparisons = min(self.config['max_semantic_comparisons'], 
                            len(non_duplicates) * (len(non_duplicates) - 1) // 2)
        comparison_count = 0
        
        for i, article1 in enumerate(non_duplicates):
            if article1.is_duplicate:
                continue
            
            for j, article2 in enumerate(non_duplicates[i+1:], i+1):
                if article2.is_duplicate:
                    continue
                
                if comparison_count >= max_comparisons:
                    break
                
                # Check if we've already compared this pair
                pair_key = tuple(sorted([article1.article_id, article2.article_id]))
                if pair_key in processed_pairs:
                    continue
                
                processed_pairs.add(pair_key)
                comparison_count += 1
                
                # Calculate semantic similarity
                semantic_sim = self._calculate_semantic_similarity(
                    article1.content, article2.content
                )
                
                # Calculate title similarity
                title_sim = self._calculate_title_similarity(
                    article1.title, article2.title
                )
                
                # Combined similarity score
                combined_similarity = (semantic_sim * 0.7) + (title_sim * 0.3)
                
                if combined_similarity >= self.config['semantic_similarity_threshold']:
                    # Mark as duplicate
                    article2.is_duplicate = True
                    article2.duplicate_of = article1.article_id
                    article2.similarity_score = combined_similarity
                    article2.similarity_type = 'semantic'
                    
                    # Create duplicate group
                    group = DuplicateGroup(
                        group_id=0,
                        original_article_id=article1.article_id,
                        duplicate_article_ids=[article2.article_id],
                        duplicate_count=1,
                        similarity_type='semantic',
                        confidence_score=combined_similarity,
                        created_at=datetime.now()
                    )
                    
                    duplicate_groups.append(group)
                
                if comparison_count >= max_comparisons:
                    break
            
            if comparison_count >= max_comparisons:
                break
        
        return duplicate_groups
    
    def _save_duplicate_groups(self, duplicate_groups: List[DuplicateGroup]) -> bool:
        """Save duplicate groups to the database."""
        conn = self._get_db_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            for group in duplicate_groups:
                # Insert duplicate group
                group_query = """
                    INSERT INTO duplicate_groups (
                        original_article_id, duplicate_count, created_at
                    ) VALUES (%s, %s, %s)
                    RETURNING group_id
                """
                
                cursor.execute(group_query, (
                    group.original_article_id,
                    group.duplicate_count,
                    group.created_at
                ))
                
                group.group_id = cursor.fetchone()[0]
                
                # Update articles with duplicate information
                for duplicate_id in group.duplicate_article_ids:
                    update_query = """
                        UPDATE articles 
                        SET duplicate_of = %s, 
                            is_duplicate = TRUE,
                            processing_status = 'duplicate',
                            updated_at = %s
                        WHERE id = %s
                    """
                    
                    cursor.execute(update_query, (
                        group.original_article_id,
                        datetime.now(),
                        duplicate_id
                    ))
                
                # Update original article
                update_original_query = """
                    UPDATE articles 
                    SET processing_status = 'processing',
                            updated_at = %s
                        WHERE id = %s
                """
                
                cursor.execute(update_original_query, (
                    datetime.now(),
                    group.original_article_id
                ))
            
            conn.commit()
            logger.info(f"Saved {len(duplicate_groups)} duplicate groups")
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Database error saving duplicate groups: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db_connection(conn)
    
    def _update_article_hashes(self, candidates: List[DuplicateCandidate]) -> bool:
        """Update articles with content and URL hashes."""
        conn = self._get_db_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            for candidate in candidates:
                update_query = """
                    UPDATE articles 
                    SET content_hash = %s,
                        canonical_url = %s,
                        url_hash = %s,
                        updated_at = %s
                    WHERE id = %s
                """
                
                cursor.execute(update_query, (
                    candidate.content_hash,
                    candidate.canonical_url,
                    candidate.url_hash,
                    datetime.now(),
                    candidate.article_id
                ))
            
            conn.commit()
            logger.info(f"Updated hashes for {len(candidates)} articles")
            return True
            
        except psycopg2.Error as e:
            logger.error(f"Database error updating hashes: {e}")
            conn.rollback()
            return False
        finally:
            self._close_db_connection(conn)
    
    def run_deduplication(self, max_articles: int = None) -> Dict:
        """Run the complete deduplication process."""
        start_time = datetime.now()
        logger.info("Starting article deduplication process")
        
        try:
            # Get articles for deduplication
            candidates = self._get_articles_for_deduplication(max_articles)
            if not candidates:
                logger.info("No articles found for deduplication")
                return {'status': 'success', 'articles_processed': 0}
            
            logger.info(f"Processing {len(candidates)} articles for deduplication")
            
            # Update article hashes
            self._update_article_hashes(candidates)
            
            # Find duplicates using different strategies
            content_hash_duplicates = self._find_content_hash_duplicates(candidates)
            url_duplicates = self._find_url_duplicates(candidates)
            semantic_duplicates = self._find_semantic_duplicates(candidates)
            
            # Combine all duplicate groups
            all_duplicates = content_hash_duplicates + url_duplicates + semantic_duplicates
            
            # Save duplicate groups to database
            if all_duplicates:
                self._save_duplicate_groups(all_duplicates)
            
            # Calculate statistics
            total_duplicates = sum(group.duplicate_count for group in all_duplicates)
            content_hash_count = len(content_hash_duplicates)
            url_count = len(url_duplicates)
            semantic_count = len(semantic_duplicates)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            results = {
                'status': 'success',
                'articles_processed': len(candidates),
                'duplicate_groups_found': len(all_duplicates),
                'total_duplicates': total_duplicates,
                'content_hash_duplicates': content_hash_count,
                'url_duplicates': url_count,
                'semantic_duplicates': semantic_count,
                'processing_time_seconds': duration,
                'duplicate_rate': total_duplicates / len(candidates) if candidates else 0
            }
            
            logger.info(f"Deduplication completed in {duration:.2f}s")
            logger.info(f"Found {len(all_duplicates)} duplicate groups with {total_duplicates} total duplicates")
            
            return results
            
        except Exception as e:
            logger.error(f"Deduplication process failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'articles_processed': 0
            }
    
    def get_deduplication_stats(self) -> Dict:
        """Get deduplication statistics from the database."""
        conn = self._get_db_connection()
        if not conn:
            return {}
        
        try:
            cursor = conn.cursor()
            
            # Get overall statistics
            stats_query = """
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(CASE WHEN is_duplicate THEN 1 END) as duplicate_articles,
                    COUNT(CASE WHEN duplicate_of IS NOT NULL THEN 1 END) as marked_duplicates,
                    COUNT(CASE WHEN processing_status = 'duplicate' THEN 1 END) as processing_duplicates
                FROM articles
            """
            
            cursor.execute(stats_query)
            row = cursor.fetchone()
            
            stats = {
                'total_articles': row[0],
                'duplicate_articles': row[1],
                'marked_duplicates': row[2],
                'processing_duplicates': row[3],
                'duplicate_rate': row[1] / row[0] if row[0] > 0 else 0
            }
            
            # Get duplicate group statistics
            group_query = """
                SELECT 
                    COUNT(*) as total_groups,
                    AVG(duplicate_count) as avg_duplicates_per_group,
                    MAX(duplicate_count) as max_duplicates_in_group
                FROM duplicate_groups
            """
            
            cursor.execute(group_query)
            group_row = cursor.fetchone()
            
            if group_row[0] > 0:
                stats.update({
                    'total_duplicate_groups': group_row[0],
                    'avg_duplicates_per_group': float(group_row[1]),
                    'max_duplicates_in_group': group_row[2]
                })
            
            cursor.close()
            return stats
            
        except psycopg2.Error as e:
            logger.error(f"Database error getting stats: {e}")
            return {}
        finally:
            self._close_db_connection(conn)

def main():
    """Main function for testing the deduplicator."""
    print("Testing Article Deduplicator...")
    
    # Initialize deduplicator
    deduplicator = ArticleDeduplicator()
    
    # Check component availability
    print(f"Semantic Model Available: {deduplicator.semantic_model is not None}")
    print(f"Fuzzy Matching Available: {FUZZY_AVAILABLE}")
    
    # Run deduplication
    print("\nRunning deduplication...")
    results = deduplicator.run_deduplication(max_articles=50)
    
    if results['status'] == 'success':
        print(f"\nDeduplication Results:")
        print(f"  Articles Processed: {results['articles_processed']}")
        print(f"  Duplicate Groups Found: {results['duplicate_groups_found']}")
        print(f"  Total Duplicates: {results['total_duplicates']}")
        print(f"  Processing Time: {results['processing_time_seconds']:.2f}s")
        print(f"  Duplicate Rate: {results['duplicate_rate']:.2%}")
        
        # Show detailed breakdown
        print(f"\nDuplicate Breakdown:")
        print(f"  Content Hash: {results['content_hash_duplicates']}")
        print(f"  URL Similarity: {results['url_duplicates']}")
        print(f"  Semantic: {results['semantic_duplicates']}")
        
        # Get overall statistics
        stats = deduplicator.get_deduplication_stats()
        print(f"\nOverall Statistics:")
        print(f"  Total Articles: {stats.get('total_articles', 0)}")
        print(f"  Duplicate Rate: {stats.get('duplicate_rate', 0):.2%}")
        print(f"  Duplicate Groups: {stats.get('total_duplicate_groups', 0)}")
        
    else:
        print(f"Deduplication failed: {results.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()
