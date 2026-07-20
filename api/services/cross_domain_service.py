"""
Cross-domain synthesis service — find correlations across active pipeline domains.
Populates intelligence.cross_domain_correlations; supports unified timeline.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


from shared.pipeline_domain_sql import normalize_legacy_domain_key


def _norm_tracked_domain_key(d: str) -> str:
    """Normalize legacy tokens so they match ``get_pipeline_active_domain_keys()`` hyphen keys."""
    return normalize_legacy_domain_key(d)


def _entity_profile_ids_from_row(val: Any) -> set[int]:
    out: set[int] = set()
    if not isinstance(val, list):
        return out
    for x in val:
        if isinstance(x, int):
            out.add(x)
        elif isinstance(x, float) and x == int(x):
            out.add(int(x))
        elif isinstance(x, dict) and "id" in x:
            try:
                out.add(int(x["id"]))
            except (TypeError, ValueError):
                pass
    return out


def _pairwise_entity_correlations(
    rows: list[tuple[Any, ...]],
    target_domains: list[str],
    *,
    correlation_threshold: float,
    max_rows: int = 280,
    max_pairs: int = 150,
) -> list[dict[str, Any]]:
    """Distinct event pairs sharing participant entity profiles and jointly touching 2+ target domains."""
    tset = set(target_domains)
    parsed: list[dict[str, Any]] = []
    for r in rows[:max_rows]:
        event_id, _et, _name, _sd, domain_keys, key_participant = r
        dks_raw = list(domain_keys) if domain_keys else []
        doms = [_norm_tracked_domain_key(x) for x in dks_raw]
        doms = [d for d in doms if d in tset]
        ent = _entity_profile_ids_from_row(key_participant)
        if not ent:
            continue
        try:
            eid = int(event_id)
        except (TypeError, ValueError):
            continue
        parsed.append({"id": eid, "domains": doms, "entities": ent})

    out: list[dict[str, Any]] = []
    seen_pairs: set[frozenset[int]] = set()
    for i, a in enumerate(parsed):
        for b in parsed[i + 1 :]:
            if len(out) >= max_pairs:
                return out
            shared = a["entities"] & b["entities"]
            if not shared:
                continue
            udom = (set(a["domains"]) | set(b["domains"])) & tset
            if len(udom) < 2:
                continue
            ek = frozenset({a["id"], b["id"]})
            if ek in seen_pairs:
                continue
            seen_pairs.add(ek)
            ds = sorted(udom)
            d1, d2 = ds[0], ds[1]
            strength = min(1.0, 0.55 + 0.04 * min(len(shared), 8))
            if strength < correlation_threshold:
                continue
            out.append(
                {
                    "domain_1": d1,
                    "domain_2": d2,
                    "event_ids": [a["id"], b["id"]],
                    "entity_profile_ids": list(shared)[:80],
                    "correlation_type": "entity_overlap",
                    "correlation_strength": strength,
                }
            )
    return out


def run_cross_domain_synthesis(
    domains: list[str] | None = None,
    time_window_days: int = 30,  # v8: full-history
    correlation_threshold: float = 0.5,
) -> dict[str, Any]:
    """
    Find cross-domain relationships (events spanning domains, shared entities, temporal overlap),
    persist to intelligence.cross_domain_correlations. Returns correlation_id(s) and list of correlations.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed", "correlations": []}
    from shared.domain_registry import get_pipeline_active_domain_keys

    allowed = frozenset(get_pipeline_active_domain_keys())
    target_domains = [d for d in (domains or list(allowed)) if d in allowed]
    if len(target_domains) < 2:
        return {
            "success": True,
            "correlation_id": None,
            "correlations": [],
            "message": "Need at least 2 domains",
        }
    since = date.today() - timedelta(days=time_window_days)
    try:
        with conn.cursor() as cur:
            # Events in window with domain_keys (array or similar)
            cur.execute(
                """
                SELECT id, event_type, event_name, start_date,
                       COALESCE(domain_keys, '{}') AS domain_keys,
                       COALESCE(key_participant_entity_ids, '[]') AS key_participant_entity_ids
                FROM intelligence.tracked_events
                WHERE (start_date IS NULL OR start_date >= %s)
                ORDER BY start_date DESC NULLS LAST
                LIMIT 1000
                """,
                (since,),
            )
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.warning("run_cross_domain_synthesis query: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e), "correlations": []}

    # Pairwise entity-overlap only. Mega temporal bags (every multi-domain event in
    # the window) made linked_events attach ICE / lithium / Iran war to SEC probes.
    seen_pairs: dict[tuple, dict[str, Any]] = {}
    pairwise_recs = _pairwise_entity_correlations(
        rows,
        target_domains,
        correlation_threshold=correlation_threshold,
    )
    for rec in pairwise_recs:
        pair = tuple(sorted((rec["domain_1"], rec["domain_2"])))
        eids = tuple(sorted(int(x) for x in (rec.get("event_ids") or []) if isinstance(x, int)))
        if len(eids) < 2:
            continue
        key = (pair[0], pair[1], eids)
        seen_pairs[key] = {
            "domain_1": pair[0],
            "domain_2": pair[1],
            "event_ids": list(eids),
            "entity_profile_ids": list(rec.get("entity_profile_ids", []))[:80],
            "correlation_type": "entity_overlap",
            "correlation_strength": float(
                rec.get("correlation_strength") or correlation_threshold
            ),
        }

    if not seen_pairs:
        return {"success": True, "correlation_id": None, "correlations": [], "meta_storylines": []}

    conn = get_db_connection()
    if not conn:
        return {
            "success": True,
            "correlation_id": None,
            "correlations": list(seen_pairs.values()),
            "meta_storylines": [],
        }
    inserted = []
    try:
        with conn.cursor() as cur:
            # Drop oversized bags first so linked_events stops serving junk immediately.
            cur.execute(
                """
                DELETE FROM intelligence.cross_domain_correlations
                WHERE cardinality(COALESCE(event_ids, '{}')) > 12
                """
            )
            purged = cur.rowcount or 0
            if purged:
                logger.info("cross_domain_synthesis purged %s mega-correlation rows", purged)

            # Aggregate pairwise hits per domain pair for today's upsert key.
            by_domain_pair: dict[tuple[str, str], dict[str, Any]] = {}
            for rec in seen_pairs.values():
                dp = (rec["domain_1"], rec["domain_2"])
                bucket = by_domain_pair.setdefault(
                    dp,
                    {
                        "domain_1": dp[0],
                        "domain_2": dp[1],
                        "event_ids": [],
                        "entity_profile_ids": [],
                        "correlation_type": "entity_overlap",
                        "correlation_strength": correlation_threshold,
                    },
                )
                for eid in rec["event_ids"]:
                    if eid not in bucket["event_ids"] and len(bucket["event_ids"]) < 12:
                        bucket["event_ids"].append(eid)
                for eid in rec["entity_profile_ids"]:
                    if eid not in bucket["entity_profile_ids"]:
                        bucket["entity_profile_ids"].append(eid)
                bucket["correlation_strength"] = max(
                    float(bucket["correlation_strength"]),
                    float(rec["correlation_strength"]),
                )

            for _dp, rec in by_domain_pair.items():
                event_ids = list(rec["event_ids"])[:12]
                entity_ids = list(rec["entity_profile_ids"])[:100]
                strength = float(rec.get("correlation_strength") or correlation_threshold)
                if strength < correlation_threshold or len(event_ids) < 2:
                    continue
                cor_id = uuid.uuid4()
                meta = {
                    "time_window_days": int(time_window_days),
                    "event_count": len(event_ids),
                    "entity_count": len(entity_ids),
                    "mode": "pairwise_entity_overlap",
                }
                cur.execute(
                    """
                    INSERT INTO intelligence.cross_domain_correlations
                    (correlation_id, domain_1, domain_2, entity_profile_ids, event_ids,
                     correlation_strength, correlation_type, as_of_date, discovered_at, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, NOW(), %s::jsonb)
                    ON CONFLICT (domain_1, domain_2, correlation_type, as_of_date)
                    DO UPDATE SET
                        entity_profile_ids = EXCLUDED.entity_profile_ids,
                        event_ids = EXCLUDED.event_ids,
                        correlation_strength = EXCLUDED.correlation_strength,
                        discovered_at = NOW(),
                        metadata = EXCLUDED.metadata
                    RETURNING correlation_id
                    """,
                    (
                        str(cor_id),
                        rec["domain_1"],
                        rec["domain_2"],
                        entity_ids,
                        event_ids,
                        strength,
                        rec["correlation_type"],
                        json.dumps(meta),
                    ),
                )
                row = cur.fetchone()
                out_id = str(row[0]) if row else str(cor_id)
                inserted.append(
                    {
                        "correlation_id": out_id,
                        "domain_1": rec["domain_1"],
                        "domain_2": rec["domain_2"],
                        "event_ids": event_ids,
                        "entity_profile_ids": entity_ids,
                        "correlation_strength": strength,
                        "correlation_type": rec["correlation_type"],
                        "as_of_date": None,
                    }
                )
        conn.commit()
    except Exception as e:
        logger.warning("run_cross_domain_synthesis insert: %s", e)
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    # Meta-storylines: one per correlation (storylines that span domains)
    meta_storylines = [
        {
            "title": f"{c['domain_1']}–{c['domain_2']} correlation",
            "domain_1": c["domain_1"],
            "domain_2": c["domain_2"],
            "correlation_id": c["correlation_id"],
            "event_ids": c["event_ids"],
            "entity_profile_ids": c.get("entity_profile_ids", []),
            "correlation_strength": c.get("correlation_strength"),
        }
        for c in inserted
    ]

    # v8: Processed documents that span domains (PDF sections in multiple domain_keys in window)
    cross_domain_document_ids: list[int] = []
    try:
        conn2 = get_db_connection()
        if conn2:
            with conn2.cursor() as cur:
                cur.execute(
                    """
                    SELECT (c.metadata->>'document_id')::int AS doc_id
                    FROM intelligence.contexts c
                    WHERE c.source_type = 'pdf_section'
                      AND c.created_at::date >= %s
                      AND c.metadata ? 'document_id'
                    GROUP BY (c.metadata->>'document_id')::int
                    HAVING COUNT(DISTINCT c.domain_key) >= 2
                    LIMIT 50
                    """,
                    (since,),
                )
                cross_domain_document_ids = [r[0] for r in cur.fetchall() if r[0] is not None]
            conn2.close()
    except Exception as e:
        logger.debug("run_cross_domain_synthesis cross_domain_documents: %s", e)

    return {
        "success": True,
        "correlation_id": str(inserted[0]["correlation_id"]) if inserted else None,
        "correlations": inserted,
        "meta_storylines": meta_storylines,
        "cross_domain_document_ids": cross_domain_document_ids,
    }


def get_cross_domain_correlations(
    domain_1: str | None = None,
    domain_2: str | None = None,
    since_days: int | None = None,
    limit: int = 50,
    latest_only: bool | None = None,
) -> dict[str, Any]:
    """Read correlation rows with optional filters.

    When ``latest_only`` is True (default if ``since_days`` is unset), return at most
    one row per (domain_1, domain_2) — the newest ``as_of_date``.
    """
    if latest_only is None:
        latest_only = since_days is None
    conn = get_db_connection()
    if not conn:
        return {"success": False, "correlations": [], "error": "Database connection failed"}
    try:
        conditions = ["1=1"]
        args: list[Any] = []
        if domain_1:
            conditions.append("c.domain_1 = %s")
            args.append(domain_1)
        if domain_2:
            conditions.append("c.domain_2 = %s")
            args.append(domain_2)
        if since_days is not None:
            conditions.append("c.discovered_at >= NOW() - INTERVAL '1 day' * %s")
            args.append(since_days)
        where_sql = " AND ".join(conditions)
        args.append(limit)
        if latest_only:
            sql = f"""
                SELECT c.correlation_id, c.domain_1, c.domain_2, c.entity_profile_ids, c.event_ids,
                       c.correlation_strength, c.correlation_type, c.discovered_at, c.metadata,
                       c.as_of_date
                FROM (
                    SELECT DISTINCT ON (domain_1, domain_2)
                           correlation_id, domain_1, domain_2, entity_profile_ids, event_ids,
                           correlation_strength, correlation_type, discovered_at, metadata, as_of_date
                    FROM intelligence.cross_domain_correlations
                    ORDER BY domain_1, domain_2, as_of_date DESC NULLS LAST,
                             discovered_at DESC NULLS LAST
                ) c
                WHERE {where_sql}
                ORDER BY c.correlation_strength DESC NULLS LAST, c.as_of_date DESC NULLS LAST
                LIMIT %s
                """
        else:
            sql = f"""
                SELECT c.correlation_id, c.domain_1, c.domain_2, c.entity_profile_ids, c.event_ids,
                       c.correlation_strength, c.correlation_type, c.discovered_at, c.metadata,
                       c.as_of_date
                FROM intelligence.cross_domain_correlations c
                WHERE {where_sql}
                ORDER BY c.discovered_at DESC
                LIMIT %s
                """
        with conn.cursor() as cur:
            cur.execute(sql, tuple(args))
            rows = cur.fetchall()
        conn.close()
        correlations = []
        for r in rows:
            event_ids = list(r[4]) if r[4] else []
            entity_ids = list(r[3]) if r[3] else []
            meta = r[8] or {}
            if not isinstance(meta, dict):
                meta = {}
            correlations.append(
                {
                    "correlation_id": str(r[0]),
                    "domain_1": r[1],
                    "domain_2": r[2],
                    "entity_profile_ids": entity_ids,
                    "event_ids": event_ids,
                    "correlation_strength": float(r[5]) if r[5] is not None else None,
                    "correlation_type": r[6],
                    "discovered_at": r[7].isoformat() if r[7] else None,
                    "metadata": meta,
                    "as_of_date": str(r[9]) if r[9] else None,
                    "event_count": int(meta.get("event_count") or len(event_ids)),
                    "entity_count": int(meta.get("entity_count") or len(entity_ids)),
                }
            )
        return {"success": True, "correlations": correlations}
    except Exception as e:
        logger.warning("get_cross_domain_correlations: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "correlations": [], "error": str(e)}


def _normalize_pair(domain_1: str, domain_2: str) -> tuple[str, str]:
    d1 = (domain_1 or "").strip().lower()
    d2 = (domain_2 or "").strip().lower()
    return (d1, d2) if d1 <= d2 else (d2, d1)


def get_cross_domain_bridges(limit: int = 50) -> dict[str, Any]:
    """Latest snapshot per domain pair (live bridges), with top entity display names."""
    result = get_cross_domain_correlations(latest_only=True, limit=limit)
    if not result.get("success"):
        return {"success": False, "bridges": [], "error": result.get("error")}
    bridges = []
    profile_ids: list[int] = []
    for c in result.get("correlations", []):
        ids = [int(x) for x in (c.get("entity_profile_ids") or [])[:10] if x is not None]
        profile_ids.extend(ids)
        bridges.append(
            {
                "domain_1": c["domain_1"],
                "domain_2": c["domain_2"],
                "correlation_type": c.get("correlation_type"),
                "correlation_strength": c.get("correlation_strength"),
                "as_of_date": c.get("as_of_date"),
                "discovered_at": c.get("discovered_at"),
                "event_count": c.get("event_count", 0),
                "entity_count": c.get("entity_count", 0),
                "entity_profile_ids": ids,
                "correlation_id": c.get("correlation_id"),
                "top_entities": [],
            }
        )
    name_by_id: dict[int, str] = {}
    uniq_ids = list(dict.fromkeys(profile_ids))[:200]
    if uniq_ids:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id,
                               COALESCE(
                                 metadata->>'canonical_name',
                                 sections->'identity'->>'canonical_name',
                                 sections->>'canonical_name',
                                 'profile:' || id::text
                               )
                        FROM intelligence.entity_profiles
                        WHERE id = ANY(%s)
                        """,
                        (uniq_ids,),
                    )
                    for row in cur.fetchall():
                        name_by_id[int(row[0])] = row[1] or f"profile:{row[0]}"
            except Exception as e:
                logger.debug("get_cross_domain_bridges entity names: %s", e)
            finally:
                conn.close()
    for b in bridges:
        names = []
        for eid in b["entity_profile_ids"][:3]:
            names.append(
                {
                    "entity_profile_id": eid,
                    "display_name": name_by_id.get(eid, f"profile:{eid}"),
                }
            )
        b["top_entities"] = names
    return {"success": True, "bridges": bridges}


def get_cross_domain_bridge_trend(
    domain_1: str,
    domain_2: str,
    days: int = 90,
) -> dict[str, Any]:
    """Daily strength + event_count series for a domain pair."""
    d1, d2 = _normalize_pair(domain_1, domain_2)
    days = max(1, min(int(days or 90), 365))
    conn = get_db_connection()
    if not conn:
        return {"success": False, "series": [], "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT as_of_date, correlation_strength, correlation_type,
                       COALESCE(
                         (metadata->>'event_count')::int,
                         COALESCE(array_length(event_ids, 1), 0)
                       ) AS event_count,
                       COALESCE(
                         (metadata->>'entity_count')::int,
                         COALESCE(array_length(entity_profile_ids, 1), 0)
                       ) AS entity_count
                FROM intelligence.cross_domain_correlations
                WHERE domain_1 = %s AND domain_2 = %s
                  AND as_of_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                ORDER BY as_of_date ASC
                """,
                (d1, d2, days),
            )
            rows = cur.fetchall()
        conn.close()
        series = [
            {
                "as_of_date": str(r[0]) if r[0] else None,
                "correlation_strength": float(r[1]) if r[1] is not None else None,
                "correlation_type": r[2],
                "event_count": int(r[3] or 0),
                "entity_count": int(r[4] or 0),
            }
            for r in rows
        ]
        return {
            "success": True,
            "domain_1": d1,
            "domain_2": d2,
            "days": days,
            "series": series,
        }
    except Exception as e:
        logger.warning("get_cross_domain_bridge_trend: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "series": [], "error": str(e)}


def get_cross_domain_bridge_entities(
    domain_1: str,
    domain_2: str,
    limit: int = 20,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Recurring entity_profile_ids across recent snapshots for a pair."""
    d1, d2 = _normalize_pair(domain_1, domain_2)
    limit = max(1, min(int(limit or 20), 100))
    lookback_days = max(1, min(int(lookback_days or 90), 365))
    conn = get_db_connection()
    if not conn:
        return {"success": False, "entities": [], "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH exploded AS (
                    SELECT unnest(entity_profile_ids) AS entity_profile_id, as_of_date
                    FROM intelligence.cross_domain_correlations
                    WHERE domain_1 = %s AND domain_2 = %s
                      AND as_of_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
                      AND entity_profile_ids IS NOT NULL
                      AND cardinality(entity_profile_ids) > 0
                ),
                ranked AS (
                    SELECT entity_profile_id,
                           COUNT(*)::int AS frequency,
                           MAX(as_of_date) AS last_seen
                    FROM exploded
                    WHERE entity_profile_id IS NOT NULL
                    GROUP BY entity_profile_id
                    ORDER BY COUNT(*) DESC, MAX(as_of_date) DESC
                    LIMIT %s
                )
                SELECT r.entity_profile_id,
                       r.frequency,
                       r.last_seen,
                       ep.domain_key,
                       COALESCE(
                         ep.metadata->>'canonical_name',
                         ep.sections->'identity'->>'canonical_name',
                         ep.sections->>'canonical_name'
                       ) AS display_name
                FROM ranked r
                LEFT JOIN intelligence.entity_profiles ep ON ep.id = r.entity_profile_id
                ORDER BY r.frequency DESC, r.last_seen DESC NULLS LAST
                """,
                (d1, d2, lookback_days, limit),
            )
            rows = cur.fetchall()
        conn.close()
        entities = [
            {
                "entity_profile_id": int(r[0]),
                "frequency": int(r[1] or 0),
                "last_seen": str(r[2]) if r[2] else None,
                "domain_key": r[3],
                "display_name": r[4] or f"profile:{r[0]}",
            }
            for r in rows
            if r[0] is not None
        ]
        return {
            "success": True,
            "domain_1": d1,
            "domain_2": d2,
            "lookback_days": lookback_days,
            "entities": entities,
        }
    except Exception as e:
        logger.warning("get_cross_domain_bridge_entities: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "entities": [], "error": str(e)}


def get_unified_timeline(
    domains: list[str] | None = None,
    since_days: int | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Chronological events across domains with domain_key, event_type, entity links."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "events": [], "error": "Database connection failed"}
    try:
        conditions = ["1=1"]
        args: list[Any] = []
        if since_days is not None:
            conditions.append(
                "(te.start_date IS NULL OR te.start_date >= CURRENT_DATE - INTERVAL '1 day' * %s)"
            )
            args.append(since_days)
        if domains:
            conditions.append("te.domain_keys && %s")
            args.append(domains)
        args.append(limit)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT te.id, te.event_type, te.event_name, te.start_date, te.end_date,
                       te.geographic_scope, te.key_participant_entity_ids, te.domain_keys, te.created_at
                FROM intelligence.tracked_events te
                WHERE """
                + " AND ".join(conditions)
                + """
                ORDER BY te.start_date DESC NULLS LAST, te.created_at DESC
                LIMIT %s
                """,
                tuple(args),
            )
            rows = cur.fetchall()
        conn.close()
        events = []
        for r in rows:
            events.append(
                {
                    "id": r[0],
                    "event_type": r[1],
                    "event_name": r[2],
                    "start_date": str(r[3]) if r[3] else None,
                    "end_date": str(r[4]) if r[4] else None,
                    "geographic_scope": r[5],
                    "key_participant_entity_ids": r[6]
                    if isinstance(r[6], list)
                    else (list(r[6]) if r[6] else []),
                    "domain_keys": list(r[7]) if r[7] else [],
                    "created_at": r[8].isoformat() if r[8] else None,
                }
            )
        return {"success": True, "events": events}
    except Exception as e:
        logger.warning("get_unified_timeline: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "events": [], "error": str(e)}


def get_meta_storylines(
    domain_1: str | None = None,
    domain_2: str | None = None,
    since_days: int | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Meta-storylines (cross-domain storylines) derived from cross_domain_correlations."""
    result = get_cross_domain_correlations(
        domain_1=domain_1,
        domain_2=domain_2,
        since_days=since_days,
        limit=limit,
    )
    if not result.get("success"):
        return {"success": False, "meta_storylines": [], "error": result.get("error")}
    meta_storylines = [
        {
            "title": f"{c['domain_1']}–{c['domain_2']} correlation",
            "domain_1": c["domain_1"],
            "domain_2": c["domain_2"],
            "correlation_id": c["correlation_id"],
            "event_ids": c["event_ids"],
            "entity_profile_ids": c.get("entity_profile_ids", []),
            "correlation_strength": c.get("correlation_strength"),
            "discovered_at": c.get("discovered_at"),
        }
        for c in result.get("correlations", [])
    ]
    return {"success": True, "meta_storylines": meta_storylines}
