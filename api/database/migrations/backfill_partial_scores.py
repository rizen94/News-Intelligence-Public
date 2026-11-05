#!/usr/bin/env python3
"""Backfill zeroed relevance/semantic/keyword scores from quality_score.

This migration fixes items that were inserted before the five-score pipeline existed,
where missing columns defaulted to 0.0 and never got updated because:
1. The INSERT path didn't populate them (pre-migration 251 era)
2. They pointed to article_ids that were later purged (orphans — these are skipped below)

Run once via:
    python api/database/migrations/backfill_partial_scores.py [--dry-run]

Then confirm counts with:
    SELECT COUNT(*) FROM public.storyline_article_suggestions
    WHERE status = 'pending' AND (relevance_score <= 0 OR semantic_score <= 0 OR keyword_score <= 0);
"""

import sys
import time

def run(dry_run: bool = True):
    from shared.database import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: No database connection")
        return

    try:
        with conn.cursor() as cur:
            # Phase 1: Count existing partial-scored items
            cur.execute(
                """
                SELECT COUNT(*) FROM public.storyline_article_suggestions
                WHERE status = 'pending'
                  AND combined_score IS NOT NULL
                  AND (relevance_score <= 0 OR semantic_score <= 0 OR keyword_score <= 0)
                """
            )
            total = int(cur.fetchone()[0])
            print(f"Found {total} partial-scored pending items")

            if total == 0:
                print("Nothing to backfill — all scores are present.")
                return

            # Phase 2: Find and backfill each item where quality_score > 0
            cur.execute(
                """
                SELECT id, domain_key, storyline_id, article_id, quality_score
                FROM public.storyline_article_suggestions
                WHERE status = 'pending'
                  AND combined_score IS NOT NULL
                  AND (relevance_score <= 0 OR semantic_score <= 0 OR keyword_score <= 0)
                  AND quality_score > 0
                ORDER BY suggested_at ASC
                """
            )
            rows = cur.fetchall()
            backfilled = 0
            errors = 0

            for row in rows:
                sid, domain_key, storyline_id, article_id, quality_score = row
                fill_value = round(quality_score, 2)

                try:
                    # First verify the article still exists in its schema
                    from shared.pipeline_context import resolve_domain_schema
                    schema = resolve_domain_schema(domain_key)
                    cur.execute(
                        f"SELECT 1 FROM {schema}.articles WHERE id = %s",
                        (article_id,),
                    )
                    if not cur.fetchone():
                        # Article was purged — mark as orphaned instead of backfilling
                        print(f"  Skipping sid={sid}: article_id={article_id} no longer exists in {schema}")
                        continue

                    query = f"""
                        UPDATE public.storyline_article_suggestions
                        SET relevance_score = %s,
                            semantic_score = %s,
                            keyword_score = %s
                        WHERE id = %s AND domain_key = %s AND status = 'pending'
                          AND combined_score IS NOT NULL
                    """
                    params = (fill_value, fill_value, fill_value, sid, domain_key)

                    if dry_run:
                        cur.execute(query.replace("UPDATE", "SELECT"), params[:-2] + (sid,))
                        print(f"  [DRY-RUN] Would backfill sid={sid} with value={fill_value}")
                    else:
                        cur.execute(query, params)
                        backfilled += cur.rowcount

                except Exception as e:
                    errors += 1
                    print(f"  ERROR on sid={sid}: {e}")

            if not dry_run:
                print(f"\nCommitted: {backfilled} rows backfilled")
                print(f"Errors: {errors}")
                # Verify final state
                cur.execute(
                    """
                    SELECT COUNT(*) FROM public.storyline_article_suggestions
                    WHERE status = 'pending'
                      AND (relevance_score <= 0 OR semantic_score <= 0 OR keyword_score <= 0)
                      AND quality_score > 0
                    """
                )
                remaining = int(cur.fetchone()[0])
                print(f"Remaining partial-scored items: {remaining}")

            # Phase 3: Report orphans (items pointing to deleted articles)
            print("\nPhase 3: Orphan detection")
            
            # Collect all active domain schemas
            from shared.pipeline_context import resolve_domain_schema
            try:
                from services.backlog_metrics import get_pipeline_schema_names_active
                schemas = get_pipeline_schema_names_active()
            except Exception:
                schemas = ['politics', 'finance', 'science_tech']
            
            if not schemas:
                print("  No active domains — skipping orphan count")
            else:
                # Use get_storyline_review_queue_orphan_count from backlog_metrics
                import sys
                sys.path.insert(0, '../../../api')
                try:
                    from services.backlog_metrics import get_storyline_review_queue_orphan_count
                    orphans = get_storyline_review_queue_orphan_count()
                    print(f"Orphaned suggestions (no matching article): {orphans}")
                except Exception as e:
                    print(f"  Orphan count error: {e}")



    finally:
        conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or len(sys.argv) == 1
    run(dry_run=dry_run)
