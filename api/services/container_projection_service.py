"""
Deterministic container projection: episode signatures → hub / TE containers.

Containers never receive article membership. Hub-only events → context feed only.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.episode_attach_gate import parse_anchor_signature, _hub_name_set

logger = logging.getLogger(__name__)

# Too-generic hub name tokens — never alone project an episode into a container.
_GENERIC_HUB_BLOCKLIST = frozenset(
    {
        "court",
        "house",
        "senate",
        "congress",
        "trump",
        "biden",
        "doj",
        "fed",
        "fda",
        "epa",
        "who",
        "un",
        "eu",
        "uk",
        "us",
    }
)


def project_episode_to_containers(
    domain_key: str,
    episode_id: int,
    *,
    apply: bool = True,
) -> dict[str, Any]:
    """
    If episode signature overlaps a hub facet set, ensure TE container facet link.
    """
    schema = resolve_domain_schema(domain_key)
    hub_names = _hub_name_set(domain_key)
    result: dict[str, Any] = {
        "episode_id": episode_id,
        "hubs": [],
        "projected": [],
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title, anchor_signature, story_kind,
                       COALESCE(is_mega_storyline, FALSE)
                FROM {schema}.storylines WHERE id = %s
                """,
                (int(episode_id),),
            )
            row = cur.fetchone()
            if not row:
                return result
            title, raw_sig, skind, is_mega = row
            if (skind or "").lower() == "container_index" or is_mega:
                result["skipped"] = "is_container"
                return result
            sig = parse_anchor_signature(raw_sig)
            tokens = set(sig.get("identity") or []) | set(sig.get("supporting") or [])
            # Also match hubs via SEI names + title (signatures are often cid: tokens)
            name_haystack: set[str] = set()
            title_l = (title or "").strip().lower()
            if title_l:
                name_haystack.add(title_l)
            try:
                cur.execute(
                    f"""
                    SELECT lower(entity_name)
                    FROM {schema}.story_entity_index
                    WHERE storyline_id = %s AND entity_name IS NOT NULL
                    LIMIT 80
                    """,
                    (int(episode_id),),
                )
                for (ename,) in cur.fetchall() or []:
                    if ename:
                        name_haystack.add(str(ename).strip().lower())
            except Exception:
                pass

            matched_hubs = []
            for h in hub_names:
                hl = h.strip().lower()
                if not hl or hl in _GENERIC_HUB_BLOCKLIST:
                    continue
                # Prefer specific multi-word / longer hubs (≥8 chars unless digit/id-like)
                if len(hl) < 8 and not any(ch.isdigit() for ch in hl):
                    continue
                if hl in tokens or any(hl in t or t in hl for t in tokens if len(hl) >= 4):
                    matched_hubs.append(h)
                    continue
                if any(
                    hl == n or (len(hl) >= 8 and (hl in n or n in hl))
                    for n in name_haystack
                ):
                    matched_hubs.append(h)
            # Prefer facet keys / shorter labels first — de-dupe preserve order
            seen: set[str] = set()
            deduped: list[str] = []
            for h in matched_hubs:
                k = h.strip().lower()
                if k not in seen:
                    seen.add(k)
                    deduped.append(h)
            matched_hubs = deduped
            result["hubs"] = matched_hubs
            if not matched_hubs or not apply:
                return result
            for hub in matched_hubs[:5]:
                cur.execute(
                    """
                    SELECT id FROM intelligence.tracked_events
                    WHERE container_kind = 'hub_facet'
                      AND %s = ANY(domain_keys)
                      AND lower(event_name) = lower(%s)
                    LIMIT 1
                    """,
                    (domain_key, hub),
                )
                te_row = cur.fetchone()
                if te_row:
                    te_id = int(te_row[0])
                else:
                    cur.execute(
                        """
                        INSERT INTO intelligence.tracked_events
                        (event_type, event_name, start_date, geographic_scope,
                         key_participant_entity_ids, milestones, domain_keys,
                         editorial_briefing, editorial_briefing_json,
                         briefing_version, briefing_status,
                         anchors, particulars, arc_state, container_kind)
                        VALUES (
                            'hub_facet', %s, CURRENT_DATE, NULL,
                            '[]', '[]', %s,
                            NULL, NULL,
                            1, 'draft',
                            %s::jsonb, '{}'::jsonb, 'active', 'hub_facet'
                        )
                        RETURNING id
                        """,
                        (
                            hub[:200],
                            [domain_key],
                            json.dumps([{"name": hub, "class": "hub"}]),
                        ),
                    )
                    te_id = int((cur.fetchone() or (None,))[0])
                cur.execute(
                    """
                    INSERT INTO intelligence.tracked_event_storyline_facets
                        (tracked_event_id, domain_key, storyline_id, facet)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tracked_event_id, domain_key, storyline_id) DO NOTHING
                    """,
                    (te_id, domain_key, int(episode_id), f"hub:{hub}"),
                )
                result["projected"].append({"tracked_event_id": te_id, "hub": hub})
            conn.commit()
    return result


def hub_context_feed(
    domain_key: str,
    hub_key: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Articles associated with a hub for context only — not container membership.
    """
    try:
        from services.hub_facets_service import list_hub_articles

        payload = list_hub_articles(domain_key, hub_key, limit=limit, offset=0)
        if isinstance(payload, dict):
            return list(payload.get("articles") or payload.get("items") or [])
        if isinstance(payload, list):
            return payload
    except Exception:
        pass
    schema = resolve_domain_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id, a.title, a.published_at
                FROM {schema}.articles a
                JOIN {schema}.article_entities ae ON ae.article_id = a.id
                WHERE lower(ae.entity_name) LIKE %s
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT %s
                """,
                (f"%{hub_key.lower()}%", int(limit)),
            )
            return [
                {"article_id": r[0], "title": r[1], "published_at": r[2]}
                for r in (cur.fetchall() or [])
            ]
