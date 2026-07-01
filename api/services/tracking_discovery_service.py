"""
Deterministic tracking discovery — ports news-tracking-discovery.md passes to Python.

Single discovery brain for Widow cron, NI API, and Open WebUI thin-client prompts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.runtime import env_int
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

from services import vault_bridge_service as vault_bridge

logger = logging.getLogger(__name__)

_CANDIDATE_TYPES = frozenset(
    {"storyline", "context_thread", "entity_hub", "cross_domain_bridge", "investigation_lead"}
)


def _parse_since(since: str | None, cursors: dict[str, str | None]) -> datetime:
    raw = since or cursors.get("last_tracking_scan_at") or cursors.get("last_reviewed_at")
    if raw:
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.utcnow() - timedelta(days=7)


def _score_candidate(
    *,
    momentum: int,
    coherence: int,
    vault_gap: int,
    cross_domain: int,
    editorial: int,
) -> int:
    return max(5, min(25, momentum + coherence + vault_gap + cross_domain + editorial))


def _pass1_domain_pulse(since: datetime, domain_keys: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for dk in domain_keys:
                    schema = resolve_domain_schema(dk)
                    try:
                        cur.execute(
                            f"""
                            SELECT id, title, article_count, quality_score, updated_at
                            FROM {schema}.storylines
                            WHERE status = 'active'
                              AND merged_into_id IS NULL
                              AND updated_at >= %s
                            ORDER BY updated_at DESC, article_count DESC NULLS LAST,
                                     quality_score DESC NULLS LAST
                            LIMIT 15
                            """,
                            (since,),
                        )
                        for sid, title, ac, qs, upd in cur.fetchall():
                            momentum = 5 if (ac or 0) >= 5 else 3 if (ac or 0) >= 2 else 1
                            coherence = 4 if (qs or 0) >= 0.6 else 2
                            out.append(
                                {
                                    "type": "storyline",
                                    "domain_key": dk,
                                    "domain_keys": [dk],
                                    "storyline_id": int(sid),
                                    "title": title,
                                    "article_count": ac or 0,
                                    "updated_at": upd.isoformat() if upd else None,
                                    "momentum": momentum,
                                    "coherence": coherence,
                                    "cross_domain": 1,
                                    "editorial": 3,
                                    "why": f"Active storyline momentum in {dk}",
                                    "suggested_action": "30_Stories brief",
                                }
                            )
                        cur.execute(
                            f"""
                            SELECT COUNT(*) FROM {schema}.articles a
                            WHERE a.created_at >= %s
                              AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                            """,
                            (since,),
                        )
                        recent_count = int(cur.fetchone()[0] or 0)
                        if recent_count >= 10:
                            out.append(
                                {
                                    "type": "storyline",
                                    "domain_key": dk,
                                    "domain_keys": [dk],
                                    "title": f"Unlinked article momentum ({recent_count} new)",
                                    "momentum": 5,
                                    "coherence": 2,
                                    "cross_domain": 1,
                                    "editorial": 4,
                                    "why": f"{recent_count} articles since scan — assembly catch-up",
                                    "suggested_action": "run storyline_assembly",
                                }
                            )
                        cur.execute(
                            f"""
                            SELECT id, cluster_name, article_count, updated_at
                            FROM {schema}.topic_clusters
                            WHERE article_count > 0 AND updated_at >= %s
                            ORDER BY article_count DESC, updated_at DESC
                            LIMIT 10
                            """,
                            (since,),
                        )
                        for tc_id, name, ac, upd in cur.fetchall():
                            out.append(
                                {
                                    "type": "investigation_lead",
                                    "domain_key": dk,
                                    "domain_keys": [dk],
                                    "topic_cluster_id": int(tc_id),
                                    "title": name or f"Topic cluster {tc_id}",
                                    "momentum": 3 if (ac or 0) >= 3 else 1,
                                    "coherence": 3,
                                    "cross_domain": 1,
                                    "editorial": 2,
                                    "why": "Rising topic cluster — manual convert only",
                                    "suggested_action": "append to work-queue",
                                }
                            )
                    except Exception as e:
                        logger.debug("pass1 %s: %s", dk, e)
    except Exception as e:
        logger.warning("_pass1_domain_pulse: %s", e)
    return out


def _pass2_intelligence_layer(since: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.title, c.domain_key, COUNT(ec.id) AS claim_count
                    FROM intelligence.contexts c
                    JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                    WHERE c.updated_at >= %s
                    GROUP BY c.id, c.title, c.domain_key
                    HAVING COUNT(ec.id) >= 3
                    ORDER BY claim_count DESC
                    LIMIT 20
                    """,
                    (since,),
                )
                for ctx_id, title, dk, cc in cur.fetchall():
                    out.append(
                        {
                            "type": "context_thread",
                            "domain_key": dk,
                            "domain_keys": [dk] if dk else [],
                            "context_id": int(ctx_id),
                            "title": title or f"Context {ctx_id}",
                            "momentum": 4 if cc >= 8 else 3,
                            "coherence": 5 if cc >= 5 else 3,
                            "cross_domain": 1,
                            "editorial": 4,
                            "why": f"{cc} claims on context",
                            "suggested_action": "open investigation",
                        }
                    )
                cur.execute(
                    """
                    SELECT ep.id, ep.domain_key, ep.canonical_entity_id,
                           COUNT(DISTINCT cem.context_id) AS ctx_count
                    FROM intelligence.entity_profiles ep
                    JOIN intelligence.context_entity_mentions cem ON cem.entity_profile_id = ep.id
                    JOIN intelligence.contexts c ON c.id = cem.context_id
                    WHERE c.updated_at >= %s
                    GROUP BY ep.id, ep.domain_key, ep.canonical_entity_id
                    HAVING COUNT(DISTINCT cem.context_id) >= 3
                    ORDER BY ctx_count DESC
                    LIMIT 15
                    """,
                    (since,),
                )
                for pid, dk, cid, ctx_count in cur.fetchall():
                    out.append(
                        {
                            "type": "entity_hub",
                            "domain_key": dk,
                            "domain_keys": [dk] if dk else [],
                            "entity_profile_id": int(pid),
                            "canonical_entity_id": cid,
                            "title": f"Entity profile {pid} ({ctx_count} contexts)",
                            "momentum": 4,
                            "coherence": 3,
                            "cross_domain": 1,
                            "editorial": 3,
                            "why": f"Entity in {ctx_count} recent contexts",
                            "suggested_action": "entity hub",
                        }
                    )
    except Exception as e:
        logger.warning("_pass2_intelligence_layer: %s", e)
    return out


