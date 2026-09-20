"""
Storyline hygiene — scheduled freeze → core prune → near-dup merge loop.

Keeps proteins from re-inflating into kitchen-sink bags and collapses
near-duplicate titles after prune (operator pattern from 3720/3731).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from config.runtime import env_int, env_str
from shared.database.connection import get_db_connection_context
from shared.domain_registry import (
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_TITLE_STOP = frozenset(
    {
        "amid",
        "and",
        "as",
        "escalates",
        "for",
        "from",
        "into",
        "ongoing",
        "over",
        "rising",
        "the",
        "toward",
        "with",
    }
)


def storyline_hygiene_enabled() -> bool:
    return env_str("STORYLINE_HYGIENE_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def storyline_hygiene_dry_run() -> bool:
    return env_str("STORYLINE_HYGIENE_DRY_RUN", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def _min_articles() -> int:
    return max(3, env_int("STORYLINE_HYGIENE_MIN_ARTICLES", 25))


def _max_unlinks() -> int:
    return max(10, env_int("STORYLINE_HYGIENE_MAX_UNLINKS", 200))


def _title_sim_threshold() -> float:
    try:
        return float(env_str("STORYLINE_HYGIENE_TITLE_SIM", "0.72"))
    except ValueError:
        return 0.72


def _freeze_hours() -> float:
    try:
        return float(env_str("STORYLINE_HYGIENE_FREEZE_HOURS", "2.0"))
    except ValueError:
        return 2.0


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def _title_tokens(title: str) -> set[str]:
    return {
        t
        for t in _TOKEN_RE.findall(_normalize_title(title))
        if t not in _TITLE_STOP and not t.isdigit()
    }


def title_near_duplicate(a: str, b: str) -> float:
    """Return best of SequenceMatcher ratio and token Jaccard."""
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = _title_tokens(a), _title_tokens(b)
    jac = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0
    return max(seq, jac)


def count_storyline_hygiene_pending() -> int:
    """Backlog proxy: active storylines at/above hygiene min membership."""
    if not storyline_hygiene_enabled():
        return 0
    min_n = _min_articles()
    total = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for domain in get_pipeline_active_domain_keys():
                    schema = resolve_domain_schema(domain)
                    try:
                        cur.execute(
                            f"""
                            SELECT COUNT(*)::int
                            FROM {schema}.storylines s
                            WHERE s.merged_into_id IS NULL
                              AND COALESCE(s.status, 'active') NOT IN
                                  ('archived', 'merged', 'deleted')
                              AND (
                                COALESCE(s.article_count, 0) >= %s
                                OR EXISTS (
                                  SELECT 1 FROM {schema}.storyline_articles sa
                                  WHERE sa.storyline_id = s.id
                                  GROUP BY sa.storyline_id
                                  HAVING COUNT(*) >= %s
                                )
                              )
                            """,
                            (min_n, min_n),
                        )
                        total += int(cur.fetchone()[0] or 0)
                    except Exception as e:
                        logger.debug("hygiene pending count %s: %s", domain, e)
    except Exception as e:
        logger.debug("hygiene pending total: %s", e)
    return total


def _list_candidates(domain: str, limit: int) -> list[tuple[int, str, int]]:
    schema = resolve_domain_schema(domain)
    min_n = _min_articles()
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id, s.title,
                       COALESCE(
                         (SELECT COUNT(*)::int FROM {schema}.storyline_articles sa
                          WHERE sa.storyline_id = s.id),
                         COALESCE(s.article_count, 0)
                       ) AS members
                FROM {schema}.storylines s
                WHERE s.merged_into_id IS NULL
                  AND COALESCE(s.status, 'active') NOT IN
                      ('archived', 'merged', 'deleted')
                ORDER BY members DESC, s.id
                LIMIT %s
                """,
                (max(1, limit) * 3,),
            )
            rows = [(int(r[0]), str(r[1] or ""), int(r[2] or 0)) for r in cur.fetchall()]
    # Prefer oversized bags; still include smaller ones for near-dup scan
    oversized = [r for r in rows if r[2] >= min_n]
    if len(oversized) >= limit:
        return oversized[:limit]
    return rows[:limit]


