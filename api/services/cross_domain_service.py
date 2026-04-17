"""
Cross-domain synthesis service — find correlations across active pipeline domains.
Populates intelligence.cross_domain_correlations; supports unified timeline.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import logging
import uuid
from datetime import date, timedelta
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def _norm_tracked_domain_key(d: str) -> str:
    """Normalize legacy tokens so they match ``get_pipeline_active_domain_keys()`` hyphen keys."""
    x = str(d).lower().strip().replace("_", "-")
    if x in ("science-tech", "sciencetech", "science tech"):
        return "artificial-intelligence"
    return x


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

    # Build correlation rows: (domain_1, domain_2, event_ids, entity_ids, type, strength)
    seen_pairs: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        event_id, event_type, event_name, start_date, domain_keys, key_participant = r
        event_domains = [
            _norm_tracked_domain_key(x)
            for x in (list(domain_keys) if isinstance(domain_keys, (list, tuple)) else [])
        ]
        entity_ids = []
        if isinstance(key_participant, list):
            for x in key_participant:
                if isinstance(x, int):
                    entity_ids.append(x)
                elif isinstance(x, dict) and "id" in x:
                    entity_ids.append(x["id"])
        for i, d1 in enumerate(event_domains):
            for d2 in event_domains[i + 1 :]:
                if d1 not in target_domains or d2 not in target_domains:
                    continue
                pair = (min(d1, d2), max(d1, d2))
                if pair not in seen_pairs:
                    seen_pairs[pair] = {
                        "domain_1": pair[0],
                        "domain_2": pair[1],
                        "event_ids": [],
                        "entity_profile_ids": [],
                        "correlation_type": "temporal",
                        "correlation_strength": correlation_threshold,
                    }
                rec = seen_pairs[pair]
                if event_id not in rec["event_ids"]:
                    rec["event_ids"].append(event_id)
                for eid in entity_ids:
                    if eid not in rec["entity_profile_ids"]:
                        rec["entity_profile_ids"].append(eid)

    pairwise_recs = _pairwise_entity_correlations(
        rows,
        target_domains,
        correlation_threshold=correlation_threshold,
    )
    for rec in pairwise_recs:
        pair = tuple(sorted((rec["domain_1"], rec["domain_2"])))
        if pair not in seen_pairs:
            seen_pairs[pair] = {
                "domain_1": pair[0],
                "domain_2": pair[1],
                "event_ids": list(rec.get("event_ids", [])),
                "entity_profile_ids": list(rec.get("entity_profile_ids", [])),
                "correlation_type": rec.get("correlation_type", "entity_overlap"),
                "correlation_strength": rec.get("correlation_strength", correlation_threshold),
            }
        else:
            existing = seen_pairs[pair]
            for eid in rec.get("event_ids", []):
                if eid not in existing["event_ids"]:
                    existing["event_ids"].append(eid)
            for eid in rec.get("entity_profile_ids", []):
                if eid not in existing["entity_profile_ids"]:
                    existing["entity_profile_ids"].append(eid)
            if (
                rec.get("correlation_type") == "entity_overlap"
                and existing.get("correlation_type") == "temporal"
            ):
                existing["correlation_type"] = "mixed"

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
            for pair, rec in seen_pairs.items():
                strength = min(
                    1.0, 0.5 + 0.1 * (len(rec["event_ids"]) + len(rec["entity_profile_ids"]))
                )
                if strength < correlation_threshold:
                    continue
                cor_id = uuid.uuid4()
                cur.execute(
                    """
                    INSERT INTO intelligence.cross_domain_correlations
                    (correlation_id, domain_1, domain_2, entity_profile_ids, event_ids, correlation_strength, correlation_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        cor_id,
                        rec["domain_1"],
                        rec["domain_2"],
                        rec["entity_profile_ids"][:100],
                        rec["event_ids"][:100],
                        strength,
                        rec["correlation_type"],
                    ),
                )
                inserted.append(
                    {
                        "correlation_id": str(cor_id),
                        "domain_1": rec["domain_1"],
                        "domain_2": rec["domain_2"],
                        "event_ids": rec["event_ids"],
                        "entity_profile_ids": rec["entity_profile_ids"],
                        "correlation_strength": strength,
                        "correlation_type": rec["correlation_type"],
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
) -> dict[str, Any]:
    """Read correlation rows with optional filters."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "correlations": [], "error": "Database connection failed"}
    try:
        conditions = ["1=1"]
        args: list[Any] = []
        if domain_1:
            conditions.append("domain_1 = %s")
            args.append(domain_1)
        if domain_2:
            conditions.append("domain_2 = %s")
            args.append(domain_2)
        if since_days is not None:
            conditions.append("discovered_at >= NOW() - INTERVAL '1 day' * %s")
            args.append(since_days)
        args.append(limit)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT correlation_id, domain_1, domain_2, entity_profile_ids, event_ids,
                       correlation_strength, correlation_type, discovered_at, metadata
                FROM intelligence.cross_domain_correlations
                WHERE """
                + " AND ".join(conditions)
                + """
                ORDER BY discovered_at DESC
                LIMIT %s
                """,
                tuple(args),
            )
            rows = cur.fetchall()
        conn.close()
        correlations = []
        for r in rows:
            correlations.append(
                {
                    "correlation_id": str(r[0]),
                    "domain_1": r[1],
                    "domain_2": r[2],
                    "entity_profile_ids": list(r[3]) if r[3] else [],
                    "event_ids": list(r[4]) if r[4] else [],
                    "correlation_strength": float(r[5]) if r[5] is not None else None,
                    "correlation_type": r[6],
                    "discovered_at": r[7].isoformat() if r[7] else None,
                    "metadata": r[8] or {},
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
