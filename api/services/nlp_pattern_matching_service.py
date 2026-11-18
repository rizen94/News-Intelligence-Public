"""
NLP Pattern Matching Service

Enhanced pattern matching framework that moves from simple keyword matching to 
contextual significance scoring using NLP capabilities.
"""

import logging
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from api.shared.database import get_db_connection

logger = logging.getLogger(__name__)

class NLPPatternMatchingService:
    """
    Enhanced pattern matching service with NLP capabilities for better 
    contextual significance scoring.
    """
    
    def __init__(self):
        """Initialize the NLP pattern matching service."""
        try:
            # Load sentence transformer model for semantic similarity
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("NLP pattern matching service initialized with sentence transformer")
        except Exception as e:
            logger.error(f"Failed to initialize NLP model: {e}")
            self.model = None
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts using sentence transformers.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        if not self.model or not text1 or not text2:
            return 0.0
            
        try:
            # Get embeddings for both texts
            embeddings = self.model.encode([text1, text2])
            # Calculate cosine similarity
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return float(similarity)
        except Exception as e:
            logger.debug(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def _find_best_matching_pattern(self, text: str, keywords: List[str]) -> Tuple[str, float]:
        """
        Find the best matching pattern using semantic similarity.
        
        Args:
            text: Text to match against
            keywords: List of keywords to check
            
        Returns:
            Tuple of (best_keyword, similarity_score)
        """
        if not self.model or not text or not keywords:
            return "", 0.0
            
        try:
            # Get embedding for the text we're matching
            text_embedding = self.model.encode([text])[0]
            
            best_similarity = 0.0
            best_keyword = ""
            
            # Compare against each keyword
            for keyword in keywords:
                keyword_embedding = self.model.encode([keyword])[0]
                similarity = cosine_similarity([text_embedding], [keyword_embedding])[0][0]
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_keyword = keyword
                    
            return best_keyword, best_similarity
        except Exception as e:
            logger.debug(f"Pattern matching failed: {e}")
            return "", 0.0
    
    def match_content_with_contextual_scoring(self, text: str, story_type: str) -> List[Tuple[str, str, float]]:
        """
        Enhanced pattern matching with contextual scoring using NLP.
        
        Args:
            text: Text to match against
            story_type: Type of story category
            
        Returns:
            List of (pattern_type, matched_text, significance_score)
        """
        from api.services.watch_pattern_service import PATTERN_KEYWORDS_BY_STORY_TYPE, DEFAULT_STORY_TYPE
        
        keywords = (
            PATTERN_KEYWORDS_BY_STORY_TYPE.get(story_type)
            or PATTERN_KEYWORDS_BY_STORY_TYPE.get(DEFAULT_STORY_TYPE)
            or []
        )
        
        if not keywords:
            return []
            
        # Use NLP to find best matching pattern
        best_keyword, similarity = self._find_best_matching_pattern(text, keywords)
        
        if similarity > 0.0:
            # Convert semantic similarity to significance score (0.5 minimum for keyword matches)
            # Add a boost factor to make NLP matches more significant
            significance_score = min(1.0, 0.5 + (similarity * 0.5))
            return [("semantic_keyword", best_keyword, significance_score)]
        
        return []
    
    def get_contextual_source_scores(self, text: str, source_ids: List[str]) -> Dict[str, float]:
        """
        Calculate contextual scores for different sources based on semantic similarity.
        
        Args:
            text: Text to match against sources
            source_ids: List of source IDs to score
            
        Returns:
            Dictionary mapping source_id to similarity score
        """
        if not self.model or not text or not source_ids:
            return {}
            
        try:
            # Get embedding for the text we're matching
            text_embedding = self.model.encode([text])[0]
            scores = {}
            
            # For each source, we'd typically fetch its content and calculate similarity
            # Since we don't have source content here, we'll simulate this with a basic approach
            for source_id in source_ids:
                # In a real implementation, this would query the actual source content
                # For now, we'll use a simple heuristic based on source ID patterns
                scores[source_id] = 0.1  # Placeholder - would be calculated from actual content
            
            return scores
        except Exception as e:
            logger.debug(f"Source scoring failed: {e}")
            return {}

# Create global instance
nlp_pattern_matching_service = NLPPatternMatchingService()