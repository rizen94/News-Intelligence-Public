"""
Intelligence cleanup controller — automated maintenance for the intelligence layer.

Designed to be called by the automation_manager (data_cleanup phase) or the
newsroom orchestrator. Keeps entity profiles, tracked events, and contexts
lean by removing noise, merging duplicates, and pruning stale data.

Routine data cleanliness includes entity bad-merge decouple: splitting
canonicals that were incorrectly merged (e.g. role-word last name like
"X executives" + "Y executives"). Controlled by policy entity_bad_merge_decouple;
runs once per data_cleanup cycle.

Configurable retention policies control what gets cleaned and when.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import get_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)

DEFAULT_POLICY = {
    "entity_noise_removal": True,
    "entity_duplicate_merge": True,
    "entity_low_value_prune": True,
    "entity_low_value_min_age_days": 14,
    "entity_low_value_max_mentions": 1,
    "stale_event_archive_days": 30,
    "orphan_profile_cleanup": True,
    "max_entity_profiles_per_domain": 10000,
    # Bad-merge decouple: split canonicals that were incorrectly merged (e.g. role-word last name).
    "entity_bad_merge_decouple": True,
    "entity_decouple_max_splits_per_domain": 0,  # 0 = no cap
    # Retention for unbounded intelligence tables (keep under ~1 TB). Set to 0 to disable.
    "retention_fact_log_days": 7,
    "retention_queue_days": 7,
    "retention_pattern_matches_days": 90,
    "retention_storyline_states_days": 365,
}


def _schema(domain_key: str) -> str:
    return resolve_domain_schema(domain_key)


class IntelligenceCleanupController:
    """
    Stateless controller — call run() to execute a full cleanup cycle.
    Each method is idempotent and safe to call repeatedly.
    """

    def __init__(self, policy: dict[str, Any] | None = None):
        self.policy = {**DEFAULT_POLICY, **(policy or {})}

    def run(self, domain_key: str | None = None) -> dict[str, Any]:
        """
        Execute a full cleanup cycle for one domain or all domains.
        Returns a summary of actions taken.
        """
        domains = [domain_key] if domain_key else list(get_active_domain_keys())
        results: dict[str, Any] = {}

        for d in domains:
            domain_result: dict[str, Any] = {}
            try:
                if self.policy["entity_noise_removal"]:
                    domain_result["noise_removed"] = self._remove_noise_entities(d)

                if self.policy["entity_duplicate_merge"]:
                    domain_result["duplicates_merged"] = self._merge_duplicate_entities(d)

                if self.policy["entity_low_value_prune"]:
                    domain_result["low_value_pruned"] = self._prune_low_value_entities(d)

                if self.policy["orphan_profile_cleanup"]:
                    domain_result["orphan_profiles_removed"] = self._cleanup_orphan_profiles(d)

                if self.policy.get("entity_bad_merge_decouple"):
                    domain_result["entity_decouple_splits"] = self._run_entity_decouple(d)

                cap = self.policy["max_entity_profiles_per_domain"]
                if cap:
                    domain_result["excess_capped"] = self._cap_entity_count(d, cap)

            except Exception as e:
                logger.error(f"Cleanup failed for {d}: {e}")
                domain_result["error"] = str(e)

            results[d] = domain_result

        if self.policy.get("stale_event_archive_days"):
            results["stale_events_archived"] = self._archive_stale_events(
                self.policy["stale_event_archive_days"]
            )

        retention = self._apply_intelligence_retention()
        if retention:
            results["retention"] = retention

        total = _sum_results(results)
        logger.info(
            f"Intelligence cleanup complete: {total} total actions across {len(domains)} domain(s)"
        )
        return {"domains": results, "total_actions": total}

    # -- Entity noise removal --------------------------------------------------

    def _remove_noise_entities(self, domain_key: str) -> int:
        """Remove entities that are clearly not real entities (numbers, too-long, generic)."""
        import re

        conn = get_db_connection()
        if not conn:
            return 0

        schema = _schema(domain_key)
        removed = 0

        generic_fragments = [
            "no name",
            "mentioned",
            "unknown",
            "n/a",
            "not specified",
            "unnamed",
            "unidentified",
        ]

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, canonical_name, entity_type FROM {schema}.entity_canonical"
                )
                rows = cur.fetchall()

                noise_ids = []
                for row_id, name, etype in rows:
                    s = name.strip()
                    if (
                        len(s) < 2
                        or re.match(r"^[\d,.\s%$€£]+$", s)
                        or len(s) > 80
                        or any(g in s.lower() for g in generic_fragments)
                        or (etype == "person" and (re.match(r"^\d", s) or len(s) > 60))
                    ):
                        noise_ids.append(row_id)

                if noise_ids:
                    removed = self._delete_canonical_ids(cur, schema, domain_key, noise_ids)

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"noise removal {domain_key}: {e}")
            _safe_rollback_close(conn)
        return removed

    # -- Duplicate merge -------------------------------------------------------

    def _merge_duplicate_entities(self, domain_key: str) -> int:
        """Merge entities with the same lowercase name + type."""
        from collections import defaultdict

        conn = get_db_connection()
        if not conn:
            return 0

        schema = _schema(domain_key)
        merged = 0
        merged_pairs: list[tuple[int, int]] = []

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, canonical_name, entity_type FROM {schema}.entity_canonical ORDER BY id"
                )
                rows = cur.fetchall()

                by_lower = defaultdict(list)
                for row_id, name, etype in rows:
                    by_lower[(name.lower().strip(), etype)].append(row_id)

                for _, ids in by_lower.items():
                    if len(ids) < 2:
                        continue
                    keep_id = ids[0]
                    merge_ids = ids[1:]
                    for mid in merge_ids:
                        merged_pairs.append((int(keep_id), int(mid)))
                    cur.execute(
                        f"""
                        UPDATE {schema}.article_entities
                        SET canonical_entity_id = %s
                        WHERE canonical_entity_id = ANY(%s)
                    """,
                        (keep_id, merge_ids),
                    )
                    self._delete_canonical_ids(cur, schema, domain_key, merge_ids)
                    merged += len(merge_ids)

            conn.commit()
            try:
                from services.graph_connection_queue_service import finalize_entity_merges_in_queue

                finalize_entity_merges_in_queue(domain_key, merged_pairs)
            except Exception:
                pass
            conn.close()
        except Exception as e:
            logger.warning(f"duplicate merge {domain_key}: {e}")
            _safe_rollback_close(conn)
        return merged

    # -- Low-value entity pruning ----------------------------------------------

    def _prune_low_value_entities(self, domain_key: str) -> int:
        """
        Remove entities that appear in very few articles and are old enough
        that they won't gain more mentions. Controlled by policy thresholds.
        """
        conn = get_db_connection()
        if not conn:
            return 0

        schema = _schema(domain_key)
        min_age = timedelta(days=self.policy["entity_low_value_min_age_days"])
        max_mentions = self.policy["entity_low_value_max_mentions"]
        cutoff = datetime.now(timezone.utc) - min_age
        pruned = 0

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT ec.id
                    FROM {schema}.entity_canonical ec
                    WHERE ec.created_at < %s
                      AND (
                          SELECT COUNT(*) FROM {schema}.article_entities ae
                          WHERE ae.canonical_entity_id = ec.id
                      ) <= %s
                """,
                    (cutoff, max_mentions),
                )
                prune_ids = [r[0] for r in cur.fetchall()]

                if prune_ids:
                    pruned = self._delete_canonical_ids(cur, schema, domain_key, prune_ids)

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"low-value prune {domain_key}: {e}")
            _safe_rollback_close(conn)
        return pruned

    # -- Orphan profile cleanup ------------------------------------------------

    def _cleanup_orphan_profiles(self, domain_key: str) -> int:
        """
        Remove entity_profiles that no longer have a matching entity_canonical row.
        """
        conn = get_db_connection()
        if not conn:
            return 0

        schema = _schema(domain_key)
        removed = 0

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM intelligence.entity_profiles ep
                    WHERE ep.domain_key = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM """
                    + schema
                    + """.entity_canonical ec
                          WHERE ec.id = ep.canonical_entity_id
                      )
                """,
                    (domain_key,),
                )
                removed = cur.rowcount

                cur.execute(
                    """
                    DELETE FROM intelligence.old_entity_to_new
                    WHERE domain_key = %s
                      AND old_entity_id NOT IN (
                          SELECT id FROM """
                    + schema
                    + """.entity_canonical
                      )
                """,
                    (domain_key,),
                )

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"orphan cleanup {domain_key}: {e}")
            _safe_rollback_close(conn)
        return removed

    # -- Entity count cap ------------------------------------------------------

    def _cap_entity_count(self, domain_key: str, max_count: int) -> int:
        """
        If entity count exceeds max_count, remove the least-referenced entities
        until we're back under the cap.
        """
        conn = get_db_connection()
        if not conn:
            return 0

        schema = _schema(domain_key)
        removed = 0

        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {schema}.entity_canonical")
                total = cur.fetchone()[0]
                if total <= max_count:
                    conn.close()
                    return 0

                excess = total - max_count
                cur.execute(
                    f"""
                    SELECT ec.id FROM {schema}.entity_canonical ec
                    LEFT JOIN (
                        SELECT canonical_entity_id, COUNT(*) AS cnt
                        FROM {schema}.article_entities
                        WHERE canonical_entity_id IS NOT NULL
                        GROUP BY canonical_entity_id
                    ) ae ON ae.canonical_entity_id = ec.id
                    ORDER BY COALESCE(ae.cnt, 0) ASC, ec.created_at ASC
                    LIMIT %s
                """,
                    (excess,),
                )
                cap_ids = [r[0] for r in cur.fetchall()]

                if cap_ids:
                    removed = self._delete_canonical_ids(cur, schema, domain_key, cap_ids)

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"cap entities {domain_key}: {e}")
            _safe_rollback_close(conn)
        return removed

    # -- Entity bad-merge decouple (routine data cleanliness) ------------------

    def _run_entity_decouple(self, domain_key: str) -> int:
        """
        Run entity decouple pipeline for this domain: split canonicals that were
        incorrectly merged (e.g. role-word last name). Part of routine data cleanup.
        """
        try:
            from services.entity_resolution_service import run_entity_decouple_pipeline

            max_splits = self.policy.get("entity_decouple_max_splits_per_domain") or None
            if max_splits == 0:
                max_splits = None
            result = run_entity_decouple_pipeline(
                domain_keys=[domain_key],
                dry_run=False,
                max_splits_per_domain=max_splits,
            )
            by_domain = result.get("by_domain") or {}
            domain_result = by_domain.get(domain_key) or {}
            count = domain_result.get("split_count", 0)
            if count:
                logger.info(
                    "Entity decouple %s: %s splits (canonicals_processed=%s)",
                    domain_key,
                    count,
                    domain_result.get("canonicals_processed", 0),
                )
            return count
        except Exception as e:
            logger.warning("Entity decouple %s: %s", domain_key, e)
            return 0

    # -- Stale event archival --------------------------------------------------

    def _archive_stale_events(self, max_age_days: int) -> int:
        """
        Remove tracked events that haven't had a new chronicle entry in
        max_age_days AND have no end_date (open-ended stale events).
        Sets end_date to today rather than deleting, preserving history.
        """
        conn = get_db_connection()
        if not conn:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        archived = 0

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.tracked_events te
                    SET end_date = CURRENT_DATE, updated_at = NOW()
                    WHERE te.end_date IS NULL
                      AND te.updated_at < %s
                      AND NOT EXISTS (
                          SELECT 1 FROM intelligence.event_chronicles ec
                          WHERE ec.event_id = te.id AND ec.created_at >= %s
                      )
                """,
                    (cutoff, cutoff),
                )
                archived = cur.rowcount

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"stale event archive: {e}")
            _safe_rollback_close(conn)
        return archived

    # -- Intelligence table retention (keep under ~1 TB) -----------------------

    def _apply_intelligence_retention(self) -> dict[str, int] | None:
        """
        Delete old processed/obsolete rows from fact_change_log, story_update_queue,
        pattern_matches, and storyline_states. Only runs when policy retention_*_days > 0.
        """
        out: dict[str, int] = {}
        conn = get_db_connection()
        if not conn:
            return out

        try:
            with conn.cursor() as cur:
                if self.policy.get("retention_fact_log_days"):
                    cutoff = datetime.now(timezone.utc) - timedelta(
                        days=self.policy["retention_fact_log_days"]
                    )
                    cur.execute(
                        """
                        DELETE FROM intelligence.fact_change_log
                        WHERE processed = TRUE AND processed_at IS NOT NULL AND processed_at < %s
                        """,
                        (cutoff,),
                    )
                    out["fact_change_log_deleted"] = cur.rowcount

                if self.policy.get("retention_queue_days"):
                    cutoff = datetime.now(timezone.utc) - timedelta(
                        days=self.policy["retention_queue_days"]
                    )
                    cur.execute(
                        """
                        DELETE FROM intelligence.story_update_queue
                        WHERE processed = TRUE AND processed_at IS NOT NULL AND processed_at < %s
                        """,
                        (cutoff,),
                    )
                    out["story_update_queue_deleted"] = cur.rowcount

                if self.policy.get("retention_pattern_matches_days"):
                    cutoff = datetime.now(timezone.utc) - timedelta(
                        days=self.policy["retention_pattern_matches_days"]
                    )
                    cur.execute(
                        "DELETE FROM intelligence.pattern_matches WHERE created_at < %s",
                        (cutoff,),
                    )
                    out["pattern_matches_deleted"] = cur.rowcount

                if self.policy.get("retention_storyline_states_days"):
                    cutoff = datetime.now(timezone.utc) - timedelta(
                        days=self.policy["retention_storyline_states_days"]
                    )
                    cur.execute(
                        "DELETE FROM intelligence.storyline_states WHERE created_at < %s",
                        (cutoff,),
                    )
                    out["storyline_states_deleted"] = cur.rowcount

            conn.commit()
            conn.close()
            if out:
                logger.info(
                    "Intelligence retention: fact_log=%s queue=%s pattern_matches=%s storyline_states=%s",
                    out.get("fact_change_log_deleted", 0),
                    out.get("story_update_queue_deleted", 0),
                    out.get("pattern_matches_deleted", 0),
                    out.get("storyline_states_deleted", 0),
                )
        except Exception as e:
            logger.warning("Intelligence retention failed: %s", e)
            _safe_rollback_close(conn)
        if out and sum(out.values()) > 0:
            return out
        return None

    # -- Helpers ---------------------------------------------------------------

    def _delete_canonical_ids(self, cur, schema: str, domain_key: str, ids: list) -> int:
        """
        Remove entity_canonical IDs and cascade to article_entities FK,
        intelligence.old_entity_to_new, and intelligence.entity_profiles.
        """
        if not ids:
            return 0

        cur.execute(
            f"""
            UPDATE {schema}.article_entities
            SET canonical_entity_id = NULL
            WHERE canonical_entity_id = ANY(%s)
        """,
            (ids,),
        )

        cur.execute(
            """
            DELETE FROM intelligence.old_entity_to_new
            WHERE domain_key = %s AND old_entity_id = ANY(%s)
        """,
            (domain_key, ids),
        )

        cur.execute(
            """
            DELETE FROM intelligence.entity_profiles
            WHERE domain_key = %s AND canonical_entity_id = ANY(%s)
        """,
            (domain_key, ids),
        )

        cur.execute(
            f"""
            DELETE FROM {schema}.entity_canonical WHERE id = ANY(%s)
        """,
            (ids,),
        )
        return len(ids)


def _safe_rollback_close(conn) -> None:
    try:
        conn.rollback()
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass


def _sum_results(results: dict[str, Any]) -> int:
    total = 0
    for val in results.values():
        if isinstance(val, dict):
            for v in val.values():
                if isinstance(v, int):
                    total += v
        elif isinstance(val, int):
            total += val
    return total


# -- Convenience function for orchestrator integration -------------------------


async def run_intelligence_cleanup(
    domain_key: str | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Async wrapper for use by automation_manager or newsroom orchestrator.
    Runs the full cleanup cycle in the default executor.
    """
    import asyncio

    loop = asyncio.get_event_loop()
    controller = IntelligenceCleanupController(policy=policy)
    return await loop.run_in_executor(None, controller.run, domain_key)
