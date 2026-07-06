"""Aggregated kit health for Dashboard."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter

from config.runtime import env_str
from kit_api.services.setup_state import is_setup_complete
from kit_api.services import vault_service

router = APIRouter(prefix="/api/system_monitoring", tags=["Kit Status"])


@router.get("/kit_status")
async def kit_status() -> dict[str, Any]:
    ollama_ok = False
    models: list[str] = []
    db_ok = False
    vault_ok = False
    try:
        host = env_str("OLLAMA_HOST", "http://ollama:11434").rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{host}/api/tags")
            if r.status_code == 200:
                ollama_ok = True
                models = [m.get("name", "") for m in (r.json().get("models") or [])]
    except Exception:
        pass
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_ok = cur.fetchone()[0] == 1
    except Exception:
        pass
    try:
        root = vault_service.vault_root()
        vault_ok = root.is_dir() and root.exists()
    except Exception:
        pass
    return {
        "setup_complete": is_setup_complete(),
        "ollama_ok": ollama_ok,
        "ollama_models": models[:20],
        "db_ok": db_ok,
        "vault_ok": vault_ok,
        "hardware_tier": env_str("KIT_HARDWARE_TIER", "standard"),
        "status": "ok" if db_ok and is_setup_complete() else "degraded",
    }
