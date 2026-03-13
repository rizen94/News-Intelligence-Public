"""
Pattern recognition service — Phase 2.2 context-centric.
Detects behavioral, temporal, network, and event patterns from contexts/claims/mentions;
persists to intelligence.pattern_discoveries. See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

PATTERN_TYPES = ("network", "temporal", "behavioral", "event")


def _discover_network_patterns(conn, domain_key: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """
    Co-occurrence: entity profiles that appear together in the same context.
    One pattern per (profile_a, profile_b) pair with context_ids and confidence from mention count.
    """
    patterns = []
    with conn.cursor() as cur:
        if domain_key:
            cur.execute(
                """
                SELECT cem.context_id, array_agg(cem.entity_profile_id ORDER BY cem.entity_profile_id) AS profile_ids
                FROM intelligence.context_entity_mentions cem
                JOIN intelligence.contexts c ON c.id = cem.context_id
                WHERE c.domain_key = %s
                GROUP BY cem.context_id
                HAVING COUNT(DISTINCT cem.entity_profile_id) >= 2
                ORDER BY cem.context_id DESC
                LIMIT %s
                """,
                (domain_key, limit * 2),
            )
        else:
            cur.execute(
                """
                SELECT cem.context_id, array_agg(cem.entity_profile_id ORDER BY cem.entity_profile_id) AS profile_ids
                FROM intelligence.context_entity_mentions cem
                GROUP BY cem.context_id
                HAVING COUNT(DISTINCT cem.entity_profile_id) >= 2
                ORDER BY cem.context_id DESC
                LIMIT %s
                """,
                (limit * 2,),
            )
        for context_id, profile_ids in cur.fetchall():
            if not profile_ids or len(profile_ids) < 2:
                continue
            profile_ids = list(profile_ids)
            for i in range(len(profile_ids)):
                for j in range(i + 1, len(profile_ids)):
                    a, b = profile_ids[i], profile_ids[j]
                    patterns.append({
                        "pattern_type": "network",
                        "domain_key": domain_key,
                        "context_ids": [context_id],
                        "entity_profile_ids": [a, b],
                        "confidence": 0.75,
                        "data": {"relation": "co_mentioned", "context_count": 1},
                    })
    return patterns


def _discover_temporal_patterns(conn, domain_key: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """
    Context density over time: group contexts by created_at date, emit one pattern per day with multiple contexts.
    """
    patterns = []
    with conn.cursor() as cur:
        if domain_key:
            cur.execute(
                """
                SELECT DATE(c.created_at) AS d, array_agg(c.id ORDER BY c.id) AS ctx_ids, COUNT(*) AS cnt
                FROM intelligence.contexts c
                WHERE c.domain_key = %s AND c.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(c.created_at)
                HAVING COUNT(*) >= 2
                ORDER BY d DESC
                LIMIT %s
                """,
                (domain_key, limit),
            )
        else:
            cur.execute(
                """
                SELECT DATE(c.created_at) AS d, array_agg(c.id ORDER BY c.id) AS ctx_ids, COUNT(*) AS cnt
                FROM intelligence.contexts c
                WHERE c.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(c.created_at)
                HAVING COUNT(*) >= 2
                ORDER BY d DESC
                LIMIT %s
                """,
                (limit,),
            )
        for d, ctx_ids, cnt in cur.fetchall():
            patterns.append({
                "pattern_type": "temporal",
                "domain_key": domain_key,
                "context_ids": list(ctx_ids) if ctx_ids else [],
                "entity_profile_ids": [],
                "confidence": min(0.9, 0.5 + 0.1 * min(cnt, 4)),
                "data": {"date": str(d), "context_count": cnt},
            })
    return patterns


def _discover_behavioral_patterns(conn, domain_key: Optional[str], limit: int) -> List[Dict[str, Any]]:
    """
    Entity + source type: which entity profiles appear in which source types (e.g. article).
    One pattern per (entity_profile_id, source_type) with context count.
    """
    patterns = []
    with conn.cursor() as cur:
        if domain_key:
            cur.execute(
                """
                SELECT c.source_type, cem.entity_profile_id, array_agg(DISTINCT c.id) AS ctx_ids, COUNT(DISTINCT c.id) AS cnt
                FROM intelligence.contexts c
                JOIN intelligence.context_entity_mentions cem ON cem.context_id = c.id
                WHERE c.domain_key = %s
                GROUP BY c.source_type, cem.entity_profile_id
                HAVING COUNT(DISTINCT c.id) >= 2
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (domain_key, limit),
            )
        else:
            cur.execute(
                """
                SELECT c.source_type, cem.entity_profile_id, array_agg(DISTINCT c.id) AS ctx_ids, COUNT(DISTINCT c.id) AS cnt
                FROM intelligence.contexts c
                JOIN intelligence.context_entity_mentions cem ON cem.context_id = c.id
                GROUP BY c.source_type, cem.entity_profile_id
                HAVING COUNT(DISTINCT c.id) >= 2
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (limit,),
            )
        for source_type, profile_id, ctx_ids, cnt in cur.fetchall():
            patterns.append({
                "pattern_type": "behavioral",
                "domain_key": domain_key,
                "context_ids": list(ctx_ids)[:50] if ctx_ids else [],
                "entity_profile_ids": [profile_id],
                "confidence": min(0.9, 0.5 + 0.05 * min(cnt, 8)),
                "data": {"source_type": source_type, "context_count": cnt},
            })
    return patterns


def _discover_event_patterns(conn, limit: int) -> List[Dict[str, Any]]:
    """
    Events sharing participants: from tracked_events.key_participant_entity_ids, find events that share >= 1 entity.
    """
    patterns = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, event_type, event_name, key_participant_entity_ids
            FROM intelligence.tracked_events
            WHERE key_participant_entity_ids IS NOT NULL AND jsonb_array_length(key_participant_entity_ids) > 0
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit * 2,),
        )
        rows = cur.fetchall()
    if len(rows) < 2:
        return patterns
    # Build sets of participant ids per event; find pairs that share at least one participant
    event_profiles: Dict[int, Set[int]] = {}
    for event_id, _et, _en, ids_json in rows:
        ids: Set[int] = set()
        try:
            raw = ids_json if isinstance(ids_json, list) else json.loads(ids_json or "[]")
            for x in raw or []:
                if isinstance(x, int):
                    ids.add(x)
                elif isinstance(x, (float, str)):
                    ids.add(int(x))
        except Exception:
            pass
        if ids:
            event_profiles[event_id] = ids
    seen_pairs: Set[Tuple[int, int]] = set()
    for eid1, set1 in event_profiles.items():
        for eid2, set2 in event_profiles.items():
            if eid1 >= eid2:
                continue
            if set1 & set2:
                pair = (eid1, eid2)
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    patterns.append({
                        "pattern_type": "event",
                        "domain_key": None,
                        "context_ids": [],
                        "entity_profile_ids": list(set1 | set2),
                        "confidence": 0.7,
                        "data": {"event_ids": [eid1, eid2], "shared_participants": True},
                    })
                    if len(patterns) >= limit:
                        return patterns
    return patterns


def run_pattern_discovery(domain_key: Optional[str] = None, limit_per_type: int = 20) -> int:
    """
    Run pattern detectors and insert into pattern_discoveries.
    When domain_key is None, only event and temporal (all domains) run.
    Returns number of patterns inserted.
    """
    conn = get_db_connection()
    if not conn:
        logger.warning("Pattern recognition: no DB connection")
        return 0
    inserted = 0
    try:
        all_patterns: List[Dict[str, Any]] = []
        if domain_key is not None:
            all_patterns.extend(_discover_network_patterns(conn, domain_key, limit_per_type))
            all_patterns.extend(_discover_temporal_patterns(conn, domain_key, limit_per_type))
            all_patterns.extend(_discover_behavioral_patterns(conn, domain_key, limit_per_type))
        else:
            all_patterns.extend(_discover_temporal_patterns(conn, None, limit_per_type))
        all_patterns.extend(_discover_event_patterns(conn, limit_per_type))

        with conn.cursor() as cur:
            for p in all_patterns:
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.pattern_discoveries
                        (pattern_type, domain_key, context_ids, entity_profile_ids, confidence, data)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            p["pattern_type"],
                            p.get("domain_key"),
                            p.get("context_ids") or [],
                            p.get("entity_profile_ids") or [],
                            p.get("confidence"),
                            json.dumps(p.get("data") or {}),
                        ),
                    )
                    inserted += 1
                except Exception as e:
                    logger.debug(f"Pattern insert skip: {e}")
        conn.commit()
        conn.close()
        if inserted > 0:
            logger.info(f"Pattern recognition: {inserted} patterns discovered")
        return inserted
    except Exception as e:
        logger.warning(f"Pattern recognition failed: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return 0


def run_pattern_discovery_batch() -> int:
    """Run pattern discovery for each domain, then global (temporal + event). Returns total inserted."""
    total = 0
    for domain_key in ("politics", "finance", "science-tech"):
        total += run_pattern_discovery(domain_key=domain_key, limit_per_type=15)
    total += run_pattern_discovery(domain_key=None, limit_per_type=10)
    return total
