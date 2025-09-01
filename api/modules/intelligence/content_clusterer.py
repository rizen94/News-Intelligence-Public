#!/usr/bin/env python3
"""
News Intelligence System v2.5.0 - Content Clusterer
Groups similar articles for better ML processing and summarization
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentClusterer:
    """Groups similar articles for ML processing"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.connection = None
        
    def connect_db(self) -> bool:
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(
                host=self.db_config.get('host', 'postgres'),
                database=self.db_config.get('database', 'news_system'),
                user=self.db_config.get('user', 'newsapp'),
                password=self.db_config.get('password', ''),
                connect_timeout=10,
                options='-c statement_timeout=30000'
            )
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def find_similar_articles(self, article_id: int, similarity_threshold: float = 0.7) -> List[Dict]:
        """Find articles similar to a given article"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return []
            
            # Get the target article
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM articles WHERE id = %s
                """, (article_id,))
                target_article = cursor.fetchone()
                
                if not target_article:
                    logger.warning(f"Article {article_id} not found")
                    return []
            
            # Extract key phrases from target article
            target_phrases = self._extract_key_phrases(target_article.get('content', ''))
            target_domain = self._extract_domain(target_article.get('url', ''))
            target_date = target_article.get('published_date')
            
            # Find similar articles based on multiple criteria
            similar_articles = []
            
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get articles from similar time period (±3 days)
                if target_date:
                    start_date = target_date - timedelta(days=3)
                    end_date = target_date + timedelta(days=3)
                    
                    cursor.execute("""
                        SELECT * FROM articles 
                        WHERE id != %s 
                        AND published_date BETWEEN %s AND %s
                        AND processing_status = 'ml_processed'
                        ORDER BY published_date DESC
                    """, (article_id, start_date, end_date))
                else:
                    # If no date, get recent articles
                    cursor.execute("""
                        SELECT * FROM articles 
                        WHERE id != %s 
                        AND processing_status = 'ml_processed'
                        AND created_at >= NOW() - INTERVAL '7 days'
                        ORDER BY created_at DESC
                    """, (article_id,))
                
                candidate_articles = cursor.fetchall()
            
            # Calculate similarity scores
            for article in candidate_articles:
                similarity_score = self._calculate_similarity_score(
                    target_article, article, target_phrases, target_domain
                )
                
                if similarity_score >= similarity_threshold:
                    article['similarity_score'] = similarity_score
                    similar_articles.append(article)
            
            # Sort by similarity score
            similar_articles.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            logger.info(f"Found {len(similar_articles)} similar articles for article {article_id}")
            return similar_articles
            
        except Exception as e:
            logger.error(f"Error finding similar articles: {e}")
            return []
    
    def create_article_clusters(self, min_cluster_size: int = 2, max_cluster_size: int = 20) -> List[Dict]:
        """Create clusters of similar articles"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return []
            
            # Get all ML-processed articles
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id FROM articles 
                    WHERE processing_status = 'ml_processed'
                    AND ml_data IS NOT NULL
                    ORDER BY created_at DESC
                """)
                
                article_ids = [row['id'] for row in cursor.fetchall()]
            
            if not article_ids:
                logger.info("No ML-processed articles found for clustering")
                return []
            
            # Create clusters using a simple approach
            clusters = []
            processed_articles = set()
            
            for article_id in article_ids:
                if article_id in processed_articles:
                    continue
                
                # Find similar articles for this article
                similar_articles = self.find_similar_articles(article_id, similarity_threshold=0.6)
                
                if len(similar_articles) >= min_cluster_size:
                    # Create cluster
                    cluster = {
                        'cluster_id': len(clusters) + 1,
                        'main_article_id': article_id,
                        'article_ids': [article_id] + [a['id'] for a in similar_articles[:max_cluster_size-1]],
                        'size': min(len(similar_articles) + 1, max_cluster_size),
                        'created_at': datetime.now().isoformat(),
                        'cluster_type': 'similarity_based'
                    }
                    
                    clusters.append(cluster)
                    
                    # Mark articles as processed
                    processed_articles.update(cluster['article_ids'])
                    
                    logger.info(f"Created cluster {cluster['cluster_id']} with {cluster['size']} articles")
            
            # Store clusters in database
            self._store_clusters(clusters)
            
            logger.info(f"Created {len(clusters)} article clusters")
            return clusters
            
        except Exception as e:
            logger.error(f"Error creating article clusters: {e}")
            return []
    
    def get_cluster_summary(self, cluster_id: int) -> Dict:
        """Get summary information for a cluster"""
        try:
            if not self.connection:
                if not self.connect_db():
                    return {}
            
            # Get cluster information
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM article_clusters WHERE cluster_id = %s
                """, (cluster_id,))
                
                cluster = cursor.fetchone()
                if not cluster:
                    logger.warning(f"Cluster {cluster_id} not found")
                    return {}
                
                # Get articles in cluster
                article_ids = cluster.get('article_ids', [])
                if not article_ids:
                    return cluster
                
                # Get article details
                placeholders = ','.join(['%s'] * len(article_ids))
                cursor.execute(f"""
                    SELECT id, title, url, published_date, word_count, quality_score
                    FROM articles 
                    WHERE id IN ({placeholders})
                    ORDER BY published_date DESC
                """, article_ids)
                
                articles = cursor.fetchall()
                
                # Calculate cluster metrics
                total_words = sum(a.get('word_count', 0) for a in articles)
                avg_quality = sum(a.get('quality_score', 0) for a in articles) / len(articles) if articles else 0
                
                # Get date range
                dates = [a.get('published_date') for a in articles if a.get('published_date')]
                date_range = {
                    'earliest': min(dates) if dates else None,
                    'latest': max(dates) if dates else None
                }
                
                # Get common domains
                domains = [self._extract_domain(a.get('url', '')) for a in articles]
                domain_counts = defaultdict(int)
                for domain in domains:
                    if domain:
                        domain_counts[domain] += 1
                
                common_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                
                cluster_summary = {
                    'cluster_id': cluster_id,
                    'size': len(articles),
                    'total_words': total_words,
                    'average_quality': round(avg_quality, 2),
                    'date_range': date_range,
                    'common_domains': common_domains,
                    'articles': articles,
                    'created_at': cluster.get('created_at'),
                    'cluster_type': cluster.get('cluster_type')
                }
                
                return cluster_summary
                
        except Exception as e:
            logger.error(f"Error getting cluster summary: {e}")
            return {}
    
    def _calculate_similarity_score(self, article1: Dict, article2: Dict, 
                                  target_phrases: List[str], target_domain: str) -> float:
        """Calculate similarity score between two articles"""
        try:
            score = 0.0
            
            # Content similarity (0-40 points)
            content1 = article1.get('content', '').lower()
            content2 = article2.get('content', '').lower()
            
            # Check for common key phrases
            common_phrases = 0
            for phrase in target_phrases:
                if phrase.lower() in content2:
                    common_phrases += 1
            
            if common_phrases > 0:
                score += min(40, common_phrases * 8)
            
            # Domain similarity (0-20 points)
            domain2 = self._extract_domain(article2.get('url', ''))
            if domain2 == target_domain:
                score += 20
            elif domain2 and target_domain and domain2.split('.')[-2:] == target_domain.split('.')[-2:]:
                score += 10
            
            # Title similarity (0-20 points)
            title1 = article1.get('title', '').lower()
            title2 = article2.get('title', '').lower()
            
            # Check for common words in titles
            title_words1 = set(title1.split())
            title_words2 = set(title2.split())
            common_title_words = len(title_words1.intersection(title_words2))
            
            if common_title_words > 0:
                score += min(20, common_title_words * 4)
            
            # Time proximity (0-20 points)
            date1 = article1.get('published_date')
            date2 = article2.get('published_date')
            
            if date1 and date2:
                try:
                    if isinstance(date1, str):
                        date1 = datetime.fromisoformat(date1.replace('Z', '+00:00'))
                    if isinstance(date2, str):
                        date2 = datetime.fromisoformat(date2.replace('Z', '+00:00'))
                    
                    time_diff = abs((date1 - date2).total_seconds() / 3600)  # hours
                    
                    if time_diff <= 1:  # Within 1 hour
                        score += 20
                    elif time_diff <= 24:  # Within 1 day
                        score += 15
                    elif time_diff <= 72:  # Within 3 days
                        score += 10
                except:
                    pass
            
            return min(100.0, score)
            
        except Exception as e:
            logger.error(f"Error calculating similarity score: {e}")
            return 0.0
    
    def _extract_key_phrases(self, content: str) -> List[str]:
        """Extract key phrases from content"""
        try:
            if not content:
                return []
            
            # Simple key phrase extraction
            words = content.lower().split()
            
            # Filter out common stop words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            filtered_words = [word for word in words if word not in stop_words and len(word) > 3]
            
            # Count word frequency
            word_freq = {}
            for word in filtered_words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top phrases
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, freq in sorted_words[:15] if freq > 1]
            
        except Exception as e:
            logger.error(f"Error extracting key phrases: {e}")
            return []
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            if not url:
                return ""
            
            if '://' in url:
                domain = url.split('://')[1]
            else:
                domain = url
            
            if '/' in domain:
                domain = domain.split('/')[0]
            
            return domain.lower()
        except Exception:
            return ""
    
    def _store_clusters(self, clusters: List[Dict]):
        """Store clusters in database"""
        try:
            # First, create the clusters table if it doesn't exist
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS article_clusters (
                        cluster_id SERIAL PRIMARY KEY,
                        main_article_id INTEGER REFERENCES articles(id),
                        article_ids INTEGER[] NOT NULL,
                        size INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        cluster_type VARCHAR(50),
                        summary_data JSONB
                    )
                """)
                
                # Insert clusters
                for cluster in clusters:
                    cursor.execute("""
                        INSERT INTO article_clusters 
                        (main_article_id, article_ids, size, created_at, cluster_type)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        cluster['main_article_id'],
                        cluster['article_ids'],
                        cluster['size'],
                        cluster['created_at'],
                        cluster['cluster_type']
                    ))
                
                self.connection.commit()
                logger.info(f"Stored {len(clusters)} clusters in database")
                
        except Exception as e:
            logger.error(f"Error storing clusters: {e}")
            if self.connection:
                self.connection.rollback()
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
