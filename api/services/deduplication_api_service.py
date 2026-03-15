"""
Deduplication API backend (P3): consolidate_articles, merge_claims.
"""

import logging
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def consolidate_articles(
    domain: Optional[str] = None,
    limit: int = 50,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """
    Run article consolidation (merge duplicates). Uses ArticleDeduplicationSystem when available.
    Returns merged count and clusters.
    """
    try:
        from scripts.article_deduplication import ArticleDeduplicationSystem
        dedup = ArticleDeduplicationSystem()
        if not dedup.connect_database():
            return {"success": False, "merged": 0, "clusters": [], "error": "Database connection failed"}
        try:
            report = dedup.generate_deduplication_report()
            url_dups = report.get("url_duplicates", [])[:limit]
            if not url_dups:
                return {"success": True, "merged": 0, "clusters": [], "dry_run": dry_run}
            merge_results = dedup.merge_duplicates(url_dups, dry_run=dry_run)
            merged = merge_results.get("total_processed", 0)
            clusters = merge_results.get("merged", [])
            return {"success": True, "merged": merged, "clusters": clusters, "dry_run": dry_run}
        finally:
            dedup.close_connection()
    except Exception as e:
        logger.warning("consolidate_articles: %s", e)
        return {"success": False, "merged": 0, "clusters": [], "error": str(e)}


def merge_claims(
    claim_ids: Optional[List[int]] = None,
    similarity_threshold: float = 0.9,
) -> Dict[str, Any]:
    """
    Record claim merges: first claim in list is canonical; others are merged into it.
    Persists to intelligence.claim_merges.
    """
    if not claim_ids or len(claim_ids) < 2:
        return {"success": True, "merged": 0, "unified_claim_ids": claim_ids or []}
    canonical = claim_ids[0]
    merged_ids = claim_ids[1:]
    conn = get_db_connection()
    if not conn:
        return {"success": False, "merged": 0, "unified_claim_ids": [], "error": "Database unavailable"}
    inserted = 0
    try:
        with conn.cursor() as cur:
            for mid in merged_ids:
                if mid == canonical:
                    continue
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.claim_merges (canonical_claim_id, merged_claim_id)
                        VALUES (%s, %s)
                        ON CONFLICT (merged_claim_id) DO NOTHING
                        """,
                        (canonical, mid),
                    )
                    if cur.rowcount:
                        inserted += 1
                except Exception as e:
                    if "does not exist" in str(e).lower():
                        break
                    logger.debug("merge_claims insert: %s", e)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning("merge_claims: %s", e)
        return {"success": False, "merged": 0, "unified_claim_ids": [], "error": str(e)}
    finally:
        conn.close()
    return {"success": True, "merged": inserted, "unified_claim_ids": [canonical]}
