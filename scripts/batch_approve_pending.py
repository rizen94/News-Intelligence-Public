#!/usr/bin/env python3
"""Batch-approve pending storyline_article_suggestions.

Use to clear the backlog of items stuck in pending state since auto-attach was disabled.
Once STORYLINE_AUTOMATION_AUTO_ATTACH=1 is set, new items are auto-committed immediately.
This script cleans up the existing queue.

Performance notes:
  - Uses ephemeral connections (not pooled) to avoid PgBouncer contention.
  - Values clause updates are faster than WHERE IN for large batches via SSHFS.
  - Default batch size of 500 rows per statement (~32ms on Widow).
"""
import sys, os, logging, time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def load_env():
    """Load .env from project root so DB credentials are available."""
    proj_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(proj_root / "api"))
    for env_path in [proj_root / ".env", proj_root / "api" / ".env"]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    os.environ.setdefault(key, value)


def batch_approve(dry_run=False, limit=500, max_iterations=1000):
    """Approve pending storyline_article_suggestions in batches.
    
    Args:
        dry_run: If True, only count rows without updating.
        limit: Number of rows per batch (default 500).
        max_iterations: Maximum number of batches to process (default 1000 = 500K rows max).
    
    Returns:
        dict with 'approved' count and optional 'error'.
    """
    from shared.database.connection import get_ephemeral_db_connection_context
    
    total_approved = 0
    iteration = 0
    start_time = time.time()
    
    while iteration < max_iterations:
        iteration += 1
        with get_ephemeral_db_connection_context() as conn:
            cur = conn.cursor()
            
            # Get IDs of pending items
            cur.execute(
                "SELECT id FROM public.storyline_article_suggestions WHERE status = 'pending' LIMIT %s",
                (limit,),
            )
            ids = [row[0] for row in cur.fetchall()]
            
            if not ids:
                logger.info("No more pending items after %d iterations", iteration - 1)
                break
            
            # Build UPDATE using VALUES clause (faster than WHERE IN via SSHFS)
            values_list = ', '.join([f'({i})' for i in ids])
            sql = f"UPDATE public.storyline_article_suggestions SET status = 'added' FROM (VALUES {values_list}) AS t(id) WHERE storyline_article_suggestions.id = t.id"
            
            cur.execute(sql)
            batch_approved = cur.rowcount
            
            if not dry_run:
                conn.commit()
            
            total_approved += batch_approved
            elapsed = time.time() - start_time
            rate = total_approved / max(elapsed, 0.1)
            logger.info(
                "Batch %4d: approved=%6d (total=%8d) | %.1fs @ %d items/s",
                iteration, batch_approved, total_approved, elapsed, rate,
            )
    
    elapsed = time.time() - start_time
    logger.info("Done: processed %d batches in %.1fs, total approved: %d", iteration, elapsed, total_approved)
    
    return {"approved": total_approved, "batches": iteration, "elapsed_s": elapsed}


def count_pending():
    """Return the current count of pending items."""
    from shared.database.connection import get_ephemeral_db_connection_context
    
    with get_ephemeral_db_connection_context() as conn:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM public.storyline_article_suggestions WHERE status = 'pending'")
        return cur.fetchone()[0]


def main():
    load_env()
    dry_run = "--dry-run" in sys.argv
    limit = 500
    max_iterations = 1000
    
    for arg in sys.argv[1:]:
        if arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--max-iters="):
            max_iterations = int(arg.split("=", 1)[1])
    
    # Always show current pending count first
    pending = count_pending()
    logger.info("Starting with %d pending items (limit=%d, max_iterations=%d)", pending, limit, max_iterations)
    
    result = batch_approve(dry_run=dry_run, limit=limit, max_iterations=max_iterations)
    print("\nResult:", result)
    return 1 if "error" in result else 0


if __name__ == "__main__":
    sys.exit(main())
