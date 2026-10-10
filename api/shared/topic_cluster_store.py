"""SSOT writes and lookups for domain topic_clusters + article_topic_clusters."""

from __future__ import annotations

import logging
import re
from typing import Any

from psycopg2.extras import Json

logger = logging.getLogger(__name__)


def _rollback_safe(cur) -> None:
    conn = getattr(cur, "connection", None)
    if conn is None:
        return
    try:
        conn.rollback()
    except Exception:
        pass


def _rollback_to_savepoint(cur, name: str) -> None:
    try:
        cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
        cur.execute(f"RELEASE SAVEPOINT {name}")
    except Exception:
        _rollback_safe(cur)


def _pg_trgm_available(cur) -> bool:
    try:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm' LIMIT 1")
        return cur.fetchone() is not None
    except Exception:
        return False


def find_cluster_candidates(
    cur,
    schema: str,
    name: str,
    keywords: list[str] | None = None,
    *,
    limit: int = 400,
) -> list[tuple[int, str, Any]]:
    """Return (cluster_id, cluster_name, keywords_payload) for fuzzy matching."""
    name = (name or "").strip()
    if not name:
        return []
    rows: dict[int, tuple[int, str, Any]] = {}

    cur.execute(
        f"""
        SELECT id, cluster_name, NULL::jsonb
        FROM {schema}.topic_clusters
        WHERE cluster_name = %s OR lower(trim(cluster_name)) = lower(trim(%s))
        LIMIT 5
        """,
        (name, name),
    )
    for r in cur.fetchall():
        rows[int(r[0])] = (int(r[0]), r[1], r[2])

    words = [w for w in re.findall(r"[a-z0-9']+", name.lower()) if len(w) >= 3][:8]
    if words:
        if _pg_trgm_available(cur):
            cur.execute(
                f"""
                SELECT id, cluster_name, NULL::jsonb
                FROM {schema}.topic_clusters
                WHERE similarity(lower(cluster_name), lower(%s)) > 0.25
                ORDER BY similarity(lower(cluster_name), lower(%s)) DESC
                LIMIT %s
                """,
                (name, name, limit),
            )
        else:
            ors = " OR ".join(["lower(cluster_name) LIKE %s"] * len(words))
            params = tuple(f"%{w}%" for w in words) + (limit,)
            cur.execute(
                f"""
                SELECT id, cluster_name, NULL::jsonb
                FROM {schema}.topic_clusters
                WHERE {ors}
                LIMIT %s
                """,
                params,
            )
        for r in cur.fetchall():
            cid = int(r[0])
            if cid not in rows:
                rows[cid] = (cid, r[1], r[2])

    kw_list = [k for k in (keywords or []) if isinstance(k, str) and len(k.strip()) >= 2][:6]
    if kw_list:
        try:
            cur.execute("SAVEPOINT kw_lookup")
            cur.execute(
                f"""
                SELECT DISTINCT tc.id, tc.cluster_name, NULL::jsonb
                FROM {schema}.topic_keywords tk
                JOIN {schema}.topic_clusters tc ON tc.id = tk.topic_cluster_id
                WHERE lower(tk.keyword) = ANY(%s)
                LIMIT %s
                """,
                ([k.lower() for k in kw_list], limit),
            )
            for r in cur.fetchall():
                cid = int(r[0])
                if cid not in rows:
                    rows[cid] = (cid, r[1], r[2])
            cur.execute("RELEASE SAVEPOINT kw_lookup")
        except Exception as e:
            logger.debug("topic_keywords candidate lookup: %s", e)
            _rollback_to_savepoint(cur, "kw_lookup")

    return list(rows.values())[:limit]


def get_or_create_cluster(
    cur,
    schema: str,
    cluster_name: str,
    *,
    relevance_score: float = 0.5,
    min_match_score: float = 0.58,
    keywords: list[str] | None = None,
) -> tuple[int, str, bool]:
    """Return (cluster_id, canonical_name, created). Fuzzy-match before insert."""
    from domains.content_analysis.services.topic_merge_suggestions import find_best_matching_topic

    cluster_name = (cluster_name or "").strip()
    if not cluster_name:
        raise ValueError("cluster_name required")

    cur.execute(
        f"""
        SELECT id, cluster_name FROM {schema}.topic_clusters
        WHERE cluster_name = %s OR lower(trim(cluster_name)) = lower(trim(%s))
        LIMIT 1
        """,
        (cluster_name, cluster_name),
    )
    row = cur.fetchone()
    if row:
        return int(row[0]), row[1], False

    candidates = find_cluster_candidates(cur, schema, cluster_name, keywords)
    best = find_best_matching_topic(cluster_name, keywords, candidates, min_score=min_match_score)
    if best:
        cid, cname, _score = best
        return cid, cname, False

    cur.execute(
        f"""
        INSERT INTO {schema}.topic_clusters (cluster_name, relevance_score, article_count, created_at, updated_at)
        VALUES (%s, %s, 0, NOW(), NOW())
        RETURNING id, cluster_name
        """,
        (cluster_name, relevance_score),
    )
    row = cur.fetchone()
    return int(row[0]), row[1], True


