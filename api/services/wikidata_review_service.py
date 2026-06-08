"""
Wikidata QID review queue — entities missing QIDs for longitudinal join keys.
"""

from __future__ import annotations

from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema


def list_entities_missing_wikidata_qid(
    *,
    domain_key: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    domains = [domain_key] if domain_key else list(get_pipeline_active_domain_keys())
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in domains:
                schema = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT id, canonical_name, entity_type, created_at
                    FROM {schema}.entity_canonical
                    WHERE wikidata_qid IS NULL OR wikidata_qid = ''
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    item = dict(zip(cols, row))
                    item["domain_key"] = dk
                    if item.get("created_at"):
                        item["created_at"] = item["created_at"].isoformat()
                    out.append(item)
    return {"count": len(out), "items": out[:limit]}


def wikidata_qid_required_for_domain(domain_key: str) -> bool:
    import os

    required = {
        s.strip()
        for s in (os.environ.get("WIKIDATA_QID_REQUIRED_DOMAIN_KEYS") or "").split(",")
        if s.strip()
    }
    return domain_key in required
