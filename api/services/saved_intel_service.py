"""
Append-only persistence for generated intel outputs (reading history).

Never deletes or overwrites on regenerate — each generation appends a row.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)


def save_intel_output(
    *,
    content_type: str,
    subject_type: str,
    subject_id: int,
    content_md: str,
    domain_key: str | None = None,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> int | None:
    """Append one generated intel output. Returns new row id or None on failure."""
    if not content_md or not content_md.strip():
        return None
    ts = generated_at
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            ts = None
    if ts is None:
        ts = datetime.now(timezone.utc)
    meta_json = json.dumps(metadata or {})
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.saved_intel_outputs
                    (content_type, domain_key, subject_type, subject_id, title, content_md, metadata, generated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    RETURNING id
                    """,
                    (
                        content_type,
                        domain_key,
                        subject_type,
                        subject_id,
                        title,
                        content_md,
                        meta_json,
                        ts,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return row[0] if row else None
    except Exception as e:
        logger.warning("save_intel_output failed (%s/%s): %s", content_type, subject_id, e)
        return None


def list_saved_intel_outputs(
    domain_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List saved intel outputs, newest first. Optional domain_key filter."""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conditions: list[str] = []
    params: list[Any] = []
    if domain_key:
        conditions.append("domain_key = %s")
        params.append(domain_key)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, content_type, domain_key, subject_type, subject_id, title,
                           LEFT(content_md, 500) AS content_preview,
                           metadata, generated_at, created_at
                    FROM intelligence.saved_intel_outputs
                    {where}
                    ORDER BY generated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "content_type": r[1],
                "domain_key": r[2],
                "subject_type": r[3],
                "subject_id": r[4],
                "title": r[5],
                "content_preview": r[6],
                "metadata": r[7] if isinstance(r[7], dict) else {},
                "generated_at": r[8].isoformat() if r[8] else None,
                "created_at": r[9].isoformat() if r[9] else None,
            })
        return {"items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("list_saved_intel_outputs: %s", e)
        return {"items": [], "limit": limit, "offset": offset, "error": str(e)}
