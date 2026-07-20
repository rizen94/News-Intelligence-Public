"""
Context-centric API — Phase 3.1 / 4.2.
Read-only APIs for entity_profiles, contexts, tracked_events, claims.
Flat /api/... routes. See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import asyncio
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from shared.database.connection import get_db_connection, get_ui_db_connection_context
from shared.domain_registry import (
    domain_key_to_schema,
    get_active_domain_keys,
    get_schema_names_active,
    is_valid_domain_key,
    resolve_domain_schema,
    url_schema_pairs,
)

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


def _safe_count_params(cur, sql: str, params: tuple, default: int = 0) -> int:
    """Parameterized COUNT; return default if relation/column does not exist."""
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row is not None else default
    except Exception:
        return default


def _count_extracted_events_for_status(cur, domain_key: str | None) -> int:
    """
    Same scope as GET /api/{domain}/events — rows in public.chronological_events whose
    source_article_id exists in that domain's articles. When domain_key is None, count events
    tied to any active domain silo (no double-counting).
    """
    try:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'chronological_events'
            """
        )
        cols = {r[0] for r in cur.fetchall()}
        if "source_article_id" not in cols:
            return 0
    except Exception:
        return 0

    if domain_key:
        try:
            schema = domain_key_to_schema(domain_key)
        except KeyError:
            return 0
        try:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM public.chronological_events ce
                WHERE EXISTS (
                    SELECT 1 FROM {schema}.articles a WHERE a.id = ce.source_article_id
                )
                """
            )
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception:
            return 0

    schemas = get_schema_names_active()
    if not schemas:
        return 0
    parts = [
        f"EXISTS (SELECT 1 FROM {schema}.articles a WHERE a.id = ce.source_article_id)"
        for schema in schemas
    ]
    try:
        cur.execute(
            f"""
            SELECT COUNT(*) FROM public.chronological_events ce
            WHERE {" OR ".join(parts)}
            """
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


# Entity routes: domains/intelligence_hub/routes/entity_resolution.py



@router.get("/context_centric/claim_subject_gaps", response_model=dict)
def get_claim_subject_gaps(
    limit: int = Query(200, ge=1, le=2000),
    status: str | None = Query(None, description="open | seeded | ignored"),
    domain_key: str | None = Query(None, description="Filter by domain_key"),
) -> dict:
    """
    Research list: unpromoted high-confidence claim subjects that still lack a matching
    ``entity_profiles`` canonical_name and ``entity_canonical`` row in that domain.
    Call POST .../claim_subject_gaps/refresh to rebuild the snapshot.
    """
    if domain_key and not is_valid_domain_key(domain_key):
        raise HTTPException(status_code=400, detail="invalid domain_key")
    if status and status not in ("open", "seeded", "ignored"):
        raise HTTPException(status_code=400, detail="status must be open, seeded, or ignored")
    from services.claim_subject_gap_service import list_claim_subject_gaps

    rows = list_claim_subject_gaps(limit=limit, status=status, domain_key=domain_key)
    return {"success": True, "count": len(rows), "gaps": rows}


@router.post("/context_centric/claim_subject_gaps/refresh", response_model=dict)
def post_refresh_claim_subject_gaps(
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    max_per_domain: int = Query(2000, ge=100, le=10000),
) -> dict:
    """Rebuild ``intelligence.claim_subject_gap_catalog`` from unpromoted claims (per active domain)."""
    from services.claim_subject_gap_service import refresh_claim_subject_gap_catalog

    return refresh_claim_subject_gap_catalog(
        min_confidence=min_confidence,
        max_per_domain=max_per_domain,
    )


@router.post("/context_centric/claim_subject_gaps/seed", response_model=dict)
def post_seed_claim_subject_gap(
    payload: dict = Body(
        ...,
        example={
            "domain_key": "politics",
            "canonical_name": "Example Organization",
            "entity_type": "ORG",
            "gap_id": 1,
        },
    ),
) -> dict:
    """
    Add a placeholder ``entity_canonical`` row (if missing) and run ``sync_domain_entity_profiles``.
    Use ``gap_id`` from GET claim_subject_gaps to mark the catalog row ``seeded``.
    """
    domain_key = (payload or {}).get("domain_key")
    canonical_name = (payload or {}).get("canonical_name") or (payload or {}).get("sample_subject")
    entity_type = (payload or {}).get("entity_type") or "ORG"
    gap_id = (payload or {}).get("gap_id")
    subject_norm = (payload or {}).get("subject_norm")
    if not domain_key or not canonical_name:
        raise HTTPException(status_code=400, detail="domain_key and canonical_name (or sample_subject) required")
    if not is_valid_domain_key(str(domain_key)):
        raise HTTPException(status_code=400, detail="invalid domain_key")
    from services.claim_subject_gap_service import seed_canonical_from_gap

    gid = int(gap_id) if gap_id is not None else None
    out = seed_canonical_from_gap(
        str(domain_key),
        str(canonical_name),
        str(entity_type),
        gap_id=gid,
        subject_norm=str(subject_norm).lower().strip() if subject_norm else None,
    )
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error", "seed failed"))
    return out


@router.post("/context_centric/claim_subject_gaps/{gap_id}/ignore", response_model=dict)
def post_ignore_claim_subject_gap(
    gap_id: int,
    notes: str | None = Body(None),
) -> dict:
    from services.claim_subject_gap_service import set_gap_status

    ok = set_gap_status(gap_id, "ignored", notes=notes)
    if not ok:
        raise HTTPException(status_code=404, detail="gap not found or update failed")
    return {"success": True, "id": gap_id, "status": "ignored"}


@router.post("/context_centric/claim_subject_gaps/bulk_ignore", response_model=dict)
def post_bulk_ignore_claim_subject_gaps(
    payload: dict = Body(
        ...,
        example={
            "domain_key": "politics",
            "subject_norms": ["generic source", "unnamed official"],
            "notes": "Too vague to resolve",
        },
    ),
) -> dict:
    """
    Upsert many ``ignored`` catalog rows for one domain (CLI: ``claim_subject_gap_bulk_ignore.py``).
    """
    domain_key = (payload or {}).get("domain_key")
    norms = (payload or {}).get("subject_norms") or []
    notes = (payload or {}).get("notes")
    if not domain_key or not isinstance(norms, list):
        raise HTTPException(status_code=400, detail="domain_key and subject_norms (list) required")
    if not is_valid_domain_key(str(domain_key)):
        raise HTTPException(status_code=400, detail="invalid domain_key")
    from services.claim_subject_gap_service import bulk_ignore_subjects

    out = bulk_ignore_subjects(str(domain_key), [str(x) for x in norms], notes=str(notes) if notes else None)
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error", "bulk_ignore failed"))
    return out


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
        from services.story_state_trigger_service import (
            process_fact_change_log,
            process_story_update_queue,
        )
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
    domain_key: str | None = Query(None, description="Run for this domain only; omit to run all domains"),
    limit: int = Query(50, ge=1, le=200, description="Max contexts per domain to check"),
) -> dict:
    """
    Phase 4 RAG: Run watch pattern matching on recent contexts; store pattern_matches and create
    watchlist_alerts when significance >= threshold and storyline is on watchlist.
    See docs/RAG_ENHANCEMENT_ROADMAP.md.
    """
    try:
        from services.watch_pattern_service import run_pattern_matching as run_pattern_matching_svc
        from services.watch_pattern_service import run_pattern_matching_all_domains
        if domain_key:
            if not is_valid_domain_key(domain_key):
                raise HTTPException(
                    status_code=400,
                    detail=f"domain_key must be an active domain ({', '.join(get_active_domain_keys())}) or omitted",
                )
            result = run_pattern_matching_svc(domain_key=domain_key, limit=limit)
        else:
            result = run_pattern_matching_all_domains(limit_per_domain=min(limit, 100))
        return {"success": True, **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("run_pattern_matching: %s", e, exc_info=True)
        return {"success": False, "error": str(e), "contexts_checked": 0, "matches_stored": 0, "alerts_created": 0, "errors": [str(e)]}




@router.post("/context_centric/sync_contexts", response_model=dict)
def sync_contexts(
    domain_key: str | None = Query(None, description="Sync this domain only; omit to sync all"),
    limit: int = Query(100, ge=1, le=500, description="Max articles to backfill per domain (production: 100)"),
) -> dict:
    """
    Backfill intelligence.contexts from domain articles that don't have a context yet.
    Use this to create finance (or other domain) contexts from existing articles when
    politics is filling in but another domain is not yet.
    """
    from services.context_processor_service import sync_domain_articles_to_contexts

    domains = [domain_key] if domain_key else list(get_active_domain_keys())
    if domain_key and not is_valid_domain_key(domain_key):
        raise HTTPException(
            status_code=400,
            detail=f"domain_key must be an active domain ({', '.join(get_active_domain_keys())}) or omitted",
        )

    result: dict[str, int] = {}
    for d in domains:
        try:
            created = sync_domain_articles_to_contexts(d, limit=limit)
            result[d] = created
        except Exception as e:
            logger.warning("sync_contexts %s: %s", d, e)
            result[d] = -1
    return {"success": True, "contexts_created_by_domain": result}


@router.post("/context_centric/cleanup", response_model=dict)
def run_intelligence_cleanup(
    domain_key: str | None = Query(None, description="Clean this domain only; omit for all"),
) -> dict:
    """
    Run the full intelligence cleanup cycle: noise removal, duplicate merge,
    low-value entity pruning, orphan profile cleanup, entity cap, and stale
    event archival. Safe to call repeatedly (idempotent).
    """
    if domain_key and not is_valid_domain_key(domain_key):
        raise HTTPException(
            status_code=400,
            detail=f"domain_key must be an active domain ({', '.join(get_active_domain_keys())}) or omitted",
        )
    from services.intelligence_cleanup_controller import IntelligenceCleanupController
    controller = IntelligenceCleanupController()
    return controller.run(domain_key=domain_key)


@router.post("/context_centric/discover_events", response_model=dict)
async def discover_events(
    domain_key: str | None = Query(None, description="Discover events in this domain only; omit for all"),
    limit: int = Query(100, ge=1, le=500, description="Max contexts to analyze"),
) -> dict:
    """Analyze recent contexts with LLM to discover and create tracked events."""
    from services.event_tracking_service import discover_events_from_contexts
    result = await discover_events_from_contexts(domain_key=domain_key, limit=limit)
    return result


@router.post("/context_centric/review_events", response_model=dict)
async def review_event_coherence_api(
    event_id: int | None = Query(None, description="Review a single event; omit to review all open events"),
    threshold: float = Query(0.5, ge=0.0, le=1.0, description="Relevance threshold — contexts scoring below are removed"),
    auto_remove: bool = Query(True, description="Automatically remove irrelevant contexts"),
) -> dict:
    """
    LLM-powered coherence review: for each context in an event, verify it
    actually belongs. Removes mismatches and logs reasoning.
    """
    from services.event_coherence_reviewer import review_all_open_events, review_event_coherence
    if event_id is not None:
        return await review_event_coherence(event_id, relevance_threshold=threshold, auto_remove=auto_remove)
    return await review_all_open_events(relevance_threshold=threshold, auto_remove=auto_remove)


@router.get("/context_centric/status", response_model=dict)
def context_centric_status(
    domain_key: str | None = Query(
        None,
        description="When set to an active domain key, contexts/entity_profiles/extracted_events "
        "are scoped to this domain. Omit for aggregate totals. "
        "events_stored_total and chronological_events_total are always full-database counts.",
    ),
) -> dict:
    """Return counts for context-centric pipeline (Phase 3.2 quality validation)."""
    if domain_key is not None and not is_valid_domain_key(domain_key):
        raise HTTPException(
            status_code=400,
            detail=f"domain_key must be an active domain ({', '.join(get_active_domain_keys())}) or omitted",
        )

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if domain_key:
                contexts = _safe_count_params(
                    cur,
                    "SELECT COUNT(*) FROM intelligence.contexts WHERE domain_key = %s",
                    (domain_key,),
                )
                article_links = _safe_count_params(
                    cur,
                    "SELECT COUNT(*) FROM intelligence.article_to_context WHERE domain_key = %s",
                    (domain_key,),
                )
                entity_profiles = _safe_count_params(
                    cur,
                    "SELECT COUNT(*) FROM intelligence.entity_profiles WHERE domain_key = %s",
                    (domain_key,),
                )
                mentions = _safe_count_params(
                    cur,
                    """
                    SELECT COUNT(*) FROM intelligence.context_entity_mentions cem
                    JOIN intelligence.contexts c ON c.id = cem.context_id
                    WHERE c.domain_key = %s
                    """,
                    (domain_key,),
                )
            else:
                contexts = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.contexts")
                article_links = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.article_to_context")
                entity_profiles = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.entity_profiles")
                mentions = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.context_entity_mentions")

            entity_mappings = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.old_entity_to_new")
            claims = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.extracted_claims")
            intel_tracked = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.tracked_events")
            extracted_events = _count_extracted_events_for_status(cur, domain_key)
            chronicles = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.event_chronicles")
            pattern_discoveries = _safe_count(cur, "SELECT COUNT(*) FROM intelligence.pattern_discoveries")
            # Full-table totals (always global — hero bar / dashboards; independent of domain_key filter)
            chronological_events_total = _safe_count(
                cur, "SELECT COUNT(*) FROM public.chronological_events"
            )
            try:
                ce = int(chronological_events_total)
                te = int(intel_tracked)
            except (TypeError, ValueError):
                ce, te = 0, 0
            events_stored_total = ce + te
        conn.close()
        return {
            "domain_key": domain_key,
            "contexts": contexts,
            "article_to_context_links": article_links,
            "entity_profiles": entity_profiles,
            "old_entity_to_new_mappings": entity_mappings,
            "context_entity_mentions": mentions,
            "extracted_claims": claims,
            "tracked_events": intel_tracked,
            "extracted_events": extracted_events,
            "chronological_events_total": chronological_events_total,
            "events_stored_total": events_stored_total,
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
    by_domain = {}
    try:
        with conn.cursor() as cur:
            for domain_key, schema in url_schema_pairs():
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
    pattern_type: str | None = Query(None, description="behavioral, temporal, network, event"),
    domain_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    min_context_count: int | None = Query(
        None,
        ge=0,
        le=100000,
        description="Exclude patterns with data.context_count below this (when present)",
    ),
    briefing: bool = Query(
        False,
        description="Briefings Collisions lens: drop weak network co_mentions; rank by context_count",
    ),
) -> dict:
    """List pattern discoveries (Phase 2.2). Optional pattern_type and domain_key filters."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        # Domain listing without an explicit type is the Briefings Collisions consumer —
        # apply the high-signal lens so weak network co_mentions do not flood the feed.
        if domain_key and not pattern_type:
            briefing = True

        where: list[str] = []
        params: list[Any] = []
        if pattern_type:
            where.append("pattern_type = %s")
            params.append(pattern_type)
        if domain_key:
            where.append("domain_key = %s")
            params.append(domain_key)

        # Briefing lens: hide single-article network co_mentions (dominate politics feed).
        effective_min = min_context_count
        if briefing and effective_min is None:
            effective_min = 2
        if briefing:
            where.append(
                """
                NOT (
                    pattern_type = 'network'
                    AND COALESCE(data->>'relation', '') = 'co_mentioned'
                    AND COALESCE((data->>'context_count')::int, 0) < 2
                )
                """
            )
        if effective_min is not None and effective_min > 0:
            where.append(
                """
                (
                    data->>'context_count' IS NULL
                    OR COALESCE((data->>'context_count')::int, 0) >= %s
                )
                """
            )
            params.append(int(effective_min))

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        order_sql = (
            """
            ORDER BY COALESCE((data->>'context_count')::int, 0) DESC NULLS LAST,
                     confidence DESC NULLS LAST,
                     created_at DESC
            """
            if briefing
            else "ORDER BY created_at DESC"
        )
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, pattern_type, domain_key, context_ids, entity_profile_ids,
                       confidence, data, created_at
                FROM intelligence.pattern_discoveries
                {where_sql}
                {order_sql}
                LIMIT %s OFFSET %s
                """,
                tuple(params),
            )
            rows = cur.fetchall()

            # Enrich entity display names for Collisions / Search snippets.
            all_ep_ids: list[int] = []
            for r in rows:
                ids = list(r[4]) if r[4] else []
                all_ep_ids.extend(int(x) for x in ids if x is not None)
            name_by_id: dict[int, str] = {}
            uniq = sorted(set(all_ep_ids))[:200]
            if uniq:
                cur.execute(
                    """
                    SELECT id,
                           LEFT(
                             COALESCE(
                               NULLIF(metadata->>'canonical_name', ''),
                               NULLIF(metadata->>'name', ''),
                               NULLIF(metadata->>'display_name', ''),
                               'entity ' || id::text
                             ),
                             80
                           ) AS nm
                    FROM intelligence.entity_profiles
                    WHERE id = ANY(%s)
                    """,
                    (uniq,),
                )
                for eid, nm in cur.fetchall():
                    name_by_id[int(eid)] = str(nm or f"entity {eid}")

        conn.close()
        items = []
        for r in rows:
            ep_ids = [int(x) for x in (list(r[4]) if r[4] else []) if x is not None]
            entity_names = [name_by_id[i] for i in ep_ids if i in name_by_id][:6]
            raw_data = r[6]
            data_out: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
            # Put a human label first so older Briefings UI (first two data keys) is readable.
            label_bits: list[str] = []
            if entity_names:
                label_bits.append(" · ".join(entity_names[:3]))
            rel = data_out.get("relation")
            if isinstance(rel, str) and rel.strip():
                label_bits.append(rel.replace("_", " "))
            date_v = data_out.get("date")
            if isinstance(date_v, str) and date_v.strip():
                label_bits.append(date_v)
            ctx = data_out.get("context_count")
            if ctx is not None and str(ctx).strip():
                label_bits.append(f"{ctx} contexts")
            if label_bits:
                data_out = {"label": " · ".join(label_bits), **data_out}
            items.append(
                {
                    "id": r[0],
                    "pattern_type": r[1],
                    "domain_key": r[2],
                    "context_ids": list(r[3]) if r[3] else [],
                    "entity_profile_ids": ep_ids,
                    "entity_names": entity_names,
                    "confidence": float(r[5]) if r[5] is not None else None,
                    "data": data_out if data_out else raw_data,
                    "created_at": r[7].isoformat() if r[7] else None,
                }
            )
        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "briefing": briefing,
            "min_context_count": effective_min,
        }
    except Exception as e:
        logger.warning(f"list_pattern_discoveries: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list pattern discoveries")




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


def _contexts_list_where_params(
    domain_key: str | None,
    source_type: str | None,
) -> tuple:
    """Returns (WHERE fragment without WHERE keyword, tuple of bind params)."""
    if domain_key and source_type:
        return "domain_key = %s AND source_type = %s", (domain_key, source_type)
    if domain_key:
        return "domain_key = %s", (domain_key,)
    if source_type:
        return "source_type = %s", (source_type,)
    return "TRUE", tuple()


def _list_contexts_sync(
    domain_key: str | None,
    source_type: str | None,
    limit: int,
    offset: int,
    brief: bool,
) -> dict:
    where_frag, base_params = _contexts_list_where_params(domain_key, source_type)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM intelligence.contexts WHERE {where_frag}",
                base_params,
            )
            total = int(cur.fetchone()[0])
            cur.execute(
                f"""
                SELECT id, source_type, domain_key, title, content, metadata, created_at, updated_at
                FROM intelligence.contexts
                WHERE {where_frag}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*base_params, limit, offset),
            )
            rows = cur.fetchall()
    content_len = 400 if brief else 2000
    return {
        "items": [_row_to_context(r, content_len) for r in rows],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get("/contexts", response_model=dict)
async def list_contexts(
    domain_key: str | None = Query(None),
    source_type: str | None = Query(None, description="e.g. article"),
    limit: int = Query(
        50,
        ge=1,
        le=50_000,
        description="Page size; use offset for pagination. Large limits can be slow without brief=true.",
    ),
    offset: int = Query(0, ge=0),
    brief: bool = Query(False, description="If true, truncate content for faster list load"),
) -> dict:
    """List intelligence contexts. Optional domain and source_type filters. Use brief=True for list views."""
    try:
        return await asyncio.to_thread(
            _list_contexts_sync, domain_key, source_type, limit, offset, brief
        )
    except Exception as e:
        logger.warning(f"list_contexts: {e}")
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
            related: dict = {"topics": [], "storylines": []}
            try:
                cur.execute(
                    "SELECT article_id FROM intelligence.article_to_context WHERE context_id = %s LIMIT 1",
                    (context_id,),
                )
                link_row = cur.fetchone()
                if link_row:
                    article_id = link_row[0]
                    schema = resolve_domain_schema(ctx["domain_key"])
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
                    try:
                        cur.execute(
                            f"""
                            SELECT t.id, t.name FROM {schema}.article_topic_assignments ata
                            JOIN {schema}.topics t ON t.id = ata.topic_id
                            WHERE ata.article_id = %s
                            ORDER BY t.name
                            LIMIT 50
                            """,
                            (article_id,),
                        )
                        related["topics"] = [{"id": r[0], "name": r[1]} for r in cur.fetchall()]
                    except Exception as te:
                        logger.debug("get_context topics: %s", te)
                    try:
                        cur.execute(
                            f"""
                            SELECT DISTINCT s.id, s.title FROM {schema}.storyline_articles sa
                            JOIN {schema}.storylines s ON s.id = sa.storyline_id
                            WHERE sa.article_id = %s
                            ORDER BY s.title NULLS LAST
                            LIMIT 50
                            """,
                            (article_id,),
                        )
                        related["storylines"] = [{"id": r[0], "title": r[1]} for r in cur.fetchall()]
                    except Exception as se:
                        logger.debug("get_context storylines: %s", se)
            except Exception as e:
                logger.debug(f"get_context article lookup: {e}")

            ctx["article"] = article
            ctx["related"] = related
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


@router.post("/contexts/{context_id}/grouping_feedback", response_model=dict)
def post_context_grouping_feedback(
    context_id: int,
    body: dict = Body(..., description="grouping_type, judgment; optional grouping_id, grouping_label, notes, judged_by"),
) -> dict:
    """Record whether this context belongs with a topic/storyline/pattern (human audit / training signal)."""
    from services.context_grouping_feedback_service import submit_context_grouping_feedback

    grouping_type = (body.get("grouping_type") or "").strip()
    judgment = (body.get("judgment") or "").strip()
    grouping_id = body.get("grouping_id")
    if grouping_id is not None:
        try:
            grouping_id = int(grouping_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="grouping_id must be an integer")
    result = submit_context_grouping_feedback(
        context_id=context_id,
        grouping_type=grouping_type,
        judgment=judgment,
        grouping_id=grouping_id,
        grouping_label=body.get("grouping_label"),
        notes=body.get("notes"),
        judged_by=body.get("judged_by"),
    )
    if not result.get("success"):
        msg = result.get("error", "Unknown error")
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "data": {"id": result.get("id"), "judged_at": result.get("judged_at")}, "message": None}


