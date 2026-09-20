"""Read nri.* tables and proxy NRI API for Investigate UI."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config.investigation_tables import (
    T_ENTITY_BRIDGE,
    T_FTM_ENTITY_CACHE,
    T_LOOP_RUN,
    T_PARKED_RESOLUTION,
    T_RESOLVED_MENTIONS,
    T_WATERMARKS,
)
from config.runtime import get_runtime_config
from nri_core.constants import PARKED_GENERIC_MENTIONS
from nri_core.services.bridge_qa import assess_bridge_qa, enrich_bridge_with_qa, pg_trgm_similarity
from nri_core.services.parked import review_parked_in_process
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def _nri_api_url() -> str:
    return str(get_runtime_config()["nri_api_url"])


def _nri_proxy(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    url = f"{_nri_api_url()}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode() if e.fp else str(e)
        logger.warning("NRI proxy %s %s failed: %s", method, path, detail)
        return {"error": detail, "status_code": e.code}
    except Exception as e:
        logger.warning("NRI proxy %s %s unreachable: %s", method, path, e)
        return {"error": str(e), "reachable": False}


def list_resolved_mentions(
    domain_key: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    where: list[str] = []
    params: list[Any] = []
    if domain_key:
        where.append("ep.domain_key = %s")
        params.append(domain_key)
    if status:
        where.append(f"rm.status = %s")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT rm.id, rm.context_id, rm.mention_text, rm.entity_profile_id,
                       rm.ftm_id, rm.match_score, rm.match_tier, rm.status, rm.resolved_at,
                       ep.domain_key, ep.metadata->>'canonical_name' AS canonical_name
                FROM {T_RESOLVED_MENTIONS} rm
                LEFT JOIN intelligence.entity_profiles ep ON ep.id = rm.entity_profile_id
                {where_sql}
                ORDER BY rm.resolved_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = cur.fetchall()
            items = [
                {
                    "id": r[0],
                    "context_id": r[1],
                    "mention_text": r[2],
                    "entity_profile_id": r[3],
                    "ftm_id": r[4],
                    "match_score": r[5],
                    "match_tier": r[6],
                    "status": r[7],
                    "resolved_at": r[8].isoformat() if r[8] else None,
                    "domain_key": r[9],
                    "canonical_name": r[10],
                }
                for r in rows
            ]
        conn.close()
        return {"success": True, "items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("list_resolved_mentions: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def list_parked_resolution(
    domain_key: str | None = None,
    review_status: str | None = "open",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    where: list[str] = []
    params: list[Any] = []
    if review_status:
        where.append("pr.review_status = %s")
        params.append(review_status)
    if domain_key:
        where.append("ep.domain_key = %s")
        params.append(domain_key)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    # Domain filter needs entity_profiles — use INNER JOINs to avoid scanning full parked table.
    join_ep = "INNER" if domain_key else "LEFT"

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT pr.id, pr.context_id, pr.mention_text, pr.candidate_ftm_id,
                       pr.match_score, pr.reason, pr.parked_at, pr.review_status,
                       ep.domain_key, ep.metadata->>'canonical_name' AS canonical_name
                FROM {T_PARKED_RESOLUTION} pr
                {join_ep} JOIN {T_RESOLVED_MENTIONS} rm
                    ON rm.context_id = pr.context_id AND rm.mention_text = pr.mention_text
                {join_ep} JOIN intelligence.entity_profiles ep ON ep.id = rm.entity_profile_id
                {where_sql}
                ORDER BY pr.parked_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = cur.fetchall()
            items = [
                {
                    "id": r[0],
                    "context_id": r[1],
                    "mention_text": r[2],
                    "candidate_ftm_id": r[3],
                    "match_score": r[4],
                    "reason": r[5],
                    "parked_at": r[6].isoformat() if r[6] else None,
                    "review_status": r[7],
                    "domain_key": r[8],
                    "canonical_name": r[9],
                }
                for r in rows
            ]
        conn.close()
        return {"success": True, "items": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.warning("list_parked_resolution: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def get_entity_bridge(entity_profile_id: int) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT eb.entity_profile_id, eb.ftm_id, eb.bridge_score, eb.bridged_at,
                       fc.caption, fc.schema_name, fc.dataset, fc.anchors,
                       ep.metadata->>'canonical_name' AS ni_canonical_name,
                       ep.metadata->>'entity_type' AS ni_entity_type
                FROM {T_ENTITY_BRIDGE} eb
                LEFT JOIN {T_FTM_ENTITY_CACHE} fc ON fc.ftm_id = eb.ftm_id
                LEFT JOIN intelligence.entity_profiles ep ON ep.id = eb.entity_profile_id
                WHERE eb.entity_profile_id = %s
                """,
                (entity_profile_id,),
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return {"success": True, "bridge": None}
            bridge = {
                "entity_profile_id": row[0],
                "ftm_id": row[1],
                "bridge_score": row[2],
                "bridged_at": row[3].isoformat() if row[3] else None,
                "caption": row[4],
                "schema_name": row[5],
                "dataset": row[6],
                "anchors": row[7],
            }
            bridge = enrich_bridge_with_qa(
                bridge,
                ni_canonical_name=row[8],
                ni_entity_type=row[9],
                cur=cur,
            )
        conn.close()
        return {"success": True, "bridge": bridge}
    except Exception as e:
        logger.warning("get_entity_bridge: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def audit_bridge_qa(
    domain_key: str | None = None,
    qa_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed", "items": []}

    where = ["1=1"]
    params: list[Any] = []
    if domain_key:
        where.append("ep.domain_key = %s")
        params.append(domain_key)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT eb.entity_profile_id, eb.ftm_id, eb.bridge_score, eb.bridged_at,
                       fc.caption, fc.schema_name, fc.dataset, fc.anchors,
                       ep.domain_key,
                       ep.metadata->>'canonical_name' AS ni_canonical_name,
                       ep.metadata->>'entity_type' AS ni_entity_type
                FROM {T_ENTITY_BRIDGE} eb
                JOIN intelligence.entity_profiles ep ON ep.id = eb.entity_profile_id
                LEFT JOIN {T_FTM_ENTITY_CACHE} fc ON fc.ftm_id = eb.ftm_id
                WHERE {' AND '.join(where)}
                ORDER BY eb.bridged_at DESC NULLS LAST
                """,
                tuple(params),
            )
            rows = cur.fetchall()
            items = []
            for row in rows:
                bridge = {
                    "entity_profile_id": row[0],
                    "ftm_id": row[1],
                    "bridge_score": row[2],
                    "bridged_at": row[3].isoformat() if row[3] else None,
                    "caption": row[4],
                    "schema_name": row[5],
                    "dataset": row[6],
                    "anchors": row[7],
                    "domain_key": row[8],
                }
                enriched = enrich_bridge_with_qa(
                    bridge,
                    ni_canonical_name=row[9],
                    ni_entity_type=row[10],
                    cur=cur,
                )
                if qa_status and enriched.get("qa_status") != qa_status:
                    continue
                if qa_status is None and enriched.get("qa_status") == "ok":
                    continue
                items.append(enriched)
            page = items[offset : offset + limit]
        conn.close()
        return {
            "success": True,
            "items": page,
            "limit": limit,
            "offset": offset,
            "total_filtered": len(items),
        }
    except Exception as e:
        logger.warning("audit_bridge_qa: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e), "items": []}


def get_context_intel(context_id: int, claims_limit: int = 100) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT rm.id, rm.mention_text, rm.entity_profile_id, rm.ftm_id,
                       rm.match_score, rm.status, rm.resolved_at,
                       ep.metadata->>'canonical_name' AS canonical_name,
                       ep.metadata->>'entity_type' AS entity_type,
                       fc.caption, fc.schema_name, fc.dataset, fc.anchors
                FROM {T_RESOLVED_MENTIONS} rm
                LEFT JOIN intelligence.entity_profiles ep ON ep.id = rm.entity_profile_id
                LEFT JOIN {T_FTM_ENTITY_CACHE} fc ON fc.ftm_id = rm.ftm_id
                WHERE rm.context_id = %s
                ORDER BY rm.resolved_at DESC
                """,
                (context_id,),
            )
            mentions = []
            status_counts: dict[str, int] = {}
            for row in cur.fetchall():
                status = row[5] or "unknown"
                status_counts[status] = status_counts.get(status, 0) + 1
                bridge = {
                    "ftm_id": row[3],
                    "caption": row[9],
                    "schema_name": row[10],
                    "dataset": row[11],
                    "anchors": row[12],
                }
                qa = assess_bridge_qa(
                    ni_canonical_name=row[7] or row[1],
                    ftm_caption=row[9],
                    ni_entity_type=row[8],
                    ftm_schema_name=row[10],
                    ftm_dataset=row[11],
                    mention_text=row[1],
                    anchors=row[12] if isinstance(row[12], dict) else None,
                    name_similarity=(
                        pg_trgm_similarity(cur, row[7] or row[1], row[9])
                        if row[9]
                        else None
                    ),
                )
                mentions.append(
                    {
                        "id": row[0],
                        "mention_text": row[1],
                        "entity_profile_id": row[2],
                        "ftm_id": row[3],
                        "match_score": row[4],
                        "status": status,
                        "resolved_at": row[6].isoformat() if row[6] else None,
                        "canonical_name": row[7],
                        "entity_type": row[8],
                        "ftm_caption": row[9],
                        **qa,
                    }
                )

            cur.execute(
                """
                SELECT id, subject_text, predicate_text, object_text, confidence, created_at
                FROM intelligence.extracted_claims
                WHERE context_id = %s
                ORDER BY created_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (context_id, claims_limit),
            )
            claims = [
                {
                    "id": r[0],
                    "subject_text": r[1],
                    "predicate_text": r[2],
                    "object_text": r[3],
                    "confidence": float(r[4]) if r[4] is not None else None,
                    "created_at": r[5].isoformat() if r[5] else None,
                }
                for r in cur.fetchall()
            ]
        conn.close()
        return {
            "success": True,
            "context_id": context_id,
            "mentions": mentions,
            "claims": claims,
            "status_counts": status_counts,
        }
    except Exception as e:
        logger.warning("get_context_intel: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def list_parked_cross_domain(
    exclude_generic: bool = True,
    min_domains: int = 2,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed", "items": []}

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT pr.mention_text,
                       COUNT(DISTINCT c.domain_key)::int AS domains,
                       COUNT(*)::int AS parked_contexts,
                       array_agg(DISTINCT c.domain_key ORDER BY c.domain_key) AS domain_list,
                       MIN(pr.context_id)::int AS sample_context_id
                FROM {T_PARKED_RESOLUTION} pr
                JOIN intelligence.contexts c ON c.id = pr.context_id
                GROUP BY pr.mention_text
                HAVING COUNT(DISTINCT c.domain_key) >= %s
                ORDER BY domains DESC, parked_contexts DESC, pr.mention_text
                """,
                (min_domains,),
            )
            items = []
            for row in cur.fetchall():
                mention = row[0]
                if exclude_generic and (mention or "").strip().lower() in PARKED_GENERIC_MENTIONS:
                    continue
                items.append(
                    {
                        "mention_text": mention,
                        "domains": row[1],
                        "parked_contexts": row[2],
                        "domain_list": list(row[3]) if row[3] else [],
                        "sample_context_id": row[4],
                    }
                )
            page = items[offset : offset + limit]
        conn.close()
        return {
            "success": True,
            "items": page,
            "limit": limit,
            "offset": offset,
            "total_filtered": len(items),
        }
    except Exception as e:
        logger.warning("list_parked_cross_domain: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e), "items": []}


def review_parked(parked_id: int, review_status: str, candidate_ftm_id: str | None = None) -> dict[str, Any]:
    return review_parked_in_process(
        parked_id, review_status=review_status, candidate_ftm_id=candidate_ftm_id
    )


def list_hypotheses(
    status: str | None = None,
    ftm_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    from nri_core.vault.reader.hypothesis_reader import list_hypotheses as vault_list

    return vault_list(status=status, ftm_id=ftm_id, limit=limit, offset=offset)


def get_hypothesis(hyp_id: str) -> dict[str, Any]:
    from nri_core.vault.reader.hypothesis_reader import get_hypothesis as vault_get

    result = vault_get(hyp_id)
    return result if result is not None else {"error": "not_found"}


def get_investigation_health() -> dict[str, Any]:
    """In-process health (no :8010 proxy)."""
    return {
        "success": True,
        "status": "ok",
        "component": "nri_core",
        "in_process": True,
    }


def get_nri_health() -> dict[str, Any]:
    return get_investigation_health()


def list_spine_entities(dataset: str | None = None, limit: int = 50) -> dict[str, Any]:
    from nri_core.spine.api.lookup import list_entities

    rows = list_entities(dataset=dataset, limit=limit)
    return {"success": True, "items": rows}


def match_spine(text: str, schema_name: str | None = None) -> dict[str, Any]:
    from nri_core.spine.api.lookup import match_mention

    result = match_mention(text=text, schema_name=schema_name)
    return {
        "ftm_id": result.ftm_id,
        "score": result.score,
        "tier": result.tier,
        "status": result.status,
        "candidates": result.candidates,
    }


def get_resolution_stats(domain_key: str | None = None) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    domain_filter = ""
    params: list[Any] = []
    if domain_key:
        domain_filter = "AND ep.domain_key = %s"
        params.append(domain_key)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT rm.status, COUNT(*)::int
                FROM {T_RESOLVED_MENTIONS} rm
                LEFT JOIN intelligence.entity_profiles ep ON ep.id = rm.entity_profile_id
                WHERE 1=1 {domain_filter}
                GROUP BY rm.status
                """,
                tuple(params),
            )
            by_status = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute(
                f"""
                SELECT COUNT(*)::int FROM {T_ENTITY_BRIDGE} eb
                JOIN intelligence.entity_profiles ep ON ep.id = eb.entity_profile_id
                WHERE 1=1 {('AND ep.domain_key = %s' if domain_key else '')}
                """,
                tuple([domain_key] if domain_key else ()),
            )
            bridge_count = cur.fetchone()[0]
            cur.execute(f"SELECT last_value FROM {T_WATERMARKS} WHERE name = 'mention_resolver'")
            wm = cur.fetchone()
            watermark = int(wm[0]) if wm else 0
            cur.execute("SELECT COALESCE(MAX(id), 0)::bigint FROM intelligence.context_entity_mentions")
            max_mention = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*)::bigint FROM intelligence.context_entity_mentions")
            total_cem = int(cur.fetchone()[0])
            cur.execute(f"SELECT COUNT(*)::bigint FROM {T_RESOLVED_MENTIONS}")
            resolved_total = int(cur.fetchone()[0])
        conn.close()
        person_org = {k: v for k, v in by_status.items() if k != "non_entity_topic"}
        po_total = sum(person_org.values()) or 1
        auto_linked = by_status.get("auto_linked", 0)
        parked = by_status.get("parked", 0)
        backfill_pct = round(resolved_total / total_cem, 4) if total_cem else 0.0
        watermark_pct = round(watermark / max_mention, 4) if max_mention else 0.0
        return {
            "success": True,
            "by_status": by_status,
            "entity_bridge_count": bridge_count,
            "auto_link_rate": round(auto_linked / po_total, 4),
            "park_rate": round(parked / po_total, 4),
            "watermark": watermark,
            "max_mention_id": max_mention,
            "watermark_lag": max(0, max_mention - watermark),
            "total_context_entity_mentions": total_cem,
            "resolved_mentions": resolved_total,
            "backfill_pct": backfill_pct,
            "watermark_pct": watermark_pct,
        }
    except Exception as e:
        logger.warning("get_resolution_stats: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def list_loop_runs(limit: int = 20) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, iteration, shadow_branch, killed, demoted,
                       dormant, added, started_at, finished_at
                FROM {T_LOOP_RUN}
                ORDER BY started_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            items = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                for ts_key in ("started_at", "finished_at"):
                    if d.get(ts_key):
                        d[ts_key] = d[ts_key].isoformat()
                items.append(d)
        conn.close()
        return {"success": True, "items": items}
    except Exception as e:
        logger.warning("list_loop_runs: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e), "items": []}


def get_ftm_cache_dataset_counts() -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT dataset, COUNT(*)::int
                FROM {T_FTM_ENTITY_CACHE}
                WHERE dataset IS NOT NULL
                GROUP BY dataset ORDER BY 2 DESC
                """
            )
            bridged = {r[0]: r[1] for r in cur.fetchall()}
        conn.close()
        return {"success": True, "bridged_by_dataset": bridged}
    except Exception as e:
        logger.warning("get_ftm_cache_dataset_counts: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def get_research_seeds(
    domains: list[str] | None = None,
    limit: int = 20,
    min_mentions: int = 3,
) -> dict[str, Any]:
    """
    Suggest research seeds for NRI loop based on:
    - Recent mention velocity (context_entity_mentions)
    - Claim density (extracted_claims per entity)
    - Cross-domain bridges (entity_bridge linking multiple domains)
    - Vault coverage gaps (entities with hypotheses but no tracking)
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    domain_filter = ""
    params: list[Any] = []
    if domains:
        placeholders = ",".join(["%s"] * len(domains))
        domain_filter = f"AND ep.domain_key IN ({placeholders})"
        params.extend(domains)

    try:
        with conn.cursor() as cur:
            # Get recent mention velocity per FTM entity
            cur.execute(
                f"""
                WITH recent_mentions AS (
                    SELECT
                        rm.ftm_id,
                        COUNT(*)::int AS mention_count,
                        MAX(cm.created_at) AS latest_mention
                    FROM {T_RESOLVED_MENTIONS} rm
                    JOIN intelligence.context_entity_mentions cm ON cm.id = rm.context_id
                    JOIN intelligence.entity_profiles ep ON ep.id = rm.entity_profile_id
                    WHERE rm.ftm_id IS NOT NULL
                      AND cm.created_at >= NOW() - INTERVAL '14 days'
                      {domain_filter}
                    GROUP BY rm.ftm_id
                    HAVING COUNT(*) >= %s
                ),
                claim_density AS (
                    SELECT
                        ec.ftm_id,
                        COUNT(*)::int AS claim_count
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.entity_profiles ep ON ep.id = ec.entity_profile_id
                    WHERE ec.ftm_id IS NOT NULL
                      {domain_filter}
                    GROUP BY ec.ftm_id
                ),
                cross_domain AS (
                    SELECT
                        eb.ftm_id,
                        COUNT(DISTINCT ep.domain_key)::int AS domain_count
                    FROM {T_ENTITY_BRIDGE} eb
                    JOIN intelligence.entity_profiles ep ON ep.id = eb.entity_profile_id
                    WHERE eb.ftm_id IS NOT NULL
                    GROUP BY eb.ftm_id
                    HAVING COUNT(DISTINCT ep.domain_key) >= 2
                ),
                vault_coverage AS (
                    SELECT
                        hyp.subject_ftm_id AS ftm_id,
                        COUNT(*)::int AS hyp_count,
                        MAX(hyp.confidence) AS max_confidence
                    FROM nri.hypotheses hyp
                    WHERE hyp.status IN ('open', 'promoted')
                    GROUP BY hyp.subject_ftm_id
                )
                SELECT
                    rm.ftm_id,
                    ep.metadata->>'canonical_name' AS canonical_name,
                    ep.domain_key,
                    rm.mention_count,
                    cd.claim_count,
                    COALESCE(xd.domain_count, 1) AS domain_count,
                    COALESCE(vc.hyp_count, 0) AS hypothesis_count,
                    COALESCE(vc.max_confidence, 0) AS max_hypothesis_confidence,
                    rm.latest_mention
                FROM recent_mentions rm
                JOIN intelligence.entity_profiles ep ON ep.id = (
                    SELECT id FROM intelligence.entity_profiles WHERE ftm_id = rm.ftm_id LIMIT 1
                )
                LEFT JOIN claim_density cd ON cd.ftm_id = rm.ftm_id
                LEFT JOIN cross_domain xd ON xd.ftm_id = rm.ftm_id
                LEFT JOIN vault_coverage vc ON vc.ftm_id = rm.ftm_id
                ORDER BY rm.mention_count DESC, cd.claim_count DESC, xd.domain_count DESC
                LIMIT %s
                """,
                (*params, min_mentions, limit),
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, row)) for row in cur.fetchall()]

        conn.close()

        # Score and rank
        for item in items:
            velocity = item.get("mention_count", 0)
            claims = item.get("claim_count", 0)
            domains = item.get("domain_count", 1)
            hyp = item.get("hypothesis_count", 0)

            # Score: velocity * 1.5 + claims * 2 + cross_domain_bonus * 5 - vault_coverage_penalty
            cross_bonus = 5 if domains >= 2 else 0
            vault_penalty = min(hyp * 2, 10)  # don't over-penalize
            item["score"] = round(velocity * 1.5 + claims * 2 + cross_bonus - vault_penalty, 2)
            item["rationale"] = (
                f"Velocity: {velocity}, Claims: {claims}, Domains: {domains}, Hypotheses: {hyp}"
            )

        items.sort(key=lambda x: x["score"], reverse=True)

        return {
            "success": True,
            "items": items[:limit],
            "criteria": {
                "domains": domains,
                "min_mentions": min_mentions,
                "lookback_days": 14,
            },
        }
    except Exception as e:
        logger.warning("get_research_seeds: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def set_research_seeds(ftm_ids: list[str], domains: list[str]) -> dict[str, Any]:
    """
    Store research seeds for NRI loop selector to pick up.
    Writes to runtime config watermark or a dedicated seeds table.
    """
    # For now, write to a watermark that the selector can read
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            # Use nri_watermarks table or create a simple seeds record
            cur.execute(
                f"""
                INSERT INTO {T_WATERMARKS} (name, last_value, metadata, updated_at)
                VALUES ('nri_research_seeds', 0, %s, NOW())
                ON CONFLICT (name) DO UPDATE SET
                    last_value = EXCLUDED.last_value + 1,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                (json.dumps({"ftm_ids": ftm_ids, "domains": domains, "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()},),),
            )
        conn.commit()
        conn.close()
        return {"success": True, "stored": {"ftm_ids": ftm_ids, "domains": domains}}
    except Exception as e:
        logger.warning("set_research_seeds: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
