"""
Intelligence Analysis API Routes

Provides endpoints for:
1. RAG-Enhanced Analysis - Deep context retrieval
5. Quality Assessment - Narrative coherence and validation
6. Anomaly Detection - Unusual pattern identification
7. Impact Assessment - Consequence analysis
"""

from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from dataclasses import asdict

from services.intelligence_analysis_service import (
    get_intelligence_service,
    IntelligenceAnalysisService,
    RAGContext,
    QualityAssessment,
    AnomalyReport,
    ImpactAssessment,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Intelligence Analysis"],
)


def service() -> IntelligenceAnalysisService:
    return get_intelligence_service()


# =============================================================================
# RAG-ENHANCED ANALYSIS ENDPOINTS
# =============================================================================

@router.get("/{domain}/intelligence/rag/{storyline_id}", response_model=Dict[str, Any])
async def get_rag_context(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., ge=1),
    query: Optional[str] = Query(None, description="Custom query for context retrieval"),
    max_articles: int = Query(20, ge=5, le=50),
):
    """
    Retrieve RAG-enhanced context for a storyline.
    Uses vector similarity to find relevant articles and generate context summary.
    """
    try:
        svc = service()
        context = svc.retrieve_context_for_storyline(
            domain=domain,
            storyline_id=storyline_id,
            query=query,
            max_articles=max_articles
        )

        return {
            "success": True,
            "storyline_id": storyline_id,
            "domain": domain,
            "query_used": context.query,
            "context": {
                "summary": context.context_summary,
                "historical_context": context.historical_context,
                "retrieved_articles": context.retrieved_articles,
                "related_entities": context.related_entities,
                "source_diversity": round(context.source_diversity, 3),
                "temporal_span": {
                    "start": context.temporal_span[0].isoformat() if context.temporal_span[0] else None,
                    "end": context.temporal_span[1].isoformat() if context.temporal_span[1] else None,
                },
                "avg_relevance": round(sum(context.relevance_scores) / len(context.relevance_scores), 3) if context.relevance_scores else 0,
            },
            "retrieval_time_ms": round(context.retrieval_time_ms, 2),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"RAG context retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/intelligence/rag/query", response_model=Dict[str, Any])
async def query_rag_context(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    query: str = Query(..., min_length=3, description="Query for context retrieval"),
    max_articles: int = Query(20, ge=5, le=50),
):
    """
    Query RAG context without a specific storyline.
    Useful for exploring topics or finding related content.
    """
    try:
        svc = service()
        # Use storyline_id=0 to indicate domain-wide query
        context = svc.retrieve_context_for_storyline(
            domain=domain,
            storyline_id=0,  # Will need special handling
            query=query,
            max_articles=max_articles
        )

        return {
            "success": True,
            "domain": domain,
            "query": query,
            "context": {
                "summary": context.context_summary,
                "retrieved_articles": context.retrieved_articles,
                "related_entities": context.related_entities,
            },
            "retrieval_time_ms": round(context.retrieval_time_ms, 2),
        }
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# QUALITY ASSESSMENT ENDPOINTS
# =============================================================================

