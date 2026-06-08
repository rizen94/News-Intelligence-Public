"""Discovery storyline INSERT aligned to silo DDL."""

from __future__ import annotations

import json
import os
import uuid

import pytest

from datetime import datetime, timezone

import numpy as np

from services.ai_storyline_discovery import ArticleEmbedding, StorylineCluster, get_discovery_service

_NOW = datetime.now(timezone.utc)


def _db_available() -> bool:
    if os.environ.get("SKIP_DB_TESTS", "").strip() in ("1", "true", "yes"):
        return False
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="database not available")
def test_save_storyline_suggestion_medicine_schema():
    discovery = get_discovery_service()
    title = f"pytest discovery save {uuid.uuid4().hex[:8]}"
    cluster = StorylineCluster(
        cluster_id=1,
        articles=[
            ArticleEmbedding(
                article_id=0,
                title="placeholder",
                content="",
                domain="medicine",
                embedding=np.zeros(8),
                entities=set(),
                created_at=_NOW,
            )
        ],
        centroid=np.zeros(8),
        avg_similarity=0.8,
        is_breaking_news=False,
        suggested_title=title,
        suggested_description="pytest storyline discovery insert",
        importance_score=0.42,
    )
    storyline_id = discovery.save_storyline_suggestion(cluster, "medicine")
    assert storyline_id is not None

    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT quality_score, metadata->>'source', metadata->>'importance_score'
                FROM medicine.storylines WHERE id = %s
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert float(row[0]) == pytest.approx(0.42)
            assert row[1] == "storyline_discovery"
            assert float(row[2]) == pytest.approx(0.42)
            cur.execute("DELETE FROM medicine.storylines WHERE id = %s", (storyline_id,))
        conn.commit()


def test_cluster_matches_existing_by_article_overlap():
    discovery = get_discovery_service()
    cluster = StorylineCluster(
        cluster_id=1,
        articles=[
            ArticleEmbedding(
                article_id=101,
                title="a",
                content="",
                domain="medicine",
                embedding=None,
                entities=set(),
                created_at=_NOW,
            ),
            ArticleEmbedding(
                article_id=102,
                title="b",
                content="",
                domain="medicine",
                embedding=None,
                entities=set(),
                created_at=_NOW,
            ),
        ],
        centroid=np.zeros(8),
        avg_similarity=0.5,
        is_breaking_news=False,
        suggested_title="Unrelated headline",
    )
    existing = [{"id": 55, "title": "Other", "entity_names": [], "topic_ids": [], "article_ids": [101, 102]}]
    assert discovery._cluster_matches_existing(cluster, existing) == 55
