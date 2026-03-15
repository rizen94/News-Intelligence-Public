"""
Realtime urgent ingest service — create context from payload, optional event detection (P2).
Bypasses batch cadence; request should stay time-bound (e.g. 30s).
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md section 4.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

# In-memory state for streaming_status (last_urgent_at, queue_depth)
_last_urgent_at: Optional[float] = None
_urgent_queue_depth: int = 0


def process_urgent_payload(
    source: str,
    payload: Dict[str, Any],
    priority: str = "immediate",
    bypass_queue: bool = True,
) -> Dict[str, Any]:
    """
    Create a context from the urgent payload (title, content, domain, url); optionally run event detection.
    Returns { context_id?, event_ids?, alert_ids?, error? }.
    """
    global _last_urgent_at, _urgent_queue_depth
    _last_urgent_at = time.time()
    _urgent_queue_depth = max(0, _urgent_queue_depth + 1)

    title = (payload.get("title") or "")[:2000].strip()
    content = (payload.get("content") or payload.get("body") or "")[:500000].strip()
    domain_key = (payload.get("domain") or "politics").strip()
    if domain_key not in ("politics", "finance", "science-tech"):
        domain_key = "politics"
    url = payload.get("url") or ""
    metadata = payload.get("metadata") or {}
    metadata["source"] = source
    metadata["priority"] = priority
    metadata["urgent_at"] = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection()
    if not conn:
        _urgent_queue_depth = max(0, _urgent_queue_depth - 1)
        return {"context_id": None, "event_ids": [], "alert_ids": [], "error": "Database unavailable"}

    context_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.contexts
                (source_type, domain_key, title, content, raw_content, metadata, created_at, updated_at)
                VALUES ('article', %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
                """,
                (
                    domain_key,
                    title or "(no title)",
                    content or "",
                    content or "",
                    json.dumps(metadata),
                ),
            )
            row = cur.fetchone()
            context_id = row[0] if row else None
        conn.commit()
    except Exception as e:
        logger.warning("process_urgent_payload insert: %s", e)
        if conn:
            conn.rollback()
        _urgent_queue_depth = max(0, _urgent_queue_depth - 1)
        return {"context_id": None, "event_ids": [], "alert_ids": [], "error": str(e)}
    finally:
        if conn:
            conn.close()

    _urgent_queue_depth = max(0, _urgent_queue_depth - 1)

    return {"context_id": context_id, "event_ids": [], "alert_ids": [], "domain_key": domain_key}


def get_streaming_status() -> Dict[str, Any]:
    """Return active_streams, last_urgent_at, queue_depth for GET /api/realtime/streaming_status."""
    global _last_urgent_at, _urgent_queue_depth
    return {
        "active_streams": 0,
        "last_urgent_at": _last_urgent_at,
        "queue_depth": _urgent_queue_depth,
    }
