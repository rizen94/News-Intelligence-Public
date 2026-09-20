"""
Reader pack for a single storyline: summary, timeline, citations, dossier rail.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.services.domain_aware_service import validate_domain

logger = logging.getLogger(__name__)


def _parse_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _build_dossier_tree(entities: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nest entities by member_of_family / family-like edges when present."""
    by_id = {e["id"]: {**e, "children": []} for e in entities if e.get("id") is not None}
    roots: list[dict[str, Any]] = []
    child_ids: set[Any] = set()

    for rel in relationships:
        rtype = (rel.get("relationship_type") or rel.get("type") or "").lower()
        if rtype not in ("member_of_family", "member_of", "part_of", "subsidiary_of", "works_for"):
            continue
        parent = rel.get("target_entity_id") or rel.get("to_entity_id") or rel.get("parent_id")
        child = rel.get("source_entity_id") or rel.get("from_entity_id") or rel.get("child_id")
        if parent in by_id and child in by_id and parent != child:
            by_id[parent]["children"].append(by_id[child])
            child_ids.add(child)

    for eid, node in by_id.items():
        if eid not in child_ids:
            roots.append(node)

    if not roots:
        return list(by_id.values())
    return roots


def build_storyline_reader_pack(domain: str, storyline_id: int) -> dict[str, Any]:
    if not validate_domain(domain):
        raise ValueError(f"Invalid or inactive domain: {domain}")

    schema = resolve_domain_schema(domain)
    timeline: dict[str, Any] = {}
    try:
        from services.timeline_builder_service import TimelineBuilderService

        timeline = TimelineBuilderService().build_timeline(storyline_id) or {}
    except Exception as exc:
        logger.warning("timeline build failed for %s/%s: %s", domain, storyline_id, exc)
        timeline = {"events": [], "error": str(exc)}

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    s.id, s.title, s.description, s.status,
                    s.created_at, s.updated_at, s.article_count, s.quality_score,
                    s.master_summary, s.background_information,
                    s.editorial_document, s.document_version, s.document_status,
                    s.canonical_narrative, s.timeline_narrative_chronological,
                    s.timeline_narrative_briefing, s.key_entities,
                    s.parent_storyline_id, COALESCE(s.is_mega_storyline, FALSE),
                    s.last_refinement
                FROM {schema}.storylines s
                WHERE s.id = %s AND s.merged_into_id IS NULL
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError(f"Storyline {storyline_id} not found in {domain}")

            (
                sid,
                title,
                description,
                status,
                created_at,
                updated_at,
                article_count,
                quality_score,
                master_summary,
                background_information,
                editorial_document,
                document_version,
                document_status,
                canonical_narrative,
                timeline_narrative_chronological,
                timeline_narrative_briefing,
                key_entities,
                parent_storyline_id,
                is_mega_storyline,
                last_refinement,
            ) = row

            editorial = _parse_json(editorial_document) or {}

            # Citations: member articles
            cur.execute(
                f"""
                SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT 50
                """,
                (storyline_id,),
            )
            citations = [
                {
                    "id": r[0],
                    "title": r[1],
                    "url": r[2],
                    "source_domain": r[3],
                    "published_at": r[4].isoformat() if r[4] else None,
                    "summary": r[5],
                }
                for r in cur.fetchall()
            ]

            # Entities linked to storyline (best-effort)
            entities: list[dict[str, Any]] = []
            relationships: list[dict[str, Any]] = []
            try:
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (e.id)
                        e.id, e.name, e.entity_type, e.description
                    FROM {schema}.entities e
                    JOIN {schema}.article_entities ae ON ae.entity_id = e.id
                    JOIN {schema}.storyline_articles sa ON sa.article_id = ae.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY e.id, e.name
                    LIMIT 40
                    """,
                    (storyline_id,),
                )
                for r in cur.fetchall():
                    entities.append(
                        {
                            "id": r[0],
                            "name": r[1],
                            "entity_type": r[2],
                            "description_short": (r[3] or "")[:240],
                            "who": None,
                            "what": None,
                            "why": None,
                            "href": f"/v2/entities/{r[0]}?domain={domain}",
                        }
                    )
            except Exception as exc:
                logger.debug("entity join fallback: %s", exc)
                conn.rollback()
                # Fall back to key_entities JSON
                ke = _parse_json(key_entities)
                if isinstance(ke, list):
                    for i, item in enumerate(ke[:20]):
                        if isinstance(item, dict):
                            entities.append(
                                {
                                    "id": item.get("id") or f"ke-{i}",
                                    "name": item.get("name") or "Entity",
                                    "entity_type": item.get("type") or item.get("entity_type"),
                                    "description_short": (item.get("description") or "")[:240],
                                    "href": None,
                                }
                            )
                        elif isinstance(item, str):
                            entities.append(
                                {
                                    "id": f"ke-{i}",
                                    "name": item,
                                    "entity_type": None,
                                    "description_short": "",
                                    "href": None,
                                }
                            )

            # Enrich from dossiers when available
            for ent in entities:
                eid = ent.get("id")
                if not isinstance(eid, int):
                    continue
                try:
                    cur.execute(
                        """
                        SELECT chronicle_data, relationships, metadata
                        FROM intelligence.entity_dossiers
                        WHERE entity_id = %s
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT 1
                        """,
                        (eid,),
                    )
                    drow = cur.fetchone()
                    if drow:
                        chronicle = _parse_json(drow[0]) or {}
                        rels = _parse_json(drow[1]) or []
                        meta = _parse_json(drow[2]) or {}
                        ent["who"] = chronicle.get("who") or meta.get("who") or ent.get("description_short")
                        ent["what"] = chronicle.get("what") or meta.get("what")
                        ent["why"] = chronicle.get("why") or meta.get("why")
                        if isinstance(rels, list):
                            for rel in rels:
                                if isinstance(rel, dict):
                                    relationships.append({**rel, "source_entity_id": eid})
                except Exception:
                    conn.rollback()
                    break  # dossier table may be absent

            # Hierarchy siblings / children
            hierarchy = {
                "parent_storyline_id": parent_storyline_id,
                "is_mega_storyline": bool(is_mega_storyline),
                "children": [],
            }
            try:
                cur.execute(
                    f"""
                    SELECT id, title
                    FROM {schema}.storylines
                    WHERE parent_storyline_id = %s AND merged_into_id IS NULL
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 20
                    """,
                    (storyline_id,),
                )
                hierarchy["children"] = [
                    {"id": r[0], "title": r[1], "href": f"/v2/storylines/{domain}/{r[0]}"}
                    for r in cur.fetchall()
                ]
            except Exception:
                conn.rollback()

    lede = (editorial.get("lede") if isinstance(editorial, dict) else None) or ""
    summary = (
        (master_summary or "").strip()
        or (canonical_narrative or "").strip()
        or (timeline_narrative_briefing or "").strip()
        or (description or "").strip()
        or lede
    )

    dossier_tree = _build_dossier_tree(entities, relationships)

    return {
        "domain": domain,
        "storyline_id": sid,
        "title": title,
        "status": status,
        "summary": summary,
        "lede": lede,
        "editorial_document": editorial if isinstance(editorial, dict) else {},
        "background_information": background_information,
        "timeline_narrative": timeline_narrative_chronological,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "last_refinement": last_refinement.isoformat() if last_refinement else None,
        "article_count": article_count,
        "quality_score": float(quality_score) if quality_score is not None else None,
        "document_version": document_version,
        "document_status": document_status,
        "timeline": timeline,
        "citations": citations,
        "dossier_rail": {
            "entities": entities,
            "tree": dossier_tree,
            "hierarchy": hierarchy,
        },
    }
