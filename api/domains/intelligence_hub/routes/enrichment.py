"""
Enrichment API (P3): enrich_entity, verify_claim.
POST /api/enrichment/enrich_entity, POST /api/enrichment/verify_claim.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body

from services.entity_enrichment_service import enrich_entity_profile
from services.quality_feedback_service import submit_claim_feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrichment", tags=["Enrichment (P3)"])


@router.post("/enrich_entity")
def post_enrich_entity(
    entity_profile_id: int = Body(..., embed=True),
    sources: Optional[list] = Body(None, embed=True),
    priority: Optional[str] = Body(None, embed=True),
) -> Dict[str, Any]:
    """Enrich one entity profile (e.g. Wikipedia). Returns updated, sections_added, facts_added."""
    try:
        updated = enrich_entity_profile(entity_profile_id)
        return {
            "success": True,
            "data": {
                "updated": updated,
                "sections_added": 1 if updated else 0,
                "facts_added": 1 if updated else 0,
            },
            "message": None,
        }
    except Exception as e:
        logger.warning("enrich_entity failed: %s", e)
        return {"success": False, "data": None, "message": str(e)}


@router.post("/verify_claim")
def post_verify_claim(
    claim_id: int = Body(..., embed=True),
    provider: Optional[str] = Body("internal", embed=True),
    validation_status: str = Body("accurate", embed=True),
    accuracy_score: Optional[float] = Body(None, embed=True),
    corrected_text: Optional[str] = Body(None, embed=True),
) -> Dict[str, Any]:
    """Record claim verification (internal or external). Persists to claim_validations; returns status, verified_at."""
    result = submit_claim_feedback(
        claim_id=claim_id,
        validation_status=validation_status,
        accuracy_score=accuracy_score,
        corrected_text=corrected_text,
        validated_by=provider or "internal",
    )
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "status": validation_status,
            "confidence_delta": None,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        },
        "message": None,
    }
