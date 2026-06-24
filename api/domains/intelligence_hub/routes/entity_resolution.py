"""
Entity resolution, profiles, and position tracking routes.

Moved from context_centric.py — /api/entities/*, /api/entity_profiles/*, etc.
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from shared.database.connection import get_db_connection
from shared.domain_registry import get_active_domain_keys, is_valid_domain_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Entity resolution"],
)


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


@router.post("/context_centric/sync_entity_profiles", response_model=dict)
def sync_entity_profiles(domain_key: str | None = Query(None, description="Sync this domain only; omit to sync all")) -> dict:
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
    from services.entity_profile_sync_service import (
        backfill_entity_canonical,
        sync_domain_entity_profiles,
    )

    domains = [domain_key] if domain_key else list(get_active_domain_keys())
    if domain_key and not is_valid_domain_key(domain_key):
        raise HTTPException(
            status_code=400,
            detail=f"domain_key must be an active domain ({', '.join(get_active_domain_keys())}) or omitted",
        )

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
    domain_key: str | None = Query(None, description="Filter by domain"),
    limit: int = Query(
        50,
        ge=1,
        le=50_000,
        description="Page size; use offset for pagination. Large limits can be slow without brief=true.",
    ),
    offset: int = Query(0, ge=0),
    brief: bool = Query(False, description="If true, omit sections/relationships for faster list load"),
) -> dict:
    """List entity profiles (intelligence.entity_profiles). Use brief=True for list views (skips heavy columns)."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if domain_key:
                cur.execute(
                    "SELECT COUNT(*) FROM intelligence.entity_profiles WHERE domain_key = %s",
                    (domain_key,),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM intelligence.entity_profiles")
            total = int(cur.fetchone()[0])
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
        return {"items": [to_item(r) for r in rows], "limit": limit, "offset": offset, "total": total}
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
            import json
            from datetime import datetime
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
    domain_key: str | None = Query(None, description="Domain to process; omit for all"),
    min_mentions: int = Query(2, description="Minimum articles for an alias to be added"),
) -> dict:
    """
    Batch-populate entity_canonical.aliases from article_entities mention variants.
    """
    from services.entity_resolution_service import populate_aliases_from_mentions

    domains = [domain_key] if domain_key else list(get_active_domain_keys())
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
    domain_key: str | None = Query(None, description="Domain to auto-merge; omit for all"),
    min_confidence: float = Query(0.9, description="Only merge above this confidence (use 0.6 for Trump/Donald Trump–style consolidation)"),
) -> dict:
    """
    Automatically merge canonical entities with confidence >= threshold.
    Keeps the primary (full) name and merges variants into it (variants become aliases).
    Use min_confidence=0.6 to consolidate last-name and variant matches (e.g. Trump, Donald J Trump, King Trump).
    """
    from services.entity_resolution_service import auto_merge_high_confidence

    domains = [domain_key] if domain_key else list(get_active_domain_keys())
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
    entity_type: str | None = Query(None, description="Filter by type (person, organization, subject, recurring_event)"),
    search: str | None = Query(None, description="Search canonical_name or aliases"),
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


# Investigation routes: domains/intelligence_hub/routes/investigation.py


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
    domain_key: str | None = Query(None),
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
