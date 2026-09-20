#!/usr/bin/env python3
"""Smoke-test critical API routes after consolidation deploy.

Usage (on Widow):
  cd /opt/news-intelligence && set -a && source .env && set +a
  PYTHONPATH=api python3 api/scripts/verify_api_wiring_smoke.py

Prints JSON summary to stdout.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

BASE = os.environ.get("SMOKE_API_BASE", "http://127.0.0.1:8000").rstrip("/")

# Frontend + AGENTS.md critical GET probes (no destructive POSTs)
SMOKE_PATHS: tuple[tuple[str, str], ...] = (
    ("H1", "/api/ping"),
    ("H1", "/api/system_monitoring/health"),
    ("H2", "/api/system_monitoring/monitoring/overview"),
    ("H2", "/api/system_monitoring/automation/status"),
    ("H2", "/api/system_monitoring/processing_progress?include_pending_metrics=false"),
    ("H3", "/api/system_monitoring/route_supervisor/health"),
    ("H3", "/api/orchestrator/status"),
    ("H4", "/api/context_centric/status"),
    ("H4", "/api/investigation/health"),
    ("H4", "/api/tracking/discovery?include_vault_reconcile=false"),
    ("H4", "/api/investigation/graph_neighbors?seed_kind=entity&seed_id=1&max_depth=1&max_nodes=5"),
    ("H5", "/api/legal/storylines?limit=1"),
    ("H5", "/api/politics/storylines?limit=1"),
    ("H5", "/api/finance/storylines?limit=1"),
)


def _emit(section: str, location: str, message: str, data: dict) -> None:
    payload = {
        "section": section,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    print(json.dumps(payload, default=str))


def _probe(path: str, timeout: float = 15.0) -> dict:
    url = f"{BASE}{path}"
    started = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(512)
            return {
                "path": path,
                "status": resp.status,
                "ms": round((time.time() - started) * 1000, 1),
                "ok": 200 <= resp.status < 400,
                "body_prefix": body[:120].decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as exc:
        return {
            "path": path,
            "status": exc.code,
            "ms": round((time.time() - started) * 1000, 1),
            "ok": False,
            "error": str(exc.reason),
        }
    except Exception as exc:
        return {
            "path": path,
            "status": None,
            "ms": round((time.time() - started) * 1000, 1),
            "ok": False,
            "error": str(exc),
        }


def _import_route_count() -> dict:
    try:
        from main import app

        paths = sorted({r.path for r in app.routes if hasattr(r, "path") and r.path})
        return {"import_ok": True, "route_count": len(paths)}
    except Exception as exc:
        return {"import_ok": False, "error": str(exc)[:300]}


def main() -> int:
    _emit("start", "verify_api_wiring_smoke.py:main", "smoke_start", {"base": BASE})

    import_info = _import_route_count()
    _emit("import", "verify_api_wiring_smoke.py:import", "main_import", import_info)

    results: list[dict] = []
    for hyp, path in SMOKE_PATHS:
        result = _probe(path)
        results.append(result)
        _emit(hyp, "verify_api_wiring_smoke.py:probe", "endpoint_probe", result)

    # Route supervisor full report (consolidated wiring check)
    report = _probe("/api/system_monitoring/route_supervisor/report", timeout=30.0)
    _emit("report", "verify_api_wiring_smoke.py:report", "route_supervisor_report", report)

    failed = [r for r in results if not r.get("ok")]
    summary = {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "failed_paths": [r["path"] for r in failed],
        "import_ok": import_info.get("import_ok"),
        "route_count": import_info.get("route_count"),
    }
    _emit("summary", "verify_api_wiring_smoke.py:main", "smoke_summary", summary)

    print(json.dumps(summary, indent=2))
    for r in results:
        flag = "OK" if r.get("ok") else "FAIL"
        print(f"  [{flag}] {r.get('status')} {r['path']} ({r.get('ms')}ms)")

    return 1 if failed or not import_info.get("import_ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
