"""Harvest existing discovery writers into intelligence.connection_findings."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.runtime import env_bool, env_float, env_int
from services.discovery_finding_quality import is_bridgeable
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return env_bool("CONNECTION_DISCOVERY_ENABLED", True)


def min_confidence() -> float:
    return max(0.0, min(1.0, env_float("CONNECTION_DISCOVERY_MIN_CONFIDENCE", 0.55)))


def structural_min_confidence() -> float:
    """Floor for graph/cross-domain harvest when endpoints already exist."""
    return max(
        0.0,
        min(1.0, env_float("CONNECTION_DISCOVERY_STRUCTURAL_MIN_CONFIDENCE", 0.28)),
    )


def harvest_limit() -> int:
    return max(10, env_int("CONNECTION_DISCOVERY_HARVEST_LIMIT", 200))


def _upsert_finding(
    cur,
    *,
    finding_type: str,
    dedupe_key: str,
    title: str,
    summary: str | None,
    domain_keys: list[str],
    confidence: float | None,
    left_kind: str | None = None,
    left_id: int | None = None,
    right_kind: str | None = None,
    right_id: int | None = None,
    source_table: str | None = None,
    source_id: str | None = None,
    evidence: dict[str, Any] | None = None,
    revive_dismissed: bool = False,
) -> bool:
    revive_decisions = (
        "no_seed_members",
        "graph_no_endpoints",
        "temporal_not_for_research",
        "rejected_by_research",
        "rejected_by_narrative",
        "no_attach",
    )
    cur.execute(
        """
        INSERT INTO intelligence.connection_findings (
            finding_type, status, domain_keys, confidence, title, summary,
            left_kind, left_id, right_kind, right_id,
            source_table, source_id, dedupe_key, evidence, updated_at
        ) VALUES (
            %s, 'open', %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s::jsonb, NOW()
        )
        ON CONFLICT (dedupe_key) DO UPDATE SET
            confidence = GREATEST(
                COALESCE(intelligence.connection_findings.confidence, 0),
                COALESCE(EXCLUDED.confidence, 0)
            ),
            evidence = intelligence.connection_findings.evidence || EXCLUDED.evidence,
            domain_keys = CASE
              WHEN cardinality(EXCLUDED.domain_keys) > 0 THEN EXCLUDED.domain_keys
              ELSE intelligence.connection_findings.domain_keys
            END,
            status = CASE
              WHEN %s
                   AND intelligence.connection_findings.status = 'dismissed'
                   AND COALESCE(intelligence.connection_findings.research_decision, '') = ANY(%s)
              THEN 'open'
              ELSE intelligence.connection_findings.status
            END,
            research_decision = CASE
              WHEN %s
                   AND intelligence.connection_findings.status = 'dismissed'
                   AND COALESCE(intelligence.connection_findings.research_decision, '') = ANY(%s)
              THEN NULL
              ELSE intelligence.connection_findings.research_decision
            END,
            editorial_package_id = CASE
              WHEN %s
                   AND intelligence.connection_findings.status = 'dismissed'
                   AND COALESCE(intelligence.connection_findings.research_decision, '') = ANY(%s)
              THEN NULL
              ELSE intelligence.connection_findings.editorial_package_id
            END,
            updated_at = NOW()
        WHERE intelligence.connection_findings.status IN ('open', 'queued_research')
           OR (
             %s
             AND intelligence.connection_findings.status = 'dismissed'
             AND COALESCE(intelligence.connection_findings.research_decision, '') = ANY(%s)
           )
        RETURNING id
        """,
        (
            finding_type,
            domain_keys,
            confidence,
            title[:500] if title else None,
            (summary or "")[:2000] or None,
            left_kind,
            left_id,
            right_kind,
            right_id,
            source_table,
            source_id,
            dedupe_key,
            json.dumps(evidence or {}),
            bool(revive_dismissed),
            list(revive_decisions),
            bool(revive_dismissed),
            list(revive_decisions),
            bool(revive_dismissed),
            list(revive_decisions),
            bool(revive_dismissed),
            list(revive_decisions),
        ),
    )
    return bool(cur.fetchone())


def _harvest_graph_proposals(cur, *, limit: int, min_conf: float) -> int:
    n = 0
    cur.execute(
        """
        SELECT id, proposal_kind, domain_key, confidence, subject_summary, endpoints, evidence
        FROM intelligence.graph_connection_proposals
        WHERE status = 'pending'
          AND COALESCE(confidence, 0) >= %s
        ORDER BY confidence DESC NULLS LAST, updated_at DESC NULLS LAST
        LIMIT %s
        """,
        (min_conf, limit),
    )
    for pid, kind, dk, conf, subject, endpoints, evidence in cur.fetchall() or []:
        ep = endpoints if isinstance(endpoints, dict) else {}
        if not (ep.get("storyline_ids") or ep.get("entity_profile_ids") or ep.get("canonical_entity_ids")):
            continue
        domains = [str(dk)] if dk else []
        dedupe = f"graph_proposal:{pid}"
        title = (subject or f"{kind} proposal {pid}")[:240]
        if _upsert_finding(
            cur,
            finding_type="graph_proposal",
            dedupe_key=dedupe,
            title=title,
            summary=f"Pending graph {kind} proposal",
            domain_keys=domains,
            confidence=float(conf) if conf is not None else None,
            source_table="graph_connection_proposals",
            source_id=str(pid),
            evidence={"endpoints": ep, "proposal_kind": kind, "raw": evidence},
            revive_dismissed=True,
        ):
            n += 1
    return n


def _harvest_cross_domain(cur, *, limit: int, min_conf: float) -> int:
    n = 0
    since = datetime.now(timezone.utc) - timedelta(days=7)
    cur.execute(
        """
        SELECT correlation_id, domain_1, domain_2, entity_profile_ids, event_ids,
               correlation_strength, correlation_type, metadata
        FROM intelligence.cross_domain_correlations
        WHERE discovered_at >= %s
          AND COALESCE(correlation_strength, 0) >= %s
        ORDER BY discovered_at DESC NULLS LAST
        LIMIT %s
        """,
        (since, min_conf, limit),
    )
    for cid, d1, d2, ent_ids, ev_ids, strength, ctype, meta in cur.fetchall() or []:
        dedupe = f"cross_domain:{cid}"
        title = f"{d1} ↔ {d2} ({ctype or 'correlation'})"
        if _upsert_finding(
            cur,
            finding_type="cross_domain",
            dedupe_key=dedupe,
            title=title,
            summary=f"Shared entities/events across {d1} and {d2}",
            domain_keys=[str(d1), str(d2)],
            confidence=float(strength) if strength is not None else None,
            source_table="cross_domain_correlations",
            source_id=str(cid),
            evidence={
                "entity_profile_ids": list(ent_ids or [])[:20],
                "event_ids": list(ev_ids or [])[:20],
                "correlation_type": ctype,
                "metadata": meta,
            },
            revive_dismissed=True,
        ):
            n += 1
    return n


def _harvest_research_entities(cur, *, limit: int) -> int:
    """Hot knowledge-domain entities → research_entity findings for claimish packages."""
    from services.discovery_finding_quality import RESEARCH_SEED_DOMAINS

    n = 0
    domains = sorted(RESEARCH_SEED_DOMAINS)
    per = max(5, limit // max(1, len(domains)))
    for dk in domains:
        schema = dk.replace("-", "_")
        try:
            cur.execute(
                f"""
                SELECT ep.id, ep.canonical_entity_id, COUNT(ae.id) AS mentions,
                       COALESCE(ec.canonical_name, 'entity ' || ep.canonical_entity_id::text)
                FROM intelligence.entity_profiles ep
                JOIN {schema}.article_entities ae
                  ON ae.canonical_entity_id = ep.canonical_entity_id
                LEFT JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
                WHERE ep.domain_key = %s
                  AND ep.canonical_entity_id IS NOT NULL
                  AND ae.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY ep.id, ep.canonical_entity_id, ec.canonical_name
                HAVING COUNT(ae.id) >= 8
                ORDER BY mentions DESC
                LIMIT %s
                """,
                (dk, per),
            )
        except Exception as exc:
            logger.debug("research_entity harvest %s: %s", dk, exc)
            continue
        for pid, canonical, mentions, name in cur.fetchall() or []:
            name_s = str(name or "").strip()
            if not name_s or "<" in name_s or len(name_s) < 2:
                continue
            dedupe = f"research_entity:{dk}:{canonical}"
            title = f"{name_s} ({dk})"
            conf = min(0.9, 0.45 + (float(mentions) / 200.0))
            if _upsert_finding(
                cur,
                finding_type="research_entity",
                dedupe_key=dedupe,
                title=title[:500],
                summary=f"Hot research entity with {mentions} recent mentions",
                domain_keys=[dk],
                confidence=conf,
                source_table="entity_profiles",
                source_id=str(pid),
                evidence={
                    "entity_profile_ids": [int(pid)],
                    "canonical_entity_ids": [int(canonical)],
                    "mention_count_30d": int(mentions),
                },
                revive_dismissed=True,
            ):
                n += 1
    return n


def _harvest_patterns(cur, *, limit: int, min_conf: float) -> int:
    n = 0
    since = datetime.now(timezone.utc) - timedelta(days=3)
    cur.execute(
        """
        SELECT id, pattern_type, domain_key, context_ids, entity_profile_ids, confidence, data
        FROM intelligence.pattern_discoveries
        WHERE created_at >= %s
          AND COALESCE(confidence, 0) >= %s
        ORDER BY created_at DESC NULLS LAST
        LIMIT %s
        """,
        (since, min_conf, limit),
    )
    for pid, ptype, dk, ctx_ids, ent_ids, conf, data in cur.fetchall() or []:
        candidate = {
            "finding_type": "pattern",
            "domain_keys": [str(dk)] if dk else [],
            "evidence": {
                "pattern_type": ptype,
                "context_ids": list(ctx_ids or [])[:20],
                "entity_profile_ids": list(ent_ids or [])[:20],
                "data": data,
            },
        }
        if not is_bridgeable(candidate):
            continue
        dedupe = f"pattern:{pid}"
        title = f"{ptype} pattern ({dk or 'global'})"
        if _upsert_finding(
            cur,
            finding_type="pattern",
            dedupe_key=dedupe,
            title=title,
            summary=str((data or {}).get("relation") or ptype),
            domain_keys=[str(dk)] if dk else [],
            confidence=float(conf) if conf is not None else None,
            source_table="pattern_discoveries",
            source_id=str(pid),
            evidence={
                "pattern_type": ptype,
                "context_ids": list(ctx_ids or [])[:20],
                "entity_profile_ids": list(ent_ids or [])[:20],
                "data": data,
            },
        ):
            n += 1
    return n


def _harvest_temporal_cooccurrence(cur, *, limit: int) -> int:
    """Same-day CE pairs sharing entity via article_entities (politics+finance)."""
    n = 0
    for dk in get_pipeline_active_domain_keys():
        probe = {
            "finding_type": "temporal",
            "domain_keys": [dk],
            "left_id": 1,
            "right_id": 2,
        }
        if not is_bridgeable(probe):
            continue
        schema = dk.replace("-", "_")
        try:
            cur.execute(
                f"""
                SELECT ce1.id, ce2.id, ce1.title, ce2.title, ce1.actual_event_date
                FROM public.chronological_events ce1
                JOIN public.chronological_events ce2
                  ON ce1.actual_event_date = ce2.actual_event_date
                 AND ce1.id < ce2.id
                JOIN {schema}.articles a1 ON a1.id = ce1.source_article_id
                JOIN {schema}.articles a2 ON a2.id = ce2.source_article_id
                WHERE ce1.actual_event_date >= CURRENT_DATE - INTERVAL '14 days'
                ORDER BY ce1.actual_event_date DESC NULLS LAST, ce1.id DESC
                LIMIT %s
                """,
                (max(10, limit // max(1, len(get_pipeline_active_domain_keys()))),),
            )
        except Exception:
            continue
        for e1, e2, t1, t2, ed in cur.fetchall() or []:
            candidate = {
                "finding_type": "temporal",
                "domain_keys": [dk],
                "left_id": int(e1),
                "right_id": int(e2),
            }
            if not is_bridgeable(candidate):
                continue
            dedupe = f"temporal:{dk}:{e1}:{e2}"
            title = f"Same-day events ({ed}): {(t1 or '')[:60]}"
            if _upsert_finding(
                cur,
                finding_type="temporal",
                dedupe_key=dedupe,
                title=title,
                summary=(t2 or "")[:200],
                domain_keys=[dk],
                confidence=0.65,
                left_kind="chronological_event",
                left_id=int(e1),
                right_kind="chronological_event",
                right_id=int(e2),
                evidence={"event_date": ed.isoformat() if ed else None},
            ):
                n += 1
    return n


def _dismiss_weak_open_findings(cur, *, limit: int = 500) -> int:
    """Clear the open queue of leads we would never bridge."""
    from services.discovery_finding_quality import finding_skip_reason

    cur.execute(
        """
        SELECT id, finding_type, domain_keys, left_id, right_id, evidence
        FROM intelligence.connection_findings
        WHERE status = 'open'
        ORDER BY
          CASE WHEN finding_type = 'graph_proposal' THEN 0 ELSE 1 END,
          created_at ASC
        LIMIT %s
        """,
        (int(limit),),
    )
    n = 0
    for fid, ftype, domains, left_id, right_id, evidence in cur.fetchall() or []:
        finding = {
            "finding_type": ftype,
            "domain_keys": list(domains or []),
            "left_id": left_id,
            "right_id": right_id,
            "evidence": evidence if isinstance(evidence, dict) else {},
        }
        reason = finding_skip_reason(finding)
        if not reason:
            continue
        cur.execute(
            """
            UPDATE intelligence.connection_findings
            SET status = 'dismissed',
                research_decision = %s,
                updated_at = NOW()
            WHERE id = %s AND status = 'open'
            """,
            (reason, int(fid)),
        )
        n += int(cur.rowcount or 0)
    return n


def run_discovery_harvest(*, apply: bool = True) -> dict[str, Any]:
    """Pull from graph proposals, cross_domain, patterns, temporal scan → connection_findings."""
    if not is_enabled():
        return {"enabled": False, "skipped": True}

    lim = harvest_limit()
    min_conf = min_confidence()
    struct_conf = structural_min_confidence()
    stats: dict[str, Any] = {
        "graph_proposals": 0,
        "cross_domain": 0,
        "patterns": 0,
        "temporal": 0,
        "research_entities": 0,
        "pattern_batch_written": 0,
        "cross_domain_synthesis": 0,
    }

    try:
        from services.pattern_recognition_service import run_pattern_discovery_batch

        stats["pattern_batch_written"] = int(run_pattern_discovery_batch() or 0)
    except Exception as exc:
        logger.debug("pattern_discovery_batch: %s", exc)

    try:
        from services.cross_domain_service import run_cross_domain_synthesis

        xdom = run_cross_domain_synthesis(
            domains=None, time_window_days=30, correlation_threshold=min_conf
        )
        stats["cross_domain_synthesis"] = len((xdom or {}).get("correlations") or [])
    except Exception as exc:
        logger.debug("cross_domain_synthesis: %s", exc)

    if not apply:
        return {**stats, "apply": False}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            stats["graph_proposals"] = _harvest_graph_proposals(
                cur, limit=lim, min_conf=struct_conf
            )
            stats["cross_domain"] = _harvest_cross_domain(cur, limit=lim, min_conf=min_conf)
            stats["research_entities"] = _harvest_research_entities(cur, limit=lim)
            stats["patterns"] = _harvest_patterns(cur, limit=lim, min_conf=min_conf)
            stats["temporal"] = _harvest_temporal_cooccurrence(cur, limit=lim)
            stats["weak_open_dismissed"] = _dismiss_weak_open_findings(cur, limit=500)
        conn.commit()

    stats["findings_upserted"] = (
        stats["graph_proposals"]
        + stats["cross_domain"]
        + stats["research_entities"]
        + stats["patterns"]
        + stats["temporal"]
    )
    stats["apply"] = True
    return stats


async def run_connection_discovery_phase(*, apply: bool = True) -> dict[str, Any]:
    """Discovery tick: optional harvest → 72h intake brief (not auto-package publish).

    Bridge to editorial packages is opt-in via DISCOVERY_RESEARCH_BRIDGE_ENABLED
    or POST /api/connections/findings/bridge.
    """
    if not is_enabled():
        return {"enabled": False, "skipped": True}

    harvest = run_discovery_harvest(apply=apply)
    graph_stats: dict[str, Any] = {}
    try:
        from services.graph_connection_processor_service import (
            process_graph_connection_proposals_batch,
        )

        graph_stats = process_graph_connection_proposals_batch(None) or {}
    except Exception as exc:
        logger.debug("connection_discovery graph batch: %s", exc)

    brief: dict[str, Any] = {}
    try:
        from services.discovery_intake_brief_service import build_intake_brief

        brief = build_intake_brief()
    except Exception as exc:
        logger.warning("connection_discovery intake brief: %s", exc)
        brief = {"ok": False, "error": str(exc)[:200]}

    bridge_stats: dict[str, Any] = {"skipped": True, "reason": "bridge_disabled_by_default"}
    if apply:
        try:
            from services.discovery_research_bridge_service import (
                bridge_open_findings_to_research,
                is_enabled as bridge_enabled,
            )

            if bridge_enabled():
                bridge_stats = bridge_open_findings_to_research()
            else:
                bridge_stats = {
                    "skipped": True,
                    "reason": "DISCOVERY_RESEARCH_BRIDGE_ENABLED=false",
                    "hint": "Use POST /api/research/assemble or POST /api/connections/findings/bridge",
                }
        except Exception as exc:
            logger.warning("connection_discovery bridge: %s", exc)
            bridge_stats = {"error": str(exc)[:200]}

    return {
        "harvest": harvest,
        "graph_distillation": graph_stats,
        "intake_brief": {
            "ok": brief.get("ok"),
            "window_hours": brief.get("window_hours"),
            "totals": brief.get("totals"),
            "highlight_count": len(brief.get("highlights") or []),
            "launch": brief.get("launch"),
        },
        "bridge": bridge_stats,
        "findings_open": count_open_findings(),
        "product": "intake_brief",
    }


def count_open_findings() -> int:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM intelligence.connection_findings
                    WHERE status IN ('open', 'queued_research')
                    """
                )
                row = cur.fetchone()
                return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def list_findings(
    *,
    status: str | None = "open",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id, finding_type, status, domain_keys, confidence, title, summary,
                               left_kind, left_id, right_kind, right_id,
                               source_table, source_id, editorial_package_id, evidence, created_at
                        FROM intelligence.connection_findings
                        WHERE status = %s
                        ORDER BY confidence DESC NULLS LAST, created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (status, int(limit), int(offset)),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, finding_type, status, domain_keys, confidence, title, summary,
                               left_kind, left_id, right_kind, right_id,
                               source_table, source_id, editorial_package_id, evidence, created_at
                        FROM intelligence.connection_findings
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (int(limit), int(offset)),
                    )
                rows = cur.fetchall() or []
        items = []
        for r in rows:
            items.append(
                {
                    "id": int(r[0]),
                    "finding_type": r[1],
                    "status": r[2],
                    "domain_keys": list(r[3] or []),
                    "confidence": float(r[4]) if r[4] is not None else None,
                    "title": r[5],
                    "summary": r[6],
                    "left_kind": r[7],
                    "left_id": int(r[8]) if r[8] is not None else None,
                    "right_kind": r[9],
                    "right_id": int(r[10]) if r[10] is not None else None,
                    "source_table": r[11],
                    "source_id": r[12],
                    "editorial_package_id": int(r[13]) if r[13] is not None else None,
                    "evidence": r[14],
                    "created_at": r[15].isoformat() if r[15] else None,
                }
            )
        return {"items": items, "limit": limit, "offset": offset}
    except Exception as exc:
        logger.warning("list_findings: %s", exc)
        return {"items": [], "error": str(exc)[:200]}


def update_finding_status(
    finding_id: int,
    *,
    status: str,
    research_decision: str | None = None,
    editorial_package_id: int | None = None,
) -> bool:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.connection_findings
                SET status = %s,
                    research_decision = COALESCE(%s, research_decision),
                    editorial_package_id = COALESCE(%s, editorial_package_id),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, research_decision, editorial_package_id, int(finding_id)),
            )
            ok = (cur.rowcount or 0) > 0
        conn.commit()
    return ok
