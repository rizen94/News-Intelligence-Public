"""GET /api/reader/vault-hubs — cluster hub list + pack."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/vault-hubs")
async def list_vault_hubs(
    domain: str | None = Query(None),
    limit: int = Query(40, ge=1, le=100),
):
    from services.vault_cluster_hub_service import list_cluster_hubs
    from shared.llm_text_sanitize import sanitize_reader_prose

    try:
        hubs = list_cluster_hubs(domain_key=domain, limit=limit)
        cleaned = []
        for h in hubs:
            row = dict(h)
            row["current_brief"] = (
                sanitize_reader_prose(
                    row.get("current_brief"),
                    title=str(row.get("title") or ""),
                    max_length=800,
                )
                or None
            )
            cleaned.append(row)
        return {"ok": True, "hubs": cleaned, "count": len(cleaned)}
    except Exception as exc:
        logger.exception("list vault hubs failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/vault-hubs/{id_or_slug}")
async def get_vault_hub(
    id_or_slug: str,
    domain: str | None = Query(None),
):
    from ..services.vault_hub_pack import build_vault_hub_pack

    try:
        pack = build_vault_hub_pack(id_or_slug=id_or_slug, domain=domain)
        if not pack.get("ok"):
            raise HTTPException(status_code=404, detail=pack.get("error") or "not_found")
        return pack
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("vault hub pack failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