def _pass3_cross_domain(since: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name', '') AS cname,
                           array_agg(DISTINCT ep.domain_key) AS domains,
                           COUNT(DISTINCT ep.id) AS profile_count
                    FROM intelligence.entity_profiles ep
                    WHERE ep.updated_at >= %s
                      AND COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name', '') != ''
                    GROUP BY 1
                    HAVING COUNT(DISTINCT ep.domain_key) >= 2
                    ORDER BY profile_count DESC
                    LIMIT 15
                    """,
                    (since,),
                )
                for name, domains, pc in cur.fetchall():
                    dlist = list(domains or [])
                    out.append(
                        {
                            "type": "cross_domain_bridge",
                            "domain_keys": dlist,
                            "title": name,
                            "momentum": 3,
                            "coherence": 3,
                            "cross_domain": 5,
                            "editorial": 4,
                            "why": f"Entity spans {len(dlist)} domains",
                            "suggested_action": "cross_domain_synthesis",
                        }
                    )
    except Exception as e:
        logger.warning("_pass3_cross_domain: %s", e)
    return out


def _reconcile_vault(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage = vault_bridge.build_coverage_set()
    reconciled: list[dict[str, Any]] = []
    for c in candidates[:40]:
        vault_covered = vault_bridge._is_vault_covered(c, coverage)
        vault_gap = 1 if vault_covered else 5
        score = _score_candidate(
            momentum=int(c.get("momentum", 2)),
            coherence=int(c.get("coherence", 2)),
            vault_gap=vault_gap,
            cross_domain=int(c.get("cross_domain", 1)),
            editorial=int(c.get("editorial", 2)),
        )
        row = dict(c)
        row["vault_covered"] = vault_covered
        row["score"] = score
        if vault_covered:
            row["status"] = "already_tracked"
        elif score < 12:
            row["status"] = "deferred"
        else:
            row["status"] = "candidate"
        reconciled.append(row)
    reconciled.sort(key=lambda x: x.get("score", 0), reverse=True)
    return reconciled


def run_tracking_discovery(
    *,
    since: str | None = None,
    domain_keys: list[str] | None = None,
    include_vault_reconcile: bool = True,
) -> dict[str, Any]:
    """
    Run passes 1–3 (+ optional vault reconcile). Returns ranked candidates JSON.
    """
    cursors = vault_bridge.read_cursors()
    since_dt = _parse_since(since, cursors)
    domains = domain_keys or list(get_pipeline_active_domain_keys())
    raw: list[dict[str, Any]] = []
    raw.extend(_pass1_domain_pulse(since_dt, domains))
    raw.extend(_pass2_intelligence_layer(since_dt))
    raw.extend(_pass3_cross_domain(since_dt))

    if include_vault_reconcile:
        candidates = _reconcile_vault(raw)
    else:
        candidates = raw
        for c in candidates:
            c["score"] = _score_candidate(
                momentum=int(c.get("momentum", 2)),
                coherence=int(c.get("coherence", 2)),
                vault_gap=3,
                cross_domain=int(c.get("cross_domain", 1)),
                editorial=int(c.get("editorial", 2)),
            )
            c["status"] = "candidate"

    ranked = [c for c in candidates if c.get("status") == "candidate"]
    return {
        "success": True,
        "scan_since": since_dt.isoformat() + "Z",
        "domains_scanned": domains,
        "raw_candidate_count": len(raw),
        "ranked_candidate_count": len(ranked),
        "already_tracked_count": sum(1 for c in candidates if c.get("status") == "already_tracked"),
        "items": ranked[: env_int("TRACKING_DISCOVERY_TOP_N", 25)],
        "all_candidates": candidates[:40],
    }