def _choose_primary(
    a: tuple[int, str, int], b: tuple[int, str, int]
) -> tuple[tuple[int, str, int], tuple[int, str, int]]:
    """Prefer longer/more specific title; tie-break on member count."""
    ta, tb = a[1] or "", b[1] or ""
    if len(ta) != len(tb):
        return (a, b) if len(ta) > len(tb) else (b, a)
    return (a, b) if a[2] >= b[2] else (b, a)


def _find_near_dup_pairs(
    candidates: list[tuple[int, str, int]], *, max_pairs: int
) -> list[tuple[tuple[int, str, int], tuple[int, str, int], float]]:
    thr = _title_sim_threshold()
    pairs: list[tuple[tuple[int, str, int], tuple[int, str, int], float]] = []
    used: set[int] = set()
    for i, left in enumerate(candidates):
        if left[0] in used:
            continue
        best: tuple[tuple[int, str, int], float] | None = None
        for right in candidates[i + 1 :]:
            if right[0] in used:
                continue
            sim = title_near_duplicate(left[1], right[1])
            if sim < thr:
                continue
            if best is None or sim > best[1]:
                best = (right, sim)
        if best is None:
            continue
        right, sim = best
        primary, secondary = _choose_primary(left, right)
        pairs.append((primary, secondary, sim))
        used.add(primary[0])
        used.add(secondary[0])
        if len(pairs) >= max_pairs:
            break
    return pairs


