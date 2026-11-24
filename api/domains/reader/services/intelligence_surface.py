"""
Reader-safe surfaces for article_entities and intelligence.contexts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from api.shared.database import get_ui_db_connection_context
from api.shared.domain_registry import resolve_domain_schema
from api.shared.services.domain_aware_service import validate_domain

logger = logging.getLogger(__name__)

_CONTEXT_EXCERPT_CHARS = 600
_SNIPPET_CHARS = 160


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


def list_article_entities(
    domain_key: str, article_id: int, *, limit: int = 48
) -> list[dict[str, Any]]:
    """Mentions linked to one article (domain article_entities)."""
    domain_key = validate_domain(domain_key)
    schema = resolve_domain_schema(domain_key)
    out: list[dict[str, Any]] = []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT ae.entity_name, ae.entity_type, ae.confidence,
                           ae.mention_source, ae.source_text_snippet,
                           ae.canonical_entity_id, ec.canonical_name, ec.description
                    FROM {schema}.article_entities ae
                    LEFT JOIN {schema}.entity_canonical ec
                        ON ec.id = ae.canonical_entity_id
                    WHERE ae.article_id = %s
                    ORDER BY ae.confidence DESC NULLS LAST, ae.entity_name
                    LIMIT %s
                    """,
                    (int(article_id), int(limit)),
                )
                for r in cur.fetchall():
                    name = (r[6] or r[0] or "").strip()
                    if not name:
                        continue
                    cid = r[5]
                    out.append(
                        {
                            "name": name,
                            "entity_type": r[1],
                            "confidence": float(r[2]) if r[2] is not None else None,
                            "mention_source": r[3],
                            "snippet": (r[4] or "")[:_SNIPPET_CHARS] or None,
                            "canonical_entity_id": int(cid) if cid is not None else None,
                            "description": (r[7] or "")[:240] or None,
                            "href": (
                                f"/entities/{int(cid)}?domain={domain_key}"
                                if cid is not None
                                else None
                            ),
                        }
                    )
    except Exception as exc:
        logger.debug("list_article_entities %s/%s: %s", domain_key, article_id, exc)
    return out


def article_intelligence_context(
    domain_key: str, article_id: int
) -> dict[str, Any] | None:
    """Linked intelligence.context row for an article, if any."""
    domain_key = validate_domain(domain_key)
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.content, c.metadata, c.updated_at, c.created_at
                    FROM intelligence.article_to_context atc
                    JOIN intelligence.contexts c ON c.id = atc.context_id
                    WHERE atc.domain_key = %s AND atc.article_id = %s
                    ORDER BY c.updated_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (domain_key, int(article_id)),
                )
                row = cur.fetchone()
                if not row:
                    return None
                meta = _parse_json(row[3]) or {}
                content = (row[2] or "").strip()
                excerpt = content[:_CONTEXT_EXCERPT_CHARS]
                if len(content) > _CONTEXT_EXCERPT_CHARS:
                    excerpt += "…"
                return {
                    "context_id": int(row[0]),
                    "title": row[1],
                    "excerpt": excerpt or None,
                    "metadata": meta if isinstance(meta, dict) else {},
                    "updated_at": row[4].isoformat() if row[4] else None,
                    "created_at": row[5].isoformat() if row[5] else None,
                    "href": f"/api/contexts/{int(row[0])}",
                }
    except Exception as exc:
        logger.debug("article_intelligence_context %s/%s: %s", domain_key, article_id, exc)
    return None


def build_article_intelligence_surface(
    domain_key: str, article_id: int
) -> dict[str, Any]:
    """Bundle for GET /api/reader/articles/{id}/intelligence."""
    domain_key = validate_domain(domain_key)
    entities = list_article_entities(domain_key, article_id)
    ctx = article_intelligence_context(domain_key, article_id)
    return {
        "domain": domain_key,
        "article_id": int(article_id),
        "entities": entities,
        "entity_count": len(entities),
        "context": ctx,
    }


def aggregate_entities_for_articles(
    domain_key: str, article_ids: list[int], *, limit: int = 40
) -> list[dict[str, Any]]:
    """Roll up canonical entities across member articles (storyline dossier fallback)."""
    if not article_ids:
        return []
    domain_key = validate_domain(domain_key)
    schema = resolve_domain_schema(domain_key)
    ids = [int(i) for i in article_ids if i is not None][:80]
    if not ids:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(ec.canonical_name, ae.entity_name) AS name,
                           COALESCE(ec.entity_type, ae.entity_type) AS entity_type,
                           ec.id AS canonical_entity_id,
                           ec.description,
                           COUNT(*)::int AS mention_count,
                           MAX(ae.confidence) AS max_confidence
                    FROM {schema}.article_entities ae
                    LEFT JOIN {schema}.entity_canonical ec
                        ON ec.id = ae.canonical_entity_id
                    WHERE ae.article_id = ANY(%s)
                    GROUP BY ec.id, ec.canonical_name, ec.entity_type, ec.description,
                             ae.entity_name, ae.entity_type
                    ORDER BY mention_count DESC, max_confidence DESC NULLS LAST, name
                    LIMIT %s
                    """,
                    (ids, int(limit)),
                )
                seen: set[str] = set()
                for r in cur.fetchall():
                    name = (r[0] or "").strip()
                    if not name:
                        continue
                    key = name.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    cid = r[2]
                    out.append(
                        {
                            "id": int(cid) if cid is not None else f"ae-{len(out)}",
                            "name": name,
                            "entity_type": r[1],
                            "description_short": (r[3] or "")[:240] or None,
                            "mention_count": int(r[4]),
                            "who": None,
                            "what": None,
                            "why": None,
                            "href": (
                                f"/entities/{int(cid)}?domain={domain_key}"
                                if cid is not None
                                else None
                            ),
                        }
                    )
    except Exception as exc:
        logger.debug("aggregate_entities_for_articles %s: %s", domain_key, exc)
    return out


def list_contexts_for_articles(
    domain_key: str, article_ids: list[int], *, limit: int = 12
) -> list[dict[str, Any]]:
    """Context snapshots for storyline member articles."""
    if not article_ids:
        return []
    domain_key = validate_domain(domain_key)
    ids = [int(i) for i in article_ids if i is not None][:60]
    if not ids:
        return []
    out: list[dict[str, Any]] = []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.content, atc.article_id, c.updated_at
                    FROM intelligence.article_to_context atc
                    JOIN intelligence.contexts c ON c.id = atc.context_id
                    WHERE atc.domain_key = %s AND atc.article_id = ANY(%s)
                    ORDER BY c.updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (domain_key, ids, int(limit)),
                )
                for r in cur.fetchall():
                    content = (r[2] or "").strip()
                    excerpt = content[:_CONTEXT_EXCERPT_CHARS]
                    if len(content) > _CONTEXT_EXCERPT_CHARS:
                        excerpt += "…"
                    out.append(
                        {
                            "context_id": int(r[0]),
                            "title": r[1],
                            "article_id": int(r[3]),
                            "excerpt": excerpt or None,
                            "updated_at": r[4].isoformat() if r[4] else None,
                            "href": f"/api/contexts/{int(r[0])}",
                            "article_href": (
                                f"/{domain_key}/articles/{int(r[3])}"
                                if r[3] is not None
                                else None
                            ),
                        }
                    )
    except Exception as exc:
        logger.debug("list_contexts_for_articles %s: %s", domain_key, exc)
    return out