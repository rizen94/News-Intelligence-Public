"""
Storyline Discovery Routes
AI-powered endpoints for discovering storylines from article similarity
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks
from datetime import datetime
import numpy as np

from services.ai_storyline_discovery import (
    get_discovery_service, 
    AIStorylineDiscovery, 
    ArticleEmbedding,
    StorylineCluster
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Storyline Discovery"])


@router.post("/{domain}/storylines/discover")
async def discover_storylines(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(24, ge=1, le=168, description="Hours of articles to analyze"),
    save: bool = Query(True, description="Save discovered storylines to database"),
    min_similarity: float = Query(0.75, ge=0.5, le=0.99, description="Minimum similarity threshold")
):
    """
    Discover potential storylines from recent articles using AI similarity analysis
    
    This endpoint:
    1. Fetches recent articles from the specified domain
    2. Generates embeddings using Ollama
    3. Calculates pairwise similarity
    4. Clusters similar articles into potential storylines
    5. Uses LLM to generate titles and descriptions
    6. Identifies breaking news based on similarity + volume
    
    Returns suggested storylines ranked by importance.
    """
    try:
        logger.info(f"Starting storyline discovery for {domain} (last {hours} hours)")
        
        service = get_discovery_service()
        result = service.discover_storylines(
            domain=domain,
            hours=hours,
            save_to_db=save
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in storyline discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/discover_async")
async def discover_storylines_async(
    background_tasks: BackgroundTasks,
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(24, ge=1, le=168)
):
    """
    Start storyline discovery in the background
    Returns immediately with a task ID
    """
    task_id = f"discovery_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def run_discovery():
        try:
            service = get_discovery_service()
            result = service.discover_storylines(domain=domain, hours=hours)
            logger.info(f"Background discovery completed: {result['summary']}")
        except Exception as e:
            logger.error(f"Background discovery failed: {e}")
    
    background_tasks.add_task(run_discovery)
    
    return {
        "success": True,
        "task_id": task_id,
        "message": f"Storyline discovery started for {domain}",
        "estimated_duration_minutes": 2
    }


@router.get("/{domain}/storylines/breaking_news")
async def get_breaking_news(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(6, ge=1, le=48, description="Hours to look back"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get current breaking news storylines
    These are storylines with high similarity AND high article count
    """
    try:
        service = get_discovery_service()
        
        # Quick discovery without saving
        result = service.discover_storylines(
            domain=domain,
            hours=hours,
            save_to_db=False
        )
        
        breaking = result.get("breaking_news", [])[:limit]
        
        return {
            "success": True,
            "domain": domain,
            "hours_analyzed": hours,
            "breaking_news_count": len(breaking),
            "breaking_news": breaking,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting breaking news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/articles/similarity")
async def get_article_similarity(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    article_id: int = Query(..., description="Article ID to find similar articles for"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Find articles similar to a specific article
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        from shared.database.connection import get_db_config, get_db_connection
        
        db_config = get_db_config()
        service = get_discovery_service(db_config)
        schema = domain.replace('-', '_')
        
        # Get the target article
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT id, title, COALESCE(content, '') as content, created_at
                FROM {schema}.articles
                WHERE id = %s
            """, (article_id,))
            target = cur.fetchone()
            
            if not target:
                raise HTTPException(status_code=404, detail="Article not found")
            
            # Get recent articles to compare
            cur.execute(f"""
                SELECT id, title, COALESCE(content, '') as content, created_at
                FROM {schema}.articles
                WHERE id != %s
                ORDER BY created_at DESC
                LIMIT 100
            """, (article_id,))
            candidates = cur.fetchall()
        
        conn.close()
        
        # Generate embedding for target
        target_text = f"{target['title']}\n\n{target['content'][:1000]}"
        target_embedding = service.get_embedding(target_text)
        
        if target_embedding is None:
            raise HTTPException(status_code=500, detail="Failed to generate embedding")
        
        # Calculate similarities
        similarities = []
        for candidate in candidates:
            candidate_text = f"{candidate['title']}\n\n{candidate['content'][:1000]}"
            candidate_embedding = service.get_embedding(candidate_text)
            
            if candidate_embedding is not None:
                sim = service.cosine_similarity(target_embedding, candidate_embedding)
                similarities.append({
                    "article_id": candidate['id'],
                    "title": candidate['title'],
                    "similarity": round(sim, 3),
                    "created_at": candidate['created_at'].isoformat()
                })
        
        # Sort by similarity
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        return {
            "success": True,
            "target_article": {
                "id": target['id'],
                "title": target['title']
            },
            "similar_articles": similarities[:limit],
            "total_compared": len(similarities)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/analyze_cluster")
async def analyze_cluster(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    article_ids: list[int] = Query(..., description="List of article IDs to analyze")
):
    """
    Analyze a specific cluster of articles and generate storyline metadata
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import requests
        from shared.database.connection import get_db_config, get_db_connection
        
        db_config = get_db_config()
        schema = domain.replace('-', '_')
        
        # Get articles
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            placeholders = ','.join(['%s'] * len(article_ids))
            cur.execute(f"""
                SELECT id, title, COALESCE(content, '') as content
                FROM {schema}.articles
                WHERE id IN ({placeholders})
            """, article_ids)
            articles = cur.fetchall()
        conn.close()
        
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found")
        
        # Generate analysis using LLM
        article_texts = "\n".join([f"- {a['title']}" for a in articles])
        
        prompt = f"""Analyze these {len(articles)} related news articles and provide:
1. A compelling storyline title
2. A 2-3 sentence description
3. Key themes (up to 5)
4. Is this breaking news? (yes/no)
5. Importance score (1-10)

Articles:
{article_texts}

Respond in JSON format:
{{"title": "...", "description": "...", "themes": [...], "is_breaking": true/false, "importance": 1-10}}

JSON:"""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result_text = response.json().get("response", "")
            
            # Extract JSON
            import json
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                analysis = json.loads(result_text[start:end])
                
                return {
                    "success": True,
                    "article_count": len(articles),
                    "analysis": analysis,
                    "article_ids": article_ids
                }
        
        raise HTTPException(status_code=500, detail="Failed to analyze cluster")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing cluster: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# STORYLINE-TO-STORYLINE COMPARISON ENDPOINTS
# =============================================================================

@router.get("/{domain}/storylines/compare")
async def compare_storylines_endpoint(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(48, description="Hours of storylines to analyze"),
    min_similarity: float = Query(0.3, description="Minimum similarity threshold")
):
    """
    Compare all recent storylines and find related ones.
    
    Returns a similarity matrix and groups of related storylines.
    """
    try:
        service = get_discovery_service()
        
        # First discover storylines
        result = service.discover_storylines(domain, hours=hours, save_to_db=False)
        
        if not result.get("success"):
            return result
        
        # Get the clusters
        storylines = []
        # We need to reconstruct clusters from the discovery - use internal method
        articles = service.fetch_recent_articles(domain, hours)
        articles = service._deduplicate_by_title(articles)
        articles = service.generate_embeddings_parallel(articles)
        similarity_matrix = service.calculate_hybrid_similarity_matrix(articles)
        storylines = service.cluster_hdbscan(articles, similarity_matrix)
        
        if len(storylines) < 2:
            return {
                "success": True,
                "message": "Not enough storylines to compare",
                "storyline_count": len(storylines)
            }
        
        # Calculate storyline similarity matrix
        comparison_result = service.calculate_storyline_similarity_matrix(storylines)
        
        # Find merge suggestions
        merge_suggestions = service.suggest_storyline_merges(storylines, min_similarity)
        
        return {
            "success": True,
            "domain": domain,
            "storyline_count": len(storylines),
            "similarity_matrix": comparison_result,
            "merge_suggestions": merge_suggestions[:10],  # Top 10
            "related_groups": comparison_result.get("related_groups", [])
        }
        
    except Exception as e:
        logger.error(f"Error comparing storylines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/evolution")
async def detect_storyline_evolution(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(72, description="Hours to analyze for evolution"),
    time_window: int = Query(48, description="Max hours between evolution steps")
):
    """
    Detect storylines that have evolved over time.
    
    Finds chains of related storylines that represent the same story
    developing over time.
    """
    try:
        service = get_discovery_service()
        
        # Get storylines
        articles = service.fetch_recent_articles(domain, hours)
        articles = service._deduplicate_by_title(articles)
        articles = service.generate_embeddings_parallel(articles)
        similarity_matrix = service.calculate_hybrid_similarity_matrix(articles)
        storylines = service.cluster_hdbscan(articles, similarity_matrix)
        
        if len(storylines) < 2:
            return {
                "success": True,
                "message": "Not enough storylines to detect evolution",
                "storyline_count": len(storylines)
            }
        
        # Generate titles for better output
        for sl in storylines[:10]:
            sl.suggested_title = service._generate_fast_title(sl)
        
        # Detect evolution chains
        evolution_chains = service.detect_storyline_evolution(storylines, time_window)
        
        return {
            "success": True,
            "domain": domain,
            "hours_analyzed": hours,
            "storyline_count": len(storylines),
            "evolution_chains": evolution_chains,
            "summary": {
                "chains_found": len(evolution_chains),
                "longest_chain": max((c["chain_length"] for c in evolution_chains), default=0),
                "articles_in_chains": sum(c["total_articles"] for c in evolution_chains)
            }
        }
        
    except Exception as e:
        logger.error(f"Error detecting storyline evolution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/storylines/merge_check")
async def check_merge_candidates(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_ids: List[int] = Query(..., description="Storyline IDs to check for merge")
):
    """
    Check if specific storylines are candidates for merging.
    
    Takes a list of storyline IDs and returns detailed comparison.
    """
    try:
        service = get_discovery_service()
        
        # Fetch the storylines from database
        conn = service.get_db_connection()
        schema = domain.replace('-', '_')
        
        storylines = []
        try:
            with conn.cursor() as cur:
                for sl_id in storyline_ids:
                    # Get storyline
                    cur.execute(f"""
                        SELECT id, title, description, article_count
                        FROM {schema}.storylines
                        WHERE id = %s
                    """, (sl_id,))
                    
                    sl_row = cur.fetchone()
                    if not sl_row:
                        continue
                    
                    # Get articles for this storyline
                    cur.execute(f"""
                        SELECT a.id, a.title, a.content, a.created_at
                        FROM {schema}.articles a
                        JOIN {schema}.storyline_articles sa ON a.id = sa.article_id
                        WHERE sa.storyline_id = %s
                    """, (sl_id,))
                    
                    articles = []
                    for row in cur.fetchall():
                        articles.append(ArticleEmbedding(
                            article_id=row[0],
                            title=row[1],
                            content=row[2] or "",
                            domain=domain,
                            created_at=row[3]
                        ))
                    
                    # Generate embeddings
                    articles = service.generate_embeddings_parallel(articles)
                    
                    # Create cluster
                    embeddings = [a.embedding for a in articles if a.embedding is not None]
                    centroid = np.mean(embeddings, axis=0) if embeddings else None
                    
                    cluster = StorylineCluster(
                        cluster_id=sl_id,
                        articles=articles,
                        centroid=centroid,
                        avg_similarity=0.0,
                        is_breaking_news=False,
                        suggested_title=sl_row[1],
                        suggested_description=sl_row[2] or "",
                        common_entities=list(service.extract_entities(" ".join(a.title for a in articles)))
                    )
                    storylines.append(cluster)
        finally:
            conn.close()
        
        if len(storylines) < 2:
            return {
                "success": False,
                "message": "Need at least 2 valid storylines to compare"
            }
        
        # Compare all pairs
        comparisons = []
        for i in range(len(storylines)):
            for j in range(i + 1, len(storylines)):
                comparison = service.compare_storylines(storylines[i], storylines[j])
                comparisons.append(comparison)
        
        # Overall merge recommendation
        best_match = max(comparisons, key=lambda x: x["overall_similarity"])
        
        return {
            "success": True,
            "storylines_analyzed": len(storylines),
            "comparisons": comparisons,
            "recommendation": {
                "should_merge": best_match["overall_similarity"] >= 0.6,
                "best_match": best_match,
                "reason": f"Storylines are {best_match['relationship']} with {best_match['overall_similarity']:.0%} similarity"
            }
        }
        
    except Exception as e:
        logger.error(f"Error checking merge candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

