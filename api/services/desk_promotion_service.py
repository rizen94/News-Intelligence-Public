"""
Desk promotion — editor gate from vault investigation notes into existing products.

Does not generate stories on demand. OWUI / operator must approve before Postgres long-form
fields are updated (storyline editorial_document / canonical_narrative, tracked_event
narratives, graph proposal accept/reject).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_bool
from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)


def desk_writeback_enabled() -> bool:
    return env_bool("DESK_AGENT_WRITEBACK_ENABLED", False)


def _coerce_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def merge_editorial_document(
    existing: dict[str, Any] | None,
    patch: dict[str, Any] | None,
    *,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shallow-merge editorial_document keys; nested dicts merge one level."""
    base: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    if isinstance(patch, dict):
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                merged = dict(base[k])
                merged.update(v)
                base[k] = merged
            else:
                base[k] = v
    if provenance:
        meta = dict(base.get("desk_provenance") or {}) if isinstance(base.get("desk_provenance"), dict) else {}
        meta.update(provenance)
        base["desk_provenance"] = meta
    return base


def validate_promote_gate(
    *,
    frontmatter: dict[str, Any],
    body: str,
    editor_approved: bool,
    editor_rationale: str | None,
) -> list[str]:
    """Return list of gate errors (empty = ok)."""
    errors: list[str] = []
    status = str(frontmatter.get("status") or "").strip().lower()
    if status != "ready_to_promote" and not editor_approved:
        errors.append("status_must_be_ready_to_promote_or_editor_approved")
    te = _coerce_int(frontmatter.get("tracked_event_id"))
    sl = _coerce_int(frontmatter.get("storyline_id"))
    domain_key = str(frontmatter.get("domain_key") or "").strip()
    if not te and not (sl and domain_key):
        errors.append("need_tracked_event_id_or_storyline_id_plus_domain_key")
    if sl and not domain_key:
        errors.append("domain_key_required_with_storyline_id")
    rationale = (editor_rationale or str(frontmatter.get("editor_rationale") or "")).strip()
    if len(rationale) < 12:
        errors.append("editor_rationale_required")
    text = (body or "").strip()
    # Allow promote when patch fields will be supplied separately; body should still be non-trivial
    # unless caller passes explicit narrative patches (checked by caller).
    if len(text) < 40 and not frontmatter.get("allow_short_body"):
        errors.append("investigation_body_too_short")
    return errors


def patch_storyline_editorial(
    domain_key: str,
    storyline_id: int,
    *,
    editorial_document: dict[str, Any] | None = None,
    canonical_narrative: str | None = None,
    vault_path: str | None = None,
    source: str = "desk_agent",
) -> dict[str, Any]:
    schema = resolve_domain_schema(domain_key)
    provenance = {
        "source": source,
        "vault_path": vault_path or "",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
    if editorial_document is None and canonical_narrative is None and not vault_path:
        return {"ok": False, "error": "nothing_to_patch"}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT editorial_document, canonical_narrative
                FROM {schema}.storylines
                WHERE id = %s
                """,
                (int(storyline_id),),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "storyline_not_found"}
            existing_ed = row[0] if isinstance(row[0], dict) else {}
            if isinstance(row[0], str):
                try:
                    existing_ed = json.loads(row[0])
                except json.JSONDecodeError:
                    existing_ed = {}
            merged = merge_editorial_document(
                existing_ed,
                editorial_document if editorial_document is not None else {},
                provenance=provenance,
            )
            sets: list[str] = [
                "editorial_document = %s::jsonb",
                "document_status = %s",
                "last_refinement = NOW()",
                "updated_at = NOW()",
            ]
            params: list[Any] = [json.dumps(merged), "desk_promoted"]
            if canonical_narrative is not None:
                sets.insert(0, "canonical_narrative = %s")
                params.insert(0, canonical_narrative)
            params.append(int(storyline_id))
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET {", ".join(sets)}
                WHERE id = %s
                """,
                tuple(params),
            )
        conn.commit()
    return {
        "ok": True,
        "domain_key": domain_key,
        "storyline_id": storyline_id,
        "document_status": "desk_promoted",
    }


