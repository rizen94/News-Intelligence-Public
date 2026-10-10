"""Queue connection_findings into editorial packages for LLM filtering."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from config.runtime import env_bool, env_float, env_int
from services.discovery_finding_quality import (
    bridge_sort_key,
    finding_skip_reason,
)
from shared.database.connection import get_db_connection_context, get_ui_db_connection_context
from shared.post_processing_modals import allowed_domains_for_modal, modals_for_domain

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    # Default off: discovery is an intake brief, not unsupervised package publishing.
    # Operators can still POST /api/connections/findings/bridge deliberately.
    return env_bool("DISCOVERY_RESEARCH_BRIDGE_ENABLED", False)


def bridge_limit() -> int:
    return max(1, env_int("DISCOVERY_RESEARCH_BRIDGE_LIMIT", 5))


def min_confidence() -> float:
    return max(0.0, min(1.0, env_float("DISCOVERY_RESEARCH_BRIDGE_MIN_CONFIDENCE", 0.62)))


def structural_min_confidence() -> float:
    """Floor for graph/cross-domain leads that already carry storyline/entity endpoints."""
    return max(
        0.0,
        min(1.0, env_float("DISCOVERY_RESEARCH_BRIDGE_STRUCTURAL_MIN_CONFIDENCE", 0.28)),
    )


def _finding_min_confidence(finding: dict[str, Any]) -> float:
    ftype = str(finding.get("finding_type") or "")
    if ftype in ("graph_proposal", "cross_domain", "research_entity"):
        return structural_min_confidence()
    return min_confidence()


def _legacy_seed(finding: dict[str, Any]) -> str:
    return f"discovery:{finding.get('finding_type')}:{finding.get('id')}"


def _target_modal_for_domain(domain_key: str) -> str:
    mods = modals_for_domain(domain_key)
    if "research" in mods:
        return "research"
    if "narrative" in mods:
        return "narrative"
    return "narrative"


def _resolve_finding_domain(
    finding: dict[str, Any],
    cur,
) -> tuple[str | None, list[str]]:
    """Dominant domain from finding tags + context_ids.

    Prefer research when the lead is cross-domain / entity-seedable so we land
    claimish packages instead of narrative same-day bags.
    """
    from shared.domain_registry import get_pipeline_active_domain_keys

    counts: Counter[str] = Counter()
    for dk in finding.get("domain_keys") or []:
        d = str(dk).strip()
        if d:
            counts[d] += 2

    evidence = finding.get("evidence") or {}
    ctx_ids = [int(x) for x in (evidence.get("context_ids") or [])[:40]]
    for cid in ctx_ids:
        cur.execute(
            "SELECT domain_key FROM intelligence.contexts WHERE id = %s",
            (cid,),
        )
        row = cur.fetchone()
        if row and row[0]:
            counts[str(row[0]).strip()] += 1

    if not counts:
        for dk in get_pipeline_active_domain_keys():
            if modals_for_domain(dk):
                counts[dk] = 1
                break

    if not counts:
        return None, []

    narrative = [dk for dk in counts if "narrative" in modals_for_domain(dk)]
    research = [dk for dk in counts if "research" in modals_for_domain(dk)]
    ftype = str(finding.get("finding_type") or "")
    prefer_research = ftype in (
        "cross_domain",
        "research_entity",
        "research_event",
        "graph_proposal",
    ) or bool(evidence.get("entity_profile_ids") or evidence.get("canonical_entity_ids"))

    if prefer_research and research:
        primary = max(research, key=lambda d: counts[d])
    elif narrative and not prefer_research:
        primary = max(narrative, key=lambda d: counts[d])
    elif research:
        primary = max(research, key=lambda d: counts[d])
    elif narrative:
        primary = max(narrative, key=lambda d: counts[d])
    else:
        primary = counts.most_common(1)[0][0]

    all_domains = [d for d, _ in counts.most_common(6)]
    return primary, all_domains


def _count_active_members(package_id: int) -> int:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int FROM intelligence.editorial_package_members
                WHERE package_id = %s AND status = 'active'
                """,
                (int(package_id),),
            )
            row = cur.fetchone()
            return int(row[0] or 0) if row else 0


def _canonical_from_entity_profile(profile_id: int) -> tuple[str | None, int | None]:
    try:
        from shared.entity_identity import profile_id_to_canonical_entity_id

        dk, cid = profile_id_to_canonical_entity_id(int(profile_id))
        return (str(dk).strip() or None) if dk else None, cid
    except Exception:
        return None, None


def _resolve_canonical_for_seed(
    *,
    domain_key: str | None,
    profile_ids: list[int] | None = None,
    canonical_ids: list[int] | None = None,
) -> tuple[str | None, int | None]:
    """Map profile/canonical lists to a research-seedable (domain, canonical_id)."""
    from services.discovery_finding_quality import RESEARCH_SEED_DOMAINS

    for pid in profile_ids or []:
        try:
            pdk, cid = _canonical_from_entity_profile(int(pid))
        except (TypeError, ValueError):
            continue
        use_dk = pdk or (str(domain_key or "").strip() or None)
        if cid and use_dk in RESEARCH_SEED_DOMAINS:
            return use_dk, int(cid)
    dk = str(domain_key or "").strip() or None
    if dk in RESEARCH_SEED_DOMAINS and canonical_ids:
        try:
            return dk, int(canonical_ids[0])
        except (TypeError, ValueError):
            pass
    return None, None


