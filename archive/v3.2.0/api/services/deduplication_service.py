"""
Enhanced Deduplication Service for News Intelligence System v3.0
Advanced duplicate detection with clustering and canonical version management
"""

import asyncio
import logging
import json
import hashlib
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
from collections import defaultdict

# Try to import sentence transformers for better similarity
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("Sentence transformers not available - using basic similarity")

from database.connection import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)

@dataclass
class DuplicatePair:
    """Represents a pair of duplicate articles"""
    article1_id: int
    article2_id: int
    similarity_score: float
    title_similarity: float
    content_similarity: float
    url_similarity: float
    algorithm: str
    status: str = "pending"

@dataclass
class DuplicateCluster:
    """Represents a cluster of duplicate articles"""
    cluster_id: int
    articles: List[int]
    canonical_article_id: int
    similarity_scores: Dict[Tuple[int, int], float]
    created_at: datetime

class DeduplicationService:
    """Enhanced deduplication service with clustering and canonical management"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sentence_model = None
        self.similarity_threshold = 0.85
        self.min_article_length = 100
        self.max_articles_to_process = 1000
        self.time_window_hours = 24
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            self._initialize_sentence_model()
        else:
            self.logger.warning("Using basic similarity - install sentence-transformers for better deduplication")
    
    def _initialize_sentence_model(self):
        """Initialize sentence transformer model for better similarity calculation"""
        try:
            # Use a lightweight model for similarity
            model_name = "all-MiniLM-L6-v2"
            self.logger.info(f"Loading sentence transformer model: {model_name}")
            self.sentence_model = SentenceTransformer(model_name)
            self.logger.info("Sentence transformer model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load sentence transformer model: {e}")
            self.sentence_model = None
    
    async def detect_duplicates(self, 
                               article_ids: List[int] = None,
                               time_window_hours: int = None) -> Dict[str, Any]:
        """Detect duplicates among articles"""
        try:
            if time_window_hours is None:
                time_window_hours = self.time_window_hours
            
            # Get articles to process
            articles = await self._get_articles_for_deduplication(article_ids, time_window_hours)
            
            if len(articles) < 2:
                return {
                    "duplicates_found": 0,
                    "clusters_created": 0,
                    "articles_processed": len(articles),
                    "message": "Not enough articles to process"
                }
            
            self.logger.info(f"Processing {len(articles)} articles for deduplication")
            
            # Detect duplicate pairs
            duplicate_pairs = await self._find_duplicate_pairs(articles)
            
            if not duplicate_pairs:
                return {
                    "duplicates_found": 0,
                    "clusters_created": 0,
                    "articles_processed": len(articles),
                    "message": "No duplicates found"
                }
            
            # Create clusters from duplicate pairs
            clusters = await self._create_clusters(duplicate_pairs)
            
            # Save results to database
            await self._save_duplicate_pairs(duplicate_pairs)
            await self._save_clusters(clusters)
            
            # Update article cluster assignments
            await self._update_article_clusters(clusters)
            
            self.logger.info(f"Found {len(duplicate_pairs)} duplicate pairs in {len(clusters)} clusters")
            
            return {
                "duplicates_found": len(duplicate_pairs),
                "clusters_created": len(clusters),
                "articles_processed": len(articles),
                "duplicate_pairs": len(duplicate_pairs),
                "clusters": len(clusters)
            }
            
        except Exception as e:
            self.logger.error(f"Error in duplicate detection: {e}")
            return {"error": str(e)}
    
    async def _get_articles_for_deduplication(self, 
                                            article_ids: List[int] = None,
                                            time_window_hours: int = 24) -> List[Dict[str, Any]]:
        """Get articles for deduplication processing"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                if article_ids:
                    # Process specific articles
                    placeholders = ','.join([':id' + str(i) for i in range(len(article_ids))])
                    params = {f'id{i}': aid for i, aid in enumerate(article_ids)}
                    params['min_length'] = self.min_article_length
                    
                    query = f"""
                        SELECT id, title, content, url, created_at, source
                        FROM articles 
                        WHERE id IN ({placeholders})
                        AND LENGTH(content) >= :min_length
                        ORDER BY created_at DESC
                    """
                else:
                    # Process recent articles
                    params = {
                        'time_window': time_window_hours,
                        'min_length': self.min_article_length,
                        'max_articles': self.max_articles_to_process
                    }
                    
                    query = """
                        SELECT id, title, content, url, created_at, source
                        FROM articles 
                        WHERE created_at >= NOW() - INTERVAL ':time_window hours'
                        AND LENGTH(content) >= :min_length
                        AND is_duplicate = false
                        ORDER BY created_at DESC
                        LIMIT :max_articles
                    """
                
                result = db.execute(text(query), params).fetchall()
                
                articles = []
                for row in result:
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "content": row[2],
                        "url": row[3],
                        "created_at": row[4],
                        "source": row[5]
                    })
                
                return articles
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting articles for deduplication: {e}")
            return []
    
    async def _find_duplicate_pairs(self, articles: List[Dict[str, Any]]) -> List[DuplicatePair]:
        """Find duplicate pairs among articles"""
        duplicate_pairs = []
        
        try:
            # Create article embeddings if sentence transformer is available
            if self.sentence_model:
                embeddings = await self._create_embeddings(articles)
            else:
                embeddings = None
            
            # Compare each article with others
            for i in range(len(articles)):
                for j in range(i + 1, len(articles)):
                    article1 = articles[i]
                    article2 = articles[j]
                    
                    # Calculate similarity scores
                    similarity_scores = await self._calculate_similarity(
                        article1, article2, embeddings, i, j
                    )
                    
                    # Check if articles are duplicates
                    if similarity_scores["overall"] >= self.similarity_threshold:
                        duplicate_pair = DuplicatePair(
                            article1_id=article1["id"],
                            article2_id=article2["id"],
                            similarity_score=similarity_scores["overall"],
                            title_similarity=similarity_scores["title"],
                            content_similarity=similarity_scores["content"],
                            url_similarity=similarity_scores["url"],
                            algorithm=similarity_scores["algorithm"]
                        )
                        duplicate_pairs.append(duplicate_pair)
            
            return duplicate_pairs
            
        except Exception as e:
            self.logger.error(f"Error finding duplicate pairs: {e}")
            return []
    
    async def _create_embeddings(self, articles: List[Dict[str, Any]]) -> np.ndarray:
        """Create embeddings for articles using sentence transformer"""
        try:
            if not self.sentence_model:
                return None
            
            # Combine title and content for embedding
            texts = []
            for article in articles:
                text = f"{article['title']} {article['content'][:1000]}"  # Limit content length
                texts.append(text)
            
            # Create embeddings in batches to avoid memory issues
            batch_size = 32
            embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_embeddings = self.sentence_model.encode(batch_texts)
                embeddings.append(batch_embeddings)
            
            return np.vstack(embeddings)
            
        except Exception as e:
            self.logger.error(f"Error creating embeddings: {e}")
            return None
    
    async def _calculate_similarity(self, 
                                  article1: Dict[str, Any], 
                                  article2: Dict[str, Any],
                                  embeddings: np.ndarray = None,
                                  idx1: int = None,
                                  idx2: int = None) -> Dict[str, float]:
        """Calculate similarity between two articles"""
        try:
            # Title similarity
            title_sim = self._calculate_text_similarity(article1["title"], article2["title"])
            
            # URL similarity
            url_sim = self._calculate_url_similarity(article1["url"], article2["url"])
            
            # Content similarity
            if embeddings is not None and idx1 is not None and idx2 is not None:
                content_sim = self._calculate_embedding_similarity(embeddings[idx1], embeddings[idx2])
                algorithm = "sentence_transformer"
            else:
                content_sim = self._calculate_text_similarity(article1["content"], article2["content"])
                algorithm = "basic_text"
            
            # Overall similarity (weighted average)
            overall_sim = (title_sim * 0.4 + content_sim * 0.5 + url_sim * 0.1)
            
            return {
                "title": title_sim,
                "content": content_sim,
                "url": url_sim,
                "overall": overall_sim,
                "algorithm": algorithm
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating similarity: {e}")
            return {
                "title": 0.0,
                "content": 0.0,
                "url": 0.0,
                "overall": 0.0,
                "algorithm": "error"
            }
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings"""
        try:
            if not text1 or not text2:
                return 0.0
            
            # Normalize texts
            text1_norm = self._normalize_text(text1)
            text2_norm = self._normalize_text(text2)
            
            # Calculate Jaccard similarity
            words1 = set(text1_norm.split())
            words2 = set(text2_norm.split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating text similarity: {e}")
            return 0.0
    
    def _calculate_url_similarity(self, url1: str, url2: str) -> float:
        """Calculate similarity between two URLs"""
        try:
            if not url1 or not url2:
                return 0.0
            
            # Normalize URLs
            url1_norm = self._normalize_url(url1)
            url2_norm = self._normalize_url(url2)
            
            if url1_norm == url2_norm:
                return 1.0
            
            # Calculate similarity based on domain and path
            domain1 = self._extract_domain(url1_norm)
            domain2 = self._extract_domain(url2_norm)
            
            if domain1 != domain2:
                return 0.0
            
            # Compare paths
            path1 = self._extract_path(url1_norm)
            path2 = self._extract_path(url2_norm)
            
            return self._calculate_text_similarity(path1, path2)
            
        except Exception as e:
            self.logger.error(f"Error calculating URL similarity: {e}")
            return 0.0
    
    def _calculate_embedding_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings"""
        try:
            # Calculate cosine similarity
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception as e:
            self.logger.error(f"Error calculating embedding similarity: {e}")
            return 0.0
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        
        return text.strip()
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        if not url:
            return ""
        
        # Remove protocol
        url = re.sub(r'^https?://', '', url)
        
        # Remove www
        url = re.sub(r'^www\.', '', url)
        
        # Remove trailing slash
        url = url.rstrip('/')
        
        return url.lower()
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            return url.split('/')[0]
        except:
            return url
    
    def _extract_path(self, url: str) -> str:
        """Extract path from URL"""
        try:
            parts = url.split('/')
            return '/'.join(parts[1:]) if len(parts) > 1 else ""
        except:
            return ""
    
    async def _create_clusters(self, duplicate_pairs: List[DuplicatePair]) -> List[DuplicateCluster]:
        """Create clusters from duplicate pairs"""
        try:
            # Build graph of connected articles
            graph = defaultdict(set)
            for pair in duplicate_pairs:
                graph[pair.article1_id].add(pair.article2_id)
                graph[pair.article2_id].add(pair.article1_id)
            
            # Find connected components (clusters)
            visited = set()
            clusters = []
            cluster_id = 1
            
            for article_id in graph:
                if article_id not in visited:
                    # BFS to find all connected articles
                    cluster_articles = []
                    queue = [article_id]
                    
                    while queue:
                        current = queue.pop(0)
                        if current not in visited:
                            visited.add(current)
                            cluster_articles.append(current)
                            queue.extend(graph[current] - visited)
                    
                    if len(cluster_articles) > 1:
                        # Choose canonical article (highest priority, then most recent)
                        canonical_id = await self._choose_canonical_article(cluster_articles)
                        
                        # Calculate similarity scores for cluster
                        similarity_scores = {}
                        for pair in duplicate_pairs:
                            if (pair.article1_id in cluster_articles and 
                                pair.article2_id in cluster_articles):
                                key = tuple(sorted([pair.article1_id, pair.article2_id]))
                                similarity_scores[key] = pair.similarity_score
                        
                        cluster = DuplicateCluster(
                            cluster_id=cluster_id,
                            articles=cluster_articles,
                            canonical_article_id=canonical_id,
                            similarity_scores=similarity_scores,
                            created_at=datetime.now()
                        )
                        clusters.append(cluster)
                        cluster_id += 1
            
            return clusters
            
        except Exception as e:
            self.logger.error(f"Error creating clusters: {e}")
            return []
    
    async def _choose_canonical_article(self, article_ids: List[int]) -> int:
        """Choose canonical article from cluster"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get article details for comparison
                placeholders = ','.join([':id' + str(i) for i in range(len(article_ids))])
                params = {f'id{i}': aid for i, aid in enumerate(article_ids)}
                
                query = f"""
                    SELECT id, source_tier, source_priority, created_at, LENGTH(content) as content_length
                    FROM articles 
                    WHERE id IN ({placeholders})
                    ORDER BY source_tier ASC, source_priority ASC, content_length DESC, created_at DESC
                """
                
                result = db.execute(text(query), params).fetchall()
                
                if result:
                    return result[0][0]  # Return first (highest priority) article
                else:
                    return article_ids[0]  # Fallback to first ID
                    
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error choosing canonical article: {e}")
            return article_ids[0]
    
    async def _save_duplicate_pairs(self, duplicate_pairs: List[DuplicatePair]):
        """Save duplicate pairs to database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                for pair in duplicate_pairs:
                    db.execute(text("""
                        INSERT INTO duplicate_pairs (
                            article1_id, article2_id, similarity_score,
                            title_similarity, content_similarity, url_similarity,
                            algorithm, status
                        ) VALUES (
                            :article1_id, :article2_id, :similarity_score,
                            :title_similarity, :content_similarity, :url_similarity,
                            :algorithm, :status
                        ) ON CONFLICT (article1_id, article2_id) DO NOTHING
                    """), {
                        "article1_id": pair.article1_id,
                        "article2_id": pair.article2_id,
                        "similarity_score": pair.similarity_score,
                        "title_similarity": pair.title_similarity,
                        "content_similarity": pair.content_similarity,
                        "url_similarity": pair.url_similarity,
                        "algorithm": pair.algorithm,
                        "status": pair.status
                    })
                
                db.commit()
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error saving duplicate pairs: {e}")
    
    async def _save_clusters(self, clusters: List[DuplicateCluster]):
        """Save clusters to database"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                for cluster in clusters:
                    # Update articles with cluster information
                    for article_id in cluster.articles:
                        is_canonical = article_id == cluster.canonical_article_id
                        canonical_id = cluster.canonical_article_id if not is_canonical else None
                        
                        db.execute(text("""
                            UPDATE articles 
                            SET cluster_id = :cluster_id,
                                is_duplicate = :is_duplicate,
                                canonical_article_id = :canonical_id
                            WHERE id = :article_id
                        """), {
                            "cluster_id": cluster.cluster_id,
                            "is_duplicate": not is_canonical,
                            "canonical_id": canonical_id,
                            "article_id": article_id
                        })
                
                db.commit()
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error saving clusters: {e}")
    
    async def _update_article_clusters(self, clusters: List[DuplicateCluster]):
        """Update article cluster assignments"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                for cluster in clusters:
                    for article_id in cluster.articles:
                        is_canonical = article_id == cluster.canonical_article_id
                        canonical_id = cluster.canonical_article_id if not is_canonical else None
                        
                        db.execute(text("""
                            UPDATE articles 
                            SET cluster_id = :cluster_id,
                                is_duplicate = :is_duplicate,
                                canonical_article_id = :canonical_id
                            WHERE id = :article_id
                        """), {
                            "cluster_id": cluster.cluster_id,
                            "is_duplicate": not is_canonical,
                            "canonical_id": canonical_id,
                            "article_id": article_id
                        })
                
                db.commit()
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error updating article clusters: {e}")
    
    async def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics"""
        try:
            db_gen = get_db()
            db = next(db_gen)
            try:
                # Get overall stats
                total_articles = db.execute(text("SELECT COUNT(*) FROM articles")).fetchone()[0]
                duplicate_articles = db.execute(text("SELECT COUNT(*) FROM articles WHERE is_duplicate = true")).fetchone()[0]
                clusters = db.execute(text("SELECT COUNT(DISTINCT cluster_id) FROM articles WHERE cluster_id IS NOT NULL")).fetchone()[0]
                duplicate_pairs = db.execute(text("SELECT COUNT(*) FROM duplicate_pairs")).fetchone()[0]
                
                # Get recent stats
                recent_duplicates = db.execute(text("""
                    SELECT COUNT(*) FROM duplicate_pairs 
                    WHERE detected_at >= CURRENT_DATE
                """)).fetchone()[0]
                
                return {
                    "total_articles": total_articles,
                    "duplicate_articles": duplicate_articles,
                    "clusters": clusters,
                    "duplicate_pairs": duplicate_pairs,
                    "recent_duplicates": recent_duplicates,
                    "duplicate_rate": (duplicate_articles / total_articles * 100) if total_articles > 0 else 0
                }
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Error getting deduplication stats: {e}")
            return {"error": str(e)}

# Global deduplication service instance
_deduplication_service = None

async def get_deduplication_service() -> DeduplicationService:
    """Get or create global deduplication service instance"""
    global _deduplication_service
    if _deduplication_service is None:
        _deduplication_service = DeduplicationService()
    return _deduplication_service

