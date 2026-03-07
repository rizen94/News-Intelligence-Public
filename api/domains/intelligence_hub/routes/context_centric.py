"""
Context-centric API — Phase 3.1 / 4.2.
Read-only APIs for entity_profiles, contexts, tracked_events, claims.
Flat /api/... routes. See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Body

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

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
    """Map entity_profiles row to dict."""
    return {
        "id": row[0],
        "domain_key": row[1],
        "canonical_entity_id": row[2],
        "compilation_date": str(row[3]) if row[3] else None,
        "sections": row[4],
        "relationships_summary": row[5],
        "metadata": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
        "updated_at": row[8].isoformat() if row[8] else None,
    }


@router.get("/entity_profiles", response_model=dict)
def list_entity_profiles(
    domain_key: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List entity profiles (intelligence.entity_profiles). Optional domain filter."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
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
        return {"items": [_row_to_profile(r) for r in rows], "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning(f"list_entity_profiles: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list entity profiles")


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
    body: dict = Body(..., description="Fields to merge into metadata: importance, entity_type, tracking_params, alert_thresholds"),
) -> dict:
    """Update entity profile metadata (Phase 4.2). Stores importance, entity_type, tracking_params, alert_thresholds in metadata JSONB."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    allowed = {"importance", "entity_type", "tracking_params", "alert_thresholds"}
    updates = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not updates:
        return get_entity_profile(profile_id)
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


def _row_to_context(row: tuple) -> dict:
    """Map contexts row to dict."""
    return {
        "id": row[0],
        "source_type": row[1],
        "domain_key": row[2],
        "title": row[3],
        "content": (row[4][:2000] + "...") if row[4] and len(row[4]) > 2000 else row[4],
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
) -> dict:
    """List intelligence contexts. Optional domain and source_type filters."""
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
        return {"items": [_row_to_context(r) for r in rows], "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning(f"list_contexts: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list contexts")


def _row_to_event(row: tuple) -> dict:
    """Map tracked_events row to dict (id, event_type, event_name, start_date, end_date, geographic_scope, key_participant_entity_ids, milestones, sub_event_ids, created_at, updated_at)."""
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
    }


@router.get("/tracked_events", response_model=dict)
def list_tracked_events(
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """List tracked events (intelligence.tracked_events)."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            if event_type:
                cur.execute(
                    """
                    SELECT id, event_type, event_name, start_date, end_date, geographic_scope,
                           key_participant_entity_ids, milestones, sub_event_ids, created_at, updated_at
                    FROM intelligence.tracked_events
                    WHERE event_type = %s
                    ORDER BY start_date DESC NULLS LAST, updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (event_type, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, event_type, event_name, start_date, end_date, geographic_scope,
                           key_participant_entity_ids, milestones, sub_event_ids, created_at, updated_at
                    FROM intelligence.tracked_events
                    ORDER BY start_date DESC NULLS LAST, updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
        conn.close()
        return {"items": [_row_to_event(r) for r in rows], "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning(f"list_tracked_events: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to list tracked events")


@router.get("/tracked_events/{event_id}", response_model=dict)
def get_tracked_event(event_id: int) -> dict:
    """Get a single tracked event with its chronicles."""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, event_name, start_date, end_date, geographic_scope,
                       key_participant_entity_ids, milestones, sub_event_ids, created_at, updated_at
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
