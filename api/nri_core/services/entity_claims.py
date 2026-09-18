"""Claims linked to FtM-resolved entity mentions."""

from __future__ import annotations

import logging
from typing import Any

from config.investigation_tables import T_FTM_ENTITY_CACHE, T_RESOLVED_MENTIONS
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def get_entity_claims_in_context(
    entity_profile_id: int,
    context_id: int | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed", "items": []}

    where = ["rm.entity_profile_id = %s", "rm.status = 'auto_linked'"]
    params: list[Any] = [entity_profile_id]
    if context_id is not None:
        where.append("rm.context_id = %s")
        params.append(context_id)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT
                    ec.id,
                    ec.context_id,
                    ec.subject_text,
                    ec.predicate_text,
                    ec.object_text,
                    ec.confidence,
                    ec.created_at,
                    rm.mention_text,
                    fc.caption AS ftm_caption
                FROM {T_RESOLVED_MENTIONS} rm
                LEFT JOIN {T_FTM_ENTITY_CACHE} fc ON fc.ftm_id = rm.ftm_id
                JOIN intelligence.extracted_claims ec ON ec.context_id = rm.context_id
                  AND (
                    ec.subject_text ILIKE '%%' || rm.mention_text || '%%'
                    OR ec.object_text ILIKE '%%' || rm.mention_text || '%%'
                    OR (fc.caption IS NOT NULL AND (
                      ec.subject_text ILIKE '%%' || fc.caption || '%%'
                      OR ec.object_text ILIKE '%%' || fc.caption || '%%'
                    ))
                  )
                WHERE {' AND '.join(where)}
                ORDER BY ec.created_at DESC NULLS LAST, ec.id DESC
                LIMIT %s
                """,
                (*params, limit),
            )
            items = []
            for row in cur.fetchall():
                items.append(
                    {
                        "id": row[0],
                        "context_id": row[1],
                        "subject_text": row[2],
                        "predicate_text": row[3],
                        "object_text": row[4],
                        "confidence": float(row[5]) if row[5] is not None else None,
                        "created_at": row[6].isoformat() if row[6] else None,
                        "mention_text": row[7],
                        "ftm_caption": row[8],
                    }
                )
        conn.close()
        return {"success": True, "items": items, "limit": limit}
    except Exception as e:
        logger.warning("get_entity_claims_in_context: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e), "items": []}
