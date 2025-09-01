"""
Content Deduplication Service for News Intelligence System
Removes duplicate articles and content using ML-based similarity detection
"""

import logging
import hashlib
import json
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta
import psycopg2
from difflib import SequenceMatcher
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DuplicateGroup:
    """Represents a group of duplicate articles"""
    primary_id: int
    primary_title: str
    primary_source: str
    primary_date: datetime
    duplicates: List[Dict]
    similarity_score: float
    group_size: int
    created_at: datetime

class ContentDeduplicationService:
    """
    Service for detecting and removing duplicate content
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize the deduplication service
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.similarity_threshold = 0.85  # Configurable threshold
        self.title_similarity_threshold = 0.80
        self.content_similarity_threshold = 0.75
        
    def detect_duplicates(self, 
                         similarity_threshold: Optional[float] = None,
                         max_articles: int = 1000) -> Dict[str, any]:
        """
        Detect duplicate articles in the system
        
        Args:
            similarity_threshold: Override default similarity threshold
            max_articles: Maximum number of articles to process
            
        Returns:
            Dictionary containing duplicate groups and statistics
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get recent articles for analysis
            cutoff_date = datetime.now() - timedelta(days=30)
            cursor.execute("""
                SELECT id, title, content, summary, source, published_date, 
                       url, created_at, ml_data
                FROM articles 
                WHERE created_at >= %s 
                AND content IS NOT NULL 
                AND LENGTH(content) > 100
                ORDER BY created_at DESC
                LIMIT %s
            """, (cutoff_date, max_articles))
            
            articles = cursor.fetchall()
            conn.close()
            
            if len(articles) < 2:
                return {
                    "duplicate_groups": [],
                    "total_articles": len(articles),
                    "duplicate_count": 0,
                    "unique_count": len(articles),
                    "deduplication_rate": 0.0,
                    "message": "Insufficient articles for deduplication analysis"
                }
            
            # Detect duplicates using multiple strategies
            duplicate_groups = self._find_duplicate_groups(articles, similarity_threshold)
            
            # Calculate statistics
            total_articles = len(articles)
            duplicate_count = sum(group.group_size - 1 for group in duplicate_groups)
            unique_count = total_articles - duplicate_count
            deduplication_rate = (duplicate_count / total_articles) * 100 if total_articles > 0 else 0
            
            return {
                "duplicate_groups": [self._serialize_group(group) for group in duplicate_groups],
                "total_articles": total_articles,
                "duplicate_count": duplicate_count,
                "unique_count": unique_count,
                "deduplication_rate": round(deduplication_rate, 2),
                "groups_found": len(duplicate_groups),
                "message": f"Found {len(duplicate_groups)} duplicate groups"
            }
            
        except Exception as e:
            logger.error(f"Error detecting duplicates: {e}")
            return {"error": str(e)}
    
    def remove_duplicates(self, 
                         auto_remove: bool = False,
                         similarity_threshold: Optional[float] = None) -> Dict[str, any]:
        """
        Remove duplicate articles from the system
        
        Args:
            auto_remove: Whether to automatically remove duplicates
            similarity_threshold: Override default similarity threshold
            
        Returns:
            Dictionary containing removal results
        """
        try:
            # First detect duplicates
            detection_result = self.detect_duplicates(similarity_threshold)
            
            if "error" in detection_result:
                return detection_result
            
            if not detection_result["duplicate_groups"]:
                return {
                    "message": "No duplicates found to remove",
                    "removed_count": 0,
                    "kept_count": detection_result["total_articles"]
                }
            
            if not auto_remove:
                return {
                    "message": "Duplicates detected but not removed (auto_remove=False)",
                    "duplicate_groups": detection_result["duplicate_groups"],
                    "removed_count": 0,
                    "kept_count": detection_result["total_articles"]
                }
            
            # Remove duplicates
            removed_count = self._remove_duplicate_articles(detection_result["duplicate_groups"])
            
            return {
                "message": f"Successfully removed {removed_count} duplicate articles",
                "removed_count": removed_count,
                "kept_count": detection_result["unique_count"],
                "duplicate_groups": detection_result["duplicate_groups"]
            }
            
        except Exception as e:
            logger.error(f"Error removing duplicates: {e}")
            return {"error": str(e)}
    
    def _find_duplicate_groups(self, articles: List, 
                              similarity_threshold: Optional[float] = None) -> List[DuplicateGroup]:
        """Find groups of duplicate articles"""
        try:
            threshold = similarity_threshold or self.similarity_threshold
            duplicate_groups = []
            processed_articles = set()
            
            for i, article in enumerate(articles):
                if i in processed_articles:
                    continue
                
                current_group = [article]
                processed_articles.add(i)
                
                # Compare with other articles
                for j, other_article in enumerate(articles[i+1:], i+1):
                    if j in processed_articles:
                        continue
                    
                    similarity = self._calculate_article_similarity(article, other_article)
                    
                    if similarity >= threshold:
                        current_group.append(other_article)
                        processed_articles.add(j)
                
                # If we found duplicates, create a group
                if len(current_group) > 1:
                    # Sort by quality (use ML data if available) and date
                    current_group.sort(key=lambda x: (
                        self._get_article_quality(x),
                        x[5] or datetime.min  # published_date
                    ), reverse=True)
                    
                    primary = current_group[0]
                    duplicates = current_group[1:]
                    
                    # Calculate average similarity for the group
                    avg_similarity = sum(
                        self._calculate_article_similarity(primary, dup) 
                        for dup in duplicates
                    ) / len(duplicates)
                    
                    group = DuplicateGroup(
                        primary_id=primary[0],
                        primary_title=primary[1],
                        primary_source=primary[4],
                        primary_date=primary[5] or datetime.now(),
                        duplicates=[{
                            'id': dup[0],
                            'title': dup[1],
                            'source': dup[4],
                            'published_date': dup[5],
                            'url': dup[6],
                            'similarity_score': self._calculate_article_similarity(primary, dup)
                        } for dup in duplicates],
                        similarity_score=avg_similarity,
                        group_size=len(current_group),
                        created_at=datetime.now()
                    )
                    
                    duplicate_groups.append(group)
            
            return duplicate_groups
            
        except Exception as e:
            logger.error(f"Error finding duplicate groups: {e}")
            return []
    
    def _calculate_article_similarity(self, article1: Tuple, article2: Tuple) -> float:
        """Calculate similarity between two articles"""
        try:
            # Extract article components
            title1, content1, summary1 = article1[1], article1[2], article1[3]
            title2, content2, summary2 = article2[1], article2[2], article2[3]
            
            # Calculate title similarity
            title_sim = self._calculate_text_similarity(title1 or "", title2 or "")
            
            # Calculate content similarity
            content_sim = self._calculate_text_similarity(content1 or "", content2 or "")
            
            # Calculate summary similarity
            summary_sim = self._calculate_text_similarity(summary1 or "", summary2 or "")
            
            # Weighted similarity score
            # Title is most important, then content, then summary
            weighted_sim = (title_sim * 0.4) + (content_sim * 0.4) + (summary_sim * 0.2)
            
            return weighted_sim
            
        except Exception as e:
            logger.error(f"Error calculating article similarity: {e}")
            return 0.0
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings"""
        try:
            if not text1 or not text2:
                return 0.0
            
            # Normalize text
            text1 = self._normalize_text(text1)
            text2 = self._normalize_text(text2)
            
            # Use sequence matcher for similarity
            similarity = SequenceMatcher(None, text1, text2).ratio()
            
            # Additional checks for very similar content
            if similarity > 0.9:
                # Check for minor differences (punctuation, spacing)
                normalized1 = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', text1.lower()))
                normalized2 = re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', text2.lower()))
                
                if normalized1 == normalized2:
                    similarity = 1.0
            
            return similarity
            
        except Exception as e:
            logger.error(f"Error calculating text similarity: {e}")
            return 0.0
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        try:
            if not text:
                return ""
            
            # Convert to lowercase
            text = text.lower()
            
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Remove common punctuation that doesn't affect meaning
            text = re.sub(r'[^\w\s]', '', text)
            
            # Trim whitespace
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.error(f"Error normalizing text: {e}")
            return text or ""
    
    def _get_article_quality(self, article: Tuple) -> float:
        """Get article quality score from ML data"""
        try:
            ml_data = article[8]  # ml_data column
            if ml_data and isinstance(ml_data, dict):
                return ml_data.get('quality_score', 0.5)
            return 0.5  # Default quality score
        except Exception as e:
            logger.error(f"Error getting article quality: {e}")
            return 0.5
    
    def _remove_duplicate_articles(self, duplicate_groups: List[Dict]) -> int:
        """Remove duplicate articles from the database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            removed_count = 0
            
            for group in duplicate_groups:
                duplicate_ids = [dup['id'] for dup in group['duplicates']]
                
                if duplicate_ids:
                    # Mark duplicates as removed (soft delete)
                    cursor.execute("""
                        UPDATE articles 
                        SET status = 'duplicate_removed', 
                            updated_at = %s,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                        WHERE id = ANY(%s)
                    """, (
                        datetime.now(),
                        json.dumps({
                            'removal_reason': 'duplicate_detection',
                            'removed_at': datetime.now().isoformat(),
                            'primary_article_id': group['primary_id'],
                            'similarity_score': group['similarity_score']
                        }),
                        duplicate_ids
                    ))
                    
                    removed_count += len(duplicate_ids)
            
            conn.commit()
            conn.close()
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Error removing duplicate articles: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return 0
    
    def _serialize_group(self, group: DuplicateGroup) -> Dict:
        """Serialize duplicate group for JSON response"""
        return {
            'primary_id': group.primary_id,
            'primary_title': group.primary_title,
            'primary_source': group.primary_source,
            'primary_date': group.primary_date.isoformat() if group.primary_date else None,
            'duplicates': group.duplicates,
            'similarity_score': round(group.similarity_score, 3),
            'group_size': group.group_size,
            'created_at': group.created_at.isoformat()
        }
    
    def get_deduplication_stats(self) -> Dict[str, any]:
        """Get deduplication statistics"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get total article count
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            # Get duplicate count
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE status = 'duplicate_removed'
            """)
            duplicate_count = cursor.fetchone()[0]
            
            # Get recent duplicates
            cursor.execute("""
                SELECT COUNT(*) FROM articles 
                WHERE status = 'duplicate_removed' 
                AND updated_at >= %s
            """, (datetime.now() - timedelta(days=7),))
            recent_duplicates = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_articles': total_articles,
                'duplicate_count': duplicate_count,
                'recent_duplicates': recent_duplicates,
                'deduplication_rate': round((duplicate_count / total_articles) * 100, 2) if total_articles > 0 else 0,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting deduplication stats: {e}")
            return {"error": str(e)}
