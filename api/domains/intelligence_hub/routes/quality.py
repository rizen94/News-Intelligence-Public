"""
Quality API — claim/event feedback and source rankings (pipeline enhancements P0).
Routes: POST claim_feedback, POST event_validation, GET extraction_metrics, GET source_rankings, POST source_feedback.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body

from services.quality_feedback_service import (
    submit_claim_feedback,
    submit_event_validation,
    submit_source_feedback,
    get_source_rankings,
    get_extraction_metrics,
)

router = APIRouter(prefix="/api", tags=["Quality (feedback & source reliability)"])


@router.post("/quality/claim_feedback")
def post_claim_feedback(
    claim_id: int = Body(..., embed=True),
    validation_status: str = Body(..., embed=True),
    accuracy_score: Optional[float] = Body(None, embed=True),
    corrected_text: Optional[str] = Body(None, embed=True),
    validated_by: Optional[str] = Body(None, embed=True),
) -> Dict[str, Any]:
    """Persist validation/correction for an extracted claim. Feeds extraction pattern tuning."""
    result = submit_claim_feedback(
        claim_id=claim_id,
        validation_status=validation_status,
        accuracy_score=accuracy_score,
        corrected_text=corrected_text,
        validated_by=validated_by,
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {"success": True, "data": {"validation_id": result.get("validation_id")}, "message": None}


@router.post("/quality/event_validation")
def post_event_validation(
    event_id: int = Body(..., embed=True),
    validation_status: str = Body(..., embed=True),
    corrections: Optional[Dict[str, Any]] = Body(None, embed=True),
) -> Dict[str, Any]:
    """Persist validation/correction for a tracked event. Feeds event_tracking / detection tuning."""
    result = submit_event_validation(
        event_id=event_id,
        validation_status=validation_status,
        corrections=corrections,
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {"success": True, "data": {"validation_id": result.get("validation_id")}, "message": None}


@router.get("/quality/extraction_metrics")
def get_quality_extraction_metrics(
    source: Optional[str] = Query(None, description="Filter by source name"),
    phase: Optional[str] = Query(None, description="Filter by phase (e.g. claim_extraction)"),
    since: Optional[int] = Query(None, description="Only metrics since N days ago"),
) -> Dict[str, Any]:
    """Per-source and per-phase quality scores (sample sizes, accurate/corrected/rejected, avg accuracy)."""
    result = get_extraction_metrics(source=source, phase=phase, since_days=since)
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "metrics": result.get("metrics", []),
            "source": result.get("source"),
            "phase": result.get("phase"),
            "since_days": result.get("since_days"),
        },
        "message": None,
    }


@router.get("/quality/source_rankings")
def get_quality_source_rankings(
    domain: Optional[str] = Query(None, description="Filter by domain (substring match on source_name)"),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    """Sources ranked by reliability (accuracy_score, exclusive_stories_count). For Collection Governor prioritization."""
    result = get_source_rankings(domain=domain, limit=limit)
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {"success": True, "data": {"rankings": result.get("rankings", [])}, "message": None}


@router.post("/quality/source_feedback")
def post_source_feedback(
    source_name: str = Body(..., embed=True),
    metric: str = Body(..., embed=True, description="One of: accuracy, exclusive, correction"),
    value: float = Body(..., embed=True),
) -> Dict[str, Any]:
    """Update source_reliability with a single metric (accuracy 0–1, exclusive count delta, correction rate 0–1)."""
    result = submit_source_feedback(source_name=source_name, metric=metric, value=value)
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {"success": True, "data": {}, "message": None}
