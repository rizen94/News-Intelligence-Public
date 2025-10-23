"""
Deduplication API Routes
Provides endpoints for duplicate detection, clustering, and storyline suggestions
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from config.database import get_db, get_db_config
from schemas.robust_schemas import APIResponse
from services.deduplication_integration_service import DeduplicationIntegrationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deduplication", tags=["Deduplication"])

# Initialize deduplication service
def get_deduplication_service():
    """Get deduplication service instance"""
    db_config = get_database_config()
    return DeduplicationIntegrationService(db_config)

@router.get("/duplicates/{article_id}", response_model=APIResponse)
async def find_duplicates_for_article(
    article_id: int,
    db: Session = Depends(get_db)
):
    """Find all duplicates for a specific article"""
    try:
        dedup_service = get_deduplication_service()
        result = await dedup_service.find_duplicates_for_article(article_id)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=404, detail=result.get('message', 'Article not found'))
        
        return APIResponse(
            success=True,
            data=result,
            message=f"Duplicate analysis completed for article {article_id}"
        )
        
    except Exception as e:
        logger.error(f"Error finding duplicates for article {article_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cluster", response_model=APIResponse)
async def cluster_articles(
    article_ids: List[int],
    db: Session = Depends(get_db)
):
    """Cluster articles for storyline suggestions"""
    try:
        if len(article_ids) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 articles for clustering")
        
        dedup_service = get_deduplication_service()
        result = await dedup_service.batch_process_articles(article_ids)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result.get('error', 'Clustering failed'))
        
        return APIResponse(
            success=True,
            data=result,
            message=f"Clustering completed: {result.get('clusters_created', 0)} clusters created"
        )
        
    except Exception as e:
        logger.error(f"Error clustering articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storyline-suggestions", response_model=APIResponse)
async def get_storyline_suggestions(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get storyline suggestions from recent clusters"""
    try:
        dedup_service = get_deduplication_service()
        result = await dedup_service.get_storyline_suggestions(limit)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to get suggestions'))
        
        return APIResponse(
            success=True,
            data=result,
            message=f"Retrieved {result.get('total_suggestions', 0)} storyline suggestions"
        )
        
    except Exception as e:
        logger.error(f"Error getting storyline suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics", response_model=APIResponse)
async def get_deduplication_statistics(db: Session = Depends(get_db)):
    """Get deduplication statistics and performance metrics"""
    try:
        # Get duplicate statistics
        duplicate_stats = db.execute(text("""
            SELECT 
                duplicate_type,
                COUNT(*) as duplicate_count,
                AVG(similarity_score) as avg_similarity,
                MIN(similarity_score) as min_similarity,
                MAX(similarity_score) as max_similarity
            FROM duplicate_pairs
            WHERE status = 'active'
            GROUP BY duplicate_type
        """)).fetchall()
        
        # Get cluster statistics
        cluster_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_clusters,
                AVG(cluster_size) as avg_cluster_size,
                MAX(cluster_size) as max_cluster_size,
                COUNT(CASE WHEN storyline_suggestion IS NOT NULL THEN 1 END) as clusters_with_suggestions
            FROM cluster_metadata
        """)).fetchone()
        
        # Get processing statistics
        processing_stats = db.execute(text("""
            SELECT 
                operation_type,
                COUNT(*) as operation_count,
                AVG(processing_time_ms) as avg_processing_time,
                SUM(duplicates_found) as total_duplicates_found,
                SUM(clusters_created) as total_clusters_created
            FROM deduplication_log
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY operation_type
        """)).fetchall()
        
        # Get recent activity
        recent_activity = db.execute(text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as operations,
                SUM(articles_processed) as articles_processed,
                SUM(duplicates_found) as duplicates_found,
                SUM(clusters_created) as clusters_created
            FROM deduplication_log
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """)).fetchall()
        
        statistics = {
            'duplicate_statistics': [
                {
                    'duplicate_type': row[0],
                    'duplicate_count': row[1],
                    'avg_similarity': float(row[2]) if row[2] else 0.0,
                    'min_similarity': float(row[3]) if row[3] else 0.0,
                    'max_similarity': float(row[4]) if row[4] else 0.0
                }
                for row in duplicate_stats
            ],
            'cluster_statistics': {
                'total_clusters': cluster_stats[0] if cluster_stats else 0,
                'avg_cluster_size': float(cluster_stats[1]) if cluster_stats and cluster_stats[1] else 0.0,
                'max_cluster_size': cluster_stats[2] if cluster_stats else 0,
                'clusters_with_suggestions': cluster_stats[3] if cluster_stats else 0
            },
            'processing_statistics': [
                {
                    'operation_type': row[0],
                    'operation_count': row[1],
                    'avg_processing_time_ms': float(row[2]) if row[2] else 0.0,
                    'total_duplicates_found': row[3] if row[3] else 0,
                    'total_clusters_created': row[4] if row[4] else 0
                }
                for row in processing_stats
            ],
            'recent_activity': [
                {
                    'date': row[0].isoformat() if row[0] else None,
                    'operations': row[1],
                    'articles_processed': row[2] if row[2] else 0,
                    'duplicates_found': row[3] if row[3] else 0,
                    'clusters_created': row[4] if row[4] else 0
                }
                for row in recent_activity
            ]
        }
        
        return APIResponse(
            success=True,
            data=statistics,
            message="Deduplication statistics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting deduplication statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-recent-articles", response_model=APIResponse)
