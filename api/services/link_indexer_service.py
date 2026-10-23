"""
Passive link indexer — programmatic edges on spine-complete articles (no LLM).

Runs from spine_sql_tail after unified intake clears.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from config.runtime import env_str
from shared.database.connection import get_db_connection_context
from shared.domain_registry import pipeline_url_schema_pairs, resolve_domain_schema
from shared.entity_relationships_store import UPSERT_ENTITY_RELATIONSHIP_SQL, normalize_edge
from shared.pipeline_pass_marker import sql_article_pass_cleared

logger = logging.getLogger(__name__)

RELATIONSHIP_TYPE_CO_MENTIONED = "co_mentioned"


def _batch_limit() -> int:
    try:
        return max(10, min(500, int(env_str("LINK_INDEXER_BATCH_LIMIT", "100"))))
    except (TypeError, ValueError):
        return 100


def index_spine_complete_articles(*, limit: int | None = None) -> dict[str, Any]:
    """
    Index recently spine-complete articles across pipeline domains.
    """
    cap = limit if limit is not None else _batch_limit()
    totals = {
        "articles": 0,
        "entity_edges": 0,
        "event_proposals": 0,
        "cross_domain_proposals": 0,
        "storyline_index_updates": 0,
    }
    for domain_key, schema_name in pipeline_url_schema_pairs():
        try:
            article_ids = _fetch_indexable_article_ids(schema_name, cap)
            for aid in article_ids:
                stats = index_article(domain_key, schema_name, aid)
                totals["articles"] += 1
                totals["entity_edges"] += int(stats.get("entity_edges") or 0)
                totals["event_proposals"] += int(stats.get("event_proposals") or 0)
                totals["cross_domain_proposals"] += int(stats.get("cross_domain_proposals") or 0)
                totals["storyline_index_updates"] += int(stats.get("storyline_index_updates") or 0)
        except Exception as e:
            logger.warning("link_indexer domain %s: %s", domain_key, e)
    try:
        from services.assembly_throughput_metrics import record_link_indexer_batch

        record_link_indexer_batch(totals)
    except Exception:
        pass
    if totals["articles"]:
        logger.info("link_indexer batch: %s", totals)
    return totals


def index_domain_co_mentions(domain_key: str, *, limit: int = 50) -> dict[str, Any]:
    """Index co-mention edges for pending articles in one domain (entity_organizer path)."""
    from shared.domain_registry import resolve_domain_schema

    schema_name = resolve_domain_schema(domain_key)
    cap = max(1, min(int(limit), 500))
    totals = {
        "articles": 0,
        "entity_edges": 0,
        "event_proposals": 0,
        "cross_domain_proposals": 0,
        "storyline_index_updates": 0,
    }
    article_ids = _fetch_indexable_article_ids(schema_name, cap)
    for aid in article_ids:
        stats = index_article(domain_key, schema_name, aid)
        totals["articles"] += 1
        totals["entity_edges"] += int(stats.get("entity_edges") or 0)
        totals["event_proposals"] += int(stats.get("event_proposals") or 0)
        totals["cross_domain_proposals"] += int(stats.get("cross_domain_proposals") or 0)
        totals["storyline_index_updates"] += int(stats.get("storyline_index_updates") or 0)
    totals["success"] = True
    totals["extracted"] = totals["entity_edges"]
    totals["contexts_processed"] = totals["articles"]
    return totals


def _fetch_indexable_article_ids(schema_name: str, limit: int) -> list[int]:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id
                FROM {schema_name}.articles a
                WHERE ({sql_article_pass_cleared("unified_intake_extraction", "a")})
                  AND COALESCE(
                      (a.metadata #>> '{{pipeline,link_indexer,last_pass_at}}')::text,
                      ''
                  ) = ''
                ORDER BY a.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            return [int(r[0]) for r in cur.fetchall()]


def index_article(domain_key: str, schema_name: str, article_id: int) -> dict[str, int]:
    stats = {
        "entity_edges": 0,
        "event_proposals": 0,
        "cross_domain_proposals": 0,
        "storyline_index_updates": 0,
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            stats["entity_edges"] = _index_entity_co_mentions(
                cur, schema_name, domain_key, article_id
            )
            stats["event_proposals"] = _index_event_entity_proposals(
                cur, schema_name, domain_key, article_id
            )
            stats["storyline_index_updates"] = _refresh_story_entity_index(
                cur, schema_name, article_id
            )
            _mark_link_indexer_pass(cur, schema_name, article_id)
        conn.commit()
    stats["cross_domain_proposals"] = _index_cross_domain_soft_links(
        domain_key, schema_name, article_id
    )
    return stats


def _index_entity_co_mentions(
    cur, schema_name: str, domain_key: str, article_id: int
) -> int:
    cur.execute(
        f"""
        SELECT canonical_entity_id, entity_name, entity_type
        FROM {schema_name}.article_entities
        WHERE article_id = %s AND canonical_entity_id IS NOT NULL
        """,
        (article_id,),
    )
    rows = cur.fetchall()
    if len(rows) < 2:
        return 0
    from shared.entity_relationships_store import entity_relationships_at_cap

    if entity_relationships_at_cap():
        logger.warning("link_indexer: entity_relationships at cap — skipping new edges")
        return 0
    n = 0
    ids = [int(r[0]) for r in rows]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            d1, id1, d2, id2 = normalize_edge(domain_key, ids[i], domain_key, ids[j])
            cur.execute(
                UPSERT_ENTITY_RELATIONSHIP_SQL,
                (d1, id1, d2, id2, RELATIONSHIP_TYPE_CO_MENTIONED, 0.55),
            )
            if cur.fetchone():
                n += 1
    return n


def _index_event_entity_proposals(
    cur, schema_name: str, domain_key: str, article_id: int
) -> int:
    cur.execute(
        """
        SELECT id, event_title, event_date
        FROM public.chronological_events
        WHERE source_article_id = %s
        ORDER BY id DESC
        LIMIT 10
        """,
        (article_id,),
    )
    events = cur.fetchall()
    if not events:
        return 0
    cur.execute(
        f"""
        SELECT canonical_entity_id FROM {schema_name}.article_entities
        WHERE article_id = %s AND canonical_entity_id IS NOT NULL
        LIMIT 20
        """,
        (article_id,),
    )
    entity_ids = [int(r[0]) for r in cur.fetchall()]
    if not entity_ids:
        return 0
    from services.graph_connection_queue_service import upsert_graph_connection_proposal

    n = 0
    for evt_id, title, evt_date in events:
        dedupe = hashlib.sha256(
            f"event_entity|{article_id}|{evt_id}|{','.join(map(str, entity_ids[:5]))}".encode()
        ).hexdigest()[:32]
        pid = upsert_graph_connection_proposal(
            dedupe_key=f"link_indexer|{dedupe}",
            proposal_kind="associate",
            domain_key=domain_key,
            confidence=0.62,
            source="link_indexer",
            endpoints={
                "domain_key": domain_key,
                "entity_ids": entity_ids[:10],
                "article_id": article_id,
            },
            evidence={
                "chronological_event_id": int(evt_id),
                "event_title": (title or "")[:200],
                "event_date": str(evt_date) if evt_date else None,
            },
            subject_summary=(title or f"event {evt_id}")[:255],
        )
        if pid:
            n += 1
    return n


def _refresh_story_entity_index(cur, schema_name: str, article_id: int) -> int:
    cur.execute(
        f"""
        SELECT sa.storyline_id
        FROM {schema_name}.storyline_articles sa
        WHERE sa.article_id = %s
        LIMIT 1
        """,
        (article_id,),
    )
    row = cur.fetchone()
    if not row:
        return 0
    storyline_id = int(row[0])
    cur.execute(
        f"""
        SELECT entity_name, entity_type, COUNT(*) AS cnt
        FROM {schema_name}.article_entities
        WHERE article_id = %s AND entity_name IS NOT NULL
        GROUP BY entity_name, entity_type
        """,
        (article_id,),
    )
    n = 0
    for name, etype, cnt in cur.fetchall():
        try:
            cur.execute(
                f"""
                INSERT INTO {schema_name}.story_entity_index
                (storyline_id, entity_name, entity_type, mention_count, is_core_entity, last_seen)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (storyline_id, entity_name) DO UPDATE SET
                    mention_count = {schema_name}.story_entity_index.mention_count + EXCLUDED.mention_count,
                    last_seen = NOW(),
                    is_core_entity = {schema_name}.story_entity_index.is_core_entity OR EXCLUDED.is_core_entity
                """,
                (
                    storyline_id,
                    (name or "")[:255],
                    (etype or "unknown")[:50],
                    int(cnt or 1),
                    int(cnt or 0) >= 2,
                ),
            )
            n += 1
        except Exception as e:
            logger.debug("story_entity_index %s/%s: %s", storyline_id, name, e)
    return n


def _mark_link_indexer_pass(cur, schema_name: str, article_id: int) -> None:
    cur.execute(
        f"""
        UPDATE {schema_name}.articles
        SET metadata = jsonb_set(
            COALESCE(metadata, '{{}}'::jsonb),
            '{{pipeline,link_indexer}}',
            jsonb_build_object('last_pass_at', NOW()::text, 'outcome', 'indexed'),
            true
        ),
        updated_at = NOW()
        WHERE id = %s
        """,
        (article_id,),
    )


def _index_cross_domain_soft_links(
    domain_key: str, schema_name: str, article_id: int
) -> int:
    """Shared canonical entities appearing in another domain recently → soft associate proposal."""
    try:
        other_window_days = int(env_str("LINK_INDEXER_CROSS_DOMAIN_DAYS", "14"))
    except ValueError:
        other_window_days = 14
    n = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT DISTINCT ae.canonical_entity_id
                FROM {schema_name}.article_entities ae
                WHERE ae.article_id = %s AND ae.canonical_entity_id IS NOT NULL
                """,
                (article_id,),
            )
            canonical_ids = [int(r[0]) for r in cur.fetchall()]
            if not canonical_ids:
                return 0
            for other_dk, other_schema in pipeline_url_schema_pairs():
                if other_dk == domain_key:
                    continue
                cur.execute(
                    f"""
                    SELECT DISTINCT ae.canonical_entity_id
                    FROM {other_schema}.article_entities ae
                    JOIN {other_schema}.articles a ON a.id = ae.article_id
                    WHERE ae.canonical_entity_id = ANY(%s)
                      AND a.updated_at >= NOW() - (%s || ' days')::interval
                    LIMIT 5
                    """,
                    (canonical_ids, other_window_days),
                )
                shared = [int(r[0]) for r in cur.fetchall()]
                if not shared:
                    continue
                from services.graph_connection_queue_service import upsert_graph_connection_proposal

                dedupe = f"cross_domain|{domain_key}|{other_dk}|{article_id}"
                pid = upsert_graph_connection_proposal(
                    dedupe_key=dedupe,
                    proposal_kind="associate",
                    domain_key=domain_key,
                    confidence=0.58,
                    source="link_indexer_cross_domain",
                    endpoints={
                        "domain_key": domain_key,
                        "entity_ids": shared,
                        "peer_domain_key": other_dk,
                    },
                    evidence={"article_id": article_id, "shared_canonical_ids": shared},
                    subject_summary=f"cross-domain entity overlap {domain_key}↔{other_dk}",
                )
                if pid:
                    n += 1
    return n


def export_open_proposals(*, limit: int = 40) -> list[dict[str, Any]]:
    """Context pack for editorial room loop."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, proposal_kind, domain_key, confidence, subject_summary,
                       endpoints, evidence, source
                FROM intelligence.graph_connection_proposals
                WHERE status = 'pending'
                ORDER BY confidence DESC, created_at DESC
                LIMIT %s
                """,
                (max(1, min(200, limit)),),
            )
            cols = [
                "id",
                "proposal_kind",
                "domain_key",
                "confidence",
                "subject_summary",
                "endpoints",
                "evidence",
                "source",
            ]
            out = []
            for row in cur.fetchall():
                item = dict(zip(cols, row))
                for k in ("endpoints", "evidence"):
                    if isinstance(item.get(k), str):
                        try:
                            item[k] = json.loads(item[k])
                        except json.JSONDecodeError:
                            pass
                out.append(item)
            return out
