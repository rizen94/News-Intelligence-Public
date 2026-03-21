#!/usr/bin/env python3
"""
Test orchestrator coordinator and API endpoints.
Run from project root: PYTHONPATH=api python3 api/scripts/test_orchestrator_api.py
Or from api/: PYTHONPATH=. python3 scripts/test_orchestrator_api.py

Uses httpx.AsyncClient with ASGITransport. For full test with coordinator running,
start the API (e.g. uvicorn main_v4:app --port 8000) and:
  curl http://localhost:8000/api/orchestrator/status
  curl http://localhost:8000/api/orchestrator/metrics
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure api is on path
api_dir = Path(__file__).resolve().parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))
os.chdir(api_dir)


async def main():
    try:
        import httpx
        from httpx import ASGITransport
    except ImportError:
        print("httpx not installed; run: pip install httpx")
        sys.exit(1)

    from main_v4 import app

    transport = ASGITransport(app=app)
    errors = []

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/orchestrator/status
        try:
            r = await client.get("/api/orchestrator/status")
            if r.status_code != 200:
                errors.append(
                    f"GET /api/orchestrator/status returned {r.status_code}: {r.text[:200]}"
                )
            else:
                data = r.json()
                assert "running" in data, "status should have 'running'"
                print("GET /api/orchestrator/status:", r.status_code, data)
        except Exception as e:
            errors.append(f"GET /api/orchestrator/status failed: {e}")

        # GET /api/orchestrator/metrics
        try:
            r = await client.get("/api/orchestrator/metrics")
            if r.status_code != 200:
                errors.append(
                    f"GET /api/orchestrator/metrics returned {r.status_code}: {r.text[:200]}"
                )
            else:
                data = r.json()
                assert "performance_metrics" in data and "resource_usage" in data
                print(
                    "GET /api/orchestrator/metrics:",
                    r.status_code,
                    "metrics={} usage={}".format(
                        len(data.get("performance_metrics", [])),
                        len(data.get("resource_usage", [])),
                    ),
                )
        except Exception as e:
            errors.append(f"GET /api/orchestrator/metrics failed: {e}")

    if errors:
        print("Errors:", errors)
        sys.exit(1)
    print("Orchestrator API tests OK")


if __name__ == "__main__":
    asyncio.run(main())