def _seed_claimish_members(
    package_id: int,
    *,
    domain_key: str,
    actor: str = "discovery_bridge",
    limit: int = 12,
) -> int:
    """Attach existing claims/facts for package articles so research readiness can pass."""
    from services.editorial_package_service import add_member, get_package

    pkg = get_package(int(package_id), include=True) or {}
    article_ids: list[int] = []
    context_ids: list[int] = []
    for m in pkg.get("members") or []:
        if m.get("status") not in (None, "active"):
            continue
        mt = str(m.get("member_type") or "")
        try:
            mid = int(m["member_id"])
        except (TypeError, ValueError, KeyError):
            continue
        if mt == "article":
            article_ids.append(mid)
        elif mt == "context":
            context_ids.append(mid)

    if not article_ids and not context_ids:
        return 0

    added = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                if article_ids and not context_ids:
                    cur.execute(
                        """
                        SELECT id FROM intelligence.contexts
                        WHERE article_id = ANY(%s)
                        LIMIT 40
                        """,
                        (article_ids,),
                    )
                    context_ids = [int(r[0]) for r in (cur.fetchall() or [])]

                if not context_ids:
                    return 0

                cur.execute(
                    """
                    SELECT id, subject_text, predicate_text, object_text, confidence, context_id
                    FROM intelligence.extracted_claims
                    WHERE context_id = ANY(%s)
                    ORDER BY confidence DESC NULLS LAST, id DESC
                    LIMIT %s
                    """,
                    (context_ids, int(limit)),
                )
                claims = cur.fetchall() or []
                claim_ids = [int(r[0]) for r in claims]

                for r in claims:
                    quote = " ".join(
                        str(x) for x in (r[1], r[2], r[3]) if x
                    ).strip()[:400]
                    try:
                        add_member(
                            int(package_id),
                            member_type="extracted_claim",
                            member_id=int(r[0]),
                            member_family="research",
                            domain_key=domain_key,
                            role="core_claim",
                            added_by_modal="research",
                            added_by=actor,
                            provenance={
                                "quote": quote or None,
                                "context_id": int(r[5]) if r[5] is not None else None,
                                "confidence": r[4],
                                "discovery": True,
                            },
                            actor=actor,
                        )
                        added += 1
                    except Exception as exc:
                        logger.debug("seed claim %s: %s", r[0], exc)

                if claim_ids:
                    cur.execute(
                        """
                        SELECT id, fact_text, source_claim_id, metadata
                        FROM intelligence.versioned_facts
                        WHERE COALESCE(metadata->>'source_claim_id','') = ANY(%s)
                           OR EXISTS (
                             SELECT 1 FROM unnest(%s::text[]) cid
                             WHERE COALESCE(metadata->'source_claim_ids','[]'::jsonb) ? cid
                           )
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (
                            [str(i) for i in claim_ids],
                            [str(i) for i in claim_ids],
                            int(limit),
                        ),
                    )
                    for fr in cur.fetchall() or []:
                        quote = str(fr[1] or "")[:400]
                        try:
                            add_member(
                                int(package_id),
                                member_type="versioned_fact",
                                member_id=int(fr[0]),
                                member_family="research",
                                domain_key=domain_key,
                                role="core_claim",
                                added_by_modal="research",
                                added_by=actor,
                                provenance={
                                    "quote": quote or None,
                                    "source_claim_id": fr[2],
                                    "discovery": True,
                                },
                                actor=actor,
                            )
                            added += 1
                        except Exception as exc:
                            logger.debug("seed fact %s: %s", fr[0], exc)
    except Exception as exc:
        logger.debug("seed_claimish_members: %s", exc)
    return added


def repair_stale_discovery_packages() -> dict[str, Any]:
    """Reset queued findings tied to empty/wrong-modal packages; link if package advanced."""
    repaired = 0
    linked = 0
    requeued = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cf.id, cf.editorial_package_id, cf.status,
                           ep.primary_modal, ep.domain_keys, ep.status
                    FROM intelligence.connection_findings cf
                    JOIN intelligence.editorial_packages ep ON ep.id = cf.editorial_package_id
                    WHERE cf.status IN ('queued_research', 'researching')
                    """
                )
                rows = cur.fetchall() or []
                for fid, pkg_id, fstatus, modal, domains, pkg_status in rows:
                    member_n = _count_active_members(int(pkg_id))
                    dk = (domains or [None])[0]
                    expected = _target_modal_for_domain(str(dk or "")) if dk else None
                    bad_modal = expected and str(modal or "") != expected
                    pkg_st = str(pkg_status or "")
                    advanced = pkg_st in (
                        "in_reduction",
                        "in_editor",
                        "published",
                        "closed_thin",
                        "ready",
                    )
                    if advanced and member_n > 0:
                        cur.execute(
                            """
                            UPDATE intelligence.connection_findings
                            SET status = 'linked',
                                research_decision = 'package_advanced',
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (int(fid),),
                        )
                        linked += 1
                        continue
                    if member_n > 0 and not bad_modal and not advanced:
                        if fstatus == "researching" and pkg_st not in (
                            "in_research",
                            "in_narrative",
                        ):
                            cur.execute(
                                """
                                UPDATE intelligence.connection_findings
                                SET status = 'queued_research',
                                    research_decision = 'requeued_after_crash',
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                (int(fid),),
                            )
                            requeued += 1
                        continue
                    cur.execute(
                        """
                        UPDATE intelligence.connection_findings
                        SET status = 'open',
                            editorial_package_id = NULL,
                            research_decision = 'repaired_stale_package',
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (int(fid),),
                    )
                    repaired += 1
            conn.commit()
    except Exception as exc:
        logger.warning("repair_stale_discovery_packages: %s", exc)
    return {"repaired": repaired, "linked": linked, "requeued": requeued}


def _fetch_ce_row(cur, event_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id, title, source_text, source_article_id, actual_event_date
        FROM public.chronological_events WHERE id = %s
        """,
        (int(event_id),),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "title": row[1],
        "source_text": row[2],
        "source_article_id": row[3],
        "actual_event_date": row[4],
    }


