"""Vault API for Open WebUI agent tools."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from kit_api.services import vault_service

router = APIRouter(prefix="/api/vault", tags=["Kit Vault"])


class WriteNoteBody(BaseModel):
    path: str = Field(..., min_length=1, max_length=256)
    content: str
    append: bool = False


@router.get("/notes")
async def vault_list(subdir: str = "") -> dict[str, Any]:
    return {"notes": vault_service.list_notes(subdir)}


@router.get("/notes/{path:path}")
async def vault_read(path: str) -> dict[str, Any]:
    try:
        return vault_service.read_note(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/notes")
async def vault_write(body: WriteNoteBody) -> dict[str, Any]:
    try:
        return vault_service.write_note(body.path, body.content, append=body.append)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
