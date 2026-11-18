"""
Integrated Pattern Matching and Source Tracking Service

This service provides an integrated pipeline that connects pattern matching with historic context source selection,
tracking which sources were used for each pattern match to provide better context and evidence.
"""

import logging
from typing import Any, List, Dict
from datetime import datetime

from api.shared.database import get_db_connection

logger = logging.getLogger(__name__)


class IntegratedPatternSourceService:
    """
    Service that integrates pattern matching with historic context source tracking.
    Provides pipeline functionality for connecting patterns to their source evidence.
    """
    
    def __init__(self):
        self.source_types = ["news_api", "wikipedia", "edgar", "fred"]
    
    def create_pattern_match_with_sources(
        self, 
        domain_key: str,
        storyline_id: int,
        content_ref_type: str,
        content_ref_id: int,
        matched_text: str,
        significance_score: float,
        source_ids_used: List[str],
        story_type: str = "person_tenure"
    ) -> bool:
        """
        Create a pattern match record with source tracking information.
        
        Args:
            domain_key: Domain key
            storyline_id: Storyline ID
            content_ref_type: Type of content referenced (context, fact, etc.)
            content_ref_id: ID of the content reference
            matched_text: Text that matched the pattern
            significance_score: Score of the match (0.0-1.0)
            source_ids_used: List of source IDs used for this match
            story_type: Type of story being analyzed
            
        Returns:
            True if record created successfully, False otherwise
        """
        conn = get_db_connection()
        if not conn:
            return False
            
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.pattern_matches (
                        domain_key, storyline_id, content_ref_type, content_ref_id,
                        matched_text, significance_score, source_ids_used, pattern_type
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        domain_key, storyline_id, content_ref_type, content_ref_id,
                        matched_text, significance_score, source_ids_used, story_type
                    ),
                )
                
                pattern_match_id = cur.fetchone()[0]
                conn.commit()
                
                logger.info("Created pattern match %s with sources %s", pattern_match_id, source_ids_used)
                return True
                
        except Exception as e:
            logger.debug("create pattern match with sources failed: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass


# Global service instance
integrated_pattern_source_service = IntegratedPatternSourceService()


def create_pattern_match_with_sources(
    domain_key: str,
    storyline_id: int,
    content_ref_type: str,
    content_ref_id: int,
    matched_text: str,
    significance_score: float,
    source_ids_used: List[str],
    story_type: str = "person_tenure"
) -> bool:
    """Create a pattern match record with source tracking information."""
    return integrated_pattern_source_service.create_pattern_match_with_sources(
        domain_key, storyline_id, content_ref_type, content_ref_id,
        matched_text, significance_score, source_ids_used, story_type
    )