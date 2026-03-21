"""
Investigation consolidation — group related tracked_events into superset events.

Finds events that are about the same theme (e.g. "war in Iran" from different angles)
and creates one superset event whose sub_event_ids list the component events.
Each component event keeps its own investigation report; the superset can have
a separate combined report (optional, via investigation_report_service).

Uses existing schema: event_type='superset', sub_event_ids = [child_id, ...].
"""

import logging
import re
from collections import defaultdict
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

# Event types we treat as "superset" container (not a leaf to cluster)
SUPERSET_EVENT_TYPE = "superset"

# Minimum events in a cluster to create a superset
MIN_CLUSTER_SIZE = 2

# Max superset events to create per run (avoid overload)
MAX_SUPERSETS_PER_RUN = 10


def _normalize_for_clustering(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return " ".join(t.split())


def _significant_tokens(event_name: str, geographic_scope: str) -> set[str]:
    """Tokens that can be used to cluster (skip very short and stopwords)."""
    stop = {
        "the",
        "and",
        "for",
        "with",
        "into",
        "from",
        "new",
        "says",
        "amid",
        "as",
        "at",
        "in",
        "on",
        "to",
    }
    name_tokens = set(_normalize_for_clustering(event_name).split())
    scope_tokens = set(_normalize_for_clustering(geographic_scope or "").split())
    combined = (name_tokens | scope_tokens) - stop
    return {t for t in combined if len(t) >= 2}


def run_consolidation(limit_events: int = 200) -> dict[str, Any]:
    """
    Cluster tracked_events by theme and create superset events where appropriate.

    - Events that are already listed in another event's sub_event_ids are skipped (already in a superset).
    - Events with event_type='superset' are skipped (they are containers).
    - Remaining "leaf" events are clustered by overlapping keywords (event_name + geographic_scope).
    - For each cluster of 2+ events, creates one new tracked_event with event_type='superset'
      and sub_event_ids = [id1, id2, ...].

    Returns summary: clusters_found, supersets_created, event_ids_consumed, errors.
    """
    result: dict[str, Any] = {
        "clusters_found": 0,
        "supersets_created": 0,
        "event_ids_consumed": [],
        "errors": [],
    }
    conn = get_db_connection()
    if not conn:
        result["errors"].append("no_db_connection")
        return result

    try:
        with conn.cursor() as cur:
            # All events: id, event_type, event_name, geographic_scope, sub_event_ids
            cur.execute(
                """
                SELECT id, event_type, event_name, geographic_scope, sub_event_ids, domain_keys
                FROM intelligence.tracked_events
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit_events,),
            )
            rows = cur.fetchall()

        # Child IDs = any event whose id appears in some other event's sub_event_ids
        child_ids: set[int] = set()
        superset_ids: set[int] = set()
        events_by_id: dict[int, dict[str, Any]] = {}
        for r in rows:
            eid, etype, name, scope, sub_ids, domain_keys = r[0], r[1], r[2], r[3], r[4], r[5]
            events_by_id[eid] = {
                "id": eid,
                "event_type": etype or "",
                "event_name": name or "",
                "geographic_scope": scope or "",
                "sub_event_ids": list(sub_ids) if sub_ids else [],
                "domain_keys": list(domain_keys) if domain_keys else [],
            }
            if etype == SUPERSET_EVENT_TYPE:
                superset_ids.add(eid)
            if sub_ids:
                for sid in sub_ids:
                    child_ids.add(sid)

        # Leaf events = not a child, not a superset
        leaf_events = [
            ev
            for ev in events_by_id.values()
            if ev["id"] not in child_ids and ev["event_type"] != SUPERSET_EVENT_TYPE
        ]

        if len(leaf_events) < MIN_CLUSTER_SIZE:
            result["message"] = (
                f"Not enough leaf events to cluster (need {MIN_CLUSTER_SIZE}+, have {len(leaf_events)})"
            )
            conn.close()
            return result

        # Cluster by shared significant tokens (event_name + geographic_scope)
        # Each event gets a "signature" set of tokens; we group events that share at least 2 tokens.
        token_to_events: dict[str, set[int]] = defaultdict(set)
        for ev in leaf_events:
            tokens = _significant_tokens(ev["event_name"], ev["geographic_scope"])
            for t in tokens:
                token_to_events[t].add(ev["id"])

        # Build clusters: connected components of events that share tokens
        leaf_ids = {e["id"] for e in leaf_events}
        assigned: set[int] = set()
        clusters: list[list[int]] = []
        for ev in leaf_events:
            eid = ev["id"]
            if eid in assigned:
                continue
            tokens = _significant_tokens(ev["event_name"], ev["geographic_scope"])
            if not tokens:
                continue
            # Collect all leaf event IDs that share any token with this event (BFS)
            cluster_ids: set[int] = set()
            stack = [eid]
            while stack:
                cur_id = stack.pop()
                if cur_id in cluster_ids:
                    continue
                if cur_id not in leaf_ids:
                    continue
                cluster_ids.add(cur_id)
                cur_ev = events_by_id.get(cur_id)
                if not cur_ev:
                    continue
                cur_tokens = _significant_tokens(cur_ev["event_name"], cur_ev["geographic_scope"])
                for t in cur_tokens:
                    for other_id in token_to_events.get(t, set()):
                        if other_id in leaf_ids and other_id not in cluster_ids:
                            stack.append(other_id)
            cluster_list = list(cluster_ids)
            if len(cluster_list) >= MIN_CLUSTER_SIZE:
                # Avoid duplicate clusters (same set)
                cluster_set = set(cluster_list)
                if not any(set(c) == cluster_set for c in clusters):
                    clusters.append(cluster_list)
                    for i in cluster_list:
                        assigned.add(i)

        result["clusters_found"] = len(clusters)

        # Create superset event per cluster (up to MAX_SUPERSETS_PER_RUN)
        created = 0
        for cluster_ids in clusters[:MAX_SUPERSETS_PER_RUN]:
            if created >= MAX_SUPERSETS_PER_RUN:
                break
            # Derive superset name from first event (e.g. "War in Iran (superset)")
            first = events_by_id.get(cluster_ids[0], {})
            base_name = (first.get("event_name") or "Event").strip()
            if "(superset)" not in base_name.lower():
                superset_name = f"{base_name} (superset)"
            else:
                superset_name = base_name
            # Geographic scope from first or combined
            scopes = {events_by_id.get(i, {}).get("geographic_scope") or "" for i in cluster_ids}
            scopes.discard("")
            geographic_scope = (
                ", ".join(sorted(scopes)) if scopes else (first.get("geographic_scope") or "")
            )
            # domain_keys: union of all in cluster
            all_domains: set[str] = set()
            for i in cluster_ids:
                for d in events_by_id.get(i, {}).get("domain_keys") or []:
                    all_domains.add(d)
            domain_keys_list = (
                list(all_domains) if all_domains else (first.get("domain_keys") or [])
            )

            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO intelligence.tracked_events
                        (event_type, event_name, start_date, end_date, geographic_scope, key_participant_entity_ids, milestones, sub_event_ids, domain_keys, created_at, updated_at)
                        VALUES (%s, %s, NULL, NULL, %s, '[]', '[]', %s, %s, NOW(), NOW())
                        RETURNING id
                        """,
                        (
                            SUPERSET_EVENT_TYPE,
                            superset_name,
                            geographic_scope,
                            cluster_ids,
                            domain_keys_list,
                        ),
                    )
                    new_id = cur.fetchone()[0]
                conn.commit()
                result["supersets_created"] += 1
                result["event_ids_consumed"].extend(cluster_ids)
                created += 1
                logger.info(
                    "Created superset event id=%s name=%s with %s sub_events",
                    new_id,
                    superset_name,
                    len(cluster_ids),
                )
            except Exception as e:
                logger.warning("Failed to create superset for cluster %s: %s", cluster_ids, e)
                result["errors"].append(str(e))
                conn.rollback()

        conn.close()
        result["message"] = (
            f"Created {result['supersets_created']} superset(s) from {result['clusters_found']} clusters."
        )
        return result
    except Exception as e:
        logger.exception("Investigation consolidation failed: %s", e)
        result["errors"].append(str(e))
        try:
            conn.close()
        except Exception:
            pass
        return result
