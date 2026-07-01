"""NDJSON debug logs for Monitor pulse accuracy (session e7d0f8)."""

from __future__ import annotations

import json
import time
from pathlib import Path

_SESSION = "e7d0f8"
_LOG = Path(__file__).resolve().parents[2] / ".cursor" / "debug-e7d0f8.log"


def monitor_pulse_debug(
    location: str,
    message: str,
    data: dict,
    *,
    hypothesis_id: str,
    run_id: str = "pre-fix",
) -> None:
    # region agent log
    try:
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessionId": _SESSION,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with _LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
    # endregion
