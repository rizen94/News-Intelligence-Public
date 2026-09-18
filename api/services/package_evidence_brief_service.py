"""
Package evidence briefs — shared cited educational profile (v11).

Narrative evidence-expand and Research literature both write this artifact.
Editor compose/publish consumes brief_md + citation_registry.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from shared.database.connection import get_ui_db_connection_context

logger = logging.getLogger(__name__)

BRIEF_STATUSES = frozenset({"draft", "expanding", "ready", "stale"})

REQUIRED_SECTIONS = (
    "## What's new",
    "## Why this matters",
    "## Timeline",
    "## What to watch",
)

# Existing briefs used the v11 educational headings; treat them as equivalents.
_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "## what's new": ("## what's new", "## what we know", "## case briefs"),
    "## why this matters": ("## why this matters", "nut graf"),
    "## timeline": ("## timeline", "## supporting evidence"),
    "## what to watch": ("## what to watch", "## open questions", "walkaway"),
}

_CITATION = re.compile(r"\[@m(\d+)\]")


def _jsonb(val: Any) -> str:
    return json.dumps(val if val is not None else {})


def _row(cur) -> dict[str, Any] | None:
    r = cur.fetchone()
    if r is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _rows(cur) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_brief(package_id: int) -> dict[str, Any] | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM intelligence.package_evidence_briefs
                WHERE package_id = %s
                """,
                (int(package_id),),
            )
            brief = _row(cur)
            if not brief:
                return None
            cur.execute(
                """
                SELECT id, expand_round, editor_actor, model_prompt_version,
                       created_at, left(brief_md, 200) AS brief_preview
                FROM intelligence.package_evidence_brief_revisions
                WHERE brief_id = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (int(brief["id"]),),
            )
            brief["revisions"] = _rows(cur)
            return brief


def get_or_create_brief(
    package_id: int,
    *,
    actor: str = "system",
) -> dict[str, Any]:
    existing = get_brief(package_id)
    if existing:
        return existing
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM intelligence.editorial_packages WHERE id = %s",
                (int(package_id),),
            )
            if not cur.fetchone():
                raise LookupError(f"Package {package_id} not found")
            cur.execute(
                """
                INSERT INTO intelligence.package_evidence_briefs (
                    package_id, status, brief_md, created_by
                )
                VALUES (%s, 'draft', '', %s)
                ON CONFLICT (package_id) DO UPDATE SET updated_at = NOW()
                RETURNING *
                """,
                (int(package_id), actor),
            )
            brief = _row(cur)
            assert brief is not None
            conn.commit()
    return get_brief(int(package_id)) or brief


def compute_density(brief_md: str, citation_registry: dict[str, Any] | None = None) -> dict[str, Any]:
    text = brief_md or ""
    markers = [int(x) for x in _CITATION.findall(text)]
    lower = text.lower()
    sections_present = []
    for s in REQUIRED_SECTIONS:
        aliases = _SECTION_ALIASES.get(s.lower(), (s.lower(),))
        if any(a in lower for a in aliases):
            sections_present.append(s)
    missing = [s for s in REQUIRED_SECTIONS if s not in sections_present]
    reg = citation_registry if isinstance(citation_registry, dict) else {}
    return {
        "char_len": len(text),
        "citation_markers": len(markers),
        "unique_members_cited": len(set(markers)),
        "registry_keys": len(reg),
        "sections_present": sections_present,
        "sections_missing": missing,
        "passes_gate": (
            len(text) >= 800
            and len(set(markers)) >= 3
            and len(missing) <= 1
        ),
    }


def update_brief(
    package_id: int,
    *,
    brief_md: str | None = None,
    lede: str | None = None,
    open_questions: list[Any] | None = None,
    citation_registry: dict[str, Any] | None = None,
    gap_ledger: list[Any] | None = None,
    status: str | None = None,
    vault_rel_path: str | None = None,
    expand_round: int | None = None,
    actor: str = "system",
    prompt_version: str | None = None,
    metadata_patch: dict[str, Any] | None = None,
    write_revision: bool = True,
) -> dict[str, Any]:
    brief = get_or_create_brief(package_id, actor=actor)
    bid = int(brief["id"])
    new_md = brief_md if brief_md is not None else (brief.get("brief_md") or "")
    new_lede = lede if lede is not None else brief.get("lede")
    new_oq = (
        open_questions
        if open_questions is not None
        else (brief.get("open_questions") or [])
    )
    new_reg = (
        citation_registry
        if citation_registry is not None
        else (brief.get("citation_registry") or {})
    )
    new_gaps = gap_ledger if gap_ledger is not None else (brief.get("gap_ledger") or [])
    new_status = status if status is not None else brief.get("status") or "draft"
    if new_status not in BRIEF_STATUSES:
        raise ValueError(f"Invalid brief status: {new_status}")
    new_round = (
        int(expand_round)
        if expand_round is not None
        else int(brief.get("expand_round") or 0)
    )
    new_vault = (
        vault_rel_path
        if vault_rel_path is not None
        else brief.get("vault_rel_path")
    )
    density = compute_density(new_md, new_reg if isinstance(new_reg, dict) else {})
    meta = dict(brief.get("metadata") or {})
    if metadata_patch:
        meta.update(metadata_patch)

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.package_evidence_briefs
                SET lede = %s,
                    brief_md = %s,
                    open_questions = %s::jsonb,
                    citation_registry = %s::jsonb,
                    gap_ledger = %s::jsonb,
                    status = %s,
                    vault_rel_path = %s,
                    expand_round = %s,
                    density = %s::jsonb,
                    metadata = %s::jsonb,
                    updated_at = NOW(),
                    material_updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (
                    new_lede,
                    new_md,
                    _jsonb(new_oq),
                    _jsonb(new_reg),
                    _jsonb(new_gaps),
                    new_status,
                    new_vault,
                    new_round,
                    _jsonb(density),
                    _jsonb(meta),
                    bid,
                ),
            )
            row = _row(cur)
            assert row is not None
            if write_revision:
                cur.execute(
                    """
                    INSERT INTO intelligence.package_evidence_brief_revisions (
                        brief_id, lede, brief_md, open_questions, citation_registry,
                        gap_ledger, expand_round, editor_actor, model_prompt_version,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        bid,
                        new_lede,
                        new_md,
                        _jsonb(new_oq),
                        _jsonb(new_reg),
                        _jsonb(new_gaps),
                        new_round,
                        actor,
                        prompt_version,
                        _jsonb({"density": density}),
                    ),
                )
            conn.commit()
    out = get_brief(package_id)
    return out or row


def brief_passes_publish_gate(package_id: int) -> dict[str, Any]:
    brief = get_brief(package_id)
    if not brief:
        return {
            "ok": False,
            "reason": "no_brief",
            "density": compute_density(""),
        }
    density = brief.get("density") or compute_density(
        brief.get("brief_md") or "",
        brief.get("citation_registry") if isinstance(brief.get("citation_registry"), dict) else {},
    )
    if not isinstance(density, dict):
        density = compute_density(brief.get("brief_md") or "")
    ok = bool(density.get("passes_gate")) and (brief.get("status") in ("ready", "expanding", "draft"))
    # Prefer ready, but allow draft/expanding if density passes (manual publish).
    if brief.get("status") == "stale" and not density.get("passes_gate"):
        ok = False
    return {
        "ok": ok,
        "reason": None if ok else "density_or_sections",
        "brief_id": brief.get("id"),
        "status": brief.get("status"),
        "density": density,
    }