@router.get("/contexts/{context_id}/grouping_feedback", response_model=dict)
def get_context_grouping_feedback(
    context_id: int,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List grouping judgments for a context (newest first)."""
    from services.context_grouping_feedback_service import list_context_grouping_feedback

    result = list_context_grouping_feedback(context_id, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to list feedback"))
    return {"success": True, "data": {"items": result.get("items", [])}, "message": None}


_EVENT_COLS = """id, event_type, event_name, start_date, end_date, geographic_scope,
                   key_participant_entity_ids, milestones, sub_event_ids, created_at, updated_at, domain_keys,
                   editorial_briefing, editorial_briefing_json, briefing_version, briefing_status,
                   global_narrative, narrative_lenses, global_narrative_version, global_narrative_updated_at, narrative_lenses_updated_at"""


def _row_to_event(row: tuple) -> dict:
    """Map tracked_events row to dict, including editorial briefing fields."""
    out = {
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
    if len(row) > 16:
        out["global_narrative"] = row[16]
    if len(row) > 17 and row[17] is not None:
        out["narrative_lenses"] = row[17] if isinstance(row[17], dict) else {}
    else:
        out["narrative_lenses"] = {}
    if len(row) > 18:
        out["global_narrative_version"] = row[18]
    if len(row) > 19 and row[19]:
        out["global_narrative_updated_at"] = row[19].isoformat()
    if len(row) > 20 and row[20]:
        out["narrative_lenses_updated_at"] = row[20].isoformat()
    return out


def _enrich_developments_with_context_titles(cur, developments: Any) -> list:
    """Add title and domain_key to context-based developments missing title."""
    if not developments:
        return []
    devs = list(developments) if isinstance(developments, list) else []
    if not devs:
        return devs
    missing_ids: set[int] = set()
    for d in devs:
        if not isinstance(d, dict):
            continue
        cid = d.get("context_id")
        if cid is not None and not d.get("title"):
            try:
                missing_ids.add(int(cid))
            except (TypeError, ValueError):
                pass
    title_map: dict[int, tuple[str | None, str | None]] = {}
    if missing_ids:
        cur.execute(
            """
            SELECT id, title, domain_key
            FROM intelligence.contexts
            WHERE id = ANY(%s)
            """,
            (list(missing_ids),),
        )
        for r in cur.fetchall() or []:
            title_map[int(r[0])] = (r[1], r[2])
    enriched: list = []
    for d in devs:
        if not isinstance(d, dict):
            enriched.append(d)
            continue
        out = dict(d)
        cid = out.get("context_id")
        if cid is not None and not out.get("title"):
            try:
                info = title_map.get(int(cid))
                if info:
                    if info[0]:
                        out["title"] = info[0]
                    if info[1] and not out.get("domain_key"):
                        out["domain_key"] = info[1]
            except (TypeError, ValueError):
                pass
        enriched.append(out)
    return enriched


def _enrich_chronicles_developments(cur, chronicles: list[dict]) -> list[dict]:
    """Enrich all chronicle developments with context titles where missing."""
    for ch in chronicles:
        ch["developments"] = _enrich_developments_with_context_titles(cur, ch.get("developments"))
    return chronicles


def _list_tracked_events_sync(
    event_type: str | None,
    domain_key: str | None,
    limit: int,
    offset: int,
) -> dict:
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
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '5s'")
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
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/tracked_events", response_model=dict)
async def list_tracked_events(
    event_type: str | None = Query(None),
    domain_key: str | None = Query(None, description="Filter: events that include this domain"),
    limit: int = Query(
        50,
        ge=1,
        le=50_000,
        description="Page size; use offset for pagination.",
    ),
    offset: int = Query(0, ge=0),
) -> dict:
    """List tracked events. Events can span multiple domains; domain_key filters to events that include that domain."""
    try:
        return await asyncio.to_thread(
            _list_tracked_events_sync, event_type, domain_key, limit, offset
        )
    except Exception as e:
        logger.warning(f"list_tracked_events: {e}")
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
                ORDER BY update_date DESC, id DESC
                """,
                (event_id,),
            )
            chronicles = []
            seen_days: set[str] = set()
            event_name = event.get("event_name") or ""
            for r in cur.fetchall():
                day = str(r[1]) if r[1] else f"id-{r[0]}"
                if day in seen_days:
                    continue
                seen_days.add(day)
                raw_devs = r[2] if isinstance(r[2], list) else []
                if isinstance(r[2], str):
                    try:
                        import json as _json
                        raw_devs = _json.loads(r[2])
                    except Exception:
                        raw_devs = []
                try:
                    from services.event_tracking_service import development_title_matches_event
                    filtered_devs = []
                    seen_titles: set[str] = set()
                    for d in raw_devs:
                        if not isinstance(d, dict):
                            continue
                        title = d.get("title")
                        if not development_title_matches_event(event_name, title):
                            continue
                        title_key = re.sub(r"\s+", " ", (title or "").strip().lower())[:120]
                        if title_key and title_key in seen_titles:
                            continue
                        if title_key:
                            seen_titles.add(title_key)
                        filtered_devs.append(d)
                except Exception:
                    filtered_devs = raw_devs if isinstance(raw_devs, list) else []
                analysis = r[3] if isinstance(r[3], dict) else r[3]
                if filtered_devs:
                    momentum = min(1.0, len(filtered_devs) * 0.1)
                else:
                    momentum = None
                    # Drop polluted attachment blurbs when nothing on-topic remains.
                    if isinstance(analysis, dict):
                        analysis = {
                            **analysis,
                            "latest_developments": None,
                            "context_count": len(filtered_devs),
                        }
                chronicles.append({
                    "id": r[0],
                    "update_date": str(r[1]) if r[1] else None,
                    "developments": filtered_devs,
                    "analysis": analysis,
                    "predictions": r[4],
                    "momentum_score": momentum,
                    "created_at": r[6].isoformat() if r[6] else None,
                })
            # Collapse empty day shells that only repeat the same summary.
            with_devs = [c for c in chronicles if c.get("developments")]
            if with_devs:
                chronicles = with_devs
            elif chronicles:
                chronicles = [chronicles[0]]
            event["chronicles"] = _enrich_chronicles_developments(cur, chronicles)
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


