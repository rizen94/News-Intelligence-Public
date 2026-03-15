"""
Context-centric API — Phase 3.1 / 4.2.
Read-only APIs for entity_profiles, contexts, tracked_events, claims.
Flat /api/... routes. See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def _json_safe(val: Any) -> Any:
    """Convert value to JSON-serializable form (Decimal, date, datetime -> str)."""
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, dict):
        return {k: _json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_json_safe(v) for v in val]
    return val

router = APIRouter(
    prefix="/api",
    tags=["Context-centric (intelligence)"],
)


def _safe_count(cur, sql: str, default: int = 0) -> int:
    """Run COUNT query; return default if relation/column does not exist."""
    try:
        cur.execute(sql)
        row = cur.fetchone()
        return row[0] if row is not None else default
    except Exception:
        return default


@router.post("/context_centric/sync_entity_profiles", response_model=dict)
def sync_entity_profiles(domain_key: Optional[str] = Query(None, description="Sync this domain only; omit to sync all")) -> dict:
    """
    Run entity_profile_sync: backfill entity_canonical from article_entities, then
    copy entity_canonical -> intelligence.entity_profiles for the given domain (or all).
    Returns counts of new profiles created per domain.
    """
    try:
        from config.context_centric_config import is_context_centric_task_enabled
        if not is_context_centric_task_enabled("entity_profile_sync"):
            return {"success": False, "error": "entity_profile_sync task is disabled in context_centric config"}
    except Exception:
        pass
    from services.entity_profile_sync_service import backfill_entity_canonical, sync_domain_entity_profiles

    domains = [domain_key] if domain_key else ["politics", "finance", "science-tech"]
    if domain_key and domain_key not in ("politics", "finance", "science-tech"):
        raise HTTPException(status_code=400, detail="domain_key must be one of politics, finance, science-tech")

    backfill_counts: dict[str, int] = {}
    result: dict[str, int] = {}
    for d in domains:
        try:
            backfilled = backfill_entity_canonical(d)
            backfill_counts[d] = backfilled
        except Exception as e:
            logger.warning(f"backfill_entity_canonical {d}: {e}")
            backfill_counts[d] = 0
        try:
            created = sync_domain_entity_profiles(d)
            result[d] = created
        except Exception as e:
            logger.warning(f"sync_entity_profiles {d}: {e}")
            result[d] = -1
    return {"success": True, "created_by_domain": result, "canonical_backfilled": backfill_counts}


@router.post("/context_centric/run_story_state_triggers", response_model=dict)
def run_story_state_triggers(
    step: str = Query("both", description="fact_log (process fact_change_log) | queue (process story_update_queue) | both"),
    fact_batch: int = Query(100, ge=1, le=200, description="Max fact_change_log rows per run (production: 100)"),
    queue_batch: int = Query(20, ge=1, le=100, description="Max story_update_queue rows per run"),
) -> dict:
    """
    Process story state update pipeline: fact_change_log -> story_update_queue -> story state refresh.
    See docs/STORY_STATE_UPDATE_TRIGGERS.md.
    """
    try:
        from services.story_state_trigger_service import process_fact_change_log, process_story_update_queue
        fact_processed = 0
        queue_processed = 0
        if step in ("fact_log", "both"):
            fact_processed = process_fact_change_log(batch_size=fact_batch)
        if step in ("queue", "both"):
            queue_processed = process_story_update_queue(batch_size=queue_batch)
        return {"success": True, "fact_change_log_processed": fact_processed, "story_update_queue_processed": queue_processed}
    except Exception as e:
        logger.warning("run_story_state_triggers: %s", e, exc_info=True)
        return {"success": False, "error": str(e), "fact_change_log_processed": 0, "story_update_queue_processed": 0}


@router.post("/context_centric/run_enhancement_cycle", response_model=dict)
async def run_enhancement_cycle(
    fact_batch: int = Query(100, ge=1, le=200, description="Fact change log batch (production: 100)"),
    queue_batch: int = Query(10, ge=1, le=100, description="Story update queue batch; max 10 stories/run (production)"),
    enrich_limit: int = Query(10, ge=1, le=50),
    build_limit: int = Query(10, ge=1, le=30),
) -> dict:
    """
    Phase 3 RAG: Run one full enhancement cycle (story state triggers + entity enrichment + profile build).
    See docs/RAG_ENHANCEMENT_ROADMAP.md.
    """
    try:
        from services.enhancement_orchestrator_service import run_enhancement_cycle as run_cycle
        result = await run_cycle(fact_batch=fact_batch, queue_batch=queue_batch, enrich_limit=enrich_limit, build_limit=build_limit)
        return {"success": True, **result}
    except Exception as e:
        logger.warning("run_enhancement_cycle: %s", e, exc_info=True)
        return {"success": False, "error": str(e), "fact_change_log_processed": 0, "story_update_queue_processed": 0, "entity_profiles_enriched": 0, "entity_profiles_built": 0, "errors": [str(e)]}


@router.post("/context_centric/run_pattern_matching", response_model=dict)
def run_pattern_matching(
    domain_key: Optional[str] = Query(None, description="Run for this domain only; omit to run all domains"),
    limit: int = Query(50, ge=1, le=200, description="Max contexts per domain to check"),
) -> dict:
    """
    Phase 4 RAG: Run watch pattern matching on recent contexts; store pattern_matches and create
    watchlist_alerts when significance >= threshold and storyline is on watchlist.
    See docs/RAG_ENHANCEMENT_ROADMAP.md.
    """
    try:
        from services.watch_pattern_service import run_pattern_matching as run_pattern_matching_svc, run_pattern_matching_all_domains
        if domain_key:
            if domain_key not in ("politics", "finance", "science-tech"):
                raise HTTPException(status_code=400, detail="domain_key must be one of politics, finance, science-tech")
            result = run_pattern_matching_svc(domain_key=domain_key, limit=limit)
        else:
            result = run_pattern_matching_all_domains(limit_per_domain=min(limit, 100))
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("run_pattern_matching: %s", e, exc_info=True)
        return {"success": False, "error": str(e), "contexts_checked": 0, "matches_stored": 0, "alerts_created": 0, "errors": [str(e)]}


@router.post("/context_centric/run_entity_enrichment", response_model=dict)
def run_entity_enrichment(limit: int = Query(20, ge=1, le=50, description="Max profiles to enrich (production: 20)")) -> dict:
    """
    Run Phase 1 entity enrichment: Wikipedia (and optional GDELT) for entity_profiles
    that lack a Wikipedia-derived section. Updates sections and versioned_facts.
    See docs/RAG_ENHANCEMENT_ROADMAP.md.
    """
    try:
        from services.entity_enrichment_service import run_enrichment_batch
        updated = run_enrichment_batch(limit=limit)
        return {"success": True, "updated": updated}
    except Exception as e:
        logger.warning("run_entity_enrichment: %s", e, exc_info=True)
        return {"success": False, "error": str(e), "updated": 0}


@router.post("/context_centric/sync_contexts", response_model=dict)
def sync_contexts(
    domain_key: Optional[str] = Query(None, description="Sync this domain only; omit to sync all"),
    limit: int = Query(100, ge=1, le=500, description="Max articles to backfill per domain (production: 100)"),
) -> dict:
    """
    Backfill intelligence.contexts from domain articles that don't have a context yet.
    Use this to create finance (or other domain) contexts from existing articles when
    politics is filling in but another domain is not yet.
    """
    from services.context_processor_service import sync_domain_articles_to_contexts

    domains = [domain_key] if domain_key else ["politics", "finance", "science-tech"]
    if domain_key and domain_key not in ("politics", "finance", "science-tech"):
        raise HTTPException(status_code=400, detail="domain_key must be one of politics, finance, science-tech")

    result: dict[str, int] = {}
    for d in domains:
        try:
            created = sync_domain_articles_to_contexts(d, limit=limit)
            result[d] = created
        except Exception as e:
            logger.warning(f"sync_contexts %s: %s", d, e)
            result[d] = -1
    return {"success": True, "contexts_created_by_domain": result}


@router.post("/context_centric/cleanup", response_model=dict)
def run_intelligence_cleanup(
    domain_key: Optional[str] = Query(None, description="Clean this domain only; omit for all"),
) -> dict:
    """
    Run the full intelligence cleanup cycle: noise removal, duplicate merge,
    low-value entity pruning, orphan profile cleanup, entity cap, and stale
    event archival. Safe to call repeatedly (idempotent).
    """
    if domain_key and domain_key not in ("politics", "finance", "science-tech"):
        raise HTTPException(status_code=400, detail="domain_key must be one of politics, finance, science-tech")
    from services.intelligence_cleanup_controller import IntelligenceCleanupController
    controller = IntelligenceCleanupController()
    return controller.run(domain_key=domain_key)


@router.post("/context_centric/discover_events", response_model=dict)
async def discover_events(
    domain_key: Optional[str] = Query(None, description="Discover events in this domain only; omit for all"),
    limit: int = Query(100, ge=1, le=500, description="Max contexts to analyze"),
) -> dict:
    """Analyze recent contexts with LLM to discover and create tracked events."""
    from services.event_tracking_service import discover_events_from_contexts
    result = await discover_events_from_contexts(domain_key=domain_key, limit=limit)
    return result


@router.post("/context_centric/review_events", response_model=dict)
async def review_event_coherence_api(
    event_id: Optional[int] = Query(None, description="Review a single event; omit to review all open events"),
    threshold: float = Query(0.5, ge=0.0, le=1.0, description="Relevance threshold — contexts scoring below are removed"),
    auto_remove: bool = Query(True, description="Automatically remove irrelevant contexts"),
) -> dict:
    """
    LLM-powered coherence review: for each context in an event, verify it
    actually belongs. Removes mismatches and logs reasoning.
    """
    from services.event_coherence_reviewer import review_event_coherence, review_all_open_events
    if event_id is not None:
        return await review_event_coherence(event_id, relevance_threshold=threshold, auto_remove=auto_remove)
    return await review_all_open_events(relevance_threshold=threshold, auto_remove=auto_remove)


@router.get("/context_centric/status", response_model=dict)
def context_centric_status() -> dict:
    """Return counts for context-centric pipeline (Phase 3.2 quality validation)."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            contexts = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.contexts")
            article_links = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.article_to_context")
            entity_profiles = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.entity_profiles")
            entity_mappings = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.old_entity_to_new")
            mentions = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.context_entity_mentions")
            claims = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.extracted_claims")
            events = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.tracked_events")
            chronicles = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.event_chronicles")
            pattern_discoveries = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.pattern_discoveries")
        conn.close()
        return {
            "contexts": contexts,
            "article_to_context_links": article_links,
            "entity_profiles": entity_profiles,
            "old_entity_to_new_mappings": entity_mappings,
            "context_entity_mentions": mentions,
            "extracted_claims": claims,
            "tracked_events": events,
            "event_chronicles": chronicles,
            "pattern_discoveries": pattern_discoveries,
        }
    except Exception as e:
        logger.warning(f"context_centric_status: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get status")


