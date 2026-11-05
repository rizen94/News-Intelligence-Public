#!/usr/bin/env python3
"""TTL cleanup for expired storyline_article_suggestions rows.

Runs via cron (daily). Removes pending suggestions whose expires_at
has passed - they are stale and no longer actionable.
"""
import sys, os, logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_env():
    """Load .env from project root so DB credentials are available."""
    proj_root = Path(__file__).resolve().parent.parent
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

def get_db():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
    from shared.database.connection import get_db_connection
    return get_db_connection()

def cleanup_suggestions(dry_run=False):
    conn = get_db()
    if not conn:
        logger.error("Cannot connect to database")
        return {"error": "no_connection", "deleted": 0, "found": 0}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public.storyline_article_suggestions WHERE status = 'pending' AND expires_at < NOW()"
            )
            total_expired = cur.fetchone()[0]
            if total_expired == 0:
                logger.info("No expired suggestions found")
                return {"found": 0, "deleted": 0}
            cur.execute(
                "DELETE FROM public.storyline_article_suggestions WHERE status = 'pending' AND expires_at < NOW()"
            )
            deleted = cur.rowcount
        conn.commit()
        logger.info("TTL cleanup: found=%d deleted=%s", total_expired, "(DRY RUN)" if dry_run else str(deleted))
        return {"found": total_expired, "deleted": deleted}
    except Exception as e:
        conn.rollback()
        logger.error("TTL cleanup failed: %s", e)
        return {"error": str(e), "deleted": 0}
    finally:
        conn.close()

def main():
    load_env()
    dry_run = "--dry-run" in sys.argv
    result = cleanup_suggestions(dry_run=dry_run)
    print("Result:", result)
    return 1 if "error" in result else 0

if __name__ == "__main__":
    sys.exit(main())