def run_storyline_hygiene_for_domain(
    domain: str,
    *,
    limit: int = 25,
    max_merges: int = 5,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """
    One domain tick: core-prune up to ``limit`` storylines, then merge up to
    ``max_merges`` near-duplicate title pairs (freeze during ops).
    """
    from services.storyline_coherence_guardrails import (
        assess_storyline_pair_merge_coherence,
    )
    from services.storyline_consolidation_service import (
        StorylineInfo,
        get_consolidation_service,
    )
    from services.storyline_core_prune_service import prune_dissimilar_parts
    from services.storyline_membership_ops_lock import set_membership_freeze

    if dry_run is None:
        dry_run = storyline_hygiene_dry_run()
    schema = resolve_domain_schema(domain)
    import os

    os.environ["STORYLINE_CORE_PRUNE_MAX_UNLINKS"] = str(_max_unlinks())

    out: dict[str, Any] = {
        "domain": domain,
        "dry_run": dry_run,
        "pruned": 0,
        "unlinked": 0,
        "merge_candidates": 0,
        "merged": 0,
        "merge_skipped": 0,
        "errors": 0,
        "samples": [],
    }
    candidates = _list_candidates(domain, limit)
    freeze_h = _freeze_hours()

    for sid, title, members in candidates:
        try:
            if not dry_run:
                set_membership_freeze(
                    schema, sid, "storyline_hygiene_prune", ttl_hours=freeze_h
                )
            stats = prune_dissimilar_parts(
                domain, sid, dry_run=bool(dry_run), count_only=False
            )
            u = int(stats.get("unlinked") or stats.get("would_unlink") or 0)
            out["pruned"] += 1
            out["unlinked"] += u
            if u and len(out["samples"]) < 8:
                out["samples"].append(
                    {
                        "storyline_id": sid,
                        "title": (title or "")[:80],
                        "members_before": members,
                        "unlinked": u,
                        "kept": stats.get("kept_members"),
                    }
                )
            if not dry_run and u:
                set_membership_freeze(
                    schema, sid, "storyline_hygiene_settle", ttl_hours=freeze_h
                )
        except Exception as e:
            out["errors"] += 1
            logger.warning("hygiene prune %s/%s: %s", domain, sid, e)

    # Refresh membership counts for near-dup scan
    refreshed = _list_candidates(domain, limit * 2)
    pairs = _find_near_dup_pairs(refreshed, max_pairs=max(0, max_merges))
    out["merge_candidates"] = len(pairs)

    for primary, secondary, sim in pairs:
        try:
            if dry_run:
                out["merged"] += 1
                continue
            set_membership_freeze(
                schema, primary[0], "storyline_hygiene_merge", ttl_hours=freeze_h
            )
            set_membership_freeze(
                schema, secondary[0], "storyline_hygiene_merge", ttl_hours=freeze_h
            )
            prune_dissimilar_parts(domain, primary[0], dry_run=False)
            prune_dissimilar_parts(domain, secondary[0], dry_run=False)

            p_info = StorylineInfo(
                id=primary[0],
                title=primary[1],
                description="",
                article_count=primary[2],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            s_info = StorylineInfo(
                id=secondary[0],
                title=secondary[1],
                description="",
                article_count=secondary[2],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            ok, reason = assess_storyline_pair_merge_coherence(
                domain, p_info, s_info
            )
            if not ok:
                out["merge_skipped"] += 1
                logger.info(
                    "hygiene merge skip %s: %s <- %s (%s)",
                    domain,
                    primary[0],
                    secondary[0],
                    reason,
                )
                continue
            result = get_consolidation_service().merge_storylines(
                domain, p_info, s_info, {"overall": float(sim)}
            )
            if not result:
                try:
                    from shared.database.connection import get_db_connection_context
                    from services.episode_merge_service import merge_episodes_eel_aware

                    with get_db_connection_context() as conn:
                        eel_result = merge_episodes_eel_aware(
                            conn,
                            domain_key=domain,
                            primary_id=primary[0],
                            secondary_id=secondary[0],
                            reason="storyline_hygiene",
                        )
                        if eel_result.get("success"):
                            conn.commit()
                            result = primary[0]
                except Exception as e:
                    logger.debug("hygiene EEL merge fallback: %s", e)
            if result:
                out["merged"] += 1
                prune_dissimilar_parts(domain, primary[0], dry_run=False)
                set_membership_freeze(
                    schema,
                    primary[0],
                    "storyline_hygiene_post_merge",
                    ttl_hours=freeze_h,
                )
            else:
                out["merge_skipped"] += 1
        except Exception as e:
            out["errors"] += 1
            logger.warning(
                "hygiene merge %s %s<-%s: %s",
                domain,
                primary[0],
                secondary[0],
                e,
            )

    # Title-duplicate episode repair (EEL-aware)
    try:
        from services.episode_merge_service import (
            episode_merge_enabled,
            scan_and_merge_duplicate_episodes,
        )
        from shared.database.connection import get_db_connection_context

        if not dry_run and episode_merge_enabled():
            with get_db_connection_context() as conn:
                dup_scan = scan_and_merge_duplicate_episodes(
                    conn, domain_key=domain, limit=20, dry_run=False
                )
                if dup_scan.get("merged"):
                    conn.commit()
                    out["merged"] += int(dup_scan["merged"])
                    out["episode_dup_repair"] = dup_scan
    except Exception as e:
        logger.debug("hygiene episode dup scan: %s", e)

    return out


def run_storyline_hygiene_all_domains(
    *,
    limit_per_domain: int = 25,
    max_merges_per_domain: int = 5,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    if not storyline_hygiene_enabled():
        return {"enabled": False, "by_domain": {}, "totals": {}}
    if dry_run is None:
        dry_run = storyline_hygiene_dry_run()
    by_domain: dict[str, Any] = {}
    totals = {
        "pruned": 0,
        "unlinked": 0,
        "merged": 0,
        "merge_skipped": 0,
        "errors": 0,
        "merge_candidates": 0,
    }
    for domain in get_pipeline_active_domain_keys():
        res = run_storyline_hygiene_for_domain(
            domain,
            limit=limit_per_domain,
            max_merges=max_merges_per_domain,
            dry_run=dry_run,
        )
        by_domain[domain] = res
        for k in totals:
            totals[k] += int(res.get(k, 0) or 0)
    return {
        "enabled": True,
        "dry_run": dry_run,
        "by_domain": by_domain,
        "totals": totals,
    }
