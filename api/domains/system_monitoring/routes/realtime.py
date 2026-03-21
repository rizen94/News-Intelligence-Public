"""
Realtime / urgent ingest API (P2). Request time-bound (e.g. 30s).
POST /api/realtime/process_urgent, GET /api/realtime/streaming_status.
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Body
from services.realtime_urgent_service import get_streaming_status, process_urgent_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["Realtime / urgent ingest"])


@router.post("/process_urgent")
async def post_process_urgent(
    source: str = Body("webhook", embed=True),
    payload: dict[str, Any] = Body(..., embed=True),
    priority: str = Body("immediate", embed=True),
    bypass_queue: bool = Body(True, embed=True),
    run_event_detection: bool = Body(False, embed=True),
) -> dict[str, Any]:
    """
    Ingest urgent content (streaming/webhook). Creates a context; optionally runs event detection (time-bound).
    Payload should include title, content, and optionally domain, url, metadata.
    """
    result = process_urgent_payload(
        source=source,
        payload=payload,
        priority=priority,
        bypass_queue=bypass_queue,
    )
    if result.get("error"):
        return {"success": False, "data": None, "message": result["error"]}

    event_ids = list(result.get("event_ids") or [])
    if run_event_detection and result.get("context_id"):
        try:
            from services.event_tracking_service import discover_events_from_contexts

            ev_result = await asyncio.wait_for(
                discover_events_from_contexts(
                    domain_key=result.get("domain_key") or "politics",
                    limit=5,
                ),
                timeout=25.0,
            )
            if ev_result.get("events") and ev_result.get("events_created"):
                event_ids = [e.get("event_id") for e in ev_result["events"] if e.get("event_id")]
        except asyncio.TimeoutError:
            logger.debug("Urgent event detection timed out")
        except Exception as e:
            logger.debug("Urgent event detection failed: %s", e)

    return {
        "success": True,
        "data": {
            "context_id": result.get("context_id"),
            "event_ids": event_ids,
            "alert_ids": result.get("alert_ids") or [],
        },
        "message": None,
    }


@router.get("/streaming_status")
def get_realtime_streaming_status() -> dict[str, Any]:
    """Return active_streams, last_urgent_at, queue_depth."""
    status = get_streaming_status()
    return {
        "success": True,
        "data": {
            "active_streams": status.get("active_streams", 0),
            "last_urgent_at": status.get("last_urgent_at"),
            "queue_depth": status.get("queue_depth", 0),
        },
        "message": None,
    }
