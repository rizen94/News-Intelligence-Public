"""Session debug NDJSON logger (agent debug mode). No secrets."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

_LOG_PATH = Path(
    os.environ.get(
        "CURSOR_DEBUG_LOG_PATH",
        "/home/pete/Documents/projects/News Intelligence/.cursor/debug-b4785d.log",
    )
)
_SESSION = os.environ.get("CURSOR_DEBUG_SESSION_ID", "b4785d")
# Ingest runs on the Cursor host (often PopOS); Widow API dual-writes so logs land in-session.
_INGEST = os.environ.get(
    "CURSOR_DEBUG_INGEST_URL",
    "http://192.168.93.99:7678/ingest/79eeed92-cd4a-41d4-872f-8f142138548b",
)


def agent_dbg(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
    *,
    run_id: str = "pre",
) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        line = json.dumps(payload, default=str) + "\n"
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with _LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
        try:
            req = urllib.request.Request(
                _INGEST,
                data=line.encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Debug-Session-Id": _SESSION,
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.4)
        except Exception:
            pass
    except Exception:
        pass
    # #endregion