@router.post("/tracked_events/{event_id}/narrative_stack", response_model=dict)
async def post_tracked_event_narrative_stack(event_id: int) -> dict:
    """
    Build domain-neutral ``global_narrative`` and per-domain ``narrative_lenses`` for this event.
    Lenses are generated only from the global narrative (plus metadata), not raw chronicles.
    Requires DB migration ``196_tracked_event_narrative_lenses.sql``.
    """
    from services.tracked_event_narrative_service import generate_narrative_stack_for_event

    result = await generate_narrative_stack_for_event(event_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "narrative_stack_failed"),
        )
    return {"success": True, "data": result, "message": None}


@router.get("/tracked_events/{event_id}/linked_events", response_model=dict)
def get_tracked_event_linked_events(
    event_id: int,
    limit: int = Query(12, ge=1, le=30),
) -> dict:
    """
    Other tracked_events meaningfully related to this one.

    Prefer entity_overlap / thematic pairwise correlations. Mega temporal bags
    (100 co-window events) are ignored — those produce junk like ICE stories
    linked to an NVIDIA SEC probe.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    items: list[dict] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_name,
                       COALESCE(key_participant_entity_ids, '[]'::jsonb)
                FROM intelligence.tracked_events
                WHERE id = %s
                """,
                (event_id,),
            )
            self_row = cur.fetchone()
            if not self_row:
                conn.close()
                return {"items": [], "limit": limit}
            self_name = self_row[0] or ""
            self_ents_raw = self_row[1]
            self_ents: set[int] = set()
            if isinstance(self_ents_raw, list):
                for x in self_ents_raw:
                    if isinstance(x, int):
                        self_ents.add(x)
                    elif isinstance(x, dict) and "id" in x:
                        try:
                            self_ents.add(int(x["id"]))
                        except (TypeError, ValueError):
                            pass

            # Pairwise-quality correlations only (skip giant temporal dumps).
            cur.execute(
                """
                SELECT correlation_type, correlation_strength, event_ids,
                       COALESCE(entity_profile_ids, '{}') AS entity_profile_ids,
                       COALESCE(cardinality(event_ids), 0) AS n_events
                FROM intelligence.cross_domain_correlations
                WHERE %s = ANY(event_ids)
                  AND (
                    correlation_type IN ('entity_overlap', 'thematic')
                    OR cardinality(event_ids) BETWEEN 2 AND 12
                  )
                ORDER BY correlation_strength DESC NULLS LAST, discovered_at DESC NULLS LAST
                LIMIT 40
                """,
                (event_id,),
            )
            rows = cur.fetchall() or []

        scored: dict[int, float] = {}
        for r in rows:
            ctype = (r[0] or "") if len(r) > 0 else ""
            strength = float(r[1] or 0)
            eids = list(r[2]) if r[2] else []
            n_events = int(r[4] or len(eids))
            # Hard reject mega-bags even if mislabeled thematic.
            if n_events > 12:
                continue
            for eid in eids:
                if not isinstance(eid, int) or eid == event_id:
                    continue
                boost = strength
                if ctype == "entity_overlap":
                    boost += 0.25
                scored[eid] = max(scored.get(eid, 0.0), boost)

        if not scored:
            conn.close()
            return {"items": [], "limit": limit}

        ranked_ids = sorted(scored.keys(), key=lambda i: scored[i], reverse=True)[
            : limit * 3
        ]
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_EVENT_COLS}
                FROM intelligence.tracked_events
                WHERE id = ANY(%s)
                """,
                (ranked_ids,),
            )
            by_id = {}
            for row in cur.fetchall() or []:
                ev = _row_to_event(row)
                by_id[ev["id"]] = ev

        from services.event_tracking_service import (
            development_title_matches_event,
            significant_event_tokens,
        )

        self_tokens = {t.lower() for t in significant_event_tokens(self_name)}
        for eid in ranked_ids:
            ev = by_id.get(eid)
            if not ev:
                continue
            other_name = ev.get("event_name") or ""
            # Require title relevance OR shared participants.
            title_ok = development_title_matches_event(self_name, other_name) or (
                bool(self_tokens)
                and len(
                    self_tokens
                    & {t.lower() for t in significant_event_tokens(other_name)}
                )
                >= 1
            )
            other_ents: set[int] = set()
            raw_ents = ev.get("key_participant_entity_ids") or []
            if isinstance(raw_ents, list):
                for x in raw_ents:
                    if isinstance(x, int):
                        other_ents.add(x)
            entity_ok = bool(self_ents & other_ents)
            if not title_ok and not entity_ok:
                continue
            items.append(ev)
            if len(items) >= limit:
                break
        conn.close()
    except Exception as e:
        logger.warning("get_tracked_event_linked_events: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list linked events")
    return {"items": items, "limit": limit}


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
    try:
        from services.saved_intel_service import save_intel_output

        save_intel_output(
            content_type="event_report",
            subject_type="tracked_event",
            subject_id=event_id,
            content_md=result.get("report_md") or "",
            title=result.get("event_name"),
            metadata={
                "context_ids_included": result.get("context_ids_included") or [],
                "chronicle_count": result.get("chronicle_count", 0),
                "context_count": result.get("context_count", 0),
            },
            generated_at=result.get("generated_at"),
        )
    except Exception as e:
        logger.warning("save_intel_output event_report: %s", e)
    return result


@router.get("/saved_intel_outputs", response_model=dict)
def list_saved_intel_outputs_route(
    domain_key: str | None = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List append-only reading history of generated intel outputs."""
    from services.saved_intel_service import list_saved_intel_outputs

    return list_saved_intel_outputs(domain_key=domain_key, limit=limit, offset=offset)


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
    source_type: str | None = Query(None),
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
                    SELECT id, source_type, source_name, source_url, title, publication_date, document_type,
                           file_hash, file_size_bytes, extraction_method, created_at
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
                    SELECT id, source_type, source_name, source_url, title, publication_date, document_type,
                           file_hash, file_size_bytes, extraction_method, created_at
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
                "file_hash": r[7],
                "file_size_bytes": r[8],
                "extraction_method": r[9],
                "created_at": r[10].isoformat() if r[10] else None,
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
                       extracted_sections, key_findings, entities_mentioned, citations, metadata,
                       file_hash, file_size_bytes, extraction_method, created_at, updated_at
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
            "file_hash": row[13],
            "file_size_bytes": row[14],
            "extraction_method": row[15],
            "created_at": row[16].isoformat() if row[16] else None,
            "updated_at": row[17].isoformat() if row[17] else None,
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
    domain_key: str | None = Query(None),
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
    domain_key: str | None = Query(None, description="Run for this domain only; omit for all domains"),
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
    context_id: int | None = Query(None),
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


