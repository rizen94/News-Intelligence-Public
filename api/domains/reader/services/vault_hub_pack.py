"""Reader pack for vault cluster hubs."""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)


def build_vault_hub_pack(
    *,
    id_or_slug: str,
    domain: str | None = None,
) -> dict[str, Any]:
    from services.vault_cluster_hub_service import get_cluster_hub, list_cluster_hubs
    from domains.reader.services.vault_note_read import build_vault_note_by_path
    from domains.reader.services.vault_context_pack import build_vault_context_pack

    hub = None
    if str(id_or_slug).isdigit():
        hub = get_cluster_hub(domain_key=domain, hub_id=int(id_or_slug))
    if hub is None:
        hub = get_cluster_hub(domain_key=domain, slug=str(id_or_slug))
    if hub is None:
        return {"ok": False, "error": "hub_not_found"}

    domain_key = str(hub.get("domain_key") or domain or "politics")
    schema = resolve_domain_schema(domain_key)
    members = [int(x) for x in (hub.get("member_storyline_ids") or [])]
    seeds = [int(x) for x in (hub.get("seed_entity_ids") or [])]
    vault_path = hub.get("vault_path") or ""

    note = build_vault_note_by_path(vault_path) if vault_path else {"ok": False}
    context_pack = build_vault_context_pack(
        domain_key=domain_key,
        entity_ids=seeds[:12],
        hops=2,
        max_notes=16,
    )

    from shared.llm_text_sanitize import sanitize_reader_prose

    _hub_title = str(hub.get("title") or "")
    _raw_brief = hub.get("current_brief")
    brief_fields: dict[str, Any] = {
        "current_brief": sanitize_reader_prose(
            _raw_brief, title=_hub_title, max_length=4000
        )
        or None,
        "brief_updated_at": hub.get("brief_updated_at"),
        "brief_fingerprint": hub.get("brief_fingerprint"),
        "brief_refreshed": False,
    }
    try:
        from services.vault_hub_brief_service import ensure_hub_brief_for_pack

        brief_fields = ensure_hub_brief_for_pack(hub, allow_llm=False)
    except Exception as brief_exc:
        logger.debug("hub brief on-read skip: %s", brief_exc)
    # ensure_hub_brief_for_pack returns stored markdown; strip markers for plain-text UI
    brief_fields["current_brief"] = (
        sanitize_reader_prose(
            brief_fields.get("current_brief"),
            title=_hub_title,
            max_length=4000,
        )
        or None
    )

    member_cards: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if members:
                cur.execute(
                    f"""
                    SELECT id, COALESCE(title, ''), COALESCE(description, ''),
                           COALESCE(article_count, 0)::int,
                           updated_at, created_at
                    FROM {schema}.storylines
                    WHERE id = ANY(%s) AND status = 'active'
                    ORDER BY COALESCE(updated_at, created_at) DESC NULLS LAST
                    """,
                    (members,),
                )
                for row in cur.fetchall() or []:
                    sid = int(row[0])
                    from shared.llm_text_sanitize import sanitize_reader_dek

                    _mh = row[1] or f"Storyline {sid}"
                    member_cards.append(
                        {
                            "storyline_id": sid,
                            "domain": domain_key,
                            "headline": _mh,
                            "dek": sanitize_reader_dek(
                                row[2] or "", title=str(_mh), max_length=280
                            ),
                            "article_count": int(row[3] or 0),
                            "updated_at": row[4].isoformat() if row[4] else None,
                            "href": f"/storylines/{domain_key}/{sid}",
                            "surface_kind": "hub_member",
                        }
                    )
                cur.execute(
                    f"""
                    SELECT a.published_at, a.title, a.id, sa.storyline_id, a.url
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = ANY(%s)
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                    ORDER BY a.published_at DESC NULLS LAST
                    LIMIT 40
                    """,
                    (members,),
                )
                seen_arts: set[int] = set()
                for pub, title, aid, sid, url in cur.fetchall() or []:
                    aid_i = int(aid)
                    if aid_i in seen_arts:
                        continue
                    seen_arts.add(aid_i)
                    timeline.append(
                        {
                            "published_at": pub.isoformat() if pub else None,
                            "title": title or "Untitled",
                            "article_id": aid_i,
                            "storyline_id": int(sid),
                            "url": url,
                        }
                    )
                    if len(timeline) >= 20:
                        break

    # Vault context excerpts are rendered as plain text on HubPage — strip MD markers
    ctx = context_pack if isinstance(context_pack, dict) else {}
    ctx_notes = []
    for n in ctx.get("notes") or []:
        if not isinstance(n, dict):
            continue
        row = dict(n)
        row["significance_excerpt"] = sanitize_reader_prose(
            row.get("significance_excerpt") or row.get("excerpt") or "",
            title=str(row.get("title") or ""),
            max_length=400,
        ) or None
        ctx_notes.append(row)
    if ctx_notes or ctx:
        ctx = {**ctx, "notes": ctx_notes}

    note_out = note
    if isinstance(note, dict) and note.get("ok") is not False:
        note_out = dict(note)
        for key in ("body", "markdown", "content", "body_md"):
            if note_out.get(key):
                note_out[key] = sanitize_reader_prose(
                    note_out.get(key),
                    title=_hub_title,
                    max_length=8000,
                )

    return {
        "ok": True,
        "hub": {
            "id": hub["id"],
            "cluster_key": hub.get("cluster_key"),
            "title": hub.get("title"),
            "domain_key": domain_key,
            "vault_path": vault_path,
            "member_storyline_ids": members,
            "seed_entity_ids": seeds,
            "href": hub.get("href") or f"/hubs/{hub.get('cluster_key') or hub['id']}",
            "tags": hub.get("tags") or [],
            "updated_at": hub.get("updated_at"),
            "current_brief": brief_fields.get("current_brief"),
            "brief_updated_at": brief_fields.get("brief_updated_at"),
            "brief_fingerprint": brief_fields.get("brief_fingerprint"),
            "brief_refreshed": bool(brief_fields.get("brief_refreshed")),
            "surface_kind": "situation",
        },
        "current_brief": brief_fields.get("current_brief"),
        "brief_updated_at": brief_fields.get("brief_updated_at"),
        "note": note_out,
        "vault_context_pack": ctx,
        "members": member_cards,
        "timeline": timeline,
        "sibling_hubs": [
            {
                "id": h["id"],
                "cluster_key": h.get("cluster_key"),
                "title": h.get("title"),
                "href": h.get("href"),
                "member_count": len(h.get("member_storyline_ids") or []),
                "current_brief": (
                    sanitize_reader_prose(
                        (h.get("current_brief") or "")[:800],
                        title=str(h.get("title") or ""),
                        max_length=200,
                    )
                    or None
                ),
            }
            for h in list_cluster_hubs(domain_key=domain_key, limit=12)
            if h["id"] != hub["id"]
        ][:8],
    }
