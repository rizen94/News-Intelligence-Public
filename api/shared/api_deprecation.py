"""Shared helpers for deprecated API endpoints (HTTP 410 Gone)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import Response

DEFAULT_SUNSET = "Fri, 01 Jan 2027 00:00:00 GMT"


def deprecated_gone_response(
    message: str,
    *,
    documentation: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Response:
    """Return HTTP 410 with Deprecation/Sunset headers and migration guidance."""
    payload: dict[str, Any] = {
        "success": False,
        "error": "Endpoint deprecated",
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    if documentation:
        payload["documentation"] = documentation
    if extra:
        payload.update(extra)

    return Response(
        content=json.dumps(payload),
        status_code=410,
        media_type="application/json",
        headers={
            "Deprecation": "true",
            "Sunset": DEFAULT_SUNSET,
            "Link": '</api/docs>; rel="describedby"',
        },
    )