@router.get("/claims/similar_clusters", response_model=dict)
def similar_claim_clusters(
    since_days: int = Query(7, ge=1, le=365),
    min_count: int = Query(3, ge=2, le=100, description="Min claims per subject cluster"),
    min_contexts: int = Query(2, ge=1, le=50, description="Min distinct contexts"),
    domain_key: str | None = Query(None),
    q: str | None = Query(None, description="ILIKE filter on subject/predicate/object"),
    mode: str = Query("both", description="subject | triple | both"),
    limit: int = Query(40, ge=1, le=100),
) -> dict:
    """Cluster similar extracted_claims for agent / discovery review."""
    if mode not in ("subject", "triple", "both"):
        raise HTTPException(status_code=400, detail="mode must be subject, triple, or both")
    try:
        from services.claim_similarity_service import scan_similar_claim_clusters

        return scan_similar_claim_clusters(
            since_days=since_days,
            min_claim_count=min_count,
            min_context_count=min_contexts,
            domain_key=domain_key,
            query=q,
            mode=mode,  # type: ignore[arg-type]
            limit=limit,
        )
    except Exception as e:
        logger.warning("similar_claim_clusters: %s", e)
        raise HTTPException(status_code=500, detail="Failed to scan similar claims")


@router.get("/context_centric/search", response_model=dict)
def context_centric_search(
    q: str | None = Query(None, description="Full-text search (claims subject/predicate/object, context title/content)"),
    claim_subject: str | None = Query(None, description="Filter claims by subject text (ILIKE)"),
    claim_predicate: str | None = Query(None, description="Filter claims by predicate text (ILIKE)"),
    entity_id: int | None = Query(None, description="Filter by entity_profile_id (claims/contexts mentioning this entity)"),
    pattern_type: str | None = Query(None, description="Filter pattern_discoveries by type: behavioral, temporal, network, event"),
    valid_from: str | None = Query(None, description="Temporal: claims valid on or after this date (YYYY-MM-DD)"),
    valid_to: str | None = Query(None, description="Temporal: claims valid on or before this date (YYYY-MM-DD)"),
    domain_key: str | None = Query(None, description="Restrict to domain"),
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
# Content synthesis endpoints (centralized intelligence aggregation)
# ---------------------------------------------------------------------------

@router.get("/synthesis/domain", response_model=dict)
def get_domain_synthesis(
    domain_key: str = Query(...),
    hours: int = Query(24, ge=1, le=168),
    max_articles: int = Query(30, ge=1, le=100),
    max_quality_tier: int | None = Query(None, ge=1, le=4, description="Only include articles with quality_tier <= this (1=best, 4=worst)"),
) -> dict:
    """
    Synthesize all intelligence for a domain within a time window.
    Returns articles with ml_data, storylines with editorial ledes, events with briefings,
    entities with mention counts, claims, and patterns — all in one response.
    """
    from services.content_synthesis_service import synthesize_domain_context
    return synthesize_domain_context(
        domain_key, hours=hours, max_articles=max_articles, max_quality_tier=max_quality_tier,
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
    Full verification for one claim: governance-weighted corroboration (excludes originating
    article), contradictions, originating-source tier, reference signals (Wikipedia, Wikidata,
    GDELT, finance SEC articles, internal peers), optional borderline LLM entailment.
    Returns verification_status, confidence, reference_checks, reference_boosts.
    """
    from services.fact_verification_service import verify_claim
    return verify_claim(claim_id, domain_key, hours=hours)


@router.post("/verification/corroborate", response_model=dict)
def corroborate_claim_text(
    body: dict = Body(..., examples=[{"claim_text": "Federal Reserve raises interest rates", "domain_key": "finance"}]),
) -> dict:
    """
    Corroborate claim text against domain articles (flexible full-text, YAML source_credibility
    weights). Status may be corroborated, partially_corroborated, authoritative_single,
    single_established, single_source, or unverified.
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
    topic: str | None = Query(None),
    storyline_id: int | None = Query(None),
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
