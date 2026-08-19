#!/usr/bin/env python3
"""Re-project signed episodes onto hub_facet containers (tightened matcher)."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)
from services.container_projection_service import (  # noqa: E402
    project_episode_to_containers,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("reproject_hub_containers")


def main() -> int:
    total_proj = 0
    total_eps = 0
    by_domain: list[dict] = []
    for dk in get_pipeline_active_domain_keys():
        schema = resolve_domain_schema(dk)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.storylines
                    WHERE COALESCE(story_kind, '') <> 'container_index'
                      AND COALESCE(is_mega_storyline, FALSE) = FALSE
                      AND anchor_signature IS NOT NULL
                      AND status IN ('active', 'dormant', 'emerging')
                    ORDER BY id DESC
                    LIMIT 200
                    """
                )
                ids = [int(r[0]) for r in (cur.fetchall() or [])]
        projected = 0
        for eid in ids:
            total_eps += 1
            r = project_episode_to_containers(dk, eid, apply=True)
            n = len(r.get("projected") or [])
            projected += n
            total_proj += n
        by_domain.append(
            {"domain": dk, "episodes": len(ids), "projections": projected}
        )
        logger.info("[%s] episodes=%s projections=%s", dk, len(ids), projected)
    print(json.dumps({"episodes_scanned": total_eps, "projections": total_proj, "by_domain": by_domain}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
