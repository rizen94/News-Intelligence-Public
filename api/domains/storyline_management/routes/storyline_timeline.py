"""
Storyline Timeline & Narrative Routes (v5.0 Phase 4)
Endpoints for building timelines and generating narrative summaries.
"""

from fastapi import APIRouter, HTTPException, Path, Query
import logging

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

_CHRONO_COL_DEFAULTS: dict[str, str] = {
    "date_precision": "'unknown'",
    "location": "NULL",
    "source_count": "1",
    "is_ongoing": "false",
    "storyline_id": "NULL",
    "importance_score": "0.0",
    "extraction_method": "NULL",
    "extraction_confidence": "NULL",
    "canonical_event_id": "NULL",
    "source_article_id": "NULL",
}


def _chronological_event_columns(cursor) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'chronological_events'
        """,
    )
    return {r[0] for r in cursor.fetchall()}


def _chronological_events_select_sql(available: set[str]) -> str:
    """SELECT list for list_domain_events — tolerate missing v5 migration columns."""
    required = ("id", "title", "event_type", "actual_event_date")
    for c in required:
        if c not in available:
            raise RuntimeError(f"chronological_events missing required column {c!r}")

    order = [
        "id",
        "title",
        "event_type",
        "actual_event_date",
        "date_precision",
        "location",
        "source_count",
        "is_ongoing",
        "storyline_id",
        "importance_score",
        "extraction_method",
        "extraction_confidence",
        "canonical_event_id",
        "source_article_id",
    ]
    parts: list[str] = []
    for name in order:
        if name in available:
            parts.append(f"ce.{name}")
        else:
            default = _CHRONO_COL_DEFAULTS.get(name, "NULL")
            parts.append(default)
    return ", ".join(parts)


router = APIRouter(
    tags=["Storyline Timeline"],
    responses={404: {"description": "Not found"}},
)


@router.get("/{domain}/storylines/{storyline_id}/timeline")
async def get_storyline_timeline(
    domain: str = Path(...),
    storyline_id: int = Path(...),
):
    """Build and return a structured chronological timeline for a storyline."""
    from services.timeline_builder_service import TimelineBuilderService

    schema = domain.replace("-", "_")
    if schema not in {"politics", "finance", "science_tech"}:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        svc = TimelineBuilderService(conn, schema_name=schema)
        timeline = svc.build_timeline(storyline_id)
        events = timeline.get("events") or []
        timeline["timeline_status"] = "ok" if events else "empty"
        timeline["timeline_empty"] = not bool(events)
        # Audits: empty timeline is valid — do not use HTTP 404 (avoids false "errors" in UI/logs).
        return {"success": True, "data": timeline}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timeline build failed for storyline {storyline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{domain}/storylines/{storyline_id}/audit")
async def get_storyline_audit(
    domain: str = Path(...),
    storyline_id: int = Path(...),
):
    """Audit counts for storyline vs timeline (chronological_events) and doc/ML metadata."""
    schema = domain.replace("-", "_")
    if schema not in {"politics", "finance", "science_tech"}:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = 'storylines'
                """,
                (schema,),
            )
            available_cols = {r[0] for r in cur.fetchall()}

            optional_cols = (
                "last_refinement",
                "document_version",
                "ml_processing_status",
                "context_last_updated",
            )
            select_optional = []
            for col in optional_cols:
                if col in available_cols:
                    select_optional.append(col)
                else:
                    select_optional.append(f"NULL AS {col}")

            cur.execute(
                f"""
                SELECT id, title, article_count, updated_at, {", ".join(select_optional)}
                FROM {schema}.storylines WHERE id = %s
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Storyline not found")

            cur.execute(
                f"SELECT COUNT(*) FROM {schema}.storyline_articles WHERE storyline_id = %s",
                (storyline_id,),
            )
            storyline_articles_count = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT COUNT(*) FROM public.chronological_events
                WHERE storyline_id = %s::text AND canonical_event_id IS NULL
                """,
                (storyline_id,),
            )
            timeline_event_count = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT COUNT(*) FROM public.chronological_events
                WHERE storyline_id = %s::text AND canonical_event_id IS NOT NULL
                """,
                (storyline_id,),
            )
            merged_duplicate_events_count = int(cur.fetchone()[0])

        conn.close()

        return {
            "success": True,
            "data": {
                "storyline_id": storyline_id,
                "title": row[1],
                "storyline_article_count_column": int(row[2] or 0),
                "storyline_articles_linked": storyline_articles_count,
                "timeline_event_count": timeline_event_count,
                "merged_duplicate_events_count": merged_duplicate_events_count,
                "timeline_status": "ok" if timeline_event_count > 0 else "empty",
                "updated_at": row[3].isoformat() if row[3] else None,
                "last_refinement": row[4].isoformat() if row[4] else None,
                "document_version": row[5],
                "ml_processing_status": row[6],
                "context_last_updated": row[7].isoformat() if row[7] else None,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Storyline audit failed for %s: %s", storyline_id, e)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/storylines/{storyline_id}/narrative")
async def get_storyline_narrative(
    domain: str = Path(...),
    storyline_id: int = Path(...),
    mode: str = Query("chronological", regex="^(chronological|briefing)$"),
):
    """Generate a journalist-quality narrative from the storyline's timeline."""
    from services.timeline_builder_service import TimelineBuilderService
    from services.narrative_synthesis_service import NarrativeSynthesisService

    schema = domain.replace("-", "_")
    if schema not in {"politics", "finance", "science_tech"}:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        tb = TimelineBuilderService(conn, schema_name=schema)
        timeline = tb.build_timeline(storyline_id)
        if not timeline.get("events"):
            raise HTTPException(status_code=404, detail="No events found for this storyline")

        ns = NarrativeSynthesisService()
        try:
            if mode == "briefing":
                result = await ns.generate_briefing(timeline)
            else:
                result = await ns.generate_chronological_narrative(timeline)
        finally:
            await ns.close()

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Narrative generation failed for storyline {storyline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{domain}/events")
async def list_domain_events(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    event_type: str = Query(None),
    ongoing_only: bool = Query(False),
    article_id: int = Query(None),
):
    """List extracted events, optionally filtered by type, ongoing status, or source article."""
    schema = domain.replace("-", "_")
    if schema not in {"politics", "finance", "science_tech"}:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # chronological_events lives in public (see migrations 060, 133). Qualify explicitly so
    # pooled connections with a domain-only search_path still resolve the table.
    ev = "public.chronological_events"

    try:
        cursor = conn.cursor()
        chrono_cols = _chronological_event_columns(cursor)
        if not chrono_cols:
            logger.error("public.chronological_events not found or has no columns (run timeline migrations)")
            raise HTTPException(
                status_code=503,
                detail="chronological_events table is not available; apply database migrations (e.g. 060, 133).",
            )

        try:
            select_list = _chronological_events_select_sql(chrono_cols)
        except RuntimeError as e:
            logger.error("chronological_events schema incomplete: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from e

        conditions: list[str] = []
        filter_params: list = []

        if "source_article_id" in chrono_cols:
            conditions.append(
                f"EXISTS (SELECT 1 FROM {schema}.articles a WHERE a.id = ce.source_article_id)",
            )
        else:
            conditions.append("true")

        if event_type:
            conditions.append("ce.event_type = %s")
            filter_params.append(event_type)
        if ongoing_only:
            if "is_ongoing" in chrono_cols:
                conditions.append("ce.is_ongoing = true")
            else:
                conditions.append("false")
        if article_id:
            if "source_article_id" in chrono_cols:
                conditions.append("ce.source_article_id = %s")
                filter_params.append(article_id)
            else:
                conditions.append("false")

        where = " AND ".join(conditions)
        list_params = list(filter_params) + [limit, offset]

        cursor.execute(f"""
            SELECT {select_list}
            FROM {ev} ce
            WHERE {where}
            ORDER BY ce.actual_event_date DESC NULLS LAST
            LIMIT %s OFFSET %s
        """, list_params)

        events = []
        for r in cursor.fetchall():
            canon = r[12]
            events.append({
                "id": r[0], "title": r[1], "event_type": r[2],
                "event_date": r[3].isoformat() if r[3] else None,
                "date_precision": r[4], "location": r[5],
                "source_count": r[6], "is_ongoing": r[7],
                "storyline_id": r[8],
                "importance": float(r[9]) if r[9] is not None else 0.0,
                "extraction_method": r[10],
                "extraction_confidence": float(r[11]) if r[11] is not None else None,
                "canonical_event_id": canon,
                "dedup_role": "merged_into_other" if canon is not None else "primary_or_unmerged",
                "source_article_id": r[13],
            })

        cursor.execute(
            f"SELECT COUNT(*) FROM {ev} ce WHERE {where}",
            filter_params,
        )
        total = cursor.fetchone()[0]
        cursor.close()

        return {"success": True, "data": events, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Event listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