def patch_tracked_event_narrative(
    event_id: int,
    *,
    global_narrative: str | None = None,
    editorial_briefing: str | None = None,
    narrative_lenses: dict[str, Any] | None = None,
    vault_path: str | None = None,
    source: str = "desk_agent",
) -> dict[str, Any]:
    if global_narrative is None and editorial_briefing is None and narrative_lenses is None:
        return {"ok": False, "error": "nothing_to_patch"}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, global_narrative, editorial_briefing, narrative_lenses
                FROM intelligence.tracked_events
                WHERE id = %s
                """,
                (int(event_id),),
            )
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "tracked_event_not_found"}
            lenses = row[3] if isinstance(row[3], dict) else {}
            if isinstance(row[3], str):
                try:
                    lenses = json.loads(row[3])
                except json.JSONDecodeError:
                    lenses = {}
            if narrative_lenses is not None:
                if isinstance(lenses, dict) and isinstance(narrative_lenses, dict):
                    lenses = {**lenses, **narrative_lenses}
                else:
                    lenses = narrative_lenses
            gn = global_narrative if global_narrative is not None else row[1]
            eb = editorial_briefing if editorial_briefing is not None else row[2]
            if editorial_briefing is None and global_narrative is not None and not (eb or "").strip():
                eb = (global_narrative or "")[:1200]
            meta_note = {
                "desk_source": source,
                "vault_path": vault_path or "",
                "promoted_at": datetime.now(timezone.utc).isoformat(),
            }
            if isinstance(lenses, dict):
                lenses = {**lenses, "_desk_provenance": meta_note}
            cur.execute(
                """
                UPDATE intelligence.tracked_events
                SET global_narrative = %s,
                    editorial_briefing = LEFT(%s, 1200),
                    narrative_lenses = %s::jsonb,
                    global_narrative_updated_at = CASE WHEN %s THEN NOW() ELSE global_narrative_updated_at END,
                    narrative_lenses_updated_at = CASE WHEN %s THEN NOW() ELSE narrative_lenses_updated_at END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    gn,
                    eb or "",
                    json.dumps(lenses or {}),
                    global_narrative is not None,
                    narrative_lenses is not None,
                    int(event_id),
                ),
            )
        conn.commit()
    return {"ok": True, "tracked_event_id": event_id}