def upsert_cluster_keywords(
    cur,
    schema: str,
    cluster_id: int,
    keywords: list[str],
    *,
    importance: float = 0.5,
) -> None:
    try:
        cur.execute("SAVEPOINT kw_table_check")
        cur.execute("SELECT to_regclass(%s)", (f"{schema}.topic_keywords",))
        if not cur.fetchone()[0]:
            cur.execute("RELEASE SAVEPOINT kw_table_check")
            return
        cur.execute("RELEASE SAVEPOINT kw_table_check")
    except Exception:
        _rollback_to_savepoint(cur, "kw_table_check")
        return
    for keyword in keywords:
        if not isinstance(keyword, str) or len(keyword.strip()) < 2:
            continue
        try:
            cur.execute("SAVEPOINT kw_upsert")
            cur.execute(
                f"""
                INSERT INTO {schema}.topic_keywords
                    (topic_cluster_id, keyword, keyword_type, frequency_count, importance_score, last_seen_at)
                VALUES (%s, %s, %s, 1, %s, NOW())
                ON CONFLICT (topic_cluster_id, keyword) DO UPDATE SET
                    frequency_count = {schema}.topic_keywords.frequency_count + 1,
                    importance_score = GREATEST({schema}.topic_keywords.importance_score, EXCLUDED.importance_score),
                    last_seen_at = NOW()
                """,
                (cluster_id, keyword.strip()[:120], "general", importance),
            )
            cur.execute("RELEASE SAVEPOINT kw_upsert")
        except Exception as e:
            logger.debug("upsert_cluster_keywords %s: %s", keyword, e)
            _rollback_to_savepoint(cur, "kw_upsert")


def upsert_cluster_assignment(
    cur,
    schema: str,
    article_id: int,
    cluster_id: int,
    *,
    confidence: float,
    relevance: float | None = None,
) -> None:
    rel = relevance if relevance is not None else confidence
    cur.execute(
        f"""
        INSERT INTO {schema}.article_topic_clusters
            (article_id, topic_cluster_id, relevance_score, confidence_score)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (article_id, topic_cluster_id) DO UPDATE SET
            relevance_score = GREATEST({schema}.article_topic_clusters.relevance_score, EXCLUDED.relevance_score),
            confidence_score = GREATEST({schema}.article_topic_clusters.confidence_score, EXCLUDED.confidence_score)
        """,
        (article_id, cluster_id, rel, confidence),
    )


def sync_cluster_article_count(cur, schema: str, cluster_id: int) -> None:
    cur.execute(
        f"""
        UPDATE {schema}.topic_clusters
        SET article_count = (
            SELECT COUNT(*)::int FROM {schema}.article_topic_clusters
            WHERE topic_cluster_id = %s
        ),
        updated_at = NOW()
        WHERE id = %s
        """,
        (cluster_id, cluster_id),
    )


def assign_topics_to_clusters(
    cur,
    schema: str,
    article_id: int,
    topics: list[dict[str, Any]],
    *,
    min_match_score: float = 0.58,
) -> dict[str, Any]:
    """Assign extracted or fast-lane topics to topic_clusters for one article."""
    from domains.content_analysis.services.topic_merge_suggestions import find_best_matching_topic

    assigned: list[dict[str, Any]] = []
    created: list[str] = []
    matched_similarity: list[dict[str, Any]] = []

    for idx, topic_data in enumerate(topics):
        topic_name = (topic_data.get("name") or topic_data.get("cluster_name") or "").strip()
        if not topic_name:
            continue
        sp = f"assign_topic_{idx}"
        try:
            cur.execute(f"SAVEPOINT {sp}")
            keywords_list = topic_data.get("keywords", [])
            if not isinstance(keywords_list, list):
                keywords_list = []
            confidence = float(topic_data.get("confidence", 0.5) or 0.5)
            assignment_method = topic_data.get("assignment_method", "auto")

            cluster_id: int | None = topic_data.get("cluster_id")
            canonical_name = topic_name
            was_created = False

            if cluster_id is not None:
                cur.execute(
                    f"SELECT id, cluster_name FROM {schema}.topic_clusters WHERE id = %s",
                    (int(cluster_id),),
                )
                row = cur.fetchone()
                if row:
                    cluster_id = int(row[0])
                    canonical_name = row[1]
            else:
                toks = re.findall(r"[a-z0-9']+", topic_name.lower())
                match_score = min_match_score
                if len(toks) == 1:
                    match_score = max(match_score, 0.72)
                candidates = find_cluster_candidates(cur, schema, topic_name, keywords_list)
                best = find_best_matching_topic(
                    topic_name, keywords_list, candidates, min_score=match_score
                )
                if best:
                    cluster_id, canonical_name, sim = best
                    assignment_method = "auto_similarity"
                    matched_similarity.append(
                        {"llm_name": topic_name, "canonical_name": canonical_name, "score": round(sim, 3)}
                    )
                else:
                    cluster_id, canonical_name, was_created = get_or_create_cluster(
                        cur,
                        schema,
                        topic_name,
                        relevance_score=confidence,
                        min_match_score=match_score,
                        keywords=keywords_list,
                    )
                    if was_created:
                        created.append(canonical_name)

            if cluster_id is None:
                cur.execute(f"RELEASE SAVEPOINT {sp}")
                continue

            upsert_cluster_assignment(
                cur, schema, article_id, int(cluster_id), confidence=confidence
            )
            if keywords_list:
                upsert_cluster_keywords(cur, schema, int(cluster_id), keywords_list, importance=confidence)
            sync_cluster_article_count(cur, schema, int(cluster_id))

            assigned.append(
                {
                    "cluster_id": int(cluster_id),
                    "topic_name": canonical_name,
                    "confidence": confidence,
                    "assignment_method": assignment_method,
                }
            )
            cur.execute(f"RELEASE SAVEPOINT {sp}")
        except Exception as e:
            _rollback_to_savepoint(cur, sp)
            logger.warning(
                "assign topic skipped for article %s (%s): %s",
                article_id,
                topic_name,
                e,
            )
            continue
    return {
        "success": True,
        "article_id": article_id,
        "assigned_topics": assigned,
        "created_topics": created,
        "matched_similarity": matched_similarity,
        "total_assigned": len(assigned),
    }
