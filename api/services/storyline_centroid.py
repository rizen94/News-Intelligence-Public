"""
Shared storyline centroid helper (consolidation / collision / discovery).

Computes a mean article embedding when available; falls back to None.
Phase 6 C8: optional trailing-window dual centroid when STORYLINE_DUAL_CENTROID_ENABLED.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.runtime import env_bool, env_int

logger = logging.getLogger(__name__)


def dual_centroid_enabled() -> bool:
    try:
        from config.feature_registry import is_feature_enabled

        if is_feature_enabled("storyline_dual_centroid", default=False):
            return True
    except Exception:
        pass
    return env_bool("STORYLINE_DUAL_CENTROID_ENABLED", False)


def trailing_window_days() -> int:
    return max(3, env_int("STORYLINE_TRAILING_CENTROID_DAYS", 14))


def get_storyline_centroid(
    schema: str,
    storyline_id: int,
    *,
    conn=None,
    limit_articles: int = 40,
    trailing_days: int | None = None,
) -> list[float] | None:
    """
    Return L2-normalized mean embedding for a storyline, or None.

    Prefer ``articles.embedding_vector``; optional future ``storylines.centroid_embedding``.
    When ``trailing_days`` is set, only articles from the last N days are averaged.
    """
    owns_conn = False
    if conn is None:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        owns_conn = True
        if not conn:
            return None
    try:
        cur = conn.cursor()
        try:
            # Full-history persisted centroid only when not trailing
            if trailing_days is None:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = 'storylines'
                          AND column_name = 'centroid_embedding'
                    )
                    """,
                    (schema,),
                )
                if cur.fetchone()[0]:
                    cur.execute(
                        f"""
                        SELECT centroid_embedding FROM {schema}.storylines
                        WHERE id = %s AND centroid_embedding IS NOT NULL
                        """,
                        (storyline_id,),
                    )
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        vec = row[0]
                        if isinstance(vec, str):
                            try:
                                vec = json.loads(vec)
                            except Exception:
                                vec = None
                        if isinstance(vec, (list, tuple)) and vec:
                            return _l2_normalize([float(x) for x in vec])

            if trailing_days is not None:
                cur.execute(
                    f"""
                    SELECT a.embedding_vector
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s AND a.embedding_vector IS NOT NULL
                      AND COALESCE(a.published_at, a.created_at)
                          >= NOW() - (%s * INTERVAL '1 day')
                    ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
                    LIMIT %s
                    """,
                    (
                        storyline_id,
                        int(trailing_days),
                        max(1, min(int(limit_articles), 80)),
                    ),
                )
            else:
                cur.execute(
                    f"""
                    SELECT a.embedding_vector
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s AND a.embedding_vector IS NOT NULL
                    LIMIT %s
                    """,
                    (storyline_id, max(1, min(int(limit_articles), 80))),
                )
            vectors: list[list[float]] = []
            for (raw,) in cur.fetchall() or []:
                try:
                    if isinstance(raw, str):
                        emb = json.loads(raw)
                    elif isinstance(raw, (list, tuple)):
                        emb = list(raw)
                    else:
                        continue
                    if emb:
                        vectors.append([float(x) for x in emb])
                except Exception:
                    continue
            if not vectors:
                return None
            dim = len(vectors[0])
            mean = [0.0] * dim
            for v in vectors:
                if len(v) != dim:
                    continue
                for i, x in enumerate(v):
                    mean[i] += x
            n = float(len(vectors))
            mean = [x / n for x in mean]
            return _l2_normalize(mean)
        finally:
            cur.close()
    except Exception as e:
        logger.debug("get_storyline_centroid %s/%s: %s", schema, storyline_id, e)
        return None
    finally:
        if owns_conn:
            try:
                conn.close()
            except Exception:
                pass


def get_dual_centroids(
    schema: str,
    storyline_id: int,
    *,
    conn=None,
    limit_articles: int = 40,
) -> dict[str, Any]:
    """
    Return ``full`` and optional ``trailing`` centroids.

    When dual-centroid flag is off, trailing is None and callers should use full only.
    """
    full = get_storyline_centroid(
        schema, storyline_id, conn=conn, limit_articles=limit_articles
    )
    trailing = None
    if dual_centroid_enabled():
        trailing = get_storyline_centroid(
            schema,
            storyline_id,
            conn=conn,
            limit_articles=limit_articles,
            trailing_days=trailing_window_days(),
        )
    return {"full": full, "trailing": trailing, "dual_enabled": dual_centroid_enabled()}


def matching_centroid(
    schema: str,
    storyline_id: int,
    *,
    conn=None,
    prefer_trailing: bool = True,
) -> list[float] | None:
    """Centroid to use in matching: trailing when dual flag on, else full."""
    dual = get_dual_centroids(schema, storyline_id, conn=conn)
    if dual.get("dual_enabled") and prefer_trailing and dual.get("trailing"):
        return dual["trailing"]
    return dual.get("full")


def centroid_cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = sum(x * x for x in vec) ** 0.5
    if norm <= 0:
        return vec
    return [x / norm for x in vec]
