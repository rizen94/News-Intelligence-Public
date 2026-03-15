"""
Deduplication API (P3): consolidate_articles, merge_claims.
POST /api/deduplication/consolidate_articles, POST /api/deduplication/merge_claims.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body

from services.deduplication_api_service import consolidate_articles as run_consolidate_articles
from services.deduplication_api_service import merge_claims as run_merge_claims

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deduplication", tags=["Deduplication (P3)"])


@router.post("/consolidate_articles")
def post_consolidate_articles(
    domain: Optional[str] = Body(None, embed=True),
    limit: int = Body(50, embed=True),
    dry_run: bool = Body(True, embed=True),
) -> Dict[str, Any]:
    """Merge duplicate articles (domain, limit, dry_run). Returns merged count and clusters."""
    result = run_consolidate_articles(domain=domain, limit=limit, dry_run=dry_run)
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "merged": result.get("merged", 0),
            "clusters": result.get("clusters", []),
            "dry_run": result.get("dry_run", True),
        },
        "message": None,
    }


@router.post("/merge_claims")
def post_merge_claims(
    claim_ids: Optional[List[int]] = Body(None, embed=True),
    similarity_threshold: float = Body(0.9, embed=True),
) -> Dict[str, Any]:
    """Merge claims: first id is canonical, others merged into it. Returns merged count and unified_claim_ids."""
    result = run_merge_claims(claim_ids=claim_ids, similarity_threshold=similarity_threshold)
    if not result.get("success"):
        return {"success": False, "data": None, "message": result.get("error", "Unknown error")}
    return {
        "success": True,
        "data": {
            "merged": result.get("merged", 0),
            "unified_claim_ids": result.get("unified_claim_ids", []),
        },
        "message": None,
    }
