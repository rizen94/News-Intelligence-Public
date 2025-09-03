"""
Clusters API Routes for News Intelligence System v3.0
Provides article clustering, story management, and analytics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from api.config.database import get_db_connection

router = APIRouter()

# Enums
class ClusterType(str, Enum):
    """Cluster types"""
    STORY = "story"
    TOPIC = "topic"
    EVENT = "event"
    TREND = "trend"

# Pydantic models
class ClusterBase(BaseModel):
    """Base cluster model"""
    cluster_type: ClusterType = Field(..., description="Cluster type")
    topic: str = Field(..., description="Cluster topic")
    summary: Optional[str] = Field(None, description="Cluster summary")

class ClusterCreate(ClusterBase):
    """Cluster creation model"""
    main_article_id: int = Field(..., description="Main article ID")

class ClusterUpdate(BaseModel):
    """Cluster update model"""
    topic: Optional[str] = None
    summary: Optional[str] = None
    cluster_type: Optional[ClusterType] = None

class ArticleInfo(BaseModel):
    """Article information for clusters"""
    id: int = Field(..., description="Article ID")
    title: str = Field(..., description="Article title")
    source: str = Field(..., description="Article source")
    published_at: datetime = Field(..., description="Publication date")
    similarity_score: float = Field(..., description="Similarity score")

class Cluster(ClusterBase):
    """Complete cluster model"""
    id: int = Field(..., description="Cluster ID")
    main_article_id: int = Field(..., description="Main article ID")
    article_count: int = Field(1, description="Number of articles in cluster")
    cohesion_score: float = Field(0.0, description="Cluster cohesion score")
    created_date: datetime = Field(..., description="Creation date")
    updated_at: datetime = Field(..., description="Last update timestamp")
    articles: List[ArticleInfo] = Field(default_factory=list, description="Articles in cluster")

class ClusterList(BaseModel):
    """Cluster list response"""
    clusters: List[Cluster] = Field(..., description="List of clusters")
    total: int = Field(..., description="Total number of clusters")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")

class ClusterStats(BaseModel):
    """Cluster statistics model"""
    total_clusters: int = Field(..., description="Total clusters")
    clusters_by_type: Dict[str, int] = Field(..., description="Clusters by type")
    avg_articles_per_cluster: float = Field(..., description="Average articles per cluster")
    avg_cohesion_score: float = Field(..., description="Average cohesion score")
    largest_clusters: List[Dict[str, Any]] = Field(..., description="Largest clusters")
    recent_clusters: List[Dict[str, Any]] = Field(..., description="Recent clusters")

# API Endpoints

@router.get("/", response_model=ClusterList)
async def get_clusters(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    cluster_type: Optional[ClusterType] = Query(None, description="Filter by cluster type"),
    search: Optional[str] = Query(None, description="Search query"),
    min_articles: Optional[int] = Query(None, description="Minimum articles in cluster"),
    sort_by: str = Query("created_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order")
):
    """Get list of clusters with filtering and pagination"""
    try:
        offset = (page - 1) * per_page
        
        # Build query conditions
        where_conditions = []
        params = []
        
        if cluster_type:
            where_conditions.append("cluster_type = %s")
            params.append(cluster_type.value)
        
        if search:
            where_conditions.append("(topic ILIKE %s OR summary ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        if min_articles is not None:
            where_conditions.append("article_count >= %s")
            params.append(min_articles)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM article_clusters {where_clause}"
        conn = await get_db_connection()
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Get clusters
        order_clause = f"ORDER BY {sort_by} {sort_order.upper()}"
        clusters_query = f"""
            SELECT 
                c.id, c.main_article_id, c.cluster_type, c.topic, c.summary,
                c.article_count, c.cohesion_score, c.created_date, c.updated_at
            FROM article_clusters c
            {where_clause}
            {order_clause}
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cursor.execute(clusters_query, params)
        
        clusters = []
        for row in cursor.fetchall():
            # Get articles for this cluster
            cursor.execute("""
                SELECT 
                    a.id, a.title, a.source, a.published_at, ca.similarity_score
                FROM cluster_articles ca
                JOIN articles a ON ca.article_id = a.id
                WHERE ca.cluster_id = %s
                ORDER BY ca.similarity_score DESC
            """, (row[0],))
            
            articles = []
            for article_row in cursor.fetchall():
                article = ArticleInfo(
                    id=article_row[0],
                    title=article_row[1],
                    source=article_row[2],
                    published_at=article_row[3],
                    similarity_score=article_row[4]
                )
                articles.append(article)
            
            cluster = Cluster(
                id=row[0],
                main_article_id=row[1],
                cluster_type=row[2],
                topic=row[3],
                summary=row[4],
                article_count=row[5],
                cohesion_score=row[6],
                created_date=row[7],
                updated_at=row[8],
                articles=articles
            )
            clusters.append(cluster)
        
        cursor.close()
        conn.close()
        
        return ClusterList(
            clusters=clusters,
            total=total,
            page=page,
            per_page=per_page
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch clusters: {str(e)}"
        )

