#!/usr/bin/env python3
"""
Estimate ETA to clear current backlogs (articles, documents, storylines).
Uses same DB/env as full_system_status_check. Run: uv run python scripts/backlog_eta.py
"""
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
API = os.path.join(ROOT, "api")
for p in (ROOT, SCRIPTS, API):
    if p not in sys.path:
        sys.path.insert(0, p)

env_path = os.path.join(ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                if key in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(key, val.strip().strip('"').strip("'"))
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())


def get_conn():
    try:
        from shared.database.connection import get_db_connection
        return get_db_connection()
    except Exception as e:
        print(f"DB connection failed: {e}")
        return None


def main():
    conn = get_conn()
    if not conn:
        print("Cannot connect to database. Set DB_* or .db_password_widow.")
        return 1

    cur = conn.cursor()

    # Backlog: articles to enrich (enrichment_status null/pending/failed, attempts < 3, url set)
    article_backlog = 0
    for schema in ("politics", "finance", "science_tech"):
        try:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.articles
                WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                  AND COALESCE(enrichment_attempts, 0) < 3
                  AND url IS NOT NULL AND url != ''
                """
            )
            article_backlog += cur.fetchone()[0] or 0
        except Exception:
            pass

    # Documents: unprocessed or without extracted_sections
    doc_backlog = 0
    try:
        cur.execute(
            """
            SELECT COUNT(*) FROM intelligence.processed_documents
            WHERE extracted_sections IS NULL OR extracted_sections = '[]'
            """
        )
        doc_backlog = cur.fetchone()[0] or 0
    except Exception:
        pass

    # Storylines: 3+ articles, no synthesis or stale
    storyline_backlog = 0
    for schema in ("politics", "finance", "science_tech"):
        try:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storylines s
                JOIN (SELECT storyline_id, COUNT(*) AS c FROM {schema}.storyline_articles GROUP BY storyline_id) sa
                  ON sa.storyline_id = s.id AND sa.c >= 3
                WHERE s.synthesized_content IS NULL
                   OR EXISTS (
                     SELECT 1 FROM {schema}.storyline_articles sa2
                     JOIN {schema}.articles a ON a.id = sa2.article_id
                     WHERE sa2.storyline_id = s.id
                     AND a.created_at > COALESCE(s.synthesized_at, '1970-01-01'::timestamptz)
                   )
                """
            )
            storyline_backlog += cur.fetchone()[0] or 0
        except Exception:
            pass

    conn.close()

    # Throughput: content_enrichment batch=60, every 5 min, 10s timeout/URL, 0.4s between fetches.
    # Re-enqueue when backlog remains. Inline enrichment at RSS means new articles rarely add to backlog.
    articles_per_hour = 500
    # Document processing: 10 per run, every 30 min → 20/hour
    docs_per_hour = 20
    # Storyline synthesis: 4 per domain per run, every 60 min → 12/hour
    storylines_per_hour = 12

    def eta_hours(backlog: int, per_hour: float) -> float:
        if per_hour <= 0:
            return 0.0
        return backlog / per_hour

    h_articles = eta_hours(article_backlog, articles_per_hour)
    h_docs = eta_hours(doc_backlog, docs_per_hour)
    h_storylines = eta_hours(storyline_backlog, storylines_per_hour)

    now = datetime.now(timezone.utc)
    eta_articles = now + timedelta(hours=h_articles) if article_backlog else now
    eta_docs = now + timedelta(hours=h_docs) if doc_backlog else now
    eta_storylines = now + timedelta(hours=h_storylines) if storyline_backlog else now
    eta_overall = max(eta_articles, eta_docs, eta_storylines) if (article_backlog or doc_backlog or storyline_backlog) else now

    print("=" * 60)
    print("Backlog ETA (after resource tuning)")
    print("=" * 60)
    print(f"  Articles (short/missing → enrich): {article_backlog:,}  → ~{articles_per_hour}/hr → ETA {h_articles:.0f}h ({eta_articles.strftime('%Y-%m-%d %H:%M')} UTC)")
    print(f"  Documents (extract sections):     {doc_backlog:,}  → ~{docs_per_hour}/hr  → ETA {h_docs:.0f}h ({eta_docs.strftime('%Y-%m-%d %H:%M')} UTC)")
    print(f"  Storylines (synthesis):            {storyline_backlog:,}  → ~{storylines_per_hour}/hr → ETA {h_storylines:.0f}h ({eta_storylines.strftime('%Y-%m-%d %H:%M')} UTC)")
    print("")
    print(f"  Overall catch-up (longest):       ~{max(h_articles, h_docs, h_storylines):.0f}h → {eta_overall.strftime('%Y-%m-%d %H:%M')} UTC")
    print("=" * 60)
    print("Throughput assumes: content_enrichment batch=60 + re-enqueue, doc 10/30min, synthesis 4/domain/60min.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
