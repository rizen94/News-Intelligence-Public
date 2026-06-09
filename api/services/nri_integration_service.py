"""Read nri.* tables and proxy NRI API for Investigate UI."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

NRI_API_URL = os.environ.get("NRI_API_URL", "http://127.0.0.1:8010").rstrip("/")
NRI_SCHEMA = os.environ.get("NRI_SCHEMA", "nri")


def _nri_proxy(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    url = f"{NRI_API_URL}{path}"
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
                FROM {NRI_SCHEMA}.resolved_mentions rm
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

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT pr.id, pr.context_id, pr.mention_text, pr.candidate_ftm_id,
                       pr.match_score, pr.reason, pr.parked_at, pr.review_status,
                       ep.domain_key, ep.metadata->>'canonical_name' AS canonical_name
                FROM {NRI_SCHEMA}.parked_resolution pr
                LEFT JOIN {NRI_SCHEMA}.resolved_mentions rm
                    ON rm.context_id = pr.context_id AND rm.mention_text = pr.mention_text
                LEFT JOIN intelligence.entity_profiles ep ON ep.id = rm.entity_profile_id
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
                       fc.caption, fc.schema_name, fc.dataset, fc.anchors
                FROM {NRI_SCHEMA}.entity_bridge eb
                LEFT JOIN {NRI_SCHEMA}.ftm_entity_cache fc ON fc.ftm_id = eb.ftm_id
                WHERE eb.entity_profile_id = %s
                """,
                (entity_profile_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return {"success": True, "bridge": None}
        return {
            "success": True,
            "bridge": {
                "entity_profile_id": row[0],
                "ftm_id": row[1],
                "bridge_score": row[2],
                "bridged_at": row[3].isoformat() if row[3] else None,
                "caption": row[4],
                "schema_name": row[5],
                "dataset": row[6],
                "anchors": row[7],
            },
        }
    except Exception as e:
        logger.warning("get_entity_bridge: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def review_parked(parked_id: int, review_status: str, candidate_ftm_id: str | None = None) -> dict[str, Any]:
    return _nri_proxy(
        "PATCH",
        f"/api/parked/{parked_id}",
        {"review_status": review_status, "candidate_ftm_id": candidate_ftm_id},
    )


def list_hypotheses(
    status: str | None = None,
    ftm_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    params = []
    if status:
        params.append(f"status={status}")
    if ftm_id:
        params.append(f"ftm_id={ftm_id}")
    params.append(f"limit={limit}")
    params.append(f"offset={offset}")
    qs = "&".join(params)
    return _nri_proxy("GET", f"/api/vault/hypotheses?{qs}")


def get_hypothesis(hyp_id: str) -> dict[str, Any]:
    return _nri_proxy("GET", f"/api/vault/hypotheses/{hyp_id}")


def get_nri_health() -> dict[str, Any]:
    return _nri_proxy("GET", "/health")