@router.get("/context_centric/quality", response_model=dict)
def context_centric_quality() -> dict:
    """
    Phase 3.2 quality validation: compare old (article_entities) vs context-centric (entity_profiles, mentions).
    Per-domain counts and simple coverage metrics. Missing tables are skipped.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    domains = ("politics", "finance", "science_tech")
    schema_map = {"politics": "politics", "finance": "finance", "science-tech": "science_tech"}
    by_domain = {}
    try:
        with conn.cursor() as cur:
            for domain_key in ("politics", "finance", "science-tech"):
                schema = schema_map.get(domain_key, domain_key.replace("-", "_"))
                row = {
                    "domain": domain_key,
                    "rss_feeds_active": None,
                    "articles": None,
                    "article_entities": None,
                    "article_entities_with_canonical": None,
                    "entity_canonical": None,
                    "contexts": None,
                    "article_to_context_links": None,
                    "entity_profiles": None,
                    "context_entity_mentions": None,
                    "entity_coverage_pct": None,
                    "context_coverage_pct": None,
                }
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.rss_feeds WHERE is_active = true")
                    row["rss_feeds_active"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.articles")
                    row["articles"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.article_entities")
                    row["article_entities"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.article_entities WHERE canonical_entity_id IS NOT NULL")
                    row["article_entities_with_canonical"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.entity_canonical")
                    row["entity_canonical"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM intelligence.contexts WHERE domain_key = %s",
                        (domain_key,),
                    )
                    row["contexts"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM intelligence.article_to_context WHERE domain_key = %s",
                        (domain_key,),
                    )
                    row["article_to_context_links"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(
                        "SELECT COUNT(*) FROM intelligence.entity_profiles WHERE domain_key = %s",
                        (domain_key,),
                    )
                    row["entity_profiles"] = cur.fetchone()[0]
                except Exception:
                    pass
                try:
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM intelligence.context_entity_mentions cem
                        JOIN intelligence.contexts c ON c.id = cem.context_id
                        WHERE c.domain_key = %s
                        """,
                        (domain_key,),
                    )
                    row["context_entity_mentions"] = cur.fetchone()[0]
                except Exception:
                    pass
                if row.get("articles") and row["articles"] > 0 and row.get("article_to_context_links") is not None:
                    row["context_coverage_pct"] = round(100.0 * row["article_to_context_links"] / row["articles"], 1)
                if row.get("entity_canonical") and row["entity_canonical"] > 0 and row.get("entity_profiles") is not None:
                    row["entity_coverage_pct"] = round(100.0 * row["entity_profiles"] / row["entity_canonical"], 1)
                by_domain[domain_key] = row
        conn.close()
        return {"by_domain": by_domain, "summary": "Compare article_entities vs entity_profiles; context_coverage = article_to_context / articles."}
    except Exception as e:
        logger.warning(f"context_centric_quality: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get quality metrics")


