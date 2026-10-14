"""
Hub facet browse — who/what/where categorization lenses (not mega-storylines).

List articles and matter storylines under a configured hub (e.g. SCOTUS) without
collapsing them into one kitchen-sink membership.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _dsc_module():
    name = "services.domain_synthesis_config"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parent / "domain_synthesis_config.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def list_hub_facets(domain_key: str) -> list[dict[str, Any]]:
    dsc = _dsc_module()
    facets = dsc.get_domain_hub_facets(domain_key)
    return [
        {
            "key": f.key,
            "role": f.role,
            "names": list(f.names),
        }
        for f in facets
    ]


def _facet_or_404(domain_key: str, hub_key: str):
    key = (hub_key or "").strip().lower()
    dsc = _dsc_module()
    for f in dsc.get_domain_hub_facets(domain_key):
        if f.key == key:
            return f
    raise LookupError(f"Unknown hub_key={hub_key!r} for domain={domain_key!r}")


def list_hub_articles(
    domain_key: str,
    hub_key: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    from shared.database.connection import get_ui_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    facet = _facet_or_404(domain_key, hub_key)
    schema = resolve_domain_schema(domain_key)
    names = [n.lower() for n in facet.names]
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    articles: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT a.id, a.title, a.url, a.published_at
                FROM {schema}.article_entities ae
                JOIN {schema}.articles a ON a.id = ae.article_id
                WHERE lower(COALESCE(ae.entity_name, '')) = ANY(%s)
                   OR (
                        length(lower(COALESCE(ae.entity_name, ''))) >= 5
                        AND EXISTS (
                            SELECT 1 FROM unnest(%s::text[]) AS hn(n)
                            WHERE lower(ae.entity_name) LIKE '%%' || hn.n || '%%'
                              AND length(hn.n) >= 5
                        )
                   )
                ORDER BY a.published_at DESC NULLS LAST, a.id DESC
                LIMIT %s OFFSET %s
                """,
                (names, names, lim, off),
            )
            for r in cur.fetchall():
                articles.append(
                    {
                        "id": int(r[0]),
                        "title": r[1],
                        "url": r[2],
                        "published_at": r[3].isoformat() if r[3] else None,
                    }
                )
    return {
        "domain_key": domain_key,
        "hub_key": facet.key,
        "role": facet.role,
        "articles": articles,
        "limit": lim,
        "offset": off,
    }


def list_hub_storylines(
    domain_key: str,
    hub_key: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Storylines that carry the hub on SEI and also have ≥1 non-hub durable
    (party/matter) — true threads under the hub lens.
    """
    from shared.database.connection import get_ui_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    facet = _facet_or_404(domain_key, hub_key)
    schema = resolve_domain_schema(domain_key)
    cfg = _dsc_module().get_domain_synthesis_config(domain_key)
    hub_names = list(cfg.hub_name_set())
    facet_names = [n.lower() for n in facet.names]
    lim = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    storylines: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH hub_sl AS (
                    SELECT DISTINCT sei.storyline_id
                    FROM {schema}.story_entity_index sei
                    WHERE lower(COALESCE(sei.entity_name, '')) = ANY(%s)
                       OR (
                            lower(COALESCE(sei.entity_role, '')) IN ('who', 'what', 'where')
                            AND EXISTS (
                                SELECT 1 FROM unnest(%s::text[]) AS hn(n)
                                WHERE lower(sei.entity_name) = hn.n
                                   OR (
                                        length(hn.n) >= 5
                                        AND lower(sei.entity_name) LIKE '%%' || hn.n || '%%'
                                   )
                            )
                       )
                ),
                non_hub AS (
                    SELECT sei.storyline_id
                    FROM {schema}.story_entity_index sei
                    JOIN hub_sl h ON h.storyline_id = sei.storyline_id
                    WHERE lower(COALESCE(sei.entity_role, '')) IN ('party', 'matter')
                       OR (
                            lower(COALESCE(sei.entity_type, '')) IN
                                ('person', 'case_number', 'legislation_id', 'organization')
                            AND NOT (lower(COALESCE(sei.entity_name, '')) = ANY(%s))
                       )
                    GROUP BY sei.storyline_id
                    HAVING COUNT(*) >= 1
                )
                SELECT s.id, s.title, s.status, s.article_count, s.updated_at
                FROM {schema}.storylines s
                JOIN non_hub nh ON nh.storyline_id = s.id
                WHERE s.status NOT IN ('archived', 'concluded')
                ORDER BY s.updated_at DESC NULLS LAST, s.id DESC
                LIMIT %s OFFSET %s
                """,
                (facet_names, facet_names, hub_names, lim, off),
            )
            for r in cur.fetchall():
                storylines.append(
                    {
                        "id": int(r[0]),
                        "title": r[1],
                        "status": r[2],
                        "article_count": r[3],
                        "updated_at": r[4].isoformat() if r[4] else None,
                    }
                )
    return {
        "domain_key": domain_key,
        "hub_key": facet.key,
        "role": facet.role,
        "storylines": storylines,
        "limit": lim,
        "offset": off,
    }
