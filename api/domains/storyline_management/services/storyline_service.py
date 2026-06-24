"""
Storyline Service
Handles creation, retrieval, and management of storylines
"""

import logging
import re
from datetime import datetime
from typing import Any, List, Optional, Tuple
from collections import defaultdict

import psycopg2
from psycopg2.extras import Json

from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema
from shared.services.domain_aware_service import validate_domain
from shared.storyline_article_counts import sync_counts_update_sql

from ..models.storyline_models import Storyline, StorylineArticle
from ..schemas.storyline_schemas import StorylineCreateRequest, StorylineUpdateRequest

logger = logging.getLogger(__name__)

class StorylineService:
    """Service for managing storylines and their articles"""
    
    def __init__(self, domain: str):
        self.domain = domain
        self.schema = resolve_domain_schema(domain)
        self.db_config = None
        
    def get_db_connection(self):
        """Get database connection"""
        return get_db_connection()
    
    async def create_storyline_from_articles(
        self, title: str, description: str | None = None, article_ids: list[int] | None = None
    ) -> dict[str, Any]:
        """
        Create a new storyline, optionally from article collection.
        If a storyline with a similar title already exists, merge articles into it.

        Args:
            title: Storyline title
            description: Optional description
            article_ids: Optional list of article IDs to include

        Returns:
            Dictionary with created storyline data
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # First check if storyline with similar title already exists using more sophisticated matching
                    # This uses the existing consolidation service approach for better similarity detection
                    cur.execute(
                        f"""
                        SELECT id, title, updated_at, article_count FROM {self.schema}.storylines
                        WHERE LOWER(title) LIKE LOWER(%s)
                        AND status != 'archived'
                        ORDER BY updated_at DESC
                        LIMIT 5
                    """,
                        (f"%{title}%",),
                    )
                    
                    existing_storylines = cur.fetchall()
                    merge_storyline = None
                    max_similarity = 0
                    
                    # Find the most similar existing storyline using title similarity
                    if existing_storylines:
                        for storyline in existing_storylines:
                            storyline_id, existing_title, updated_at, article_count = storyline
                            similarity = self._calculate_title_similarity(title, existing_title)
                            
                            if similarity > max_similarity:
                                max_similarity = similarity
                                merge_storyline = storyline
                    
                    # If we found a sufficiently similar storyline (threshold can be adjusted)
                    if merge_storyline and max_similarity > 0.3:  # 30% similarity threshold
                        # Merge into existing storyline
                        storyline_id = merge_storyline[0]
                        logger.info(f"Merging into existing storyline: {storyline_id} (similarity: {max_similarity:.2f})")
                        
                        # Add articles to existing storyline
                        if article_ids:
                            article_count = await self._add_articles_to_storyline(
                                conn, storyline_id, article_ids
                            )
                            
                            # Update article count and last updated
                            cur.execute(
                                f"""
                                UPDATE {self.schema}.storylines
                                SET {sync_counts_update_sql(self.schema)},
                                updated_at = %s
                                WHERE id = %s
                            """,
                                (storyline_id, storyline_id, datetime.now(), storyline_id),
                            )
                            
                        # Update storyline details if needed
                        if description:
                            cur.execute(
                                f"""
                                UPDATE {self.schema}.storylines
                                SET description = COALESCE(%s, description)
                                WHERE id = %s
                            """,
                                (description, storyline_id),
                            )
                            
                        conn.commit()
                        
                        return {
                            "success": True,
                            "data": {
                                "id": storyline_id,
                                "action": "merged",
                                "existing": True,
                                "similarity": max_similarity
                            }
                        }
                    else:
                        # Create new storyline
                        logger.info(f"Creating new storyline: {title}")
                        
                        cur.execute(
                            f"""
                            INSERT INTO {self.schema}.storylines
                            (title, description, created_at, updated_at, article_count, status)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """,
                            (title, description, datetime.now(), datetime.now(), 0, "active"),
                        )
                        
                        storyline_id = cur.fetchone()[0]
                        
                        # Add articles if provided
                        if article_ids:
                            article_count = await self._add_articles_to_storyline(
                                conn, storyline_id, article_ids
                            )
                            
                            # Update article count
                            cur.execute(
                                f"""
                                UPDATE {self.schema}.storylines
                                SET {sync_counts_update_sql(self.schema)},
                                updated_at = %s
                                WHERE id = %s
                            """,
                                (storyline_id, storyline_id, datetime.now(), storyline_id),
                            )
                        
                        conn.commit()
                        
                        return {
                            "success": True,
                            "data": {
                                "id": storyline_id,
                                "action": "created",
                                "existing": False
                            }
                        }
                        
            except Exception as e:
                logger.error(f"Error creating storyline: {e}")
                conn.rollback()
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e
    
    async def _add_articles_to_storyline(self, conn, storyline_id: int, article_ids: list[int]) -> int:
        """Add articles to a storyline and return the count of new articles added"""
        try:
            with conn.cursor() as cur:
                # Get current article count for reference
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {self.schema}.storyline_articles
                    WHERE storyline_id = %s
                """,
                    (storyline_id,),
                )
                existing_count = cur.fetchone()[0]
                
                # Add new articles
                new_articles_added = 0
                for article_id in article_ids:
                    try:
                        cur.execute(
                            f"""
                            INSERT INTO {self.schema}.storyline_articles
                            (storyline_id, article_id, added_at, relevance_score)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (storyline_id, article_id) DO NOTHING
                        """,
                            (storyline_id, article_id, datetime.now(), 0.7),
                        )
                        
                        if cur.rowcount > 0:
                            new_articles_added += 1
                            
                    except Exception as e:
                        logger.warning(f"Failed to add article {article_id} to storyline {storyline_id}: {e}")
                        continue
                
                return new_articles_added
                
        except Exception as e:
            logger.error(f"Error adding articles to storyline: {e}")
            raise e
    
    async def create_storyline_from_article(
        self, 
        article_id: int, 
        title: str, 
        description: str | None = None
    ) -> dict[str, Any]:
        """
        Create a storyline from a single article, checking for existing similar storylines
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # First check if this article is already in a storyline
                    cur.execute(
                        f"""
                        SELECT sa.storyline_id, s.title FROM {self.schema}.storyline_articles sa
                        JOIN {self.schema}.storylines s ON s.id = sa.storyline_id
                        WHERE sa.article_id = %s
                        AND s.status != 'archived'
                        LIMIT 1
                    """,
                        (article_id,),
                    )
                    
                    existing_storyline = cur.fetchone()
                    if existing_storyline:
                        # Article already belongs to a storyline
                        storyline_id = existing_storyline[0]
                        logger.info(f"Article {article_id} already in storyline {storyline_id}")
                        return {
                            "success": True,
                            "data": {
                                "id": storyline_id,
                                "action": "existing",
                                "existing": True
                            }
                        }
                    
                    # Check for similar storylines by title
                    cur.execute(
                        f"""
                        SELECT id, title FROM {self.schema}.storylines
                        WHERE LOWER(title) LIKE LOWER(%s)
                        AND status != 'archived'
                        ORDER BY updated_at DESC
                        LIMIT 5
                    """,
                        (f"%{title}%",),
                    )
                    
                    similar_storylines = cur.fetchall()
                    merge_storyline = None
                    
                    # Find the most similar existing storyline
                    if similar_storylines:
                        # Simple similarity check - check if new title contains existing title or vice versa
                        for storyline_id, storyline_title in similar_storylines:
                            if (title.lower() in storyline_title.lower() or 
                                storyline_title.lower() in title.lower()):
                                merge_storyline = (storyline_id, storyline_title)
                                break
                    
                    if merge_storyline:
                        # Merge into existing storyline
                        storyline_id = merge_storyline[0]
                        logger.info(f"Merging article {article_id} into existing storyline {storyline_id}")
                        
                        # Add article to existing storyline
                        cur.execute(
                            f"""
                            INSERT INTO {self.schema}.storyline_articles
                            (storyline_id, article_id, added_at, relevance_score)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (storyline_id, article_id) DO NOTHING
                        """,
                            (storyline_id, article_id, datetime.now(), 0.7),
                        )
                        
                        # Update article count
                        cur.execute(
                            f"""
                            UPDATE {self.schema}.storylines
                            SET {sync_counts_update_sql(self.schema)},
                            updated_at = %s
                            WHERE id = %s
                        """,
                            (storyline_id, storyline_id, datetime.now(), storyline_id),
                        )
                        
                        conn.commit()
                        
                        return {
                            "success": True,
                            "data": {
                                "id": storyline_id,
                                "action": "merged",
                                "existing": True
                            }
                        }
                    else:
                        # Create new storyline
                        logger.info(f"Creating new storyline from article {article_id}: {title}")
                        
                        cur.execute(
                            f"""
                            INSERT INTO {self.schema}.storylines
                            (title, description, created_at, updated_at, article_count, status)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """,
                            (title, description, datetime.now(), datetime.now(), 1, "active"),
                        )
                        
                        storyline_id = cur.fetchone()[0]
                        
                        # Add article to new storyline
                        cur.execute(
                            f"""
                            INSERT INTO {self.schema}.storyline_articles
                            (storyline_id, article_id, added_at, relevance_score)
                            VALUES (%s, %s, %s, %s)
                        """,
                            (storyline_id, article_id, datetime.now(), 0.7),
                        )
                        
                        conn.commit()
                        
                        return {
                            "success": True,
                            "data": {
                                "id": storyline_id,
                                "action": "created",
                                "existing": False
                            }
                        }
                        
            except Exception as e:
                logger.error(f"Error creating storyline from article: {e}")
                conn.rollback()
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e
    
    async def get_storyline(self, storyline_id: int) -> dict[str, Any]:
        """Get a storyline by ID"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id, title, description, status, article_count,
                               quality_score, analysis_summary, created_at, updated_at,
                               last_evolution_at, evolution_count, background_information
                        FROM {self.schema}.storylines
                        WHERE id = %s
                    """,
                        (storyline_id,),
                    )
                    
                    row = cur.fetchone()
                    if row:
                        return {
                            "success": True,
                            "data": {
                                "id": row[0],
                                "title": row[1],
                                "description": row[2],
                                "status": row[3],
                                "article_count": row[4] or 0,
                                "quality_score": row[5],
                                "analysis_summary": row[6],
                                "created_at": row[7],
                                "updated_at": row[8],
                                "last_evolution_at": row[9],
                                "evolution_count": row[10],
                                "background_information": row[11]
                            }
                        }
                    else:
                        return {"success": False, "error": "Storyline not found"}
                        
            except Exception as e:
                logger.error(f"Error getting storyline: {e}")
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e
    
    async def update_storyline(self, storyline_id: int, request: StorylineUpdateRequest) -> dict[str, Any]:
        """Update a storyline"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    updates = []
                    params = []
                    
                    if request.title is not None:
                        updates.append("title = %s")
                        params.append(request.title)
                    
                    if request.description is not None:
                        updates.append("description = %s")
                        params.append(request.description)
                    
                    if request.status is not None:
                        updates.append("status = %s")
                        params.append(request.status)
                    
                    if updates:
                        updates.append("updated_at = %s")
                        params.append(datetime.now())
                        params.append(storyline_id)
                        
                        cur.execute(
                            f"""
                            UPDATE {self.schema}.storylines
                            SET {", ".join(updates)}
                            WHERE id = %s
                        """,
                            params,
                        )
                        
                        conn.commit()
                        
                        return {"success": True, "message": "Storyline updated"}
                    else:
                        return {"success": False, "error": "No updates provided"}
                        
            except Exception as e:
                logger.error(f"Error updating storyline: {e}")
                conn.rollback()
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e
    
    async def delete_storyline(self, storyline_id: int) -> dict[str, Any]:
        """Delete a storyline"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Delete storyline articles
                    cur.execute(
                        f"""
                        DELETE FROM {self.schema}.storyline_articles
                        WHERE storyline_id = %s
                    """,
                        (storyline_id,),
                    )
                    
                    # Delete storyline
                    cur.execute(
                        f"""
                        DELETE FROM {self.schema}.storylines
                        WHERE id = %s
                    """,
                        (storyline_id,),
                    )
                    
                    if cur.rowcount > 0:
                        conn.commit()
                        return {"success": True, "message": "Storyline deleted"}
                    else:
                        return {"success": False, "error": "Storyline not found"}
                        
            except Exception as e:
                logger.error(f"Error deleting storyline: {e}")
                conn.rollback()
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e
    
    async def get_storylines(self, page: int = 1, page_size: int = 20, status: str | None = None) -> dict[str, Any]:
        """Get paginated list of storylines"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Build query with optional status filter
                    where_clause = ""
                    params = []
                    
                    if status:
                        where_clause = "WHERE s.status = %s"
                        params.append(status)
                    
                    # Get total count
                    count_query = f"SELECT COUNT(*) FROM {self.schema}.storylines s {where_clause}"
                    cur.execute(count_query, params)
                    total = cur.fetchone()[0]
                    
                    # Calculate pagination
                    offset = (page - 1) * page_size
                    pages = (total + page_size - 1) // page_size if total > 0 else 0
                    
                    # Get paginated results
                    query = f"""
                        SELECT s.id, s.title, s.description, s.created_at, s.updated_at,
                               s.status,
                               (SELECT COUNT(*)::int FROM {self.schema}.storyline_articles sa0
                                WHERE sa0.storyline_id = s.id) AS article_count,
                               s.quality_score,
                               (SELECT MAX(sa.added_at) FROM {self.schema}.storyline_articles sa
                                WHERE sa.storyline_id = s.id) AS last_article_added_at
                        FROM {self.schema}.storylines s
                        {where_clause}
                        ORDER BY (SELECT MAX(sa2.added_at) FROM {self.schema}.storyline_articles sa2 WHERE sa2.storyline_id = s.id) DESC NULLS LAST,
                                 s.updated_at DESC NULLS LAST
                        LIMIT %s OFFSET %s
                    """
                    cur.execute(query, params + [page_size, offset])
                    rows = cur.fetchall()
                    
                    storylines = []
                    for row in rows:
                        laa = row[8] if len(row) > 8 else None
                        storylines.append({
                            "id": row[0],
                            "title": row[1],
                            "description": row[2],
                            "article_count": row[6] or 0,
                            "quality_score": row[7],
                            "status": row[5],
                            "created_at": row[3],
                            "updated_at": row[4],
                            "last_article_added_at": laa
                        })
                    
                    return {
                        "success": True,
                        "data": storylines,
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total": total,
                            "pages": pages,
                            "has_next": page < pages,
                            "has_prev": page > 1
                        }
                    }
                    
            except Exception as e:
                logger.error(f"Error getting storylines: {e}")
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e
    
    async def get_storyline_articles(self, storyline_id: int, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        """Get articles in a storyline"""
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # Get total count
                    count_query = f"""
                        SELECT COUNT(*) FROM {self.schema}.storyline_articles sa
                        JOIN {self.schema}.articles a ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                    """
                    cur.execute(count_query, (storyline_id,))
                    total = cur.fetchone()[0]
                    
                    # Calculate pagination
                    offset = (page - 1) * page_size
                    pages = (total + page_size - 1) // page_size if total > 0 else 0
                    
                    # Get paginated articles
                    query = f"""
                        SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
                        FROM {self.schema}.articles a
                        JOIN {self.schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY a.published_at DESC
                        LIMIT %s OFFSET %s
                    """
                    cur.execute(query, (storyline_id, page_size, offset))
                    rows = cur.fetchall()
                    
                    articles = []
                    for row in rows:
                        articles.append({
                            "id": row[0],
                            "title": row[1],
                            "url": row[2],
                            "source_domain": row[3],
                            "published_at": row[4],
                            "summary": row[5]
                        })
                    
                    return {
                        "success": True,
                        "data": articles,
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total": total,
                            "pages": pages,
                            "has_next": page < pages,
                            "has_prev": page > 1
                        }
                    }
                    
            except Exception as e:
                logger.error(f"Error getting storyline articles: {e}")
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e

    async def generate_storyline_summary(self, storyline_id: int) -> dict[str, Any]:
        """
        Generate and persist analysis_summary for a storyline (used by automation + content_analysis).
        Delegates to RAGAnalysisService.perform_comprehensive_analysis.
        """
        try:
            from .rag_analysis_service import RAGAnalysisService

            svc = RAGAnalysisService(domain=self.domain)
            result = await svc.perform_comprehensive_analysis(storyline_id)
            if not result.get("success"):
                return result
            analysis = (result.get("data") or {}).get("analysis", "")
            return {
                "success": True,
                "data": {"summary": analysis, **(result.get("data") or {})},
            }
        except Exception as e:
            logger.warning(
                "generate_storyline_summary failed domain=%s storyline=%s: %s",
                self.domain,
                storyline_id,
                e,
            )
            return {"success": False, "error": str(e)}
    
    async def search_similar_storylines(self, title: str, threshold: float = 0.7) -> dict[str, Any]:
        """
        Search for storylines similar to the given title using text similarity
        
        Args:
            title: Title to search for
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            Dictionary with similar storylines
        """
        try:
            conn = self.get_db_connection()
            try:
                with conn.cursor() as cur:
                    # This is a simplified implementation - in production, you'd want to use
                    # more sophisticated similarity metrics like cosine similarity or semantic embeddings
                    cur.execute(
                        f"""
                        SELECT id, title, description, article_count, updated_at
                        FROM {self.schema}.storylines
                        WHERE LOWER(title) LIKE LOWER(%s)
                        AND status != 'archived'
                        ORDER BY updated_at DESC
                        LIMIT 10
                    """,
                        (f"%{title}%",),
                    )
                    
                    rows = cur.fetchall()
                    similar_storylines = []
                    
                    for row in rows:
                        # Simple similarity calculation (you could enhance this with NLP)
                        existing_title = row[1]
                        similarity = self._calculate_title_similarity(title, existing_title)
                        
                        if similarity >= threshold:
                            similar_storylines.append({
                                "id": row[0],
                                "title": row[1],
                                "description": row[2],
                                "article_count": row[3] or 0,
                                "updated_at": row[4],
                                "similarity": similarity
                            })
                    
                    return {
                        "success": True,
                        "data": similar_storylines,
                        "count": len(similar_storylines)
                    }
                    
            except Exception as e:
                logger.error(f"Error searching similar storylines: {e}")
                raise e
                
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise e
    
    def _calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles (simplified implementation)
        """
        # Convert to lowercase and remove special characters for comparison
        title1_clean = re.sub(r'[^a-zA-Z0-9\s]', '', title1.lower())
        title2_clean = re.sub(r'[^a-zA-Z0-9\s]', '', title2.lower())
        
        # Simple word overlap calculation
        words1 = set(title1_clean.split())
        words2 = set(title2_clean.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0