def _article_url(cur, domain_key: str, article_id: int | None) -> str:
    if not article_id or not domain_key:
        return ""
    schema = domain_key.replace("-", "_")
    try:
        cur.execute(
            f"SELECT url FROM {schema}.articles WHERE id = %s",
            (int(article_id),),
        )
        row = cur.fetchone()
        return str(row[0] or "").strip() if row else ""
    except Exception:
        return ""


def _storyline_for_ce(cur, domain_key: str, event_id: int) -> int | None:
    try:
        cur.execute(
            """
            SELECT storyline_id FROM intelligence.event_episode_links
            WHERE event_id = %s AND domain_key = %s
            ORDER BY confidence DESC NULLS LAST
            LIMIT 1
            """,
            (int(event_id), domain_key),
        )
        row = cur.fetchone()
        if row and row[0]:
            return int(row[0])
    except Exception:
        pass
    return None


def _seed_context_members(
    package_id: int,
    *,
    ctx_ids: list[int],
    domain_key: str,
    target_modal: str,
    actor: str,
) -> int:
    from services.editorial_package_service import add_member

    fam = "narrative" if target_modal == "narrative" else "research"
    added = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for cid in ctx_ids[:12]:
                cur.execute(
                    "SELECT id, domain_key, content FROM intelligence.contexts WHERE id = %s",
                    (cid,),
                )
                row = cur.fetchone()
                if not row:
                    continue
                ctx_dk = str(row[1] or domain_key).strip() or domain_key
                allow = set(allowed_domains_for_modal(target_modal) or [])
                if allow and ctx_dk not in allow:
                    ctx_dk = domain_key
                quote = str(row[2] or "")[:500] or None
                try:
                    add_member(
                        package_id,
                        member_type="context",
                        member_id=int(row[0]),
                        member_family=fam,
                        domain_key=ctx_dk,
                        role="supporting",
                        added_by_modal=target_modal,
                        added_by=actor,
                        provenance={
                            "quote": quote,
                            "context_id": int(row[0]),
                            "discovery": True,
                        },
                        actor=actor,
                    )
                    added += 1
                except Exception as exc:
                    logger.debug("seed context %s: %s", cid, exc)
    return added


def _attach_ce_members(
    package_id: int,
    *,
    domain_key: str,
    event_ids: list[int],
    actor: str,
    cur,
    target_modal: str,
) -> int:
    from services.editorial_package_service import add_member

    article_fam = "narrative" if target_modal == "narrative" else "research"
    added = 0
    for eid in event_ids[:6]:
        ev = _fetch_ce_row(cur, eid)
        if not ev:
            continue
        url = _article_url(cur, domain_key, ev.get("source_article_id"))
        quote = (ev.get("source_text") or ev.get("title") or "").strip()[:500] or None
        try:
            add_member(
                package_id,
                member_type="chronological_event",
                member_id=int(ev["id"]),
                member_family="narrative",
                domain_key=domain_key,
                role="anchor_event",
                added_by_modal=target_modal,
                added_by=actor,
                provenance={
                    "label": (ev.get("title") or "")[:240],
                    "quote": quote,
                    "article_id": ev.get("source_article_id"),
                    "source_url": url or None,
                    "discovery": True,
                },
                actor=actor,
            )
            added += 1
        except Exception as exc:
            logger.debug("seed ce %s: %s", eid, exc)
        aid = ev.get("source_article_id")
        if aid:
            try:
                add_member(
                    package_id,
                    member_type="article",
                    member_id=int(aid),
                    member_family=article_fam,
                    domain_key=domain_key,
                    role="supporting",
                    added_by_modal=target_modal,
                    added_by=actor,
                    provenance={
                        "label": (ev.get("title") or "")[:240],
                        "quote": quote,
                        "source_url": url or None,
                        "discovery": True,
                    },
                    actor=actor,
                )
                added += 1
            except Exception as exc:
                logger.debug("seed article %s: %s", aid, exc)
    return added