@router.get("/pattern_discoveries", response_model=dict)
def list_pattern_discoveries(
    pattern_type: Optional[str] = Query(None, description="behavioral, temporal, network, event"),
    domain_key: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List pattern discoveries (Phase 2.2). Optional pattern_type and domain_key filters."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if pattern_type and domain_key:
                cur.execute(
                    """
                    SELECT id, pattern_type, domain_key, context_ids, entity_profile_ids, confidence, data, created_at
                    FROM intelligence.pattern_discoveries
                    WHERE pattern_type = %s AND domain_key = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (pattern_type, domain_key, limit, offset),
                )
            elif pattern_type:
                cur.execute(
                    """
                    SELECT id, pattern_type, domain_key, context_ids, entity_profile_ids, confidence, data, created_at
                    FROM intelligence.pattern_discoveries
                    WHERE pattern_type = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (pattern_type, limit, offset),
                )
            elif domain_key:
                cur.execute(
                    """
                    SELECT id, pattern_type, domain_key, context_ids, entity_profile_ids, confidence, data, created_at
                    FROM intelligence.pattern_discoveries
                    WHERE domain_key = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (domain_key, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, pattern_type, domain_key, context_ids, entity_profile_ids, confidence, data, created_at
                    FROM intelligence.pattern_discoveries
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
        conn.close()
        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "pattern_type": r[1],
                "domain_key": r[2],
                "context_ids": list(r[3]) if r[3] else [],
                "entity_profile_ids": list(r[4]) if r[4] else [],
                "confidence": float(r[5]) if r[5] is not None else None,
                "data": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            })
        return {"items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning(f"list_pattern_discoveries: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list pattern discoveries")


def _row_to_profile(row: tuple) -> dict:
    """Map entity_profiles row to dict (JSON-safe)."""
    return {
        "id": row[0],
        "domain_key": row[1],
        "canonical_entity_id": row[2],
        "compilation_date": str(row[3]) if row[3] else None,
        "sections": _json_safe(row[4]) if row[4] is not None else None,
        "relationships_summary": _json_safe(row[5]) if row[5] is not None else None,
        "metadata": _json_safe(row[6]) if row[6] is not None else None,
        "created_at": row[7].isoformat() if row[7] else None,
        "updated_at": row[8].isoformat() if row[8] else None,
    }


def _row_to_profile_brief(row: tuple) -> dict:
    """Map 7-column row (no sections/relationships) to list view. Keeps response small and fast."""
    return {
        "id": row[0],
        "domain_key": row[1],
        "canonical_entity_id": row[2],
        "compilation_date": str(row[3]) if row[3] else None,
        "sections": None,
        "relationships_summary": None,
        "metadata": _json_safe(row[4]) if row[4] is not None else None,
        "created_at": row[5].isoformat() if row[5] else None,
        "updated_at": row[6].isoformat() if row[6] else None,
    }


@router.get("/entity_profiles", response_model=dict)
def list_entity_profiles(
    domain_key: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    brief: bool = Query(False, description="If true, omit sections/relationships for faster list load"),
) -> dict:
    """List entity profiles (intelligence.entity_profiles). Use brief=True for list views (skips heavy columns)."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if brief:
                # Do not SELECT sections/relationships_summary — avoids huge transfer and timeout
                if domain_key:
                    cur.execute(
                        """
                        SELECT id, domain_key, canonical_entity_id, compilation_date,
                               metadata, created_at, updated_at
                        FROM intelligence.entity_profiles
                        WHERE domain_key = %s
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT %s OFFSET %s
                        """,
                        (domain_key, limit, offset),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, domain_key, canonical_entity_id, compilation_date,
                               metadata, created_at, updated_at
                        FROM intelligence.entity_profiles
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset),
                    )
            else:
                if domain_key:
                    cur.execute(
                        """
                        SELECT id, domain_key, canonical_entity_id, compilation_date,
                               sections, relationships_summary, metadata, created_at, updated_at
                        FROM intelligence.entity_profiles
                        WHERE domain_key = %s
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT %s OFFSET %s
                        """,
                        (domain_key, limit, offset),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, domain_key, canonical_entity_id, compilation_date,
                               sections, relationships_summary, metadata, created_at, updated_at
                        FROM intelligence.entity_profiles
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset),
                    )
            rows = cur.fetchall()
        conn.close()
        to_item = _row_to_profile_brief if brief else _row_to_profile
        return {"items": [to_item(r) for r in rows], "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("list_entity_profiles: %s", e, exc_info=True)
        try:
            conn.close()
        except Exception:
            pass
        detail = str(e)
        if "does not exist" in detail or "relation" in detail.lower():
            detail = f"Entity profiles table may be missing. Run migration 143: {detail}"
        raise HTTPException(status_code=500, detail=f"Failed to list entity profiles: {detail}")


@router.get("/entity_profiles/{profile_id}", response_model=dict)
def get_entity_profile(profile_id: int) -> dict:
    """Get a single entity profile by id."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, canonical_entity_id, compilation_date,
                       sections, relationships_summary, metadata, created_at, updated_at
                FROM intelligence.entity_profiles
                WHERE id = %s
                """,
                (profile_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Entity profile not found")
        return _row_to_profile(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"get_entity_profile: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get entity profile")


@router.patch("/entity_profiles/{profile_id}", response_model=dict)
def update_entity_profile(
    profile_id: int,
    body: dict = Body(..., description="Fields to merge into metadata: importance, entity_type, tracking_params, alert_thresholds, orchestrator_tags"),
) -> dict:
    """Update entity profile metadata. Use orchestrator_tags (array of strings) so the orchestrator can prioritize for deeper stories."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    allowed = {"importance", "entity_type", "tracking_params", "alert_thresholds", "orchestrator_tags"}
    updates = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not updates:
        return get_entity_profile(profile_id)
    # Normalize orchestrator_tags to list of strings
    if "orchestrator_tags" in updates:
        raw = updates["orchestrator_tags"]
        if isinstance(raw, list):
            updates["orchestrator_tags"] = [str(x).strip() for x in raw if str(x).strip()]
        else:
            updates["orchestrator_tags"] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata FROM intelligence.entity_profiles WHERE id = %s",
                (profile_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                raise HTTPException(status_code=404, detail="Entity profile not found")
            import json
            meta = dict(row[0]) if row[0] else {}
            meta.update(updates)
            cur.execute(
                """
                UPDATE intelligence.entity_profiles
                SET metadata = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id, domain_key, canonical_entity_id, compilation_date,
                          sections, relationships_summary, metadata, created_at, updated_at
                """,
                (json.dumps(meta), profile_id),
            )
            out = cur.fetchone()
        conn.commit()
        conn.close()
        return _row_to_profile(out)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"update_entity_profile: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to update entity profile")


@router.post("/entity_profiles/{profile_id}/merge", response_model=dict)
def merge_entity_profiles(
    profile_id: int,
    body: dict = Body(..., embed=True),
) -> dict:
    """Merge source entity profile into target (Phase 4.2). Same domain required. Redirects old_entity_to_new and context_entity_mentions to target."""
    source_profile_id = body.get("source_profile_id")
    if source_profile_id is None:
        raise HTTPException(status_code=400, detail="source_profile_id required")
    try:
        source_profile_id = int(source_profile_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="source_profile_id must be an integer")
    if source_profile_id == profile_id:
        raise HTTPException(status_code=400, detail="Source and target must differ")
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, domain_key FROM intelligence.entity_profiles WHERE id IN (%s, %s)",
                (profile_id, source_profile_id),
            )
            rows = cur.fetchall()
            if len(rows) != 2:
                conn.close()
                raise HTTPException(status_code=404, detail="One or both entity profiles not found")
            by_id = {r[0]: r[1] for r in rows}
            if by_id[profile_id] != by_id[source_profile_id]:
                conn.close()
                raise HTTPException(status_code=400, detail="Source and target must be in the same domain")
            # Redirect old_entity_to_new from source -> target
            cur.execute(
                "UPDATE intelligence.old_entity_to_new SET entity_profile_id = %s WHERE entity_profile_id = %s",
                (profile_id, source_profile_id),
            )
            # Redirect context_entity_mentions from source -> target (avoid dupes: delete source mentions that target already has, then update rest)
            cur.execute(
                """
                DELETE FROM intelligence.context_entity_mentions a
                USING intelligence.context_entity_mentions b
                WHERE a.entity_profile_id = %s AND b.entity_profile_id = %s AND a.context_id = b.context_id
                """,
                (source_profile_id, profile_id),
            )
            cur.execute(
                "UPDATE intelligence.context_entity_mentions SET entity_profile_id = %s WHERE entity_profile_id = %s",
                (profile_id, source_profile_id),
            )
            # Mark source as merged (audit trail)
            cur.execute(
                "SELECT metadata FROM intelligence.entity_profiles WHERE id = %s",
                (source_profile_id,),
            )
            r = cur.fetchone()
            from datetime import datetime
            import json
            meta = dict(r[0]) if r and r[0] else {}
            meta["merged_into_profile_id"] = profile_id
            meta["merged_at"] = datetime.utcnow().isoformat() + "Z"
            cur.execute(
                "UPDATE intelligence.entity_profiles SET metadata = %s, updated_at = NOW() WHERE id = %s",
                (json.dumps(meta), source_profile_id),
            )
        conn.commit()
        conn.close()
        return {"success": True, "target_profile_id": profile_id, "source_profile_id": source_profile_id, "message": "Merged; source profile marked as merged."}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"merge_entity_profiles: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to merge entity profiles")


def _row_to_context(row: tuple, max_content_len: int = 2000) -> dict:
    """Map contexts row to dict. Use max_content_len=400 for brief list view."""
    content = row[4]
    if content and len(content) > max_content_len:
        content = content[:max_content_len] + "..."
    return {
        "id": row[0],
        "source_type": row[1],
        "domain_key": row[2],
        "title": row[3],
        "content": content,
        "metadata": row[5],
        "created_at": row[6].isoformat() if row[6] else None,
        "updated_at": row[7].isoformat() if row[7] else None,
    }


@router.get("/contexts", response_model=dict)
def list_contexts(
    domain_key: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None, description="e.g. article"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    brief: bool = Query(False, description="If true, truncate content for faster list load"),
) -> dict:
    """List intelligence contexts. Optional domain and source_type filters. Use brief=True for list views."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if domain_key and source_type:
                cur.execute(
                    """
                    SELECT id, source_type, domain_key, title, content, metadata, created_at, updated_at
                    FROM intelligence.contexts
                    WHERE domain_key = %s AND source_type = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (domain_key, source_type, limit, offset),
                )
            elif domain_key:
                cur.execute(
                    """
                    SELECT id, source_type, domain_key, title, content, metadata, created_at, updated_at
                    FROM intelligence.contexts
                    WHERE domain_key = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (domain_key, limit, offset),
                )
            elif source_type:
                cur.execute(
                    """
                    SELECT id, source_type, domain_key, title, content, metadata, created_at, updated_at
                    FROM intelligence.contexts
                    WHERE source_type = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (source_type, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, source_type, domain_key, title, content, metadata, created_at, updated_at
                    FROM intelligence.contexts
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
        conn.close()
        content_len = 400 if brief else 2000
        return {"items": [_row_to_context(r, content_len) for r in rows], "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning(f"list_contexts: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list contexts")


def _row_to_context_full(row: tuple) -> dict:
    """Map contexts row to dict without truncating content."""
    return {
        "id": row[0],
        "source_type": row[1],
        "domain_key": row[2],
        "title": row[3],
        "content": row[4],
        "metadata": row[5],
        "created_at": row[6].isoformat() if row[6] else None,
        "updated_at": row[7].isoformat() if row[7] else None,
    }


@router.get("/contexts/{context_id}", response_model=dict)
def get_context(context_id: int) -> dict:
    """Get a single context by id, with full content and linked article info."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_type, domain_key, title, content, metadata, created_at, updated_at
                FROM intelligence.contexts
                WHERE id = %s
                """,
                (context_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                raise HTTPException(status_code=404, detail="Context not found")
            ctx = _row_to_context_full(row)

            article = None
            try:
                cur.execute(
                    "SELECT article_id FROM intelligence.article_to_context WHERE context_id = %s LIMIT 1",
                    (context_id,),
                )
                link_row = cur.fetchone()
                if link_row:
                    article_id = link_row[0]
                    schema_map = {"politics": "politics", "finance": "finance", "science-tech": "science_tech"}
                    schema = schema_map.get(ctx["domain_key"], ctx["domain_key"].replace("-", "_"))
                    cur.execute(
                        f"""
                        SELECT id, title, url, source, summary, published_date, content
                        FROM {schema}.articles
                        WHERE id = %s
                        """,
                        (article_id,),
                    )
                    art_row = cur.fetchone()
                    if art_row:
                        article = {
                            "id": art_row[0],
                            "title": art_row[1],
                            "url": art_row[2],
                            "source": art_row[3],
                            "summary": art_row[4],
                            "published_date": art_row[5].isoformat() if art_row[5] else None,
                            "content": art_row[6][:5000] if art_row[6] else None,
                        }
            except Exception as e:
                logger.debug(f"get_context article lookup: {e}")

            ctx["article"] = article
        conn.close()
        return ctx
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"get_context: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get context")


@router.patch("/contexts/{context_id}", response_model=dict)
def update_context(
    context_id: int,
    body: dict = Body(..., description="Fields to merge into metadata; use orchestrator_tags (list of strings) for story prioritization"),
) -> dict:
    """Update context metadata. Use orchestrator_tags (array of strings) so the orchestrator can prioritize for deeper stories."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    allowed = {"orchestrator_tags"}
    updates = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not updates:
        return get_context(context_id)
    # Normalize orchestrator_tags to list of strings
    if "orchestrator_tags" in updates:
        raw = updates["orchestrator_tags"]
        if isinstance(raw, list):
            updates["orchestrator_tags"] = [str(x).strip() for x in raw if str(x).strip()]
        else:
            updates["orchestrator_tags"] = []
    try:
        import json
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata FROM intelligence.contexts WHERE id = %s",
                (context_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                raise HTTPException(status_code=404, detail="Context not found")
            meta = dict(row[0]) if row[0] else {}
            meta.update(updates)
            cur.execute(
                """
                UPDATE intelligence.contexts
                SET metadata = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id, source_type, domain_key, title, content, metadata, created_at, updated_at
                """,
                (json.dumps(meta), context_id),
            )
            out = cur.fetchone()
        conn.commit()
        conn.close()
        return _row_to_context_full(out)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"update_context: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to update context")


_EVENT_COLS = """id, event_type, event_name, start_date, end_date, geographic_scope,
                   key_participant_entity_ids, milestones, sub_event_ids, created_at, updated_at, domain_keys,
                   editorial_briefing, editorial_briefing_json, briefing_version, briefing_status"""


def _row_to_event(row: tuple) -> dict:
    """Map tracked_events row to dict, including editorial briefing fields."""
    return {
        "id": row[0],
        "event_type": row[1],
        "event_name": row[2],
        "start_date": str(row[3]) if row[3] else None,
        "end_date": str(row[4]) if row[4] else None,
        "geographic_scope": row[5],
        "key_participant_entity_ids": row[6],
        "milestones": row[7],
        "sub_event_ids": list(row[8]) if row[8] else None,
        "created_at": row[9].isoformat() if row[9] else None,
        "updated_at": row[10].isoformat() if row[10] else None,
        "domain_keys": list(row[11]) if row[11] else [],
        "editorial_briefing": row[12] if len(row) > 12 else None,
        "editorial_briefing_json": row[13] if len(row) > 13 else None,
        "briefing_version": row[14] if len(row) > 14 else None,
        "briefing_status": row[15] if len(row) > 15 else None,
    }


@router.get("/tracked_events", response_model=dict)
def list_tracked_events(
    event_type: Optional[str] = Query(None),
    domain_key: Optional[str] = Query(None, description="Filter: events that include this domain"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List tracked events. Events can span multiple domains; domain_key filters to events that include that domain."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        conditions = []
        params: list = []
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type)
        if domain_key:
            conditions.append("%s = ANY(domain_keys)")
            params.append(domain_key)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_EVENT_COLS}
                FROM intelligence.tracked_events
                {where}
                ORDER BY start_date DESC NULLS LAST, updated_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()
        items = [_row_to_event(r) for r in rows]
        try:
            from services.quality_feedback_service import get_latest_event_validations
            event_ids = [e["id"] for e in items]
            validations = get_latest_event_validations(event_ids, conn=conn)
            for e in items:
                e["validation_status"] = validations.get(e["id"])
        except Exception:
            for e in items:
                e["validation_status"] = None
        conn.close()
        return {"items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning(f"list_tracked_events: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list tracked events")


@router.post("/tracked_events", response_model=dict)
def create_tracked_event(
    body: dict = Body(
        ...,
        example={
            "event_type": "election",
            "event_name": "2026 Midterms",
            "start_date": "2026-01-01",
            "end_date": None,
            "geographic_scope": "US",
            "key_participant_entity_ids": [],
            "milestones": [],
            "sub_event_ids": None,
            "domain_keys": ["politics"],
        },
    ),
) -> dict:
    """Create a tracked event. Required: event_type, event_name. Optional: start_date, end_date, geographic_scope, key_participant_entity_ids, milestones, sub_event_ids, domain_keys."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        event_type = body.get("event_type") or ""
        event_name = body.get("event_name") or ""
        if not event_type or not event_name:
            raise HTTPException(status_code=400, detail="event_type and event_name are required")
        start_date = body.get("start_date")
        end_date = body.get("end_date")
        geographic_scope = body.get("geographic_scope")
        key_participant_entity_ids = body.get("key_participant_entity_ids")
        if key_participant_entity_ids is None:
            key_participant_entity_ids = []
        milestones = body.get("milestones")
        if milestones is None:
            milestones = []
        sub_event_ids = body.get("sub_event_ids")
        domain_keys = body.get("domain_keys")
        if domain_keys is None:
            domain_keys = []
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.tracked_events
                (event_type, event_name, start_date, end_date, geographic_scope,
                 key_participant_entity_ids, milestones, sub_event_ids, domain_keys)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, event_type, event_name, start_date, end_date, geographic_scope,
                          key_participant_entity_ids, milestones, sub_event_ids, created_at, updated_at, domain_keys
                """,
                    (
                    event_type,
                    event_name,
                    start_date,
                    end_date,
                    geographic_scope,
                    json.dumps(key_participant_entity_ids) if isinstance(key_participant_entity_ids, list) else "[]",
                    json.dumps(milestones) if isinstance(milestones, list) else "[]",
                    sub_event_ids,
                    domain_keys,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        conn.close()
        if not row:
            raise HTTPException(status_code=500, detail="Insert failed")
        return {
            "id": row[0],
            "event_type": row[1],
            "event_name": row[2],
            "start_date": str(row[3]) if row[3] else None,
            "end_date": str(row[4]) if row[4] else None,
            "geographic_scope": row[5],
            "key_participant_entity_ids": row[6],
            "milestones": row[7],
            "sub_event_ids": list(row[8]) if row[8] else None,
            "created_at": row[9].isoformat() if row[9] else None,
            "updated_at": row[10].isoformat() if row[10] else None,
            "domain_keys": list(row[11]) if len(row) > 11 and row[11] else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"create_tracked_event: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")


@router.put("/tracked_events/{event_id}", response_model=dict)
def update_tracked_event(event_id: int, body: dict = Body(...)) -> dict:
    """Update a tracked event. Send only fields to update (event_type, event_name, start_date, end_date, geographic_scope, key_participant_entity_ids, milestones, sub_event_ids, domain_keys)."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM intelligence.tracked_events WHERE id = %s", (event_id,))
            if not cur.fetchone():
                conn.close()
                raise HTTPException(status_code=404, detail="Tracked event not found")
            updates = []
            params: list = []
            for key in ("event_type", "event_name", "start_date", "end_date", "geographic_scope"):
                if key in body and body[key] is not None:
                    updates.append(f"{key} = %s")
                    params.append(body[key])
            if "key_participant_entity_ids" in body:
                updates.append("key_participant_entity_ids = %s")
                params.append(json.dumps(body["key_participant_entity_ids"]) if isinstance(body["key_participant_entity_ids"], list) else "[]")
            if "milestones" in body:
                updates.append("milestones = %s")
                params.append(json.dumps(body["milestones"]) if isinstance(body["milestones"], list) else "[]")
            if "sub_event_ids" in body:
                updates.append("sub_event_ids = %s")
                params.append(body["sub_event_ids"])
            if "domain_keys" in body:
                updates.append("domain_keys = %s")
                params.append(body["domain_keys"] if isinstance(body["domain_keys"], list) else [])
            if not updates:
                cur.execute(
                    f"SELECT {_EVENT_COLS} FROM intelligence.tracked_events WHERE id = %s",
                    (event_id,),
                )
                row = cur.fetchone()
                conn.close()
                return _row_to_event(row)
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(event_id)
            cur.execute(
                "UPDATE intelligence.tracked_events SET " + ", ".join(updates) + " WHERE id = %s",
                tuple(params),
            )
            conn.commit()
            cur.execute(f"SELECT {_EVENT_COLS} FROM intelligence.tracked_events WHERE id = %s", (event_id,))
            row = cur.fetchone()
        conn.close()
        return _row_to_event(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"update_tracked_event: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to update event: {str(e)}")


@router.get("/tracked_events/{event_id}", response_model=dict)
def get_tracked_event(event_id: int) -> dict:
    """Get a single tracked event with its chronicles."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_EVENT_COLS}
                FROM intelligence.tracked_events
                WHERE id = %s
                """,
                (event_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                raise HTTPException(status_code=404, detail="Tracked event not found")
            event = _row_to_event(row)
            cur.execute(
                """
                SELECT id, update_date, developments, analysis, predictions, momentum_score, created_at
                FROM intelligence.event_chronicles
                WHERE event_id = %s
                ORDER BY update_date DESC
                """,
                (event_id,),
            )
            chronicles = []
            for r in cur.fetchall():
                chronicles.append({
                    "id": r[0],
                    "update_date": str(r[1]) if r[1] else None,
                    "developments": r[2],
                    "analysis": r[3],
                    "predictions": r[4],
                    "momentum_score": float(r[5]) if r[5] is not None else None,
                    "created_at": r[6].isoformat() if r[6] else None,
                })
            event["chronicles"] = chronicles
            try:
                from services.quality_feedback_service import get_latest_event_validations
                validations = get_latest_event_validations([event_id], conn=conn)
                event["validation_status"] = validations.get(event_id)
            except Exception:
                event["validation_status"] = None
        conn.close()
        return event
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"get_tracked_event: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get tracked event")


@router.post("/tracked_events/{event_id}/chronicles/update", response_model=dict)
def update_tracked_event_chronicles(
    event_id: int,
    body: dict = Body(default=None),
) -> dict:
    """Build or refresh one event_chronicles row for this event (T2.1). Gathers developments from storylines in event domains, computes momentum_score."""
    from services.event_chronicle_builder_service import build_chronicle_for_event
    params = body or {}
    update_date = params.get("update_date")  # optional YYYY-MM-DD
    developments_days = int(params.get("developments_days", 7))
    if update_date:
        from datetime import datetime
        try:
            update_date = datetime.strptime(update_date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            update_date = None
    result = build_chronicle_for_event(
        event_id,
        update_date=update_date,
        developments_days=developments_days,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Chronicle build failed"))
    return result


@router.get("/tracked_events/{event_id}/report", response_model=dict)
def get_tracked_event_report(event_id: int) -> dict:
    """Get the latest stored investigation report (dossier) for this event, if any."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT report_md, generated_at, context_ids_included, chronicle_count, context_count
                FROM intelligence.event_reports
                WHERE event_id = %s
                """,
                (event_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="No report yet; POST to generate")
        return {
            "event_id": event_id,
            "report_md": row[0],
            "generated_at": row[1].isoformat() if row[1] else None,
            "context_ids_included": list(row[2]) if row[2] else [],
            "chronicle_count": row[3],
            "context_count": row[4],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"get_tracked_event_report: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get report")


@router.post("/tracked_events/{event_id}/report", response_model=dict)
async def generate_tracked_event_report(event_id: int) -> dict:
    """Generate a journalism-style investigation dossier from event, chronicles, and contexts. Saves to event_reports."""
    from services.investigation_report_service import generate_investigation_report

    try:
        result = await generate_investigation_report(event_id)
    except Exception as e:
        logger.exception("generate_tracked_event_report: service raised")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Report generation failed"))

    conn = get_db_connection()
    if not conn:
        return result
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.event_reports
                (event_id, report_md, generated_at, context_ids_included, chronicle_count, context_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    report_md = EXCLUDED.report_md,
                    generated_at = EXCLUDED.generated_at,
                    context_ids_included = EXCLUDED.context_ids_included,
                    chronicle_count = EXCLUDED.chronicle_count,
                    context_count = EXCLUDED.context_count
                """,
                (
                    event_id,
                    result["report_md"],
                    result["generated_at"],
                    result.get("context_ids_included") or [],
                    result.get("chronicle_count", 0),
                    result.get("context_count", 0),
                ),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"save event_report: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# Entity dossiers (Phase 1 T1.3) — GET dossier, POST compile
# ---------------------------------------------------------------------------

@router.get("/entity_dossiers", response_model=dict)
def get_entity_dossier(
    domain_key: str = Query(..., description="Domain (politics, finance, science-tech)"),
    entity_id: int = Query(..., ge=1, description="entity_canonical.id in that domain"),
) -> dict:
    """Get entity dossier for (domain_key, entity_id). Returns 404 if not compiled yet; use POST /entity_dossiers/compile to build."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, entity_id, compilation_date, chronicle_data, relationships, positions, patterns, metadata, created_at
                FROM intelligence.entity_dossiers
                WHERE domain_key = %s AND entity_id = %s
                """,
                (domain_key, entity_id),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Dossier not found; POST /entity_dossiers/compile to build")
        return {
            "id": row[0],
            "domain_key": row[1],
            "entity_id": row[2],
            "compilation_date": str(row[3]) if row[3] else None,
            "chronicle_data": row[4],
            "relationships": row[5],
            "positions": row[6],
            "patterns": row[7],
            "metadata": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"get_entity_dossier: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get dossier")


@router.post("/entity_dossiers/compile", response_model=dict)
def compile_entity_dossier(body: dict = Body(..., example={"domain_key": "politics", "entity_id": 1})) -> dict:
    """Build or refresh entity dossier from articles and storylines that mention the entity. Requires domain_key and entity_id."""
    domain_key = body.get("domain_key")
    entity_id = body.get("entity_id")
    if not domain_key or entity_id is None:
        raise HTTPException(status_code=400, detail="domain_key and entity_id are required")
    try:
        entity_id = int(entity_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="entity_id must be an integer")
    from services.dossier_compiler_service import compile_dossier
    result = compile_dossier(domain_key, entity_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Compilation failed"))
    return result


# ---------------------------------------------------------------------------
# Processed documents (Phase 3 T3.1) — list, get, create, ingest from config
# ---------------------------------------------------------------------------

@router.get("/processed_documents", response_model=dict)
def list_processed_documents(
    source_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List processed_documents (T3.1). Optional filter by source_type."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if source_type:
                cur.execute(
                    """
                    SELECT id, source_type, source_name, source_url, title, publication_date, document_type, created_at
                    FROM intelligence.processed_documents
                    WHERE source_type = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (source_type, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, source_type, source_name, source_url, title, publication_date, document_type, created_at
                    FROM intelligence.processed_documents
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
        conn.close()
        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "source_type": r[1],
                "source_name": r[2],
                "source_url": r[3],
                "title": r[4],
                "publication_date": str(r[5]) if r[5] else None,
                "document_type": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            })
        return {"items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("list_processed_documents: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list processed documents")


@router.get("/processed_documents/{document_id}", response_model=dict)
def get_processed_document(document_id: int) -> dict:
    """Get one processed_document by id (T3.1)."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_type, source_name, source_url, title, publication_date, authors, document_type,
                       extracted_sections, key_findings, entities_mentioned, citations, metadata, created_at, updated_at
                FROM intelligence.processed_documents
                WHERE id = %s
                """,
                (document_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        return {
            "id": row[0],
            "source_type": row[1],
            "source_name": row[2],
            "source_url": row[3],
            "title": row[4],
            "publication_date": str(row[5]) if row[5] else None,
            "authors": list(row[6]) if row[6] else [],
            "document_type": row[7],
            "extracted_sections": row[8],
            "key_findings": row[9],
            "entities_mentioned": row[10],
            "citations": row[11],
            "metadata": _json_safe(row[12]) if row[12] else {},
            "created_at": row[13].isoformat() if row[13] else None,
            "updated_at": row[14].isoformat() if row[14] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("get_processed_document: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to get document")


@router.post("/processed_documents", response_model=dict)
def create_processed_document(body: dict = Body(..., example={"source_url": "https://example.org/report.pdf", "title": "Report"})) -> dict:
    """Create one processed_document from metadata (T3.1). Requires source_url; optional title, source_type, document_type, publication_date, authors."""
    source_url = (body.get("source_url") or "").strip()
    if not source_url:
        raise HTTPException(status_code=400, detail="source_url is required")
    from services.document_acquisition_service import create_document
    pub_date = body.get("publication_date")
    result = create_document(
        source_url=source_url,
        title=body.get("title"),
        source_type=body.get("source_type"),
        source_name=body.get("source_name"),
        document_type=body.get("document_type"),
        publication_date=pub_date if isinstance(pub_date, date) else None,
        publication_date_str=pub_date if isinstance(pub_date, str) else None,
        authors=body.get("authors"),
        metadata=body.get("metadata"),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Create failed"))
    return result


@router.post("/processed_documents/ingest_from_config", response_model=dict)
def ingest_processed_documents_from_config() -> dict:
    """Run document acquisition from document_sources.ingest_urls (T3.1). Returns inserted count and any errors."""
    from services.document_acquisition_service import ingest_from_config
    return ingest_from_config()


@router.post("/processed_documents/{document_id}/process", response_model=dict)
def process_processed_document(
    document_id: int,
    body: dict = Body(None, example={"storyline_connections": [{"domain_key": "politics", "storyline_id": 1}], "force_reprocess": False}),
) -> dict:
    """
    Process a document: download PDF from source_url, extract text/sections/entities/findings.
    If the document has already been processed, pass force_reprocess=true to re-extract.
    Optionally pass extracted_sections/key_findings/entities_mentioned to override auto-extraction.
    """
    from services.document_processing_service import process_document
    body = body or {}
    result = process_document(
        document_id=document_id,
        storyline_connections=body.get("storyline_connections"),
        extracted_sections=body.get("extracted_sections"),
        key_findings=body.get("key_findings"),
        entities_mentioned=body.get("entities_mentioned"),
        force_reprocess=body.get("force_reprocess", False),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Processing failed"))
    return result


@router.post("/processed_documents/batch_process", response_model=dict)
def batch_process_documents(
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Process all documents that have a source_url but haven't been parsed yet."""
    from services.document_processing_service import process_unprocessed_documents
    return process_unprocessed_documents(limit=limit)


# ---------------------------------------------------------------------------
# Narrative threads (Phase 3 T3.3) — list, build, synthesize
# ---------------------------------------------------------------------------

@router.get("/narrative_threads", response_model=dict)
def list_narrative_threads(
    domain_key: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List narrative_threads (T3.3). Optional filter by domain_key."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if domain_key:
                cur.execute(
                    """
                    SELECT id, domain_key, storyline_id, summary, linked_article_ids, created_at
                    FROM intelligence.narrative_threads
                    WHERE domain_key = %s
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (domain_key, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, domain_key, storyline_id, summary, linked_article_ids, created_at
                    FROM intelligence.narrative_threads
                    ORDER BY id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
        conn.close()
        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "domain_key": r[1],
                "storyline_id": r[2],
                "summary_snippet": (r[3] or "")[:500] if r[3] else None,
                "linked_article_ids": list(r[4]) if r[4] else [],
                "created_at": r[5].isoformat() if r[5] else None,
            })
        return {"items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("list_narrative_threads: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list narrative threads")


@router.post("/narrative_threads/build", response_model=dict)
def build_narrative_threads(
    body: dict = Body(None, example={"domain_key": "politics", "limit": 50}),
) -> dict:
    """T3.3: Build or update narrative_threads from storylines for a domain."""
    from services.narrative_thread_service import build_threads_for_domain
    body = body or {}
    domain_key = body.get("domain_key")
    if not domain_key:
        raise HTTPException(status_code=400, detail="domain_key is required")
    limit = int(body.get("limit") or 50)
    result = build_threads_for_domain(domain_key, limit=limit)
    return result


@router.post("/narrative_threads/synthesize", response_model=dict)
def synthesize_narrative_threads(
    body: dict = Body(None, example={"domain_key": "politics"}),
) -> dict:
    """T3.3 stub: Return synthesis from narrative threads (domain_key or thread_ids)."""
    from services.narrative_thread_service import synthesize_threads
    body = body or {}
    result = synthesize_threads(domain_key=body.get("domain_key"), thread_ids=body.get("thread_ids"))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Synthesis failed"))
    return result


@router.post("/context_centric/entities/consolidate", response_model=dict)
def run_entity_consolidation(
    domain_key: Optional[str] = Query(None, description="Run for this domain only; omit for all domains"),
) -> dict:
    """
    Run entity consolidation: merge duplicate entities, prune low-value, extract relationships.

    Uses entity_organizer_service.run_cycle() (same as the consolidation scheduler and
    entity_organizer automation phase). Returns cleanup stats and relationship counts.
    """
    from services.entity_organizer_service import run_cycle
    result = run_cycle(domain_key=domain_key)
    return {
        "success": len(result.get("errors") or []) == 0,
        "data": {
            "cleanup": result.get("cleanup", {}),
            "relationships_extracted": result.get("relationships_extracted", 0),
            "errors": result.get("errors", []),
        },
    }


@router.post("/context_centric/investigations/consolidate", response_model=dict)
def run_investigation_consolidation(
    limit_events: int = Query(200, ge=50, le=500, description="Max events to consider for clustering"),
) -> dict:
    """
    Cluster related tracked_events (investigations) into superset events.

    Finds events about the same theme (e.g. war in Iran from different angles),
    creates one superset event per cluster with event_type='superset' and
    sub_event_ids listing the component events. Returns clusters_found,
    supersets_created, and any errors.
    """
    from services.investigation_consolidation_service import run_consolidation
    result = run_consolidation(limit_events=limit_events)
    return {"success": len(result.get("errors") or []) == 0, "data": result}


@router.get("/claims", response_model=dict)
def list_claims(
    context_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List extracted claims. Optional context_id filter."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if context_id:
                cur.execute(
                    """
                    SELECT id, context_id, subject_text, predicate_text, object_text, confidence, valid_from, valid_to, created_at
                    FROM intelligence.extracted_claims
                    WHERE context_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (context_id, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, context_id, subject_text, predicate_text, object_text, confidence, valid_from, valid_to, created_at
                    FROM intelligence.extracted_claims
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
            items = []
            for r in rows:
                items.append({
                    "id": r[0],
                    "context_id": r[1],
                    "subject_text": r[2],
                    "predicate_text": r[3],
                    "object_text": r[4],
                    "confidence": float(r[5]) if r[5] is not None else None,
                    "valid_from": r[6].isoformat() if r[6] else None,
                    "valid_to": r[7].isoformat() if r[7] else None,
                    "created_at": r[8].isoformat() if r[8] else None,
                })
            try:
                from services.quality_feedback_service import get_latest_claim_validations
                claim_ids = [c["id"] for c in items]
                validations = get_latest_claim_validations(claim_ids, conn=conn)
                for c in items:
                    c["validation_status"] = validations.get(c["id"])
            except Exception:
                for c in items:
                    c["validation_status"] = None
        conn.close()
        return {"items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning(f"list_claims: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list claims")


@router.get("/context_centric/search", response_model=dict)
def context_centric_search(
    q: Optional[str] = Query(None, description="Full-text search (claims subject/predicate/object, context title/content)"),
    claim_subject: Optional[str] = Query(None, description="Filter claims by subject text (ILIKE)"),
    claim_predicate: Optional[str] = Query(None, description="Filter claims by predicate text (ILIKE)"),
    entity_id: Optional[int] = Query(None, description="Filter by entity_profile_id (claims/contexts mentioning this entity)"),
    pattern_type: Optional[str] = Query(None, description="Filter pattern_discoveries by type: behavioral, temporal, network, event"),
    valid_from: Optional[str] = Query(None, description="Temporal: claims valid on or after this date (YYYY-MM-DD)"),
    valid_to: Optional[str] = Query(None, description="Temporal: claims valid on or before this date (YYYY-MM-DD)"),
    domain_key: Optional[str] = Query(None, description="Restrict to domain"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """Phase 4.5 advanced search: by claim, entity, pattern, temporal range. Returns claims, contexts, pattern_discoveries."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        claims, contexts, patterns = [], [], []
        with conn.cursor() as cur:
            # Claims: optional filters
            claim_conditions = ["1=1"]
            claim_args = []
            if claim_subject:
                claim_conditions.append("subject_text ILIKE %s")
                claim_args.append(f"%{claim_subject}%")
            if claim_predicate:
                claim_conditions.append("predicate_text ILIKE %s")
                claim_args.append(f"%{claim_predicate}%")
            if valid_from:
                claim_conditions.append("(valid_to IS NULL OR valid_to >= %s::date)")
                claim_args.append(valid_from)
            if valid_to:
                claim_conditions.append("(valid_from IS NULL OR valid_from <= %s::date)")
                claim_args.append(valid_to)
            if q:
                claim_conditions.append("(subject_text ILIKE %s OR predicate_text ILIKE %s OR object_text ILIKE %s)")
                claim_args.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
            claim_args.extend([limit, offset])
            cur.execute(
                """
                SELECT id, context_id, subject_text, predicate_text, object_text, confidence, valid_from, valid_to, created_at
                FROM intelligence.extracted_claims
                WHERE """ + " AND ".join(claim_conditions) + """
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(claim_args),
            )
            for r in cur.fetchall():
                claims.append({
                    "id": r[0],
                    "context_id": r[1],
                    "subject_text": r[2],
                    "predicate_text": r[3],
                    "object_text": r[4],
                    "confidence": float(r[5]) if r[5] is not None else None,
                    "valid_from": r[6].isoformat() if r[6] else None,
                    "valid_to": r[7].isoformat() if r[7] else None,
                    "created_at": r[8].isoformat() if r[8] else None,
                })
            try:
                from services.quality_feedback_service import get_latest_claim_validations
                claim_ids = [c["id"] for c in claims]
                validations = get_latest_claim_validations(claim_ids, conn=conn)
                for c in claims:
                    c["validation_status"] = validations.get(c["id"])
            except Exception:
                for c in claims:
                    c["validation_status"] = None

            # Contexts: optional q and entity_id (via context_entity_mentions)
            ctx_conditions = ["1=1"]
            ctx_args = []
            if domain_key:
                ctx_conditions.append("domain_key = %s")
                ctx_args.append(domain_key)
            if q:
                ctx_conditions.append("(title ILIKE %s OR content ILIKE %s)")
                ctx_args.extend([f"%{q}%", f"%{q}%"])
            if entity_id:
                ctx_conditions.append("id IN (SELECT context_id FROM intelligence.context_entity_mentions WHERE entity_profile_id = %s)")
                ctx_args.append(entity_id)
            ctx_args.extend([limit, offset])
            cur.execute(
                """
                SELECT id, source_type, domain_key, title,
                       LEFT(content, 500) as content, metadata, created_at, updated_at
                FROM intelligence.contexts
                WHERE """ + " AND ".join(ctx_conditions) + """
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(ctx_args),
            )
            for r in cur.fetchall():
                contexts.append({
                    "id": r[0],
                    "source_type": r[1],
                    "domain_key": r[2],
                    "title": r[3],
                    "content_snippet": r[4],
                    "metadata": r[5],
                    "created_at": r[6].isoformat() if r[6] else None,
                    "updated_at": r[7].isoformat() if r[7] else None,
                })

            # Pattern discoveries: optional pattern_type and entity_id
            pat_conditions = ["1=1"]
            pat_args = []
            if pattern_type:
                pat_conditions.append("pattern_type = %s")
                pat_args.append(pattern_type)
            if domain_key:
                pat_conditions.append("domain_key = %s")
                pat_args.append(domain_key)
            if entity_id:
                pat_conditions.append("%s = ANY(entity_profile_ids)")
                pat_args.append(entity_id)
            pat_args.extend([limit, offset])
            cur.execute(
                """
                SELECT id, pattern_type, domain_key, context_ids, entity_profile_ids, confidence, data, created_at
                FROM intelligence.pattern_discoveries
                WHERE """ + " AND ".join(pat_conditions) + """
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(pat_args),
            )
            for r in cur.fetchall():
                patterns.append({
                    "id": r[0],
                    "pattern_type": r[1],
                    "domain_key": r[2],
                    "context_ids": list(r[3]) if r[3] else [],
                    "entity_profile_ids": list(r[4]) if r[4] else [],
                    "confidence": float(r[5]) if r[5] is not None else None,
                    "data": r[6],
                    "created_at": r[7].isoformat() if r[7] else None,
                })
        conn.close()
        return {
            "claims": claims,
            "contexts": contexts,
            "pattern_discoveries": patterns,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.warning(f"context_centric_search: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to search")


# ---------------------------------------------------------------------------
# Entity resolution endpoints (T1.2)
# ---------------------------------------------------------------------------

@router.post("/entities/resolve", response_model=dict)
def resolve_entity(
    body: dict = Body(..., examples=[{"domain_key": "politics", "entity_name": "Biden", "entity_type": "person"}]),
) -> dict:
    """
    Resolve an entity name to canonical entity, returning the best match and candidates.
    Body: {domain_key, entity_name, entity_type}.
    """
    domain_key = body.get("domain_key", "politics")
    entity_name = body.get("entity_name", "")
    entity_type = body.get("entity_type", "person")
    if not entity_name:
        raise HTTPException(status_code=400, detail="entity_name required")

    from services.entity_resolution_service import resolve_with_candidates
    result = resolve_with_candidates(domain_key, entity_name, entity_type, limit=10)
    return {"success": True, **result}


@router.post("/entities/populate_aliases", response_model=dict)
def populate_entity_aliases(
    domain_key: Optional[str] = Query(None, description="Domain to process; omit for all"),
    min_mentions: int = Query(2, description="Minimum articles for an alias to be added"),
) -> dict:
    """
    Batch-populate entity_canonical.aliases from article_entities mention variants.
    """
    from services.entity_resolution_service import populate_aliases_from_mentions, ALL_DOMAINS

    domains = [domain_key] if domain_key else ALL_DOMAINS
    results = {}
    for d in domains:
        results[d] = populate_aliases_from_mentions(d, min_mentions=min_mentions)
    return {"success": True, "results": results}


@router.get("/entities/merge_candidates", response_model=dict)
def get_merge_candidates(
    domain_key: str = Query(..., description="Domain to scan"),
    min_confidence: float = Query(0.5, description="Minimum confidence threshold"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """
    Find pairs of canonical entities that likely refer to the same real-world entity.
    Returns candidates with confidence scores and match reasons.
    """
    from services.entity_resolution_service import find_merge_candidates
    return find_merge_candidates(domain_key, min_confidence=min_confidence, limit=limit)


@router.post("/entities/merge", response_model=dict)
def merge_entities(
    body: dict = Body(..., examples=[{"domain_key": "politics", "keep_id": 1, "merge_id": 2}]),
) -> dict:
    """
    Merge two canonical entities: reassign article_entities, combine aliases, delete the merged entity.
    Body: {domain_key, keep_id, merge_id}.
    """
    domain_key = body.get("domain_key")
    keep_id = body.get("keep_id")
    merge_id = body.get("merge_id")
    if not all([domain_key, keep_id, merge_id]):
        raise HTTPException(status_code=400, detail="domain_key, keep_id, and merge_id required")

    from services.entity_resolution_service import merge_canonical_entities
    return merge_canonical_entities(domain_key, keep_id=keep_id, merge_id=merge_id)


@router.post("/entities/auto_merge", response_model=dict)
def auto_merge_entities(
    domain_key: Optional[str] = Query(None, description="Domain to auto-merge; omit for all"),
    min_confidence: float = Query(0.9, description="Only merge above this confidence"),
) -> dict:
    """
    Automatically merge canonical entities with confidence >= threshold.
    High confidence (>= 0.9) means title-stripped or shared alias matches.
    """
    from services.entity_resolution_service import auto_merge_high_confidence, ALL_DOMAINS

    domains = [domain_key] if domain_key else ALL_DOMAINS
    results = {}
    for d in domains:
        results[d] = auto_merge_high_confidence(d, min_confidence=min_confidence)
    return {"success": True, "results": results}


@router.post("/entities/cross_domain_link", response_model=dict)
def cross_domain_link_entities(
    min_confidence: float = Query(0.8, description="Minimum confidence for cross-domain linking"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """
    Find the same entity across domain schemas (politics, finance, science-tech)
    and create cross_domain_same_entity relationships.
    """
    from services.entity_resolution_service import link_cross_domain_entities
    return link_cross_domain_entities(min_confidence=min_confidence, limit=limit)


@router.post("/entities/run_resolution_batch", response_model=dict)
def run_entity_resolution_batch(
    auto_merge_confidence: float = Query(0.9),
    cross_domain_confidence: float = Query(0.8),
) -> dict:
    """
    Run a full entity resolution cycle: populate aliases, auto-merge duplicates,
    link cross-domain entities. Suitable for scheduled or manual trigger.
    """
    from services.entity_resolution_service import run_resolution_batch
    return run_resolution_batch(
        auto_merge_confidence=auto_merge_confidence,
        cross_domain_confidence=cross_domain_confidence,
    )


@router.get("/entities/canonical", response_model=dict)
def list_canonical_entities(
    domain_key: str = Query(..., description="Domain to query"),
    entity_type: Optional[str] = Query(None, description="Filter by type (person, organization, subject, recurring_event)"),
    search: Optional[str] = Query(None, description="Search canonical_name or aliases"),
    min_mentions: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List canonical entities with alias info and mention counts."""
    from services.entity_resolution_service import _schema_for_domain

    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cur:
            where_clauses = []
            params: list = []

            if entity_type:
                where_clauses.append("ec.entity_type = %s")
                params.append(entity_type)
            if search:
                where_clauses.append(
                    "(LOWER(ec.canonical_name) LIKE LOWER(%s) OR EXISTS "
                    "(SELECT 1 FROM unnest(COALESCE(ec.aliases, '{}')) a WHERE LOWER(a) LIKE LOWER(%s)))"
                )
                params.extend([f"%{search}%", f"%{search}%"])

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            having_clause = ""
            if min_mentions > 0:
                having_clause = f"HAVING COUNT(ae.id) >= {int(min_mentions)}"

            cur.execute(
                f"""
                SELECT ec.id, ec.canonical_name, ec.entity_type, ec.aliases,
                       COUNT(ae.id) AS mention_count,
                       ec.created_at, ec.updated_at
                FROM {schema}.entity_canonical ec
                LEFT JOIN {schema}.article_entities ae ON ae.canonical_entity_id = ec.id
                {where_sql}
                GROUP BY ec.id, ec.canonical_name, ec.entity_type, ec.aliases,
                         ec.created_at, ec.updated_at
                {having_clause}
                ORDER BY COUNT(ae.id) DESC, ec.canonical_name
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = cur.fetchall()

            entities = []
            for row in rows:
                entities.append({
                    "canonical_entity_id": row[0],
                    "canonical_name": row[1],
                    "entity_type": row[2],
                    "aliases": row[3] or [],
                    "mention_count": row[4],
                    "created_at": _json_safe(row[5]),
                    "updated_at": _json_safe(row[6]),
                })

        conn.close()
        return {"success": True, "entities": entities, "domain_key": domain_key, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("list_canonical_entities: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Entity position tracking endpoints (T2.2)
# ---------------------------------------------------------------------------

@router.get("/entity_positions", response_model=dict)
def get_entity_positions(
    domain_key: str = Query(...),
    entity_id: int = Query(...),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Get stored positions (stances, votes, statements) for a canonical entity."""
    from services.entity_position_tracker_service import get_entity_positions as _get
    return _get(domain_key, entity_id, limit=limit)


@router.post("/entity_positions/extract", response_model=dict)
def extract_entity_positions(
    body: dict = Body(..., examples=[{"domain_key": "politics", "entity_id": 1, "max_articles": 10}]),
) -> dict:
    """Extract positions for a specific entity from its articles using LLM."""
    domain_key = body.get("domain_key")
    entity_id = body.get("entity_id")
    if not domain_key or not entity_id:
        raise HTTPException(status_code=400, detail="domain_key and entity_id required")

    from services.entity_position_tracker_service import extract_positions_for_entity
    return extract_positions_for_entity(
        domain_key, entity_id,
        max_articles=body.get("max_articles", 20),
    )


@router.post("/entity_positions/batch", response_model=dict)
def run_position_tracker_batch(
    domain_key: Optional[str] = Query(None),
    min_mentions: int = Query(5, ge=1),
    max_entities: int = Query(10, ge=1, le=50),
) -> dict:
    """
    Batch-extract positions for top entities by mention count.
    Suitable for manual trigger or scheduled runs.
    """
    from services.entity_position_tracker_service import run_position_tracker_batch as _batch
    return _batch(
        domain_key=domain_key,
        min_mentions=min_mentions,
        max_entities=max_entities,
    )


# ---------------------------------------------------------------------------
# Content synthesis endpoints (centralized intelligence aggregation)
# ---------------------------------------------------------------------------

@router.get("/synthesis/domain", response_model=dict)
def get_domain_synthesis(
    domain_key: str = Query(...),
    hours: int = Query(24, ge=1, le=168),
    max_articles: int = Query(30, ge=1, le=100),
) -> dict:
    """
    Synthesize all intelligence for a domain within a time window.
    Returns articles with ml_data, storylines with editorial ledes, events with briefings,
    entities with mention counts, claims, and patterns — all in one response.
    """
    from services.content_synthesis_service import synthesize_domain_context
    return synthesize_domain_context(
        domain_key, hours=hours, max_articles=max_articles,
    )


@router.get("/synthesis/storyline/{storyline_id}", response_model=dict)
def get_storyline_synthesis(
    storyline_id: int,
    domain_key: str = Query(...),
) -> dict:
    """
    Synthesize all intelligence for a specific storyline: articles with enrichments,
    entities, claims from linked contexts, and the editorial document.
    """
    from services.content_synthesis_service import synthesize_storyline_context
    return synthesize_storyline_context(domain_key, storyline_id)


@router.get("/synthesis/event/{event_id}", response_model=dict)
def get_event_synthesis(event_id: int) -> dict:
    """
    Synthesize all intelligence for a tracked event: metadata, chronicles,
    editorial briefing, related context.
    """
    from services.content_synthesis_service import synthesize_event_context
    return synthesize_event_context(event_id)


@router.get("/synthesis/entity/{entity_id}", response_model=dict)
def get_entity_synthesis(
    entity_id: int,
    domain_key: str = Query(...),
) -> dict:
    """
    Synthesize all intelligence for a canonical entity: dossier, positions,
    relationships, recent articles, storyline references.
    """
    from services.content_synthesis_service import synthesize_entity_context
    return synthesize_entity_context(domain_key, entity_id)


# ---------------------------------------------------------------------------
# Fact verification endpoints (T3.3)
# ---------------------------------------------------------------------------

@router.post("/verification/claim/{claim_id}", response_model=dict)
def verify_single_claim(
    claim_id: int,
    domain_key: str = Query(...),
    hours: int = Query(72, ge=1, le=720),
) -> dict:
    """
    Full verification pipeline for a single claim: corroboration, contradiction check,
    source reliability scoring. Returns verification_status and confidence.
    """
    from services.fact_verification_service import verify_claim
    return verify_claim(claim_id, domain_key, hours=hours)


@router.post("/verification/corroborate", response_model=dict)
def corroborate_claim_text(
    body: dict = Body(..., examples=[{"claim_text": "Federal Reserve raises interest rates", "domain_key": "finance"}]),
) -> dict:
    """
    Check if a claim text is corroborated by multiple independent sources.
    Returns status (corroborated/partially_corroborated/single_source/unverified),
    source count, and confidence.
    """
    claim_text = body.get("claim_text", "")
    domain_key = body.get("domain_key", "politics")
    hours = body.get("hours", 72)
    if not claim_text:
        raise HTTPException(status_code=400, detail="claim_text required")

    from services.fact_verification_service import corroborate_claim
    return corroborate_claim(claim_text, domain_key, hours=hours)


@router.get("/verification/contradictions", response_model=dict)
def get_contradictions(
    domain_key: str = Query(...),
    hours: int = Query(48, ge=1, le=720),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """
    Find contradicting claims within a domain's recent extracted claims.
    Returns pairs of claims that appear to conflict.
    """
    from services.fact_verification_service import detect_contradictions
    return detect_contradictions(domain_key, hours=hours, limit=limit)


@router.get("/verification/completeness", response_model=dict)
def get_completeness_assessment(
    domain_key: str = Query(...),
    topic: Optional[str] = Query(None),
    storyline_id: Optional[int] = Query(None),
    hours: int = Query(72, ge=1, le=720),
) -> dict:
    """
    Assess coverage completeness for a topic or storyline: source diversity,
    temporal coverage, sentiment spread, identified gaps.
    """
    if not topic and not storyline_id:
        raise HTTPException(status_code=400, detail="Provide topic or storyline_id")

    from services.fact_verification_service import assess_completeness
    return assess_completeness(domain_key, topic=topic, storyline_id=storyline_id, hours=hours)


@router.post("/verification/batch", response_model=dict)
def verify_recent_claims_batch(
    domain_key: str = Query(...),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(20, ge=1, le=50),
) -> dict:
    """
    Verify the most recent high-confidence claims in a domain.
    Returns per-claim verification status and summary statistics.
    """
    from services.fact_verification_service import verify_recent_claims
    return verify_recent_claims(domain_key, hours=hours, limit=limit)


@router.get("/verification/source_reliability", response_model=dict)
def get_source_reliability(
    source: str = Query(..., description="Source domain name to check"),
) -> dict:
    """Check reliability tier and score for a news source."""
    from services.fact_verification_service import score_source_reliability
    return score_source_reliability(source)
