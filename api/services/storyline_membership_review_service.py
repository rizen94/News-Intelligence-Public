"""
Storyline membership review — decouple off-topic articles and deprioritize weak connections.

Deterministic fit scoring first; mid-band / propose-only rows go to
intelligence.storyline_membership_actions for human/LLM approve/reject.
Each storyline is marked reviewed with a membership fingerprint so unchanged
megas are not re-scanned; fingerprint drift (member add/remove) re-queues.
High-offtopic unlinks (when auto-apply is on) reuse DELETE + count sync.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_int, env_str
from shared.database.connection import get_db_connection
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.storyline_article_counts import sync_counts_update_sql, sync_storyline_derived_metrics

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def membership_review_enabled() -> bool:
    """Default ON so mega review automation runs; set false to disable."""
    return env_str("STORYLINE_MEMBERSHIP_REVIEW_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def membership_review_dry_run() -> bool:
    """Legacy observe-only flag. Default off — use propose queue + review_state instead."""
    return env_str("STORYLINE_MEMBERSHIP_REVIEW_DRY_RUN", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def membership_auto_apply() -> bool:
    """When true (and not dry_run), apply clear unlink/demote immediately. Default: queue proposals."""
    return env_str("STORYLINE_MEMBERSHIP_AUTO_APPLY", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def membership_mega_auto_apply() -> bool:
    """
    Auto-apply clear unlink/demote on large storylines (megas).

    Default ON so kitchen-sink megas can shed dissimilar members without waiting
    for a global STORYLINE_MEMBERSHIP_AUTO_APPLY flip.
    """
    return env_str("STORYLINE_MEMBERSHIP_MEGA_AUTO_APPLY", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _keep_score() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_KEEP_SCORE", "0.55"))
    except ValueError:
        return 0.55


def _demote_score() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_DEMOTE_SCORE", "0.35"))
    except ValueError:
        return 0.35


def _unlink_score() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_UNLINK_SCORE", "0.28"))
    except ValueError:
        return 0.28


def _demote_cap() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_DEMOTE_CAP", "0.35"))
    except ValueError:
        return 0.35


def _min_remaining() -> int:
    return max(1, env_int("STORYLINE_MEMBERSHIP_MIN_REMAINING", 3))


def _max_unlinks_per_storyline() -> int:
    return max(0, env_int("STORYLINE_MEMBERSHIP_MAX_UNLINKS_PER_STORYLINE", 25))


def _min_article_count_for_review() -> int:
    return max(5, env_int("STORYLINE_MEMBERSHIP_MIN_ARTICLE_COUNT", 50))


def _max_storylines() -> int:
    return max(1, env_int("STORYLINE_MEMBERSHIP_REVIEW_MAX_STORYLINES", 100))


def _graph_quarantine_confidence() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_GRAPH_QUARANTINE_MAX_CONF", "0.55"))
    except ValueError:
        return 0.55


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


def _membership_age_weight(article_published_at: datetime | None) -> float:
    """Optional decay weight for older articles in fit scoring (default off)."""
    try:
        w = float(env_str("STORYLINE_MEMBERSHIP_AGE_WEIGHT", "0"))
    except ValueError:
        return 1.0
    if w <= 0 or article_published_at is None:
        return 1.0
    try:
        days = max(0, env_int("STORYLINE_MEMBERSHIP_AGE_DECAY_DAYS", 180))
    except ValueError:
        days = 180
    age_days = max(
        0.0,
        (datetime.now(timezone.utc) - article_published_at).total_seconds() / 86400.0,
    )
    decay = max(0.0, 1.0 - (age_days / float(days)))
    return max(0.0, min(1.0, (1.0 - w) + w * decay))


def compute_article_fit_score(
    *,
    core_tokens: set[str],
    core_entities: set[str],
    article_title: str,
    article_entities: set[str],
    relevance_score: float | None,
    article_published_at: datetime | None = None,
) -> float:
    """Deterministic 0–1 fit of an article to storyline core."""
    title_j = _jaccard(core_tokens, _tokenize(article_title))
    ent_j = _jaccard(core_entities, {e.lower() for e in article_entities if e})
    rel = float(relevance_score) if relevance_score is not None else 0.5
    rel = max(0.0, min(1.0, rel))
    raw = max(0.0, min(1.0, 0.40 * ent_j + 0.30 * title_j + 0.30 * rel))
    age_w = _membership_age_weight(article_published_at)
    return max(0.0, min(1.0, raw * age_w))


def decide_membership_article_action(
    fit: float,
    *,
    keep: float,
    demote_floor: float,
    unlink_floor: float,
    remaining: int,
    min_remain: int,
    unlinks_done: int,
    max_unlinks: int,
) -> tuple[str, str, bool]:
    """
    Return (action, rationale, queue_only).

    action: keep | demote_relevance | unlink
    queue_only: True for mid-band uncertain rows that should not auto-apply.
    """
    if fit >= keep:
        return "keep", f"fit={fit:.3f} >= keep {keep}", False

    if fit < unlink_floor:
        if remaining - 1 < min_remain or unlinks_done >= max_unlinks:
            return (
                "demote_relevance",
                (
                    f"fit={fit:.3f} below unlink but min_remaining/max_unlinks "
                    f"blocks hard unlink; demote instead"
                ),
                False,
            )
        return "unlink", f"fit={fit:.3f} below unlink threshold {unlink_floor}", False

    if fit < demote_floor:
        # Mid-band: queue for human / later LLM — do not auto-apply.
        preferred = (
            "unlink" if fit < (unlink_floor + demote_floor) / 2 else "demote_relevance"
        )
        if preferred == "unlink" and (
            remaining - 1 < min_remain or unlinks_done >= max_unlinks
        ):
            preferred = "demote_relevance"
        return (
            preferred,
            f"fit={fit:.3f} mid-band [{unlink_floor},{demote_floor}); queue",
            True,
        )

    return (
        "demote_relevance",
        f"fit={fit:.3f} in demote band [{demote_floor},{keep})",
        False,
    )


def _norm_claim_part(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def objects_incompatible(a: str, b: str) -> bool:
    """Heuristic: distinct objects with low token overlap, number mismatch, or negation."""
    na, nb = _norm_claim_part(a), _norm_claim_part(b)
    if not na or not nb or na == nb:
        return False
    neg_a = na.startswith("not ") or " no " in f" {na} " or na.startswith("never ")
    neg_b = nb.startswith("not ") or " no " in f" {nb} " or nb.startswith("never ")
    if neg_a != neg_b and (
        na.replace("not ", "").strip() == nb.replace("not ", "").strip()
        or na in nb
        or nb in na
    ):
        return True
    nums_a = re.findall(r"\d+(?:\.\d+)?", na)
    nums_b = re.findall(r"\d+(?:\.\d+)?", nb)
    if nums_a and nums_b and nums_a != nums_b:
        return True
    ta, tb = set(_TOKEN_RE.findall(na)), set(_TOKEN_RE.findall(nb))
    if not ta or not tb:
        return na != nb
    inter = len(ta & tb)
    union = len(ta | tb)
    j = float(inter) / float(union) if union else 0.0
    return j < 0.25


def detect_claim_contradictions(
    claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Same subject+predicate with incompatible objects → contradiction groups.

    Each claim dict: subject/predicate/object (or *_text), optional article_id, id.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for c in claims or []:
        subj = _norm_claim_part(str(c.get("subject") or c.get("subject_text") or ""))
        pred = _norm_claim_part(str(c.get("predicate") or c.get("predicate_text") or ""))
        obj = str(c.get("object") or c.get("object_text") or "").strip()
        if not subj or not pred or not obj:
            continue
        groups.setdefault((subj, pred), []).append(c)

    out: list[dict[str, Any]] = []
    for (subj, pred), rows in groups.items():
        if len(rows) < 2:
            continue
        objs = [
            str(r.get("object") or r.get("object_text") or "").strip() for r in rows
        ]
        conflict = False
        for i in range(len(objs)):
            for j in range(i + 1, len(objs)):
                if objects_incompatible(objs[i], objs[j]):
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            article_ids = sorted(
                {
                    int(r["article_id"])
                    for r in rows
                    if r.get("article_id") is not None
                }
            )
            out.append(
                {
                    "subject": subj,
                    "predicate": pred,
                    "objects": objs,
                    "claim_ids": [r.get("id") for r in rows if r.get("id") is not None],
                    "article_ids": article_ids,
                    "reason_code": "claim_contradiction",
                }
            )
    return out


def _load_storyline_member_claims(
    cur,
    *,
    domain_key: str,
    article_ids: list[int],
    limit: int = 200,
) -> list[dict[str, Any]]:
    if not article_ids:
        return []
    cur.execute(
        """
        SELECT ec.id, ec.subject_text, ec.predicate_text, ec.object_text,
               atc.article_id
        FROM intelligence.extracted_claims ec
        JOIN intelligence.article_to_context atc ON atc.context_id = ec.context_id
        WHERE atc.article_id = ANY(%s)
          AND (atc.domain_key = %s OR atc.domain_key IS NULL)
        ORDER BY ec.confidence DESC NULLS LAST, ec.id DESC
        LIMIT %s
        """,
        (list(article_ids), domain_key, max(1, min(int(limit), 500))),
    )
    out: list[dict[str, Any]] = []
    for r in cur.fetchall() or []:
        out.append(
            {
                "id": r[0],
                "subject_text": r[1] or "",
                "predicate_text": r[2] or "",
                "object_text": r[3] or "",
                "article_id": int(r[4]) if r[4] is not None else None,
            }
        )
    return out


# Must match intelligence.storyline_membership_actions_action_check (migration 269).
MEMBERSHIP_ACTIONS_ALLOWED = frozenset(
    {
        "unlink",
        "demote_relevance",
        "quarantine_graph",
        "demote_entity",
        "unlink_tracked_event",
    }
)


def _enqueue_action(
    cur,
    *,
    domain_key: str,
    storyline_id: int,
    action: str,
    fit_score: float | None,
    rationale: str,
    article_id: int | None = None,
    entity_name: str | None = None,
    tracked_event_id: int | None = None,
    graph_left_kind: str | None = None,
    graph_left_id: int | None = None,
    graph_right_kind: str | None = None,
    graph_right_id: int | None = None,
    status: str = "pending",
    metadata: dict[str, Any] | None = None,
) -> int | None:
    """
    Insert a membership action row. Unsupported actions are skipped (never inserted)
    so CHECK violations cannot abort the caller's transaction.

    Uses a SAVEPOINT so any remaining DB error rolls back only this insert.
    """
    if action not in MEMBERSHIP_ACTIONS_ALLOWED:
        meta = dict(metadata or {})
        meta["skipped_action"] = action
        logger.warning(
            "skip unsupported membership action=%s domain=%s storyline=%s meta=%s",
            action,
            domain_key,
            storyline_id,
            {k: meta.get(k) for k in ("source", "chunk_excerpt", "reason_code") if k in meta},
        )
        return None

    # SAVEPOINT: CheckViolation / unique race must not abort outer prune/finisher txn.
    cur.execute("SAVEPOINT membership_enqueue")
    try:
        if status == "pending":
            cur.execute(
                """
                SELECT id FROM intelligence.storyline_membership_actions
                WHERE status IN ('pending', 'dry_run')
                  AND domain_key = %s
                  AND storyline_id = %s
                  AND action = %s
                  AND article_id IS NOT DISTINCT FROM %s
                  AND entity_name IS NOT DISTINCT FROM %s
                  AND tracked_event_id IS NOT DISTINCT FROM %s
                  AND graph_left_kind IS NOT DISTINCT FROM %s
                  AND graph_left_id IS NOT DISTINCT FROM %s
                  AND graph_right_kind IS NOT DISTINCT FROM %s
                  AND graph_right_id IS NOT DISTINCT FROM %s
                LIMIT 1
                """,
                (
                    domain_key,
                    storyline_id,
                    action,
                    article_id,
                    entity_name,
                    tracked_event_id,
                    graph_left_kind,
                    graph_left_id,
                    graph_right_kind,
                    graph_right_id,
                ),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("RELEASE SAVEPOINT membership_enqueue")
                return int(existing[0])
        cur.execute(
            """
            INSERT INTO intelligence.storyline_membership_actions
            (domain_key, storyline_id, article_id, entity_name, tracked_event_id,
             graph_left_kind, graph_left_id, graph_right_kind, graph_right_id,
             action, fit_score, status, rationale, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            RETURNING id
            """,
            (
                domain_key,
                storyline_id,
                article_id,
                entity_name,
                tracked_event_id,
                graph_left_kind,
                graph_left_id,
                graph_right_kind,
                graph_right_id,
                action,
                fit_score,
                status,
                (rationale or "")[:2000],
                json.dumps(metadata or {}),
            ),
        )
        row = cur.fetchone()
        cur.execute("RELEASE SAVEPOINT membership_enqueue")
        return int(row[0]) if row else None
    except Exception as e:
        try:
            cur.execute("ROLLBACK TO SAVEPOINT membership_enqueue")
        except Exception:
            pass
        logger.warning(
            "membership enqueue failed action=%s storyline=%s: %s",
            action,
            storyline_id,
            e,
        )
        return None


def _membership_fingerprint_sql(schema: str, storyline_alias: str = "s") -> str:
    """SQL expr: count:sum(article_id):max(article_id) — changes when members add/remove."""
    return f"""(
        SELECT COUNT(*)::text
            || ':' || COALESCE(SUM(sa.article_id), 0)::text
            || ':' || COALESCE(MAX(sa.article_id), 0)::text
        FROM {schema}.storyline_articles sa
        WHERE sa.storyline_id = {storyline_alias}.id
    )"""


def membership_needs_review_where_sql(schema: str, storyline_alias: str = "s") -> str:
    """
    SSOT WHERE fragment for megas the membership drain will pick.

    Bind ``min_article_count`` once for the ``article_count >= %s`` placeholder.
    Caller must ``LEFT JOIN intelligence.storyline_membership_review_state r``
    on ``r.domain_key`` / ``r.storyline_id``.
    """
    fp_sql = _membership_fingerprint_sql(schema, storyline_alias)
    a = storyline_alias
    return f"""
                {a}.status = 'active'
                  AND {a}.merged_into_id IS NULL
                  AND COALESCE({a}.article_count, 0) >= %s
                  AND (
                    r.storyline_id IS NULL
                    OR r.membership_fingerprint IS DISTINCT FROM {fp_sql}
                  )
""".rstrip()


def count_storylines_needing_membership_review(
    *,
    domain_key: str | None = None,
) -> int:
    """Count megas matching ``_pick_storylines`` eligibility (automation drain SSOT)."""
    if not membership_review_enabled():
        return 0
    from shared.domain_processing_mode import filter_domains_for_phase
    from shared.domain_registry import get_pipeline_active_domain_keys

    domains = [domain_key] if domain_key else filter_domains_for_phase(
        get_pipeline_active_domain_keys(), "storyline_membership_review"
    )
    min_arts = _min_article_count_for_review()
    total = 0
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            for dk in domains:
                if not dk:
                    continue
                schema = resolve_domain_schema(dk)
                where = membership_needs_review_where_sql(schema, "s")
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int
                    FROM {schema}.storylines s
                    LEFT JOIN intelligence.storyline_membership_review_state r
                      ON r.domain_key = %s AND r.storyline_id = s.id
                    WHERE {where}
                    """,
                    (dk, min_arts),
                )
                total += int(cur.fetchone()[0] or 0)
        return total
    except Exception as e:
        logger.debug("count_storylines_needing_membership_review: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _read_membership_fingerprint(
    cur, schema: str, storyline_id: int
) -> tuple[str, int, int]:
    cur.execute(
        f"""
        SELECT COUNT(*)::int,
               COALESCE(SUM(article_id), 0)::bigint,
               COALESCE(MAX(article_id), 0)::bigint
        FROM {schema}.storyline_articles
        WHERE storyline_id = %s
        """,
        (storyline_id,),
    )
    row = cur.fetchone() or (0, 0, 0)
    link_count = int(row[0] or 0)
    sum_ids = int(row[1] or 0)
    max_id = int(row[2] or 0)
    fp = f"{link_count}:{sum_ids}:{max_id}"
    return fp, link_count, link_count


