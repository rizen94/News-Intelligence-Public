"""Read helpers — map topic_clusters rows to legacy topic_management API shape."""

from __future__ import annotations

from typing import Any


def cluster_row_to_topic_api(row: tuple, *, keyword_col: int | None = None) -> dict[str, Any]:
    """Map SELECT row from topic_clusters + counts to topic list API dict."""
    return {
        "id": row[0],
        "topic_uuid": None,
        "name": row[1],
        "description": row[2] if len(row) > 2 else None,
        "category": "general",
        "keywords": row[keyword_col] if keyword_col is not None and len(row) > keyword_col else [],
        "confidence_score": float(row[3]) if len(row) > 3 and row[3] is not None else 0.5,
        "accuracy_score": 0.5,
        "review_count": 0,
        "correct_assignments": 0,
        "incorrect_assignments": 0,
        "status": "active",
        "is_auto_generated": True,
        "article_count": int(row[4]) if len(row) > 4 and row[4] is not None else 0,
        "created_at": row[5].isoformat() if len(row) > 5 and row[5] else None,
        "updated_at": row[6].isoformat() if len(row) > 6 and row[6] else None,
    }


def resolve_cluster_schema(conn, cluster_id: int, domain: str | None) -> str | None:
    from shared.services.domain_aware_service import (
        get_domain_data_schemas,
        parse_optional_domain_to_schema,
    )

    if domain is not None and str(domain).strip():
        schemas = [parse_optional_domain_to_schema(domain)]
    else:
        schemas = list(get_domain_data_schemas())
    with conn.cursor() as cur:
        for sch in schemas:
            cur.execute(f"SELECT 1 FROM {sch}.topic_clusters WHERE id = %s", (cluster_id,))
            if cur.fetchone():
                return sch
    return None
