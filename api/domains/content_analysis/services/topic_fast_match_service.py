"""
Fast topic matching — assign articles to existing topic_clusters without LLM.

Uses title tokens, article entities, and keyword/trgm cluster lookup.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from config.settings import topic_fast_match_min_score
from shared.topic_cluster_store import assign_topics_to_clusters, find_cluster_candidates

logger = logging.getLogger(__name__)


@dataclass
class FastMatchResult:
    assignments: list[dict[str, Any]]
    method: str
    top_score: float


def _title_tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", (title or "").lower()) if len(w) >= 3}


def _topic_keywords_table_exists(cur, schema: str) -> bool:
    try:
        cur.execute("SELECT to_regclass(%s)", (f"{schema}.topic_keywords",))
        return cur.fetchone()[0] is not None
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return False


def _load_article_context(cur, schema: str, article_id: int) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT a.id, a.title, a.content, a.excerpt
        FROM {schema}.articles a
        WHERE a.id = %s
        """,
        (article_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    entities: list[str] = []
    try:
        cur.execute(
            f"""
            SELECT ec.canonical_name
            FROM {schema}.article_entities ae
            JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
            WHERE ae.article_id = %s
            LIMIT 30
            """,
            (article_id,),
        )
        entities = [r[0] for r in cur.fetchall() if r and r[0]]
    except Exception as e:
        logger.debug("fast_match entities %s: %s", article_id, e)
        try:
            cur.connection.rollback()
        except Exception:
            pass
    return {
        "id": row[0],
        "title": row[1] or "",
        "content": row[2] or row[3] or "",
        "entities": entities,
    }


def try_fast_match(cur, schema: str, article_id: int) -> FastMatchResult | None:
    """
    Attempt to link article to 1–3 existing clusters without LLM.
    Returns None when no match meets TOPIC_FAST_MATCH_MIN_SCORE.
    """
    from domains.content_analysis.services.topic_merge_suggestions import (
        _compute_similarity,
        find_best_matching_topic,
    )

    ctx = _load_article_context(cur, schema, article_id)
    if not ctx:
        return None

    min_score = topic_fast_match_min_score()
    title = ctx["title"]
    tokens = _title_tokens(title)
    content_preview = (ctx["content"] or "")[:500]
    entities = ctx["entities"] or []

    scored: dict[int, tuple[str, float, str]] = {}

    # Keyword index hit from title tokens
    if tokens and _topic_keywords_table_exists(cur, schema):
        try:
            cur.execute(
                f"""
                SELECT tk.topic_cluster_id, tc.cluster_name, COUNT(*)::int AS hits
                FROM {schema}.topic_keywords tk
                JOIN {schema}.topic_clusters tc ON tc.id = tk.topic_cluster_id
                WHERE lower(tk.keyword) = ANY(%s)
                GROUP BY tk.topic_cluster_id, tc.cluster_name
                ORDER BY hits DESC
                LIMIT 15
                """,
                (list(tokens),),
            )
            for cid, cname, hits in cur.fetchall():
                score = min(1.0, 0.45 + 0.08 * int(hits))
                if score >= min_score:
                    scored[int(cid)] = (cname, score, "keyword_overlap")
        except Exception as e:
            logger.debug("fast_match keywords: %s", e)
            try:
                cur.connection.rollback()
            except Exception:
                pass

    # Entity overlap against cluster names
    for ent in entities[:12]:
        ent = (ent or "").strip()
        if len(ent) < 3:
            continue
        candidates = find_cluster_candidates(cur, schema, ent, limit=50)
        best = find_best_matching_topic(ent, [], candidates, min_score=min_score)
        if best:
            cid, cname, sim = best
            prev = scored.get(cid)
            if not prev or sim > prev[1]:
                scored[cid] = (cname, sim, "entity_overlap")

    # Title vs cluster name similarity
    if title.strip():
        candidates = find_cluster_candidates(cur, schema, title, limit=80)
        best = find_best_matching_topic(title, list(tokens), candidates, min_score=min_score)
        if best:
            cid, cname, sim = best
            prev = scored.get(cid)
            if not prev or sim > prev[1]:
                scored[cid] = (cname, sim, "title_similarity")

    # Content token overlap (lightweight)
    if content_preview and scored:
        for cid, (cname, _score, _method) in list(scored.items()):
            sim, _ = _compute_similarity(cname, [], content_preview[:200], [])
            if sim >= min_score:
                prev = scored.get(cid)
                if not prev or sim > prev[1]:
                    scored[cid] = (cname, sim, "content_overlap")

    if not scored:
        return None

    ranked = sorted(scored.items(), key=lambda x: x[1][1], reverse=True)[:3]
    assignments = [
        {
            "name": cname,
            "cluster_id": cid,
            "confidence": round(score, 3),
            "assignment_method": method,
            "keywords": [],
        }
        for cid, (cname, score, method) in ranked
        if score >= min_score
    ]
    if not assignments:
        return None

    top_score = ranked[0][1][1]
    return FastMatchResult(
        assignments=assignments,
        method=ranked[0][1][2],
        top_score=top_score,
    )


def apply_fast_match(cur, schema: str, article_id: int) -> dict[str, Any] | None:
    """Run fast match and persist cluster assignments. Returns assign result or None."""
    cur.execute("SAVEPOINT topic_fast_match")
    try:
        result = try_fast_match(cur, schema, article_id)
        if not result or not result.assignments:
            cur.execute("ROLLBACK TO SAVEPOINT topic_fast_match")
            return None
        out = assign_topics_to_clusters(cur, schema, article_id, result.assignments)
        cur.execute("RELEASE SAVEPOINT topic_fast_match")
        return out
    except Exception as e:
        logger.debug("apply_fast_match %s: %s", article_id, e)
        try:
            cur.execute("ROLLBACK TO SAVEPOINT topic_fast_match")
        except Exception:
            try:
                cur.connection.rollback()
            except Exception:
                pass
        return None