def _mark_storyline_reviewed(
    cur,
    *,
    domain_key: str,
    storyline_id: int,
    schema: str,
    article_count: int | None = None,
) -> str:
    fp, link_count, _ = _read_membership_fingerprint(cur, schema, storyline_id)
    if article_count is None:
        cur.execute(
            f"""
            SELECT COALESCE(article_count, 0)::int
            FROM {schema}.storylines WHERE id = %s
            """,
            (storyline_id,),
        )
        row = cur.fetchone()
        article_count = int(row[0] or 0) if row else link_count
    cur.execute(
        """
        INSERT INTO intelligence.storyline_membership_review_state
            (domain_key, storyline_id, reviewed_at, membership_fingerprint,
             article_count, link_count)
        VALUES (%s, %s, NOW(), %s, %s, %s)
        ON CONFLICT (domain_key, storyline_id) DO UPDATE SET
            reviewed_at = EXCLUDED.reviewed_at,
            membership_fingerprint = EXCLUDED.membership_fingerprint,
            article_count = EXCLUDED.article_count,
            link_count = EXCLUDED.link_count
        """,
        (domain_key, storyline_id, fp, int(article_count or 0), link_count),
    )
    return fp


def _unlink_article(cur, schema: str, storyline_id: int, article_id: int) -> bool:
    cur.execute(
        f"""
        DELETE FROM {schema}.storyline_articles
        WHERE storyline_id = %s AND article_id = %s
        """,
        (storyline_id, article_id),
    )
    if cur.rowcount <= 0:
        return False
    cur.execute(
        f"""
        UPDATE {schema}.storylines
        SET {sync_counts_update_sql(schema)},
            updated_at = %s
        WHERE id = %s
        """,
        (storyline_id, storyline_id, datetime.now(timezone.utc), storyline_id),
    )
    sync_storyline_derived_metrics(cur, schema, storyline_id)
    return True


