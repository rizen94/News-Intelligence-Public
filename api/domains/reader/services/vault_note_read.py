"""
Reader helpers: structure headline + vault note body with async-safe status.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.vault_bridge_service import vault_root
from services.vault_notes_registry_service import get_vault_note, get_vault_note_by_path
from shared.vault_note_contract import entity_vault_rel_path


def _read_note_body(vault_path: str | None) -> str | None:
    if not vault_path:
        return None
    path = vault_root() / vault_path
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def build_entity_headline(
    *,
    domain_key: str,
    entity_id: int,
    name: str | None = None,
    mention_count: int | None = None,
) -> dict[str, Any]:
    """
    NI headline from Postgres structure — never blocks on vault LLM.
    note_status: structure_only | note_pending | note_ready
    """
    note = get_vault_note(domain_key=domain_key, note_type="entity", object_id=entity_id)
    # Index/archived stubs are not reader-facing notes (F7).
    if note and str(note.get("lifecycle") or "") in ("index", "archived"):
        note = None
    title = (note or {}).get("title") or name or f"Entity {entity_id}"
    if not note:
        status = "structure_only"
        path = entity_vault_rel_path(title) if name else None
    else:
        status = note.get("note_status") or "note_pending"
        path = note.get("vault_path")
    headline = title
    if mention_count and mention_count >= 100:
        dek = f"Living subject in {domain_key} · {mention_count} mentions"
    elif status == "note_ready":
        dek = "Vault explainer ready"
    elif status == "note_pending":
        dek = "Updating vault note…"
    else:
        dek = "Structure only — note not yet seeded"

    return {
        "domain_key": domain_key,
        "entity_id": entity_id,
        "headline": headline,
        "dek": dek,
        "note_status": status,
        "lifecycle": (note or {}).get("lifecycle") or "absent",
        "vault_path": path,
        "note_updated_at": (note or {}).get("note_updated_at"),
        "mention_count": mention_count or (note or {}).get("mention_count"),
    }


def build_vault_note_payload(
    *,
    domain_key: str,
    note_type: str,
    object_id: int,
    object_id_secondary: int | None = None,
) -> dict[str, Any]:
    note = get_vault_note(
        domain_key=domain_key,
        note_type=note_type,
        object_id=object_id,
        object_id_secondary=object_id_secondary,
    )
    if note and str(note.get("lifecycle") or "") in ("index", "archived"):
        return {
            "ok": True,
            "note_status": "structure_only",
            "lifecycle": note.get("lifecycle"),
            "title": note.get("title"),
            "body": None,
            "updating": False,
            "message": "Index card only — not shown as a living note.",
        }
    if not note:
        return {
            "ok": True,
            "note_status": "structure_only",
            "lifecycle": "absent",
            "title": None,
            "body": None,
            "updating": False,
            "message": "No vault note registered yet.",
        }
    status = note.get("note_status") or "note_pending"
    body = _read_note_body(note.get("vault_path")) if status == "note_ready" else None
    updating = status == "note_pending" or (status == "note_ready" and body is None)
    return {
        "ok": True,
        "note_status": status,
        "lifecycle": note.get("lifecycle"),
        "title": note.get("title"),
        "vault_path": note.get("vault_path"),
        "body": body,
        "updating": updating,
        "note_updated_at": note.get("note_updated_at"),
        "rag_indexed_at": note.get("rag_indexed_at"),
        "tags": note.get("tags") or [],
        "message": "Updating…" if updating and not body else None,
    }


def build_vault_note_by_path(vault_path: str) -> dict[str, Any]:
    note = get_vault_note_by_path(vault_path)
    body = _read_note_body(vault_path)
    if not note and not body:
        return {"ok": False, "error": "not_found", "note_status": "absent"}
    status = (note or {}).get("note_status") or ("note_ready" if body else "structure_only")
    return {
        "ok": True,
        "note_status": status,
        "lifecycle": (note or {}).get("lifecycle"),
        "title": (note or {}).get("title"),
        "vault_path": vault_path,
        "body": body,
        "updating": status == "note_pending",
        "domain_key": (note or {}).get("domain_key"),
        "note_type": (note or {}).get("note_type"),
        "object_id": (note or {}).get("object_id"),
    }
