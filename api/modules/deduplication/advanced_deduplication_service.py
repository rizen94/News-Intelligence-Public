"""
Advanced Deduplication Service
Moved from pipeline_deduplication_service.py for proper module structure
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import hashlib

from services.pipeline_deduplication_service import PipelineDeduplicationService

logger = logging.getLogger(__name__)


@dataclass
class ArticleMetadata:
    """Metadata for an article during deduplication"""
    id: int
    title: str
    url: str
    source: str
    published_at: datetime
    content: str | None = None


@dataclass
class ClusterResult:
    """Result of clustering similar articles"""
    cluster_id: str
    articles: list[dict]
    representative_article_id: int
    similarity_score: float


class AdvancedDeduplicationService:
    """
    Advanced deduplication service with clustering and semantic similarity
    """
    
    def __init__(self, db_config: dict):
        """Initialize the advanced deduplication service"""
        self.db_config = db_config
        self.pipeline_service = PipelineDeduplicationService()
        self.default_threshold = 0.85
        
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using multiple methods"""
        # Simple hash-based similarity for URLs
        if hasattr(text1, 'startswith') and text1.startswith('http'):
            hash1 = hashlib.md5(text1.encode()).hexdigest()
            hash2 = hashlib.md5(text2.encode()).hexdigest()
            return 1.0 if hash1 == hash2 else 0.0
        
        # Title-based similarity
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    async def find_duplicates(self, article: ArticleMetadata, threshold: float = None) -> list[dict]:
        """Find duplicate articles for the given article"""
        threshold = threshold or self.default_threshold
        
        # Use the pipeline service for actual deduplication
        result = await self.pipeline_service.run_deduplication_pipeline(
            trace_id=str(article.id),
            feed_id=article.source
        )
        
        return result.get('duplicates', [])
    
    async def cluster_similar_articles(
        self, 
        articles: list[ArticleMetadata], 
        threshold: float = None
    ) -> list[ClusterResult]:
        """Cluster similar articles together"""
        threshold = threshold or self.default_threshold
        
        # Simple clustering based on title similarity
        clusters = []
        used_indices = set()
        
        for i, article in enumerate(articles):
            if i in used_indices:
                continue
                
            cluster_articles = [article]
            used_indices.add(i)
            
            for j, other_article in enumerate(articles):
                if j in used_indices:
                    continue
                    
                similarity = self.calculate_similarity(
                    article.title, 
                    other_article.title
                )
                
                if similarity >= threshold:
                    cluster_articles.append(other_article)
                    used_indices.add(j)
            
            if len(cluster_articles) > 1:
                cluster_id = hashlib.md5(
                    '|'.join(a.title for a in cluster_articles).encode()
                ).hexdigest()[:12]
                
                clusters.append(ClusterResult(
                    cluster_id=cluster_id,
                    articles=[{'id': a.id, 'title': a.title, 'url': a.url} for a in cluster_articles],
                    representative_article_id=cluster_articles[0].id,
                    similarity_score=threshold
                ))
        
        return clusters


def get_deduplication_service(db_config: dict):
    """
    Factory function to create and return a deduplication service instance.
    
    Args:
        db_config: Database configuration dictionary
        
    Returns:
        AdvancedDeduplicationService instance
    """
    return AdvancedDeduplicationService(db_config)