def promote_investigation(
    *,
    vault_path: str,
    editor_approved: bool = False,
    editor_rationale: str | None = None,
    editorial_document: dict[str, Any] | None = None,
    canonical_narrative: str | None = None,
    global_narrative: str | None = None,
    editorial_briefing: str | None = None,
    narrative_lenses: dict[str, Any] | None = None,
    accept_proposal_ids: list[int] | None = None,
    reject_proposal_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    Editor gate: vault note → existing storyline / tracked_event fields + optional graph resolves.
    """
    if not desk_writeback_enabled():
        return {"ok": False, "error": "DESK_AGENT_WRITEBACK_ENABLED is false"}

    from services import vault_bridge_service as vault
    from services.graph_connection_processor_service import apply_graph_connection_proposal_by_id
    from services.graph_connection_queue_service import mark_proposal_resolved
    from services.saved_intel_service import save_intel_output

    note = vault.read_vault_note(vault_path)
    if not note.get("ok"):
        return {"ok": False, "error": note.get("error") or "vault_read_failed", "path": vault_path}

    fm = dict(note.get("frontmatter") or {})
    body = str(note.get("body") or "")
    # Explicit patches can substitute for long body
    if (
        editorial_document
        or canonical_narrative
        or global_narrative
        or editorial_briefing
    ):
        fm = {**fm, "allow_short_body": True}

    errors = validate_promote_gate(
        frontmatter=fm,
        body=body,
        editor_approved=editor_approved,
        editor_rationale=editor_rationale,
    )
    if errors:
        return {"ok": False, "error": "gate_failed", "gate_errors": errors}

    rationale = (editor_rationale or str(fm.get("editor_rationale") or "")).strip()
    domain_key = str(fm.get("domain_key") or "").strip()
    te_id = _coerce_int(fm.get("tracked_event_id"))
    sl_id = _coerce_int(fm.get("storyline_id"))

    # Derive narrative text from body when patches omitted
    derived = body.strip()
    # Strip leading markdown title
    derived = re.sub(r"^#\s+.+\n+", "", derived, count=1).strip()

    results: dict[str, Any] = {
        "ok": True,
        "vault_path": vault_path,
        "storyline": None,
        "tracked_event": None,
        "proposals_accepted": [],
        "proposals_rejected": [],
        "saved_intel_id": None,
    }

    if sl_id and domain_key:
        ed_patch = editorial_document
        if ed_patch is None and derived:
            ed_patch = {
                "lede": derived[:400],
                "analysis": derived[:8000],
                "outlook": "",
            }
        canon = canonical_narrative if canonical_narrative is not None else (derived[:12000] if derived else None)
        results["storyline"] = patch_storyline_editorial(
            domain_key,
            sl_id,
            editorial_document=ed_patch,
            canonical_narrative=canon,
            vault_path=vault_path,
        )
        if not results["storyline"].get("ok"):
            return {"ok": False, "error": "storyline_patch_failed", "detail": results["storyline"]}

    if te_id:
        gn = global_narrative if global_narrative is not None else (derived[:8000] if derived else None)
        eb = editorial_briefing if editorial_briefing is not None else ((gn or "")[:1200] if gn else None)
        results["tracked_event"] = patch_tracked_event_narrative(
            te_id,
            global_narrative=gn,
            editorial_briefing=eb,
            narrative_lenses=narrative_lenses,
            vault_path=vault_path,
        )
        if not results["tracked_event"].get("ok"):
            return {"ok": False, "error": "tracked_event_patch_failed", "detail": results["tracked_event"]}

    proposal_ids_fm = fm.get("proposal_ids") if isinstance(fm.get("proposal_ids"), list) else []
    accept_ids = list(accept_proposal_ids or []) + [
        int(x) for x in proposal_ids_fm if _coerce_int(x) is not None
    ]
    # de-dupe
    seen: set[int] = set()
    for pid in accept_ids:
        if pid in seen:
            continue
        seen.add(pid)
        results["proposals_accepted"].append(
            apply_graph_connection_proposal_by_id(pid, force=True)
        )

    for pid in reject_proposal_ids or []:
        ok = mark_proposal_resolved(int(pid), "rejected", f"desk_reject:{rationale[:200]}")
        results["proposals_rejected"].append({"proposal_id": pid, "ok": ok})

    subject_id = te_id or sl_id or 0
    subject_type = "tracked_event" if te_id else "storyline"
    audit_md = (
        f"# Desk promotion\n\n"
        f"- vault: `{vault_path}`\n"
        f"- rationale: {rationale}\n\n"
        f"{derived[:4000]}\n"
    )
    results["saved_intel_id"] = save_intel_output(
        content_type="desk_promotion",
        subject_type=subject_type,
        subject_id=int(subject_id),
        content_md=audit_md,
        domain_key=domain_key or None,
        title=f"Desk promote {vault_path}",
        metadata={
            "vault_path": vault_path,
            "tracked_event_id": te_id,
            "storyline_id": sl_id,
            "editor_rationale": rationale,
        },
    )

    vault.update_vault_note_frontmatter(
        vault_path,
        {
            "status": "promoted",
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "editor_rationale": rationale,
        },
    )
    return results
