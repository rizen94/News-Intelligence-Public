"""One-shot: exercise discovery n/pair caps (debug session fb1ed2)."""
from __future__ import annotations

import sys

from shared.debug_session_log import agent_dbg
from services.ai_storyline_discovery import (
    STORYLINE_DISCOVERY_CLUSTERING_MAX_N,
    STORYLINE_DISCOVERY_MAX_PAIRS,
    assembly_discovery_article_cap,
    get_discovery_service,
)


def main() -> int:
    print("clustering_max_n", STORYLINE_DISCOVERY_CLUSTERING_MAX_N)
    print("max_pairs", STORYLINE_DISCOVERY_MAX_PAIRS)
    print("assembly_cap", assembly_discovery_article_cap())
    agent_dbg(
        "A",
        "smoke:start",
        "discovery_smoke_begin",
        {
            "cap": assembly_discovery_article_cap(),
            "clustering_max_n": STORYLINE_DISCOVERY_CLUSTERING_MAX_N,
            "max_pairs": STORYLINE_DISCOVERY_MAX_PAIRS,
        },
        run_id="post-fix",
    )
    svc = get_discovery_service()
    result = svc.discover_storylines(
        domain="politics",
        hours=None,
        save_to_db=False,
        article_limit=assembly_discovery_article_cap(),
    )
    stats = result.get("stats") or {}
    fetch = (stats.get("phases") or {}).get("fetch_articles") or {}
    print("fetch_phase", fetch)
    print("clusters", (result.get("summary") or {}).get("clusters_found"))
    agent_dbg(
        "A",
        "smoke:done",
        "discovery_smoke_done",
        {"fetch": fetch},
        run_id="post-fix",
    )
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
