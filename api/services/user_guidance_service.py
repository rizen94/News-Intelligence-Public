"""
User guidance for orchestration — watchlist and automation-enabled storylines.
Feeds ProcessingGovernor and importance scoring so the loop prioritizes user-relevant work.
"""

import logging
from datetime import datetime, timezone
from typing import Any

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("orchestrator")
except Exception:
    logger = logging.getLogger(__name__)

def get_user_guidance(get_db_connection) -> dict[str, Any]:
    """
    Load watchlist storyline IDs and automation-enabled storylines from all domains.
    Returns dict: watchlist_storyline_ids (list of (domain, storyline_id)),
                  automation_storylines (list of {id, domain, last_automation_run, automation_mode, ...}).
    """
    out: dict[str, Any] = {
        "watchlist_storyline_ids": [],  # [(domain, storyline_id), ...]
        "automation_storylines": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    conn = get_db_connection()
    if not conn:
        return out
    try:
        from shared.domain_registry import url_schema_pairs

        cur = conn.cursor()
        for domain, schema in url_schema_pairs():
            # Watchlist: storyline_id per domain (watchlist lives in same schema as storylines)
            try:
                cur.execute(f"""
                    SELECT w.storyline_id FROM {schema}.watchlist w
                    INNER JOIN {schema}.storylines s ON s.id = w.storyline_id
                """)
                for row in cur.fetchall():
                    out["watchlist_storyline_ids"].append((domain, row[0]))
            except Exception as e:
                logger.debug("user_guidance watchlist %s: %s", domain, e)
            # Automation-enabled storylines
            try:
                cur.execute(f"""
                    SELECT id, title, automation_enabled, automation_mode,
                           last_automation_run, automation_frequency_hours
                    FROM {schema}.storylines
                    WHERE automation_enabled = true
                    ORDER BY last_automation_run ASC NULLS FIRST
                """)
                for row in cur.fetchall():
                    out["automation_storylines"].append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "domain": domain,
                            "automation_enabled": row[2],
                            "automation_mode": row[3],
                            "last_automation_run": row[4].isoformat() if row[4] else None,
                            "automation_frequency_hours": row[5] or 24,
                        }
                    )
            except Exception as e:
                logger.debug("user_guidance automation storylines %s: %s", domain, e)
        cur.close()
    finally:
        conn.close()
    return out


def compute_storyline_importance(
    storyline_id: int,
    domain: str,
    *,
    watchlist_ids: list[tuple[str, int]] | None = None,
    automation_storylines: list[dict] | None = None,
) -> float:
    """
    Return importance score in [0.0, 1.0] for a storyline.
    watchlist_ids: list of (domain, storyline_id) from get_user_guidance.
    automation_storylines: list from get_user_guidance["automation_storylines"].
    """
    score = 0.0
    watchlist_ids = watchlist_ids or []
    automation_storylines = automation_storylines or []
    key = (domain, storyline_id)
    if key in watchlist_ids:
        score = max(score, 0.9)
    for s in automation_storylines:
        if s.get("domain") == domain and s.get("id") == storyline_id:
            if s.get("automation_mode") == "auto_approve":
                score = max(score, 0.7)
            else:
                score = max(score, 0.5)
            break
    return min(1.0, score)
