"""
Per-domain storyline assembly — tie proactive detection, AI discovery, and automation together.

Runs when new articles arrive (post-enrichment hook) or when operators/API request assembly
so each domain keeps storylines current as RSS and detection add material.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from api.shared.database import get_db_connection_context
from api.shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)

_VALID_MODES = frozenset({"auto_approve", "suggest_only", "manual"})

_DEFAULT_LINKAGE_PRIORITY = ("politics", "finance")


def linkage_priority_domains() -> tuple[str, ...]:
    """Reader/product domains processed before high-volume research silos."""
    raw = (os.environ.get("STORYLINE_LINKAGE_PRIORITY_DOMAINS") or "").strip()
    if not raw:
        return _DEFAULT_LINKAGE_PRIORITY
    out = tuple(x.strip() for x in raw.split(",") if x.strip())
    return out or _DEFAULT_LINKAGE_PRIORITY


def sort_domains_for_linkage_work(domain_keys: list[str]) -> list[str]:
    """Priority domains first, then remaining pipeline domains in stable order."""
    prio = {d: i for i, d in enumerate(linkage_priority_domains())}
    active = list(domain_keys)

    def _key(dk: str) -> tuple[int, int, str]:
        if dk in prio:
            return (0, prio[dk], dk)
        try:
            idx = active.index(dk)
        except ValueError:
            idx = 999
        return (1, idx, dk)

    return sorted(active, key=_key)


def domain_linkage_stats(domain_key: str, *, lookback_hours: int | None = None) -> dict[str, Any]:
    """Articles vs storyline_articles membership (product KPI numerator/denominator)."""
    schema = resolve_domain_schema(domain_key)
    unlinked = count_unlinked_articles(domain_key, lookback_hours=lookback_hours)
    try:
        from api.shared.article_signal_gate import sql_article_signal_full_lane_and

        sig = sql_article_signal_full_lane_and("a", schema)
        window = ""
        params: list[Any] = []
        if lookback_hours is not None:
            window = " AND a.created_at >= NOW() - (%s || ' hours')::interval "
            params.append(str(int(lookback_hours)))
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::bigint
                    FROM {schema}.articles a
                    WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                      {window}
                      {sig}
                    """,
                    tuple(params),
                )
                articles = int(cur.fetchone()[0] or 0)
                cur.execute(
                    f"""
                    SELECT COUNT(DISTINCT sa.article_id)::bigint
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                      {window}
                      {sig}
                    """,
                    tuple(params),
                )
                linked = int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("domain_linkage_stats %s: %s", domain_key, e)
        articles = 0
        linked = 0
    rate = (float(linked) / float(articles)) if articles > 0 else 0.0
    return {
        "domain_key": domain_key,
        "articles": articles,
        "linked_articles": linked,
        "unlinked_articles": unlinked,
        "linkage_rate": round(rate, 6),
    }


def all_domain_linkage_stats() -> list[dict[str, Any]]:
    return [domain_linkage_stats(dk) for dk in get_pipeline_active_domain_keys()]


def _storyline_count(domain_key: str) -> int:
    schema = resolve_domain_schema(domain_key)
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*)::bigint FROM {schema}.storylines")
                return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("_storyline_count %s: %s", domain_key, e)
        return 0


def domain_storyline_sprawl_active(domain_key: str) -> bool:
    """
    True when the domain has many storylines but very low article linkage — discovery
    should defer until consolidation / assembly catch up.
    """
    try:
        min_storylines = max(
            50, int(os.environ.get("STORYLINE_SPRAWL_MIN_STORYLINES", "150"))
        )
        max_rate = float(os.environ.get("STORYLINE_SPRAWL_MAX_LINKAGE_RATE", "0.12"))
    except ValueError:
        min_storylines, max_rate = 150, 0.12
    if domain_key in linkage_priority_domains():
        return False
    n_sl = _storyline_count(domain_key)
    if n_sl < min_storylines:
        return False
    stats = domain_linkage_stats(domain_key)
    return float(stats.get("linkage_rate") or 0) < max_rate