async def process_recent_articles_for_clustering(
    days_back: int = Query(3, ge=1, le=30),
    min_articles: int = Query(10, ge=2, le=1000),
    db: Session = Depends(get_db)
):
    """Process recent articles for clustering and storyline suggestions"""
    try:
        # Get recent articles
        recent_articles = db.execute(text("""
            SELECT id
            FROM articles
            WHERE created_at > NOW() - INTERVAL '%s days'
            AND LENGTH(content) > 100
            AND deduplication_status = 'processed'
            ORDER BY created_at DESC
            LIMIT %s
        """), (days_back, min_articles * 2)).fetchall()
        
        if len(recent_articles) < min_articles:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough recent articles found. Found {len(recent_articles)}, need at least {min_articles}"
            )
        
        article_ids = [row[0] for row in recent_articles[:min_articles]]
        
        # Process articles for clustering
        dedup_service = get_deduplication_service()
        result = await dedup_service.batch_process_articles(article_ids)
        
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result.get('error', 'Processing failed'))
        
        return APIResponse(
            success=True,
            data=result,
            message=f"Processed {result.get('articles_processed', 0)} articles, created {result.get('clusters_created', 0)} clusters"
        )
        
    except Exception as e:
        logger.error(f"Error processing recent articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clusters/{cluster_id}", response_model=APIResponse)
async def get_cluster_details(
    cluster_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific cluster"""
    try:
        # Get cluster metadata
        cluster_meta = db.execute(text("""
            SELECT 
                cluster_id, centroid_title, centroid_content, cluster_size,
                similarity_threshold, storyline_suggestion, created_at
            FROM cluster_metadata
            WHERE cluster_id = %s
        """), (cluster_id,)).fetchone()
        
        if not cluster_meta:
            raise HTTPException(status_code=404, detail="Cluster not found")
        
        # Get articles in cluster
        cluster_articles = db.execute(text("""
            SELECT 
                a.id, a.title, a.source, a.published_at, a.url,
                ac.similarity_score, ac.cluster_rank
            FROM article_clusters ac
            JOIN articles a ON ac.article_id = a.id
            WHERE ac.cluster_id = %s
            ORDER BY ac.cluster_rank, ac.similarity_score DESC
        """), (cluster_id,)).fetchall()
        
        cluster_data = {
            'cluster_id': cluster_meta[0],
            'centroid_title': cluster_meta[1],
            'centroid_content': cluster_meta[2],
            'cluster_size': cluster_meta[3],
            'similarity_threshold': float(cluster_meta[4]) if cluster_meta[4] else 0.0,
            'storyline_suggestion': cluster_meta[5],
            'created_at': cluster_meta[6].isoformat() if cluster_meta[6] else None,
            'articles': [
                {
                    'id': row[0],
                    'title': row[1],
                    'source': row[2],
                    'published_at': row[3].isoformat() if row[3] else None,
                    'url': row[4],
                    'similarity_score': float(row[5]) if row[5] else 0.0,
                    'cluster_rank': row[6]
                }
                for row in cluster_articles
            ]
        }
        
        return APIResponse(
            success=True,
            data=cluster_data,
            message=f"Cluster {cluster_id} details retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting cluster details for {cluster_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