def _demote_relevance(cur, schema: str, storyline_id: int, article_id: int, cap: float) -> bool:
    cur.execute(
        f"""
        UPDATE {schema}.storyline_articles
        SET relevance_score = LEAST(COALESCE(relevance_score, 1.0), %s)
        WHERE storyline_id = %s AND article_id = %s
          AND COALESCE(relevance_score, 1.0) > %s
        """,
        (cap, storyline_id, article_id, cap),
    )
    return cur.rowcount > 0


def review_storyline_membership(
    domain_key: str,
    storyline_id: int,
    *,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """
    Score linked articles vs storyline core; demote / unlink / queue; then
    soft-deprioritize weak graph edges, SEI core flags, and tracked_event links.
    """
    if dry_run is None:
        dry_run = membership_review_dry_run()
    # Propose by default: queue pending. Auto-apply when explicitly enabled, or for megas.
    schema = resolve_domain_schema(domain_key)
    keep = _keep_score()
    demote_floor = _demote_score()
    unlink_floor = _unlink_score()
    demote_cap = _demote_cap()
    min_remain = _min_remaining()
    max_unlinks = _max_unlinks_per_storyline()
    mega_floor = _min_article_count_for_review()

    stats: dict[str, Any] = {
        "domain_key": domain_key,
        "storyline_id": storyline_id,
        "dry_run": dry_run,
        "auto_apply": False,
        "scored": 0,
        "kept": 0,
        "demoted": 0,
        "unlinked": 0,
        "queued": 0,
        "graph_quarantined": 0,
        "sei_demoted": 0,
        "tracked_events_unlinked": 0,
        "skipped_min_remaining": 0,
        "claim_contradictions": 0,
        "errors": 0,
    }

    conn = get_db_connection()
    if not conn:
        return {**stats, "error": "no_db_connection"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title,
                       COALESCE(canonical_narrative, master_summary, summary, description, ''),
                       COALESCE(article_count, 0)
                FROM {schema}.storylines
                WHERE id = %s AND merged_into_id IS NULL
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                return {**stats, "error": "storyline_not_found"}
            title, summary, article_count = row[1], row[2] or "", int(row[3] or 0)
            auto_apply = (not dry_run) and (
                membership_auto_apply()
                or (
                    article_count >= mega_floor
                    and membership_mega_auto_apply()
                )
            )
            stats["auto_apply"] = auto_apply
            stats["article_count"] = article_count
            core_tokens = _tokenize(f"{title} {summary}")

            cur.execute(
                f"""
                SELECT entity_name, COALESCE(mention_count, 0), COALESCE(is_core_entity, false)
                FROM {schema}.story_entity_index
                WHERE storyline_id = %s
                ORDER BY is_core_entity DESC NULLS LAST, mention_count DESC NULLS LAST
                LIMIT 40
                """,
                (storyline_id,),
            )
            sei_rows = cur.fetchall()
            core_entities = {
                (r[0] or "").strip().lower()
                for r in sei_rows
                if r[0] and (r[2] or int(r[1] or 0) >= 3)
            }
            if not core_entities:
                core_entities = {(r[0] or "").strip().lower() for r in sei_rows[:15] if r[0]}

            cur.execute(
                f"""
                SELECT sa.article_id, sa.relevance_score, a.title,
                       COALESCE(a.published_at, a.created_at),
                       COALESCE(
                         (SELECT array_agg(DISTINCT lower(ae.entity_name))
                          FROM {schema}.article_entities ae
                          WHERE ae.article_id = sa.article_id
                            AND ae.entity_name IS NOT NULL),
                         ARRAY[]::text[]
                       )
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                """,
                (storyline_id,),
            )
            members = cur.fetchall()

            # Claim contradictions among member articles → demote/split trigger.
            try:
                art_ids = [int(m[0]) for m in members if m and m[0] is not None]
                claim_rows = _load_storyline_member_claims(
                    cur,
                    domain_key=domain_key,
                    article_ids=art_ids,
                )
                contradictions = detect_claim_contradictions(claim_rows)
                stats["claim_contradictions"] = len(contradictions)
                contradicted_articles: set[int] = set()
                for group in contradictions:
                    for aid in group.get("article_ids") or []:
                        contradicted_articles.add(int(aid))
                    # Queue demote for each article in the contradiction group.
                    for aid in group.get("article_ids") or []:
                        _enqueue_action(
                            cur,
                            domain_key=domain_key,
                            storyline_id=storyline_id,
                            article_id=int(aid),
                            action="demote_relevance",
                            fit_score=None,
                            rationale=(
                                f"claim_contradiction subject={group.get('subject')!r} "
                                f"predicate={group.get('predicate')!r}"
                            ),
                            status="dry_run" if dry_run else "pending",
                            metadata={
                                "reason_code": "claim_contradiction",
                                "objects": group.get("objects"),
                                "claim_ids": group.get("claim_ids"),
                            },
                        )
                        stats["queued"] += 1
                        if auto_apply and not dry_run:
                            if _demote_relevance(
                                cur, schema, storyline_id, int(aid), demote_cap
                            ):
                                stats["demoted"] += 1
            except Exception as cex:
                logger.debug(
                    "claim contradiction scan storyline=%s: %s", storyline_id, cex
                )
                contradicted_articles = set()

            remaining = article_count
            unlinks_done = 0
            for article_id, rel, art_title, pub_at, ent_arr in members:
                stats["scored"] += 1
                # Already queued/demoted for claim contradiction — skip fit path.
                if int(article_id) in contradicted_articles:
                    continue
                ents = {e for e in (ent_arr or []) if e}
                fit = compute_article_fit_score(
                    core_tokens=core_tokens,
                    core_entities=core_entities,
                    article_title=art_title or "",
                    article_entities=ents,
                    relevance_score=float(rel) if rel is not None else None,
                    article_published_at=pub_at,
                )
                action, rationale, queue_only = decide_membership_article_action(
                    fit,
                    keep=keep,
                    demote_floor=demote_floor,
                    unlink_floor=unlink_floor,
                    remaining=remaining,
                    min_remain=min_remain,
                    unlinks_done=unlinks_done,
                    max_unlinks=max_unlinks,
                )
                if action == "keep":
                    stats["kept"] += 1
                    continue

                if "min_remaining" in rationale or "max_unlinks" in rationale:
                    stats["skipped_min_remaining"] += 1

                if (not auto_apply) or queue_only:
                    _enqueue_action(
                        cur,
                        domain_key=domain_key,
                        storyline_id=storyline_id,
                        article_id=int(article_id),
                        action=action,
                        fit_score=fit,
                        rationale=rationale
                        + (" [dry_run]" if dry_run else ""),
                        status="dry_run" if dry_run else "pending",
                        metadata={"reason_code": "dissimilar_to_core"}
                        if fit < demote_floor
                        else None,
                    )
                    stats["queued"] += 1
                    continue

                if action == "unlink":
                    if _unlink_article(cur, schema, storyline_id, int(article_id)):
                        remaining -= 1
                        unlinks_done += 1
                        stats["unlinked"] += 1
                        _enqueue_action(
                            cur,
                            domain_key=domain_key,
                            storyline_id=storyline_id,
                            article_id=int(article_id),
                            action="unlink",
                            fit_score=fit,
                            rationale=rationale,
                            status="applied",
                            metadata={"reason_code": "dissimilar_to_core"},
                        )
                    else:
                        stats["errors"] += 1
                else:
                    if _demote_relevance(cur, schema, storyline_id, int(article_id), demote_cap):
                        stats["demoted"] += 1
                    _enqueue_action(
                        cur,
                        domain_key=domain_key,
                        storyline_id=storyline_id,
                        article_id=int(article_id),
                        action="demote_relevance",
                        fit_score=fit,
                        rationale=rationale,
                        status="applied",
                        metadata={"reason_code": "dissimilar_to_core"}
                        if fit < keep
                        else None,
                    )

            # --- Connection deprioritize ---
            # Graph links involving this storyline id
            cur.execute(
                """
                SELECT id, left_kind, left_id, right_kind, right_id,
                       COALESCE(confidence, 0.0), link_role
                FROM intelligence.graph_connection_links
                WHERE status = 'active'
                  AND (domain_key IS NULL OR domain_key = %s)
                  AND (
                    (left_kind = 'storyline' AND left_id = %s)
                    OR (right_kind = 'storyline' AND right_id = %s)
                  )
                LIMIT 100
                """,
                (domain_key, storyline_id, storyline_id),
            )
            graph_rows = cur.fetchall()
            qmax = _graph_quarantine_confidence()
            for _gid, lk, li, rk, ri, conf, role in graph_rows:
                if float(conf or 0) > qmax:
                    continue
                rationale = f"weak graph edge confidence={float(conf):.3f} <= {qmax}"
                if not auto_apply:
                    _enqueue_action(
                        cur,
                        domain_key=domain_key,
                        storyline_id=storyline_id,
                        action="quarantine_graph",
                        fit_score=float(conf),
                        rationale=rationale + (" [dry_run]" if dry_run else ""),
                        graph_left_kind=lk,
                        graph_left_id=int(li),
                        graph_right_kind=rk,
                        graph_right_id=int(ri),
                        status="dry_run" if dry_run else "pending",
                        metadata={"link_role": role},
                    )
                    stats["queued"] += 1
                    continue
                try:
                    from services.graph_connection_queue_service import break_graph_connection_link

                    ok = break_graph_connection_link(
                        left_kind=str(lk),
                        left_id=int(li),
                        right_kind=str(rk),
                        right_id=int(ri),
                        link_role=str(role or "associated"),
                        reason=rationale,
                        quarantine=True,
                        domain_key=domain_key,
                    )
                    if ok:
                        stats["graph_quarantined"] += 1
                        _enqueue_action(
                            cur,
                            domain_key=domain_key,
                            storyline_id=storyline_id,
                            action="quarantine_graph",
                            fit_score=float(conf),
                            rationale=rationale,
                            graph_left_kind=lk,
                            graph_left_id=int(li),
                            graph_right_kind=rk,
                            graph_right_id=int(ri),
                            status="applied",
                        )
                except Exception as e:
                    logger.debug("membership graph quarantine: %s", e)
                    stats["errors"] += 1

            # SEI: demote core flags for entities not in core set / low mentions
            cur.execute(
                f"""
                SELECT entity_name, COALESCE(mention_count, 0), COALESCE(is_core_entity, false)
                FROM {schema}.story_entity_index
                WHERE storyline_id = %s AND COALESCE(is_core_entity, false) = true
                """,
                (storyline_id,),
            )
            for ename, mcount, _is_core in cur.fetchall():
                name_l = (ename or "").strip().lower()
                if not name_l:
                    continue
                if name_l in core_entities and int(mcount or 0) >= 3:
                    continue
                rationale = f"demote SEI core entity mentions={mcount}"
                if not auto_apply:
                    _enqueue_action(
                        cur,
                        domain_key=domain_key,
                        storyline_id=storyline_id,
                        action="demote_entity",
                        fit_score=None,
                        rationale=rationale + (" [dry_run]" if dry_run else ""),
                        entity_name=ename,
                        status="dry_run" if dry_run else "pending",
                    )
                    stats["queued"] += 1
                    continue
                cur.execute(
                    f"""
                    UPDATE {schema}.story_entity_index
                    SET is_core_entity = false
                    WHERE storyline_id = %s AND entity_name = %s AND is_core_entity = true
                    """,
                    (storyline_id, ename),
                )
                if cur.rowcount:
                    stats["sei_demoted"] += 1
                    _enqueue_action(
                        cur,
                        domain_key=domain_key,
                        storyline_id=storyline_id,
                        action="demote_entity",
                        fit_score=None,
                        rationale=rationale,
                        entity_name=ename,
                        status="applied",
                    )

            # Tracked events weakly linked to this storyline
            storyline_ref = f"{schema}:{storyline_id}"
            try:
                from config.settings import event_tracking_storyline_min_entity_overlap

                min_ov = event_tracking_storyline_min_entity_overlap()
            except Exception:
                min_ov = 3
            cur.execute(
                """
                SELECT id, COALESCE(key_participant_entity_ids, '[]'::jsonb)
                FROM intelligence.tracked_events
                WHERE storyline_id = %s
                LIMIT 50
                """,
                (storyline_ref,),
            )
            for te_id, profile_ids_json in cur.fetchall():
                try:
                    profile_ids = (
                        json.loads(profile_ids_json)
                        if isinstance(profile_ids_json, str)
                        else (profile_ids_json or [])
                    )
                    profile_ids = [int(x) for x in profile_ids if isinstance(x, (int, float))]
                except Exception:
                    profile_ids = []
                overlap = 0
                if profile_ids and core_entities:
                    cur.execute(
                        """
                        SELECT COUNT(DISTINCT lower(COALESCE(metadata->>'canonical_name', '')))
                        FROM intelligence.entity_profiles
                        WHERE id = ANY(%s)
                          AND lower(COALESCE(metadata->>'canonical_name', '')) = ANY(%s)
                        """,
                        (profile_ids, list(core_entities)),
                    )
                    overlap = int(cur.fetchone()[0] or 0)
                if overlap >= min_ov:
                    continue
                rationale = f"tracked_event overlap={overlap} < {min_ov}"
                if not auto_apply:
                    _enqueue_action(
                        cur,
                        domain_key=domain_key,
                        storyline_id=storyline_id,
                        action="unlink_tracked_event",
                        fit_score=float(overlap),
                        rationale=rationale + (" [dry_run]" if dry_run else ""),
                        tracked_event_id=int(te_id),
                        status="dry_run" if dry_run else "pending",
                    )
                    stats["queued"] += 1
                    continue
                cur.execute(
                    """
                    UPDATE intelligence.tracked_events
                    SET storyline_id = NULL, updated_at = NOW()
                    WHERE id = %s AND storyline_id = %s
                    """,
                    (int(te_id), storyline_ref),
                )
                if cur.rowcount:
                    stats["tracked_events_unlinked"] += 1
                    _enqueue_action(
                        cur,
                        domain_key=domain_key,
                        storyline_id=storyline_id,
                        action="unlink_tracked_event",
                        fit_score=float(overlap),
                        rationale=rationale,
                        tracked_event_id=int(te_id),
                        status="applied",
                    )

        # Mark outside the main `with conn.cursor()` block — that cursor is closed.
        # Open a fresh cursor so review_state persists (otherwise megas re-queue forever).
        try:
            with conn.cursor() as mark_cur:
                stats["membership_fingerprint"] = _mark_storyline_reviewed(
                    mark_cur,
                    domain_key=domain_key,
                    storyline_id=storyline_id,
                    schema=schema,
                )
        except Exception as mark_e:
            logger.warning("membership review_state mark: %s", mark_e)

        conn.commit()
    except Exception as e:
        logger.exception("review_storyline_membership: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        stats["errors"] += 1
        stats["error"] = str(e)[:300]
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return stats


def _pick_storylines(domain_key: str, limit: int) -> list[int]:
    """Pick megas never reviewed, or whose membership fingerprint drifted since last pass."""
    schema = resolve_domain_schema(domain_key)
    min_arts = _min_article_count_for_review()
    where = membership_needs_review_where_sql(schema, "s")
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id
                FROM {schema}.storylines s
                LEFT JOIN intelligence.storyline_membership_review_state r
                  ON r.domain_key = %s AND r.storyline_id = s.id
                WHERE {where}
                ORDER BY s.article_count DESC NULLS LAST, s.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (domain_key, min_arts, limit),
            )
            return [int(r[0]) for r in cur.fetchall()]
    except Exception as e:
        logger.debug("_pick_storylines %s: %s", domain_key, e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def expire_pending_dry_run_membership_actions() -> dict[str, int]:
    """
    Reclassify dry-run rows that were incorrectly stored as status=pending.

    Safe: does not apply unlinks/demotes. Clears Monitor queue_depth while
    retaining audit rows (status=dry_run) so storyline pick/backlog still
    treats those megas as recently reviewed.
    """
    conn = get_db_connection()
    if not conn:
        return {"updated": 0, "error": 1}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.storyline_membership_actions
                SET status = 'dry_run',
                    resolved_at = COALESCE(resolved_at, NOW())
                WHERE status = 'pending'
                  AND (
                    rationale ILIKE %s
                    OR COALESCE(metadata->>'dry_run', '') IN ('1', 'true', 'True')
                  )
                """,
                ("%[dry_run]%",),
            )
            updated = int(cur.rowcount or 0)
        conn.commit()
        return {"updated": updated}
    except Exception as e:
        logger.warning("expire_pending_dry_run_membership_actions: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"updated": 0, "error": 1}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_storyline_membership_review_for_domain(
    domain_key: str,
    *,
    limit: int | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    lim = limit if limit is not None else _max_storylines()
    ids = _pick_storylines(domain_key, lim)
    out: dict[str, Any] = {
        "domain_key": domain_key,
        "storylines": [],
        "totals": {
            "unlinked": 0,
            "demoted": 0,
            "queued": 0,
            "graph_quarantined": 0,
            "sei_demoted": 0,
            "tracked_events_unlinked": 0,
        },
    }
    for sid in ids:
        st = review_storyline_membership(domain_key, sid, dry_run=dry_run)
        out["storylines"].append(st)
        for k in out["totals"]:
            out["totals"][k] += int(st.get(k, 0) or 0)
    return out


def run_storyline_membership_review_all_domains(
    *,
    limit_per_domain: int | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    by_domain = {}
    totals = {
        "unlinked": 0,
        "demoted": 0,
        "queued": 0,
        "graph_quarantined": 0,
        "sei_demoted": 0,
        "tracked_events_unlinked": 0,
        "skipped_chemistry_kind": 0,
    }
    from services.domain_synthesis_config import get_domain_synthesis_config
    from shared.domain_processing_mode import filter_domains_for_phase

    for dk in filter_domains_for_phase(
        get_pipeline_active_domain_keys(), "storyline_membership_review"
    ):
        cfg = get_domain_synthesis_config(dk)
        # Chemistry kinds normally use soft membership — but oversize evidence
        # threads (kitchen-sink megas) must still be pruned.
        skip_chemistry = (
            cfg.is_chemistry_kind() and not cfg.link_score_profile.aggressive_membership
        )
        if skip_chemistry:
            try:
                from shared.domain_registry import resolve_domain_schema
                from shared.database.connection import get_db_connection

                schema = resolve_domain_schema(dk)
                conn = get_db_connection()
                oversize = False
                if conn and schema:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT 1 FROM {schema}.storylines
                            WHERE merged_into_id IS NULL
                              AND COALESCE(article_count, 0) > %s
                            LIMIT 1
                            """,
                            (
                                int(
                                    cfg.link_score_profile.max_member_articles
                                    or 48
                                ),
                            ),
                        )
                        oversize = cur.fetchone() is not None
                    try:
                        conn.close()
                    except Exception:
                        pass
                if not oversize:
                    by_domain[dk] = {
                        "skipped": True,
                        "reason": f"story_kind={cfg.story_kind}_soft_membership",
                    }
                    totals["skipped_chemistry_kind"] += 1
                    continue
                # Fall through: prune oversize chemistry proteins
            except Exception:
                by_domain[dk] = {
                    "skipped": True,
                    "reason": f"story_kind={cfg.story_kind}_soft_membership",
                }
                totals["skipped_chemistry_kind"] += 1
                continue
        res = run_storyline_membership_review_for_domain(
            dk, limit=limit_per_domain, dry_run=dry_run
        )
        by_domain[dk] = res
        for k in totals:
            if k == "skipped_chemistry_kind":
                continue
            totals[k] += int((res.get("totals") or {}).get(k, 0) or 0)
    return {"by_domain": by_domain, "totals": totals}


def list_membership_actions(
    domain_key: str,
    *,
    status: str = "pending",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    conn = get_db_connection()
    if not conn:
        return {"items": [], "total": 0}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.storyline_membership_actions
                WHERE domain_key = %s AND status = %s
                """,
                (domain_key, status),
            )
            total = int(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT id, storyline_id, article_id, entity_name, tracked_event_id,
                       action, fit_score, status, rationale, created_at,
                       graph_left_kind, graph_left_id, graph_right_kind, graph_right_id
                FROM intelligence.storyline_membership_actions
                WHERE domain_key = %s AND status = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (domain_key, status, limit, offset),
            )
            items = []
            for r in cur.fetchall():
                items.append(
                    {
                        "id": int(r[0]),
                        "storyline_id": int(r[1]),
                        "article_id": int(r[2]) if r[2] is not None else None,
                        "entity_name": r[3],
                        "tracked_event_id": int(r[4]) if r[4] is not None else None,
                        "action": r[5],
                        "fit_score": float(r[6]) if r[6] is not None else None,
                        "status": r[7],
                        "rationale": r[8],
                        "created_at": r[9].isoformat() if r[9] else None,
                        "graph": {
                            "left_kind": r[10],
                            "left_id": int(r[11]) if r[11] is not None else None,
                            "right_kind": r[12],
                            "right_id": int(r[13]) if r[13] is not None else None,
                        },
                    }
                )
        return {"items": items, "total": total}
    except Exception as e:
        logger.warning("list_membership_actions: %s", e)
        return {"items": [], "total": 0, "error": str(e)[:200]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def apply_membership_action(action_id: int, *, approve: bool) -> dict[str, Any]:
    """Approve (apply) or reject a pending membership action."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db_connection"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, storyline_id, article_id, entity_name, tracked_event_id,
                       action, graph_left_kind, graph_left_id, graph_right_kind, graph_right_id,
                       status, rationale
                FROM intelligence.storyline_membership_actions
                WHERE id = %s
                FOR UPDATE
                """,
                (action_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"success": False, "error": "not_found"}
            if row[11] != "pending":
                return {"success": False, "error": f"not_pending:{row[11]}"}
            (
                _id,
                domain_key,
                storyline_id,
                article_id,
                entity_name,
                tracked_event_id,
                action,
                glk,
                gli,
                grk,
                gri,
                _status,
                rationale,
            ) = row
            schema = resolve_domain_schema(domain_key)

            if not approve:
                cur.execute(
                    """
                    UPDATE intelligence.storyline_membership_actions
                    SET status = 'rejected', resolved_at = NOW()
                    WHERE id = %s
                    """,
                    (action_id,),
                )
                conn.commit()
                return {"success": True, "status": "rejected"}

            applied = False
            if action == "unlink" and article_id is not None:
                applied = _unlink_article(cur, schema, int(storyline_id), int(article_id))
            elif action == "demote_relevance" and article_id is not None:
                applied = _demote_relevance(
                    cur, schema, int(storyline_id), int(article_id), _demote_cap()
                )
            elif action == "demote_entity" and entity_name:
                cur.execute(
                    f"""
                    UPDATE {schema}.story_entity_index
                    SET is_core_entity = false
                    WHERE storyline_id = %s AND entity_name = %s
                    """,
                    (int(storyline_id), entity_name),
                )
                applied = cur.rowcount > 0
            elif action == "unlink_tracked_event" and tracked_event_id is not None:
                ref = f"{schema}:{int(storyline_id)}"
                cur.execute(
                    """
                    UPDATE intelligence.tracked_events
                    SET storyline_id = NULL, updated_at = NOW()
                    WHERE id = %s AND storyline_id = %s
                    """,
                    (int(tracked_event_id), ref),
                )
                applied = cur.rowcount > 0
            elif action == "quarantine_graph" and glk and grk and gli is not None and gri is not None:
                from services.graph_connection_queue_service import break_graph_connection_link

                applied = break_graph_connection_link(
                    left_kind=str(glk),
                    left_id=int(gli),
                    right_kind=str(grk),
                    right_id=int(gri),
                    reason=rationale or "membership_review_approve",
                    quarantine=True,
                    domain_key=domain_key,
                )
            else:
                cur.execute(
                    """
                    UPDATE intelligence.storyline_membership_actions
                    SET status = 'skipped', resolved_at = NOW()
                    WHERE id = %s
                    """,
                    (action_id,),
                )
                conn.commit()
                return {"success": False, "error": "unsupported_action", "action": action}

            cur.execute(
                """
                UPDATE intelligence.storyline_membership_actions
                SET status = %s, resolved_at = NOW()
                WHERE id = %s
                """,
                ("applied" if applied else "skipped", action_id),
            )
            # Keep review fingerprint aligned with post-apply membership (same SSOT as drain).
            if applied:
                try:
                    _mark_storyline_reviewed(
                        cur,
                        domain_key=str(domain_key),
                        storyline_id=int(storyline_id),
                        schema=schema,
                    )
                except Exception as mark_e:
                    logger.warning(
                        "apply_membership_action review_state mark id=%s: %s",
                        action_id,
                        mark_e,
                    )
            conn.commit()
            return {"success": True, "status": "applied" if applied else "skipped"}
    except Exception as e:
        logger.exception("apply_membership_action: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:300]}
    finally:
        try:
            conn.close()
        except Exception:
            pass
