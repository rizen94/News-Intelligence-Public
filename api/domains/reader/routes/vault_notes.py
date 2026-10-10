"""GET /api/reader/vault-notes — headline + full note (async-safe)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from ..services.vault_note_read import (
    build_entity_headline,
    build_vault_note_by_path,
    build_vault_note_payload,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/vault-notes/entity/{entity_id}/headline")
async def entity_vault_headline(
    entity_id: int,
    domain: str = Query("politics"),
    name: str | None = Query(None),
    mention_count: int | None = Query(None),
):
    """Structure-first headline; note_status may be structure_only / pending / ready."""
    try:
        return build_entity_headline(
            domain_key=domain,
            entity_id=entity_id,
            name=name,
            mention_count=mention_count,
        )
    except Exception as exc:
        logger.exception("vault headline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/vault-notes/{note_type}/{object_id}")
async def get_vault_note(
    note_type: str,
    object_id: int,
    domain: str = Query("politics"),
    object_id_secondary: int | None = Query(None),
):
    if note_type not in ("entity", "connection", "event", "storyline", "cluster"):
        raise HTTPException(status_code=400, detail="invalid note_type")
    try:
        return build_vault_note_payload(
            domain_key=domain,
            note_type=note_type,
            object_id=object_id,
            object_id_secondary=object_id_secondary,
        )
    except Exception as exc:
        logger.exception("vault note fetch failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/vault-notes/by-path")
async def get_vault_note_path(path: str = Query(..., min_length=3)):
    try:
        out = build_vault_note_by_path(path)
        if not out.get("ok"):
            raise HTTPException(status_code=404, detail=out.get("error") or "not_found")
        return out
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("vault note by-path failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/vault-notes/context-pack")
async def vault_context_pack(
    domain: str = Query("politics"),
    entity_ids: str | None = Query(
        None, description="Comma-separated canonical entity IDs"
    ),
    titles: str | None = Query(None, description="Comma-separated note titles"),
    hops: int = Query(2, ge=0, le=4),
    max_notes: int = Query(12, ge=1, le=40),
):
    """Canned research background: expand vault links + geo parents."""
    from ..services.vault_context_pack import build_vault_context_pack

    ids: list[int] = []
    if entity_ids:
        for part in entity_ids.split(","):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
    title_list = [t.strip() for t in (titles or "").split(",") if t.strip()]
    try:
        return build_vault_context_pack(
            domain_key=domain,
            entity_ids=ids,
            titles=title_list or None,
            hops=hops,
            max_notes=max_notes,
        )
    except Exception as exc:
        logger.exception("vault context pack failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