def _ensure_discovery_package(
    finding: dict[str, Any],
    *,
    actor: str = "discovery_bridge",
) -> dict[str, Any] | None:
    from services.editorial_package_service import (
        create_package,
        ensure_package_from_entity,
        ensure_package_from_storyline,
        find_package_by_legacy_seed,
        update_package,
    )
    from services.connection_discovery_service import update_finding_status

    fid = int(finding["id"])
    ftype = str(finding.get("finding_type") or "")
    evidence = finding.get("evidence") or {}
    seed = _legacy_seed(finding)

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            dk, domains = _resolve_finding_domain(finding, cur)

    if not dk:
        update_finding_status(fid, status="dismissed", research_decision="no_domain")
        return None

    target_modal = _target_modal_for_domain(dk)
    create_status = "in_research" if target_modal == "research" else "in_narrative"
    package_domains = [d for d in domains if d in modals_for_domain(target_modal)] or [dk]

    existing = find_package_by_legacy_seed(seed)
    if existing:
        pkg_id = int(existing["id"])
        pkg_st = str(existing.get("status") or "")
        members = _count_active_members(pkg_id)
        terminal = pkg_st in ("closed_thin", "published", "archived")
        if members <= 0 and not terminal:
            ctx_ids = [int(x) for x in (evidence.get("context_ids") or [])[:12]]
            if ctx_ids:
                members += _seed_context_members(
                    pkg_id,
                    ctx_ids=ctx_ids,
                    domain_key=dk,
                    target_modal=target_modal,
                    actor=actor,
                )
        if terminal or members <= 0:
            # Free the seed so we can re-bridge into a fresh package.
            try:
                from services.editorial_package_research_service import _merge_package_metadata

                _merge_package_metadata(
                    pkg_id,
                    {"legacy_seed": f"{seed}:superseded:{pkg_id}"},
                )
            except Exception as exc:
                logger.debug("supersede legacy seed %s: %s", seed, exc)
            existing = None
        else:
            claimish = 0
            if target_modal == "research":
                claimish = _seed_claimish_members(pkg_id, domain_key=dk, actor=actor)
                if claimish <= 0:
                    try:
                        with get_ui_db_connection_context() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    """
                                    SELECT COUNT(*)::int
                                    FROM intelligence.editorial_package_members
                                    WHERE package_id = %s AND status = 'active'
                                      AND member_type IN (
                                        'extracted_claim', 'versioned_fact',
                                        'claim_evidence_appraisal', 'hypothesis'
                                      )
                                    """,
                                    (int(pkg_id),),
                                )
                                row = cur.fetchone()
                                claimish = int(row[0] or 0) if row else 0
                    except Exception:
                        pass
                if claimish:
                    members = _count_active_members(pkg_id)
            try:
                update_package(
                    pkg_id,
                    status=create_status,
                    primary_modal=target_modal,
                    actor=actor,
                    modal=target_modal,
                    rationale="discovery bridge refresh",
                )
            except Exception:
                pass
            try:
                from services.editorial_package_research_service import _merge_package_metadata

                _merge_package_metadata(
                    pkg_id,
                    {
                        "legacy_seed": seed,
                        "discovery_finding_ids": [fid],
                        "discovery_source": ftype,
                        "discovery_confidence": finding.get("confidence"),
                        "discovery_target_modal": target_modal,
                        "discovery_claimish_seeded": claimish,
                    },
                )
            except Exception:
                pass
            update_finding_status(fid, status="queued_research", editorial_package_id=pkg_id)
            return {
                "package_id": pkg_id,
                "created": False,
                "finding_id": fid,
                "target_modal": target_modal,
                "members": members,
                "claimish": claimish,
            }

    pkg_id: int | None = None
    created = False
    members_added = 0

    try:
        if ftype == "graph_proposal":
            ep = evidence.get("endpoints") or {}
            sids = ep.get("storyline_ids") or []
            profile_ids = [int(x) for x in (ep.get("entity_profile_ids") or [])[:8]]
            canonical_ids = [int(x) for x in (ep.get("canonical_entity_ids") or [])[:8]]
            if isinstance(sids, list) and sids:
                pkg = ensure_package_from_storyline(
                    domain_key=dk,
                    storyline_id=int(sids[0]),
                    target_modal=target_modal,
                    actor=actor,
                    refresh_members=True,
                )
                pkg_id = int(pkg["id"])
                members_added = _count_active_members(pkg_id)
            else:
                use_dk, canonical = _resolve_canonical_for_seed(
                    domain_key=dk,
                    profile_ids=profile_ids,
                    canonical_ids=canonical_ids,
                )
                if canonical and use_dk:
                    try:
                        pkg = ensure_package_from_entity(
                            domain_key=use_dk,
                            canonical_entity_id=int(canonical),
                            actor=actor,
                            refresh_members=True,
                        )
                        pkg_id = int(pkg["id"])
                        members_added = _count_active_members(pkg_id)
                        dk = use_dk
                    except Exception as exc:
                        logger.debug("graph_proposal entity: %s", exc)
        elif ftype == "cross_domain":
            ent_ids = [int(x) for x in (evidence.get("entity_profile_ids") or [])[:12]]
            ev_ids = [int(x) for x in (evidence.get("event_ids") or [])[:6]]
            if ent_ids and target_modal == "research":
                use_dk, canonical = _resolve_canonical_for_seed(
                    domain_key=dk,
                    profile_ids=ent_ids,
                )
                if canonical and use_dk:
                    try:
                        pkg = ensure_package_from_entity(
                            domain_key=use_dk,
                            canonical_entity_id=int(canonical),
                            actor=actor,
                            refresh_members=True,
                        )
                        pkg_id = int(pkg["id"])
                        members_added = _count_active_members(pkg_id)
                        dk = use_dk
                    except Exception as exc:
                        logger.debug("cross_domain entity: %s", exc)
            if not pkg_id and ev_ids:
                with get_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        sid = _storyline_for_ce(cur, dk, ev_ids[0])
                if sid:
                    pkg = ensure_package_from_storyline(
                        domain_key=dk,
                        storyline_id=sid,
                        target_modal=target_modal,
                        actor=actor,
                        refresh_members=True,
                    )
                    pkg_id = int(pkg["id"])
                    members_added = _count_active_members(pkg_id)
                else:
                    pkg = create_package(
                        working_title=str(finding.get("title") or "Cross-domain lead"),
                        summary_stub=str(finding.get("summary") or "")[:500] or None,
                        primary_modal=target_modal,
                        domain_keys=package_domains,
                        status=create_status,
                        actor=actor,
                        metadata={
                            "legacy_seed": seed,
                            "discovery_finding_ids": [fid],
                            "discovery_source": ftype,
                            "discovery_target_modal": target_modal,
                        },
                    )
                    pkg_id = int(pkg["id"])
                    created = True
                    with get_db_connection_context() as conn:
                        with conn.cursor() as cur:
                            members_added = _attach_ce_members(
                                pkg_id,
                                domain_key=dk,
                                event_ids=ev_ids,
                                actor=actor,
                                cur=cur,
                                target_modal=target_modal,
                            )
        elif ftype == "pattern":
            ctx_ids = [int(x) for x in (evidence.get("context_ids") or [])[:12]]
            ent_profiles = [int(x) for x in (evidence.get("entity_profile_ids") or [])[:8]]
            # Prefer entity research packages when profiles map to knowledge domains.
            if ent_profiles and target_modal == "research":
                use_dk, canonical = _resolve_canonical_for_seed(
                    domain_key=dk,
                    profile_ids=ent_profiles,
                )
                if canonical and use_dk:
                    try:
                        pkg = ensure_package_from_entity(
                            domain_key=use_dk,
                            canonical_entity_id=int(canonical),
                            actor=actor,
                            refresh_members=True,
                        )
                        pkg_id = int(pkg["id"])
                        members_added = _count_active_members(pkg_id)
                        dk = use_dk
                    except Exception as exc:
                        logger.debug("pattern entity seed: %s", exc)
            if not pkg_id:
                pkg = create_package(
                    working_title=str(finding.get("title") or "Pattern lead"),
                    summary_stub=str(finding.get("summary") or "")[:500] or None,
                    primary_modal=target_modal,
                    domain_keys=package_domains,
                    status=create_status,
                    actor=actor,
                    metadata={
                        "legacy_seed": seed,
                        "discovery_finding_ids": [fid],
                        "discovery_source": ftype,
                        "discovery_target_modal": target_modal,
                    },
                )
                pkg_id = int(pkg["id"])
                created = True
                members_added = _seed_context_members(
                    pkg_id,
                    ctx_ids=ctx_ids,
                    domain_key=dk,
                    target_modal=target_modal,
                    actor=actor,
                )
        elif ftype in ("research_entity", "research_event"):
            ent_profiles = [int(x) for x in (evidence.get("entity_profile_ids") or [])[:4]]
            canonicals = [int(x) for x in (evidence.get("canonical_entity_ids") or [])[:4]]
            ev_ids = []
            if finding.get("left_id"):
                ev_ids.append(int(finding["left_id"]))
            ev_ids.extend(int(x) for x in (evidence.get("event_ids") or [])[:4])
            use_dk, canonical = _resolve_canonical_for_seed(
                domain_key=dk,
                profile_ids=ent_profiles,
                canonical_ids=canonicals,
            )
            if canonical and use_dk and target_modal == "research":
                try:
                    pkg = ensure_package_from_entity(
                        domain_key=use_dk,
                        canonical_entity_id=int(canonical),
                        actor=actor,
                        refresh_members=True,
                    )
                    pkg_id = int(pkg["id"])
                    members_added = _count_active_members(pkg_id)
                    dk = use_dk
                except Exception as exc:
                    logger.debug("research_entity seed: %s", exc)
            if not pkg_id and ev_ids:
                pkg = create_package(
                    working_title=str(finding.get("title") or "Research event"),
                    summary_stub=str(finding.get("summary") or "")[:500] or None,
                    primary_modal=target_modal,
                    domain_keys=package_domains,
                    status=create_status,
                    actor=actor,
                    metadata={
                        "legacy_seed": seed,
                        "discovery_finding_ids": [fid],
                        "discovery_source": ftype,
                        "discovery_target_modal": target_modal,
                    },
                )
                pkg_id = int(pkg["id"])
                created = True
                with get_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        members_added = _attach_ce_members(
                            pkg_id,
                            domain_key=dk,
                            event_ids=ev_ids[:1],
                            actor=actor,
                            cur=cur,
                            target_modal=target_modal,
                        )
        elif ftype == "temporal":
            ev_ids = []
            if finding.get("left_id"):
                ev_ids.append(int(finding["left_id"]))
            if finding.get("right_id"):
                ev_ids.append(int(finding["right_id"]))
            # Research modal: single event only (pair bags never publish).
            if target_modal == "research" and ev_ids:
                ev_ids = ev_ids[:1]
            pkg = create_package(
                working_title=str(finding.get("title") or "Same-day events"),
                summary_stub=str(finding.get("summary") or "")[:500] or None,
                primary_modal=target_modal,
                domain_keys=package_domains,
                status=create_status,
                actor=actor,
                metadata={
                    "legacy_seed": seed,
                    "discovery_finding_ids": [fid],
                    "discovery_source": ftype,
                    "discovery_target_modal": target_modal,
                },
            )
            pkg_id = int(pkg["id"])
            created = True
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    members_added = _attach_ce_members(
                        pkg_id,
                        domain_key=dk,
                        event_ids=ev_ids,
                        actor=actor,
                        cur=cur,
                        target_modal=target_modal,
                    )
        else:
            pkg = create_package(
                working_title=str(finding.get("title") or "Discovery lead"),
                summary_stub=str(finding.get("summary") or "")[:500] or None,
                primary_modal=target_modal,
                domain_keys=package_domains,
                status=create_status,
                actor=actor,
                metadata={
                    "legacy_seed": seed,
                    "discovery_finding_ids": [fid],
                    "discovery_source": ftype,
                    "discovery_target_modal": target_modal,
                },
            )
            pkg_id = int(pkg["id"])
            created = True
    except Exception as exc:
        logger.warning("discovery bridge finding %s failed: %s", fid, exc)
        return None

    if not pkg_id:
        update_finding_status(fid, status="dismissed", research_decision="no_seed_members")
        return None

    if members_added <= 0:
        members_added = _count_active_members(pkg_id)
    if members_added <= 0:
        logger.info("discovery bridge skip finding %s: zero members seeded", fid)
        update_finding_status(fid, status="dismissed", research_decision="no_seed_members")
        return None

    claimish = 0
    if target_modal == "research":
        claimish = _seed_claimish_members(pkg_id, domain_key=dk, actor=actor)
        if claimish <= 0:
            # Entity seed paths often already attach claims/facts.
            try:
                with get_ui_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT COUNT(*)::int
                            FROM intelligence.editorial_package_members
                            WHERE package_id = %s AND status = 'active'
                              AND member_type IN (
                                'extracted_claim', 'versioned_fact',
                                'claim_evidence_appraisal', 'hypothesis'
                              )
                            """,
                            (int(pkg_id),),
                        )
                        row = cur.fetchone()
                        claimish = int(row[0] or 0) if row else 0
            except Exception:
                pass
        if claimish:
            members_added = _count_active_members(pkg_id)

    from services.editorial_package_research_service import _merge_package_metadata

    try:
        _merge_package_metadata(
            pkg_id,
            {
                "legacy_seed": seed,
                "discovery_finding_ids": [fid],
                "discovery_source": ftype,
                "discovery_confidence": finding.get("confidence"),
                "discovery_target_modal": target_modal,
                "discovery_claimish_seeded": claimish,
            },
        )
    except Exception:
        pass

    if created:
        try:
            update_package(
                pkg_id,
                status=create_status,
                primary_modal=target_modal,
                actor=actor,
                modal=target_modal,
                rationale=f"discovery bridge → {target_modal}",
            )
        except Exception:
            pass

    update_finding_status(fid, status="queued_research", editorial_package_id=pkg_id)
    return {
        "package_id": pkg_id,
        "created": created,
        "finding_id": fid,
        "target_modal": target_modal,
        "members": members_added,
        "claimish": claimish,
    }


def bridge_open_findings_to_research(*, limit: int | None = None) -> dict[str, Any]:
    if not is_enabled():
        return {"enabled": False, "skipped": True}

    repair = repair_stale_discovery_packages()
    lim = int(limit or bridge_limit())
    min_conf = min_confidence()
    struct_conf = structural_min_confidence()
    bridged: list[dict[str, Any]] = []
    research_n = 0
    narrative_n = 0
    skipped = 0

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, finding_type, domain_keys, confidence, title, summary,
                           left_kind, left_id, right_kind, right_id, evidence
                    FROM intelligence.connection_findings
                    WHERE status = 'open'
                      AND (
                        (
                          finding_type IN ('graph_proposal', 'cross_domain', 'research_entity')
                          AND COALESCE(confidence, 0) >= %s
                        )
                        OR (
                          finding_type NOT IN ('graph_proposal', 'cross_domain', 'research_entity')
                          AND COALESCE(confidence, 0) >= %s
                        )
                      )
                      AND NOT (
                        finding_type = 'graph_proposal'
                        AND COALESCE(jsonb_array_length(evidence->'endpoints'->'storyline_ids'), 0) = 0
                        AND COALESCE(jsonb_array_length(evidence->'endpoints'->'entity_profile_ids'), 0) = 0
                        AND COALESCE(jsonb_array_length(evidence->'endpoints'->'canonical_entity_ids'), 0) = 0
                      )
                      AND NOT (
                        finding_type = 'pattern'
                        AND COALESCE(evidence->>'pattern_type', '') = 'temporal'
                        AND (
                          domain_keys IS NULL
                          OR cardinality(domain_keys) = 0
                        )
                      )
                    ORDER BY
                      CASE finding_type
                        WHEN 'research_entity' THEN 0
                        WHEN 'cross_domain' THEN 1
                        WHEN 'graph_proposal' THEN 2
                        WHEN 'research_event' THEN 3
                        WHEN 'pattern' THEN 4
                        WHEN 'temporal' THEN 5
                        ELSE 9
                      END,
                      CASE
                        WHEN domain_keys && ARRAY[
                          'artificial-intelligence','medicine','neurodiversity'
                        ]::text[] THEN 0
                        ELSE 1
                      END,
                      confidence DESC NULLS LAST,
                      created_at ASC
                    LIMIT %s
                    """,
                    (struct_conf, min_conf, max(lim * 20, 80)),
                )
                rows = cur.fetchall() or []
        findings: list[dict[str, Any]] = []
        for r in rows:
            finding = {
                "id": int(r[0]),
                "finding_type": r[1],
                "domain_keys": list(r[2] or []),
                "confidence": float(r[3]) if r[3] is not None else None,
                "title": r[4],
                "summary": r[5],
                "left_kind": r[6],
                "left_id": int(r[7]) if r[7] is not None else None,
                "right_kind": r[8],
                "right_id": int(r[9]) if r[9] is not None else None,
                "evidence": r[10] if isinstance(r[10], dict) else {},
            }
            if float(finding.get("confidence") or 0) < _finding_min_confidence(finding):
                continue
            reason = finding_skip_reason(finding)
            if reason:
                from services.connection_discovery_service import update_finding_status

                update_finding_status(
                    int(finding["id"]),
                    status="dismissed",
                    research_decision=reason,
                )
                skipped += 1
                continue
            findings.append(finding)
        findings.sort(key=bridge_sort_key)
        for finding in findings:
            if len(bridged) >= lim:
                break
            out = _ensure_discovery_package(finding)
            if not out:
                continue
            bridged.append(out)
            if out.get("target_modal") == "research":
                research_n += 1
            else:
                narrative_n += 1
    except Exception as exc:
        logger.warning("bridge_open_findings: %s", exc)
        return {
            "error": str(exc)[:200],
            "bridged": bridged,
            "repair": repair,
            "skipped_weak": skipped,
        }

    return {
        "bridged_count": len(bridged),
        "research_queued": research_n,
        "narrative_queued": narrative_n,
        "packages": bridged,
        "repair": repair,
        "skipped_weak": skipped,
    }


