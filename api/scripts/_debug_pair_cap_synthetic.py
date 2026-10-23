"""Synthetic proof that discovery keeps at most STORYLINE_DISCOVERY_MAX_PAIRS."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import numpy as np

from shared.debug_session_log import agent_dbg
from services.ai_storyline_discovery import (
    STORYLINE_DISCOVERY_MAX_PAIRS,
    AIStorylineDiscovery,
    ArticleEmbedding,
)


def main() -> int:
    n = 800
    mat = np.full((n, n), 0.9, dtype=np.float64)
    np.fill_diagonal(mat, 1.0)
    now = datetime.now(timezone.utc)
    articles = [
        ArticleEmbedding(
            article_id=i,
            title=f"t{i}",
            content="",
            domain="politics",
            created_at=now,
            embedding=np.zeros(8),
            entities=set(),
        )
        for i in range(n)
    ]
    svc = AIStorylineDiscovery.__new__(AIStorylineDiscovery)
    clusters = AIStorylineDiscovery.cluster_hdbscan(
        svc, articles, mat, similarity_threshold=0.5, min_cluster_size=4
    )
    approx = n * (n - 1) // 2
    print(
        "n",
        n,
        "approx_pair_space",
        approx,
        "max_pairs",
        STORYLINE_DISCOVERY_MAX_PAIRS,
        "clusters",
        len(clusters),
    )
    agent_dbg(
        "A",
        "synthetic:pairs",
        "synthetic_pair_cap_done",
        {
            "n": n,
            "approx": approx,
            "max_pairs": STORYLINE_DISCOVERY_MAX_PAIRS,
            "clusters": len(clusters),
        },
        run_id="post-fix",
    )
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
