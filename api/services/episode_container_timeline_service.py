"""
Episode and container timeline read models.

Episode timeline: CE by actual_event_date via event_episode_links.
Container timeline: union of child episode major events (+ optional Mode C connectors).
Dossiers remain projection-only (knowledge_profiles) — no membership writes here.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)


def episode_timeline(
    domain_key: str,
    episode_id: int,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    schema = resolve_domain_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, episode_state, anchor_signature, story_kind,
                       COALESCE(is_mega_storyline, FALSE)
                FROM {schema}.storylines WHERE id = %s
                """,
                (int(episode_id),),
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
            if not row:
                return {"episode": None, "events": []}
            episode = dict(zip(cols, row))
            cur.execute(
                """
                SELECT e.id, e.title, e.actual_event_date, e.event_type,
                       e.source_article_id, e.description AS summary,
                       eel.link_type, eel.matched_anchors, eel.inference_stage,
                       eel.blend_rank
                FROM intelligence.event_episode_links eel
                JOIN public.chronological_events e ON e.id = eel.event_id
                WHERE eel.domain_key = %s
                  AND eel.episode_id = %s
                  AND eel.inference_stage <> 'quarantined'
                ORDER BY e.actual_event_date DESC NULLS LAST, e.id DESC
                LIMIT %s
                """,
                (domain_key, int(episode_id), int(limit)),
            )
            ev_cols = [d[0] for d in cur.description] if cur.description else []
            events = [dict(zip(ev_cols, r)) for r in (cur.fetchall() or [])]
            return {
                "episode": episode,
                "events": events,
                "event_count": len(events),
            }


def container_timeline(
    domain_key: str,
    tracked_event_id: int,
    *,
    limit: int = 150,
) -> dict[str, Any]:
    """Union of events from episodes projected onto this container TE."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_name, container_kind, arc_state, domain_keys, anchors
                FROM intelligence.tracked_events WHERE id = %s
                """,
                (int(tracked_event_id),),
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
            if not row:
                return {"container": None, "episodes": [], "events": []}
            container = dict(zip(cols, row))
            cur.execute(
                """
                SELECT domain_key, storyline_id, facet
                FROM intelligence.tracked_event_storyline_facets
                WHERE tracked_event_id = %s
                """,
                (int(tracked_event_id),),
            )
            facets = [
                {"domain_key": r[0], "episode_id": r[1], "facet": r[2]}
                for r in (cur.fetchall() or [])
            ]
            episode_ids = [f["episode_id"] for f in facets if f["domain_key"] == domain_key]
            if not episode_ids:
                episode_ids = [f["episode_id"] for f in facets]
            events: list[dict[str, Any]] = []
            if episode_ids:
                cur.execute(
                    """
                    SELECT e.id, e.title, e.actual_event_date, e.event_type,
                           e.source_article_id, eel.episode_id, eel.link_type,
                           eel.domain_key
                    FROM intelligence.event_episode_links eel
                    JOIN public.chronological_events e ON e.id = eel.event_id
                    WHERE eel.episode_id = ANY(%s)
                      AND eel.inference_stage <> 'quarantined'
                    ORDER BY e.actual_event_date DESC NULLS LAST
                    LIMIT %s
                    """,
                    (episode_ids, int(limit)),
                )
                ev_cols = [d[0] for d in cur.description] if cur.description else []
                events = [dict(zip(ev_cols, r)) for r in (cur.fetchall() or [])]
            # Optional Mode C connectors (associate proposals mentioning domain)
            connectors: list[dict[str, Any]] = []
            try:
                cur.execute(
                    """
                    SELECT id, proposal_kind, confidence, inference_stage, subject_summary
                    FROM intelligence.graph_connection_proposals
                    WHERE domain_key = %s
                      AND status IN ('pending', 'auto_applied', 'applied_manual')
                      AND COALESCE(inference_stage, '') <> 'quarantined'
                    ORDER BY confidence DESC NULLS LAST
                    LIMIT 40
                    """,
                    (domain_key,),
                )
                ccols = [d[0] for d in cur.description] if cur.description else []
                connectors = [dict(zip(ccols, r)) for r in (cur.fetchall() or [])]
            except Exception as exc:
                logger.debug("container connectors: %s", exc)
            return {
                "container": container,
                "episodes": facets,
                "events": events,
                "event_count": len(events),
                "connectors": connectors,
                "note": "Container indexes episodes; does not own articles",
            }


def dossier_projection_stub(
    domain_key: str,
    *,
    canonical_entity_id: int | None = None,
    entity_name: str | None = None,
) -> dict[str, Any]:
    """
    Read-only dossier pointer — never writes membership.
    Prefer knowledge_profiles when present.
    """
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if canonical_entity_id is not None:
                try:
                    cur.execute(
                        """
                        SELECT id, domain_key, canonical_entity_id, title, status,
                               material_updated_at
                        FROM intelligence.knowledge_profiles
                        WHERE domain_key = %s AND canonical_entity_id = %s
                        LIMIT 1
                        """,
                        (domain_key, int(canonical_entity_id)),
                    )
                    cols = [d[0] for d in cur.description] if cur.description else []
                    row = cur.fetchone()
                    if row:
                        return {
                            "kind": "knowledge_profile",
                            "profile": dict(zip(cols, row)),
                            "writable_membership": False,
                        }
                except Exception:
                    pass
            return {
                "kind": "projection",
                "domain_key": domain_key,
                "canonical_entity_id": canonical_entity_id,
                "entity_name": entity_name,
                "writable_membership": False,
                "note": "Rebuild dossiers from events/episodes/containers only",
            }