@router.get("/{domain}/intelligence/quality/{storyline_id}", response_model=Dict[str, Any])
async def assess_storyline_quality(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., ge=1),
):
    """
    Comprehensive quality assessment for a storyline.
    Evaluates coherence, factual accuracy, completeness, and more.
    """
    try:
        svc = service()
        assessment = svc.assess_storyline_quality(domain, storyline_id)

        return {
            "success": True,
            "storyline_id": storyline_id,
            "domain": domain,
            "assessment": {
                "overall_score": assessment.overall_score,
                "scores": {
                    "coherence": assessment.coherence_score,
                    "factual_accuracy": assessment.factual_score,
                    "completeness": assessment.completeness_score,
                    "source_diversity": assessment.source_diversity_score,
                    "temporal_consistency": assessment.temporal_consistency_score,
                },
                "quality_grade": _score_to_grade(assessment.overall_score),
                "issues": assessment.issues,
                "recommendations": assessment.recommendations,
            },
            "assessed_at": assessment.assessed_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Quality assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/intelligence/quality/batch", response_model=Dict[str, Any])
async def batch_quality_assessment(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(10, ge=1, le=50),
    min_articles: int = Query(3, ge=1),
):
    """
    Batch quality assessment for multiple storylines.
    Returns quality scores for active storylines.
    """
    try:
        svc = service()
        schema = domain.replace('-', '_')

        # Get storylines to assess
        conn = svc.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id FROM {schema}.storylines
                    WHERE status = 'active' AND article_count >= %s
                    ORDER BY updated_at DESC
                    LIMIT %s
                """, (min_articles, limit))
                storyline_ids = [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

        assessments = []
        for sid in storyline_ids:
            try:
                assessment = svc.assess_storyline_quality(domain, sid)
                assessments.append({
                    "storyline_id": sid,
                    "overall_score": assessment.overall_score,
                    "grade": _score_to_grade(assessment.overall_score),
                    "issues_count": len(assessment.issues),
                    "issues": [str(i) for i in assessment.issues[:5]],
                    "recommendations": [str(r) for r in (assessment.recommendations or [])[:3]],
                })
            except Exception as e:
                logger.warning(f"Failed to assess storyline {sid}: {e}")

        return {
            "success": True,
            "domain": domain,
            "assessments": assessments,
            "summary": {
                "total_assessed": len(assessments),
                "avg_score": round(sum(a['overall_score'] for a in assessments) / len(assessments), 3) if assessments else 0,
                "needs_attention": len([a for a in assessments if a['overall_score'] < 0.5]),
            },
        }
    except Exception as e:
        logger.error(f"Batch quality assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade"""
    if score >= 0.9:
        return "A"
    elif score >= 0.8:
        return "B"
    elif score >= 0.7:
        return "C"
    elif score >= 0.6:
        return "D"
    else:
        return "F"


# =============================================================================
# ANOMALY DETECTION ENDPOINTS
# =============================================================================

@router.get("/{domain}/intelligence/anomalies", response_model=Dict[str, Any])
async def detect_anomalies(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    hours: int = Query(24, ge=1, le=168, description="Time window to analyze"),
    sensitivity: float = Query(2.0, ge=1.0, le=3.0, description="Detection sensitivity (std devs)"),
):
    """
    Detect anomalies in article flow, storylines, and entity patterns.
    Returns unusual patterns that may indicate breaking news or data issues.
    """
    try:
        svc = service()
        anomalies = svc.detect_anomalies(domain, hours, sensitivity)

        # Group by type
        by_type = {}
        for a in anomalies:
            if a.anomaly_type not in by_type:
                by_type[a.anomaly_type] = []
            by_type[a.anomaly_type].append({
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "severity": a.severity,
                "description": a.description,
                "detected_value": a.detected_value,
                "expected_range": list(a.expected_range),
                "evidence": a.supporting_evidence,
                "detected_at": a.detected_at.isoformat(),
            })

        # Count by severity
        severity_counts = {
            "critical": len([a for a in anomalies if a.severity == 'critical']),
            "high": len([a for a in anomalies if a.severity == 'high']),
            "medium": len([a for a in anomalies if a.severity == 'medium']),
            "low": len([a for a in anomalies if a.severity == 'low']),
        }

        return {
            "success": True,
            "domain": domain,
            "time_window_hours": hours,
            "sensitivity": sensitivity,
            "total_anomalies": len(anomalies),
            "severity_breakdown": severity_counts,
            "anomalies_by_type": by_type,
            "requires_attention": severity_counts['critical'] + severity_counts['high'] > 0,
        }
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/intelligence/anomalies/watch", response_model=Dict[str, Any])
async def get_anomaly_watchlist(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
):
    """
    Get current anomaly watchlist - entities being monitored for unusual behavior.
    """
    try:
        svc = service()

        # Run quick anomaly check
        anomalies = svc.detect_anomalies(domain, hours=6, sensitivity=2.5)

        critical = [a for a in anomalies if a.severity in ['critical', 'high']]

        return {
            "success": True,
            "domain": domain,
            "alert_status": "critical" if any(a.severity == 'critical' for a in critical) else "warning" if critical else "normal",
            "active_alerts": len(critical),
            "watchlist": [{
                "type": a.entity_type,
                "id": a.entity_id,
                "severity": a.severity,
                "description": a.description,
            } for a in critical[:10]],
        }
    except Exception as e:
        logger.error(f"Anomaly watchlist failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# IMPACT ASSESSMENT ENDPOINTS
# =============================================================================

@router.get("/{domain}/intelligence/impact/{storyline_id}", response_model=Dict[str, Any])
async def assess_storyline_impact(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    storyline_id: int = Path(..., ge=1),
):
    """
    Comprehensive impact assessment for a storyline.
    Evaluates reach, significance, velocity, and predicts consequences.
    """
    try:
        svc = service()
        impact = svc.assess_storyline_impact(domain, storyline_id)

        return {
            "success": True,
            "storyline_id": storyline_id,
            "domain": domain,
            "impact": {
                "overall_score": impact.overall_impact_score,
                "impact_level": _score_to_level(impact.overall_impact_score),
                "scores": {
                    "reach": impact.reach_score,
                    "significance": impact.significance_score,
                    "velocity": impact.velocity_score,
                },
                "longevity_prediction": impact.longevity_prediction,
                "affected_domains": impact.affected_domains,
                "key_stakeholders": impact.key_stakeholders,
                "potential_consequences": impact.potential_consequences,
                "confidence": impact.confidence,
            },
            "assessed_at": impact.assessed_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Impact assessment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/intelligence/impact/trending", response_model=Dict[str, Any])
async def get_high_impact_storylines(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(10, ge=1, le=50),
    min_impact: float = Query(0.5, ge=0.0, le=1.0),
):
    """
    Get storylines with highest predicted impact.
    Useful for prioritizing coverage and attention.
    """
    try:
        svc = service()
        schema = domain.replace('-', '_')

        # Get active storylines
        conn = svc.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT id, title, article_count,
                           editorial_document->>'lede' as editorial_lede,
                           document_status
                    FROM {schema}.storylines
                    WHERE status = 'active' AND article_count >= 2
                    ORDER BY updated_at DESC
                    LIMIT 30
                """)
                storylines = cur.fetchall()
        finally:
            conn.close()

        # Assess impact for each
        impacts = []
        for row in storylines:
            sid, title, count = row[0], row[1], row[2]
            editorial_lede = row[3] if len(row) > 3 else None
            doc_status = row[4] if len(row) > 4 else None
            try:
                impact = svc.assess_storyline_impact(domain, sid)
                if impact.overall_impact_score >= min_impact:
                    impacts.append({
                        "storyline_id": sid,
                        "title": title,
                        "article_count": count,
                        "editorial_lede": editorial_lede,
                        "document_status": doc_status,
                        "impact_score": impact.overall_impact_score,
                        "impact_level": _score_to_level(impact.overall_impact_score),
                        "velocity": impact.velocity_score,
                        "longevity": impact.longevity_prediction,
                        "affected_domains": impact.affected_domains,
                    })
            except Exception as e:
                logger.warning(f"Failed to assess impact for {sid}: {e}")

        # Sort by impact score
        impacts.sort(key=lambda x: x['impact_score'], reverse=True)
        impacts = impacts[:limit]

        return {
            "success": True,
            "domain": domain,
            "high_impact_storylines": impacts,
            "summary": {
                "total_found": len(impacts),
                "avg_impact": round(sum(i['impact_score'] for i in impacts) / len(impacts), 3) if impacts else 0,
                "critical_count": len([i for i in impacts if i['impact_level'] == 'critical']),
            },
        }
    except Exception as e:
        logger.error(f"High impact storylines failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _score_to_level(score: float) -> str:
    """Convert impact score to level"""
    if score >= 0.8:
        return "critical"
    elif score >= 0.6:
        return "high"
    elif score >= 0.4:
        return "medium"
    else:
        return "low"


# =============================================================================
# COMBINED INTELLIGENCE DASHBOARD
# =============================================================================

@router.get("/{domain}/intelligence/dashboard", response_model=Dict[str, Any])
async def get_intelligence_dashboard(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
):
    """
    Combined intelligence dashboard with all key metrics.
    Provides a comprehensive overview of domain intelligence.
    """
    try:
        svc = service()
        schema = domain.replace('-', '_')

        # Get basic counts + editorial ledes from top storylines
        conn = svc.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT
                        (SELECT COUNT(*) FROM {schema}.storylines WHERE status = 'active') as active_storylines,
                        (SELECT COUNT(*) FROM {schema}.articles WHERE created_at > NOW() - INTERVAL '24 hours') as recent_articles,
                        (SELECT COUNT(DISTINCT source_name) FROM {schema}.articles WHERE created_at > NOW() - INTERVAL '24 hours') as active_sources
                """)
                counts = cur.fetchone()

                # Fetch editorial ledes from recent active storylines
                cur.execute(f"""
                    SELECT id, title, editorial_document->>'lede' as lede,
                           document_status, article_count
                    FROM {schema}.storylines
                    WHERE status = 'active'
                      AND editorial_document IS NOT NULL
                      AND editorial_document->>'lede' IS NOT NULL
                      AND editorial_document->>'lede' != ''
                    ORDER BY updated_at DESC
                    LIMIT 5
                """)
                editorial_storylines = []
                for row in cur.fetchall():
                    editorial_storylines.append({
                        "storyline_id": row[0],
                        "title": row[1],
                        "lede": row[2],
                        "document_status": row[3],
                        "article_count": row[4] or 0,
                    })
        finally:
            conn.close()

        # Get anomalies (quick check)
        anomalies = svc.detect_anomalies(domain, hours=12, sensitivity=2.5)
        critical_anomalies = [a for a in anomalies if a.severity in ['critical', 'high']]

        return {
            "success": True,
            "domain": domain,
            "generated_at": datetime.now().isoformat(),
            "overview": {
                "active_storylines": counts[0] if counts else 0,
                "articles_24h": counts[1] if counts else 0,
                "active_sources": counts[2] if counts else 0,
            },
            "editorial_highlights": editorial_storylines,
            "health": {
                "status": "critical" if len(critical_anomalies) > 2 else "warning" if critical_anomalies else "healthy",
                "anomaly_count": len(anomalies),
                "critical_alerts": len(critical_anomalies),
            },
            "capabilities": {
                "rag_analysis": True,
                "quality_assessment": True,
                "anomaly_detection": True,
                "impact_assessment": True,
            },
            "endpoints": {
                "rag_context": f"/api/{domain}/intelligence/rag/{{storyline_id}}",
                "quality": f"/api/{domain}/intelligence/quality/{{storyline_id}}",
                "anomalies": f"/api/{domain}/intelligence/anomalies",
                "impact": f"/api/{domain}/intelligence/impact/{{storyline_id}}",
            },
        }
    except Exception as e:
        logger.error(f"Intelligence dashboard failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ACTIONABLE KNOWLEDGE ASSEMBLY ENDPOINTS
# =============================================================================

@router.get("/{domain}/intelligence/consistency", response_model=Dict[str, Any])
async def get_event_storyline_claim_consistency(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit_events: int = Query(25, ge=5, le=100),
    min_claim_confidence: float = Query(0.55, ge=0.0, le=1.0),
):
    """
    Assemble event-storyline-claim consistency:
    - contested claims per event cluster
    - stable participant facts
    - storyline refresh recommendations
    """
    try:
        svc = service()
        result = svc.build_event_storyline_claim_consistency(
            domain=domain,
            limit_events=limit_events,
            min_claim_confidence=min_claim_confidence,
        )
        return {"success": True, "domain": domain, "data": result}
    except Exception as e:
        logger.error(f"Consistency assembly failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/intelligence/participant_deltas", response_model=Dict[str, Any])
async def get_participant_position_deltas(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    days: int = Query(30, ge=1, le=180),
):
    """
    Track participant stance/position drift over time.
    Uses entity_positions first; falls back to versioned_facts.
    """
    try:
        svc = service()
        result = svc.get_participant_position_deltas(domain=domain, days=days)
        return {"success": True, "domain": domain, "data": result}
    except Exception as e:
        logger.error(f"Participant delta assembly failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/intelligence/causal_chains", response_model=Dict[str, Any])
async def get_cross_domain_causal_chains(
    days: int = Query(30, ge=1, le=180),
    min_strength: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Assemble cross-domain causal chain candidates from correlation groups.
    """
    try:
        svc = service()
        result = svc.assemble_causal_chains(days=days, min_strength=min_strength, limit=limit)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Causal chain assembly failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/intelligence/narrative_divergence/{event_id}", response_model=Dict[str, Any])
async def get_narrative_divergence_map(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    event_id: int = Path(..., ge=1),
    min_contexts_per_cluster: int = Query(1, ge=1, le=10),
):
    """
    Same-event different-framing map:
    side-by-side source clusters + entity/lexical framing terms.
    """
    try:
        svc = service()
        data = svc.build_narrative_divergence_map(
            domain=domain,
            event_id=event_id,
            min_contexts_per_cluster=min_contexts_per_cluster,
        )
        return {"success": True, "domain": domain, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Narrative divergence map failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/intelligence/watchlist_theme_bridge", response_model=Dict[str, Any])
async def post_watchlist_theme_trigger_bridge(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    create_alerts: bool = Query(False, description="Persist watchlist_alerts for matched triggers"),
    max_items: int = Query(25, ge=1, le=100),
):
    """
    Auto-bridge watched storylines to emerging themes/events.
    Optionally persists watchlist alerts.
    """
    try:
        svc = service()
        data = svc.build_watchlist_theme_trigger_bridge(
            domain=domain,
            create_alerts=create_alerts,
            max_items=max_items,
        )
        return {"success": True, "domain": domain, "data": data}
    except Exception as e:
        logger.error(f"Watchlist-theme bridge failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/intelligence/document_integration", response_model=Dict[str, Any])
async def post_document_intelligence_integration(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    days: int = Query(30, ge=1, le=180),
    persist_links: bool = Query(False, description="Persist links into intelligence.document_intelligence"),
    limit: int = Query(30, ge=1, le=100),
):
    """
    Attach processed PDF document contexts to active themes and event chains.
    """
    try:
        svc = service()
        data = svc.build_document_intelligence_integration(
            domain=domain,
            days=days,
            persist_links=persist_links,
            limit=limit,
        )
        return {"success": True, "domain": domain, "data": data}
    except Exception as e:
        logger.error(f"Document intelligence integration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