def run_consolidation_for_domain(domain_key: str) -> dict[str, Any]:
    """Sync consolidation pass (merge/mega) before new discovery on sprawl domains."""
    try:
        from services.storyline_consolidation_service import StorylineConsolidationService

        svc = StorylineConsolidationService(db_config={})
        return svc.run_consolidation(domain_key) or {}
    except Exception as e:
        logger.warning("run_consolidation_for_domain %s: %s", domain_key, e)
        return {"error": str(e)}


def get_storyline_automation_mode(domain_key: str) -> str:
    """Domain-configured automation_mode for new/promoted storylines."""
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        mode = get_domain_synthesis_config(domain_key).storyline_development.automation.default_mode
        if mode in _VALID_MODES:
            return mode
    except Exception as e:
        logger.debug("get_storyline_automation_mode %s: %s", domain_key, e)
    env_mode = (os.environ.get("STORYLINE_DEFAULT_AUTOMATION_MODE") or "auto_approve").strip()
    return env_mode if env_mode in _VALID_MODES else "auto_approve"


def count_unlinked_articles(domain_key: str, *, lookback_hours: int | None = None) -> int:
    """Articles in lookback window with no storyline_articles link."""
    schema = resolve_domain_schema(domain_key)
    if lookback_hours is None:
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config

            lookback_hours = get_domain_synthesis_config(
                domain_key
            ).storyline_development.proactive.lookback_hours
        except Exception:
            lookback_hours = 72
    try:
        from api.shared.article_signal_gate import sql_article_signal_full_lane_and

        sig = sql_article_signal_full_lane_and("a", schema)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {schema}.articles a
                    WHERE a.created_at >= NOW() - (%s || ' hours')::interval
                      AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                      AND NOT EXISTS (
                          SELECT 1 FROM {schema}.storyline_articles sa
                          WHERE sa.article_id = a.id
                      )
                      {sig}
                    """,
                    (lookback_hours,),
                )
                return int(cur.fetchone()[0] or 0)
    except Exception as e:
        logger.debug("count_unlinked_articles %s: %s", domain_key, e)
        return 0


def domains_needing_assembly() -> list[str]:
    """Pipeline domains with unlinked-article count above per-domain threshold."""
    needing: list[str] = []
    for dk in get_pipeline_active_domain_keys():
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config

            cfg = get_domain_synthesis_config(dk)
            if not cfg.storyline_development.automation.assembly_after_enrichment:
                continue
            threshold = cfg.storyline_development.automation.unlinked_article_threshold
        except Exception:
            threshold = int(os.environ.get("STORYLINE_ASSEMBLY_UNLINKED_THRESHOLD", "25"))
        if count_unlinked_articles(dk) >= threshold:
            needing.append(dk)
    return sort_domains_for_linkage_work(needing)


async def run_storyline_assembly_for_domain(
    domain_key: str,
    *,
    run_proactive: bool = True,
    run_discovery: bool = True,
    run_automation: bool = True,
    discovery_hours: int | None = None,
    max_automation_storylines: int | None = None,
    discovery_save_to_db: bool = True,
    run_eel_reconcile: bool = False,
) -> dict[str, Any]:
    """
    Full storyline assembly for one domain:
    1. Proactive detection (promote emerging clusters)
    2. AI storyline discovery (save new clusters)
    3. Storyline automation (attach new articles to enabled storylines)
    """
    from api.shared.narrative_source_stage_patch import (
        assembly_default_kwargs,
        assembly_operator_override,
        assembly_step_log,
        narrative_source_stage_patch_enabled,
    )

    patch_defaults = assembly_default_kwargs()
    if patch_defaults and not assembly_operator_override():
        run_discovery = bool(patch_defaults.get("run_discovery", run_discovery))
        discovery_save_to_db = bool(
            patch_defaults.get("discovery_save_to_db", discovery_save_to_db)
        )
        run_eel_reconcile = bool(patch_defaults.get("run_eel_reconcile", run_eel_reconcile))

    schema = resolve_domain_schema(domain_key)
    steps: dict[str, Any] = {}
    if narrative_source_stage_patch_enabled():
        steps["patch_v1"] = True
    unlinked_before = count_unlinked_articles(domain_key)

    if run_proactive:
        try:
            from domains.storyline_management.services.proactive_detection_service import (
                ProactiveDetectionService,
            )

            svc = ProactiveDetectionService(domain=domain_key)
            assembly_step_log(domain_key, "proactive_detection")
            result = await svc.detect_emerging_storylines()
            steps["proactive_detection"] = result.get("data") or result
        except Exception as e:
            logger.warning("storyline assembly proactive %s: %s", domain_key, e)
            steps["proactive_detection"] = {"error": str(e)}

    if run_discovery:
        try:
            from services.ai_storyline_discovery import get_discovery_service

            save_db = discovery_save_to_db
            if narrative_source_stage_patch_enabled() and not assembly_operator_override():
                save_db = False
            assembly_step_log(domain_key, "storyline_discovery" if save_db else "storyline_discovery_dry")
            loop = asyncio.get_event_loop()
            discovery = await loop.run_in_executor(
                None,
                lambda: get_discovery_service().discover_storylines(
                    domain=domain_key,
                    hours=discovery_hours,
                    save_to_db=save_db,
                ),
            )
            steps["storyline_discovery"] = {
                "clusters_found": (discovery.get("summary") or {}).get("clusters_found", 0),
                "saved_storylines": len(discovery.get("saved_storylines") or []),
            }
        except Exception as e:
            logger.warning("storyline assembly discovery %s: %s", domain_key, e)
            steps["storyline_discovery"] = {"error": str(e)}

    if run_automation:
        try:
            from services.storyline_automation_service import StorylineAutomationService

            if max_automation_storylines is None:
                try:
                    from services.domain_synthesis_config import get_domain_synthesis_config

                    max_automation_storylines = get_domain_synthesis_config(
                        domain_key
                    ).storyline_development.automation.automation_batch_per_assembly
                except Exception:
                    max_automation_storylines = int(
                        os.environ.get("STORYLINE_ASSEMBLY_AUTOMATION_LIMIT", "20")
                    )

            assembly_step_log(domain_key, "storyline_automation")
            svc = StorylineAutomationService(domain=domain_key)
            linked = 0
            scanned = 0
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT id FROM {schema}.storylines
                        WHERE automation_enabled = true
                        ORDER BY last_automation_run ASC NULLS FIRST
                        LIMIT %s
                        """,
                        (max(1, max_automation_storylines),),
                    )
                    storyline_ids = [int(r[0]) for r in cur.fetchall()]
            for sid in storyline_ids:
                scanned += 1
                result = await svc.discover_articles_for_storyline(sid, force_refresh=False)
                articles = result.get("articles") or []
                linked += len(articles)
            steps["storyline_automation"] = {
                "storylines_scanned": scanned,
                "articles_matched": linked,
            }
        except Exception as e:
            logger.warning("storyline assembly automation %s: %s", domain_key, e)
            steps["storyline_automation"] = {"error": str(e)}

    if run_eel_reconcile:
        try:
            from api.shared.membership_store import reconcile_derived_bags_for_domain

            assembly_step_log(domain_key, "eel_reconcile", stage="S4")
            with get_db_connection_context() as conn:
                steps["eel_reconcile"] = reconcile_derived_bags_for_domain(
                    conn, domain_key=domain_key, schema=schema
                )
                conn.commit()
        except Exception as e:
            logger.warning("storyline assembly eel_reconcile %s: %s", domain_key, e)
            steps["eel_reconcile"] = {"error": str(e)}

    unlinked_after = count_unlinked_articles(domain_key)
    return {
        "success": True,
        "domain": domain_key,
        "unlinked_before": unlinked_before,
        "unlinked_after": unlinked_after,
        "steps": steps,
    }


async def run_storyline_assembly_all_domains(**kwargs: Any) -> dict[str, Any]:
    """Run assembly for every active pipeline domain."""
    from api.shared.narrative_source_stage_patch import assembly_default_kwargs

    merged = {**assembly_default_kwargs(), **kwargs}
    results: dict[str, Any] = {}
    for dk in get_pipeline_active_domain_keys():
        results[dk] = await run_storyline_assembly_for_domain(dk, **merged)
    return {"success": True, "domains": results}