def _article_id_for_event(event_id: int) -> int | None:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                ev = _fetch_ce_row(cur, event_id)
                aid = (ev or {}).get("source_article_id")
                return int(aid) if aid is not None else None
    except Exception:
        return None


def _event_title(event_id: int) -> str:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                ev = _fetch_ce_row(cur, event_id)
                return str((ev or {}).get("title") or f"event {event_id}")[:240]
    except Exception:
        return f"event {event_id}"


def split_incoherent_discovery_package(package_id: int) -> dict[str, Any]:
    """Keep the first chronological event; spawn sibling packages for the rest."""
    from services.discovery_finding_quality import active_chronological_event_ids
    from services.editorial_package_research_service import _merge_package_metadata
    from services.editorial_package_service import (
        add_member,
        create_package,
        get_package,
        set_member_status,
        update_package,
    )

    pkg = get_package(int(package_id), include=True)
    if not pkg:
        return {"ok": False, "reason": "not_found", "package_id": package_id}

    events = active_chronological_event_ids(pkg)
    if len(events) < 2:
        return {"ok": False, "reason": "need_two_events", "package_id": package_id}

    keep_eid = events[0]
    spawn_eids = events[1:]
    members = list(pkg.get("members") or [])
    event_articles = {eid: _article_id_for_event(eid) for eid in events}

    def _belongs_to(member: dict[str, Any], eid: int) -> bool:
        mt = str(member.get("member_type") or "")
        try:
            mid = int(member["member_id"])
        except (TypeError, ValueError, KeyError):
            return False
        if mt == "chronological_event":
            return mid == eid
        if mt == "article":
            if event_articles.get(eid) == mid:
                return True
            prov = member.get("provenance") if isinstance(member.get("provenance"), dict) else {}
            try:
                return int(prov.get("chronological_event_id") or 0) == eid
            except (TypeError, ValueError):
                return False
        return False

    dk = (list(pkg.get("domain_keys") or []) or ["artificial-intelligence"])[0]
    modal = str(pkg.get("primary_modal") or "research")
    status = "in_research" if modal == "research" else "in_narrative"
    meta = pkg.get("metadata") or {}
    if isinstance(meta, str):
        import json as _json

        try:
            meta = _json.loads(meta)
        except Exception:
            meta = {}

    sibling_ids: list[int] = []
    for eid in spawn_eids:
        title = _event_title(eid)
        child = create_package(
            working_title=title[:200] or f"Event {eid}",
            summary_stub=title[:500] or None,
            primary_modal=modal,
            domain_keys=list(pkg.get("domain_keys") or [dk]),
            status=status,
            actor="discovery_split",
            metadata={
                "split_from_package_id": int(package_id),
                "discovery_source": "split",
                "discovery_parent_source": meta.get("discovery_source"),
                "discovery_finding_ids": list(meta.get("discovery_finding_ids") or []),
                "discovery_target_modal": modal,
            },
        )
        child_id = int(child["id"])
        sibling_ids.append(child_id)
        for m in members:
            if m.get("status") not in (None, "active"):
                continue
            if not _belongs_to(m, eid):
                continue
            try:
                add_member(
                    child_id,
                    member_type=str(m["member_type"]),
                    member_id=int(m["member_id"]),
                    member_family=str(m.get("member_family") or "research"),
                    domain_key=m.get("domain_key") or dk,
                    role=str(m.get("role") or "supporting"),
                    added_by_modal=modal,
                    added_by="discovery_split",
                    provenance=m.get("provenance") if isinstance(m.get("provenance"), dict) else {},
                    actor="discovery_split",
                )
            except Exception as exc:
                logger.debug("split copy member %s: %s", m.get("id"), exc)
        for m in members:
            if m.get("status") not in (None, "active"):
                continue
            if not _belongs_to(m, eid):
                continue
            try:
                set_member_status(
                    int(package_id),
                    int(m["id"]),
                    status="removed",
                    actor="discovery_split",
                    modal=modal,
                    rationale=f"split incoherent pair → package {child_id}",
                )
            except Exception as exc:
                logger.debug("split remove member %s: %s", m.get("id"), exc)

    keep_title = _event_title(keep_eid)
    try:
        update_package(
            int(package_id),
            working_title=keep_title[:200],
            summary_stub=keep_title[:500],
            status=status,
            primary_modal=modal,
            actor="discovery_split",
            modal=modal,
            rationale="split incoherent discovery package; kept first event",
        )
    except Exception:
        pass
    _merge_package_metadata(
        int(package_id),
        {
            "split_into_package_ids": sibling_ids,
            "split_kept_event_id": keep_eid,
            "last_research_insufficient": False,
        },
    )

    from services.connection_discovery_service import update_finding_status

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM intelligence.connection_findings
                    WHERE editorial_package_id = %s
                      AND status IN ('queued_research', 'researching')
                    """,
                    (int(package_id),),
                )
                fids = [int(r[0]) for r in (cur.fetchall() or [])]
        for fid in fids:
            update_finding_status(
                fid,
                status="linked",
                research_decision="split_incoherent",
            )
    except Exception as exc:
        logger.debug("split finalize finding: %s", exc)

    logger.info(
        "split incoherent package %s keep_event=%s siblings=%s",
        package_id,
        keep_eid,
        sibling_ids,
    )
    return {
        "ok": True,
        "package_id": int(package_id),
        "kept_event_id": keep_eid,
        "sibling_package_ids": sibling_ids,
        "route_target": status,
    }


def finalize_discovery_after_editorial_pass(
    package_id: int,
    *,
    validated: dict[str, Any] | None,
    changed: int = 0,
    insufficient: bool = False,
    pass_name: str = "research",
) -> int:
    """Mark linked/dismissed on findings tied to an editorial package.

    Do not dismiss when the pass never got a real LLM decision (503 / preempt).
    """
    del insufficient  # kept for call-site compatibility
    from services.connection_discovery_service import update_finding_status
    from services.discovery_finding_quality import discovery_finalize_action

    updated = 0
    status, decision = discovery_finalize_action(
        validated, changed=changed, pass_name=pass_name
    )

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM intelligence.connection_findings
                    WHERE editorial_package_id = %s
                      AND status IN ('queued_research', 'researching')
                    """,
                    (int(package_id),),
                )
                ids = [int(r[0]) for r in (cur.fetchall() or [])]
    except Exception:
        ids = []

    for fid in ids:
        if update_finding_status(fid, status=status, research_decision=decision):
            updated += 1
    return updated


def finalize_discovery_after_research(
    package_id: int,
    *,
    validated: dict[str, Any] | None,
    changed: int = 0,
    insufficient: bool = False,
) -> int:
    return finalize_discovery_after_editorial_pass(
        package_id,
        validated=validated,
        changed=changed,
        insufficient=insufficient,
        pass_name="research",
    )