@router.get("/{cluster_id}", response_model=Cluster)
async def get_cluster(cluster_id: int = Path(..., description="Cluster ID")):
    """Get specific cluster by ID"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get cluster details
        cursor.execute("""
            SELECT 
                id, main_article_id, cluster_type, topic, summary,
                article_count, cohesion_score, created_date, updated_at
            FROM article_clusters 
            WHERE id = %s
        """, (cluster_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cluster not found")
        
        # Get articles for this cluster
        cursor.execute("""
            SELECT 
                a.id, a.title, a.source, a.published_at, ca.similarity_score
            FROM cluster_articles ca
            JOIN articles a ON ca.article_id = a.id
            WHERE ca.cluster_id = %s
            ORDER BY ca.similarity_score DESC
        """, (cluster_id,))
        
        articles = []
        for article_row in cursor.fetchall():
            article = ArticleInfo(
                id=article_row[0],
                title=article_row[1],
                source=article_row[2],
                published_at=article_row[3],
                similarity_score=article_row[4]
            )
            articles.append(article)
        
        cluster = Cluster(
            id=row[0],
            main_article_id=row[1],
            cluster_type=row[2],
            topic=row[3],
            summary=row[4],
            article_count=row[5],
            cohesion_score=row[6],
            created_date=row[7],
            updated_at=row[8],
            articles=articles
        )
        
        cursor.close()
        conn.close()
        
        return cluster
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch cluster: {str(e)}"
        )

@router.post("/", response_model=Cluster)
async def create_cluster(cluster_data: ClusterCreate):
    """Create new cluster"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if main article exists
        cursor.execute("SELECT id FROM articles WHERE id = %s", (cluster_data.main_article_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail="Main article not found")
        
        # Insert new cluster
        cursor.execute("""
            INSERT INTO article_clusters (
                main_article_id, cluster_type, topic, summary, article_count,
                cohesion_score, created_date, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            cluster_data.main_article_id,
            cluster_data.cluster_type.value,
            cluster_data.topic,
            cluster_data.summary,
            1,  # Start with 1 article
            0.0,  # Initial cohesion score
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        cluster_id = cursor.fetchone()[0]
        
        # Add main article to cluster
        cursor.execute("""
            INSERT INTO cluster_articles (cluster_id, article_id, similarity_score)
            VALUES (%s, %s, %s)
        """, (cluster_id, cluster_data.main_article_id, 1.0))
        
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return created cluster
        return await get_cluster(cluster_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create cluster: {str(e)}"
        )

@router.put("/{cluster_id}", response_model=Cluster)
async def update_cluster(
    cluster_id: int = Path(..., description="Cluster ID"),
    cluster_data: ClusterUpdate = Body(..., description="Cluster update data")
):
    """Update cluster"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if cluster exists
        cursor.execute("SELECT id FROM article_clusters WHERE id = %s", (cluster_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Cluster not found")
        
        # Build update query dynamically
        update_fields = []
        params = []
        
        if cluster_data.topic is not None:
            update_fields.append("topic = %s")
            params.append(cluster_data.topic)
        
        if cluster_data.summary is not None:
            update_fields.append("summary = %s")
            params.append(cluster_data.summary)
        
        if cluster_data.cluster_type is not None:
            update_fields.append("cluster_type = %s")
            params.append(cluster_data.cluster_type.value)
        
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_fields.append("updated_at = %s")
        params.append(datetime.utcnow())
        params.append(cluster_id)
        
        update_query = f"""
            UPDATE article_clusters 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(update_query, params)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Return updated cluster
        return await get_cluster(cluster_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update cluster: {str(e)}"
        )

@router.delete("/{cluster_id}")
async def delete_cluster(cluster_id: int = Path(..., description="Cluster ID")):
    """Delete cluster"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if cluster exists
        cursor.execute("SELECT id FROM article_clusters WHERE id = %s", (cluster_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Cluster not found")
        
        # Delete cluster (cascade will handle cluster_articles)
        cursor.execute("DELETE FROM article_clusters WHERE id = %s", (cluster_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "Cluster deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete cluster: {str(e)}"
        )

@router.post("/{cluster_id}/articles/{article_id}")
async def add_article_to_cluster(
    cluster_id: int = Path(..., description="Cluster ID"),
    article_id: int = Path(..., description="Article ID"),
    similarity_score: float = Body(0.5, description="Similarity score")
):
    """Add article to cluster"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Check if cluster exists
        cursor.execute("SELECT id FROM article_clusters WHERE id = %s", (cluster_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Cluster not found")
        
        # Check if article exists
        cursor.execute("SELECT id FROM articles WHERE id = %s", (article_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Add article to cluster
        cursor.execute("""
            INSERT INTO cluster_articles (cluster_id, article_id, similarity_score)
            VALUES (%s, %s, %s)
            ON CONFLICT (cluster_id, article_id) DO UPDATE SET
                similarity_score = EXCLUDED.similarity_score
        """, (cluster_id, article_id, similarity_score))
        
        # Update cluster article count
        cursor.execute("""
            UPDATE article_clusters 
            SET article_count = (
                SELECT COUNT(*) FROM cluster_articles WHERE cluster_id = %s
            ), updated_at = %s
            WHERE id = %s
        """, (cluster_id, datetime.utcnow(), cluster_id))
        
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "Article added to cluster successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add article to cluster: {str(e)}"
        )

@router.delete("/{cluster_id}/articles/{article_id}")
async def remove_article_from_cluster(
    cluster_id: int = Path(..., description="Cluster ID"),
    article_id: int = Path(..., description="Article ID")
):
    """Remove article from cluster"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Remove article from cluster
        cursor.execute("""
            DELETE FROM cluster_articles 
            WHERE cluster_id = %s AND article_id = %s
        """, (cluster_id, article_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Article not found in cluster")
        
        # Update cluster article count
        cursor.execute("""
            UPDATE article_clusters 
            SET article_count = (
                SELECT COUNT(*) FROM cluster_articles WHERE cluster_id = %s
            ), updated_at = %s
            WHERE id = %s
        """, (cluster_id, datetime.utcnow(), cluster_id))
        
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {"message": "Article removed from cluster successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove article from cluster: {str(e)}"
        )

@router.get("/stats/overview", response_model=ClusterStats)
async def get_cluster_stats():
    """Get cluster statistics"""
    try:
        conn = await get_db_connection()
        cursor = conn.cursor()
        
        # Get total clusters
        cursor.execute("SELECT COUNT(*) FROM article_clusters")
        total_clusters = cursor.fetchone()[0]
        
        # Get clusters by type
        cursor.execute("""
            SELECT cluster_type, COUNT(*) 
            FROM article_clusters 
            GROUP BY cluster_type 
            ORDER BY COUNT(*) DESC
        """)
        clusters_by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get average articles per cluster
        cursor.execute("SELECT AVG(article_count) FROM article_clusters")
        avg_articles_per_cluster = float(cursor.fetchone()[0] or 0)
        
        # Get average cohesion score
        cursor.execute("SELECT AVG(cohesion_score) FROM article_clusters")
        avg_cohesion_score = float(cursor.fetchone()[0] or 0)
        
        # Get largest clusters
        cursor.execute("""
            SELECT id, topic, article_count, cohesion_score
            FROM article_clusters 
            ORDER BY article_count DESC 
            LIMIT 10
        """)
        largest_clusters = [
            {
                "id": row[0],
                "topic": row[1],
                "article_count": row[2],
                "cohesion_score": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        # Get recent clusters
        cursor.execute("""
            SELECT id, topic, cluster_type, created_date
            FROM article_clusters 
            ORDER BY created_date DESC 
            LIMIT 10
        """)
        recent_clusters = [
            {
                "id": row[0],
                "topic": row[1],
                "cluster_type": row[2],
                "created_date": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        conn.close()
        
        return ClusterStats(
            total_clusters=total_clusters,
            clusters_by_type=clusters_by_type,
            avg_articles_per_cluster=avg_articles_per_cluster,
            avg_cohesion_score=avg_cohesion_score,
            largest_clusters=largest_clusters,
            recent_clusters=recent_clusters
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch cluster statistics: {str(e)}"
        )
