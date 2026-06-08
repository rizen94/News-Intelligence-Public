"""
Deduplication Module
Provides deduplication services and utilities
"""

from .advanced_deduplication_service import (
    AdvancedDeduplicationService,
    ArticleMetadata,
    ClusterResult,
)


class DeduplicationManager:
    """
    Deduplication Manager for RSS collector
    Provides a simple interface for deduplication operations
    """
    
    def __init__(self, db_config: dict):
        """Initialize the deduplication manager"""
        self.db_config = db_config
        self.service = AdvancedDeduplicationService(db_config)
    
    async def is_duplicate(self, title: str, url: str, source: str) -> bool:
        """Check if an article is a duplicate"""
        # Basic implementation - check URL hash
        import hashlib
        url_hash = hashlib.md5(url.encode()).hexdigest()
        
        # In a real implementation, this would check against the database
        # For now, return False to allow new articles
        return False
    
    async def get_similarity_score(self, title1: str, title2: str) -> float:
        """Get similarity score between two titles"""
        return self.service.calculate_similarity(title1, title2)