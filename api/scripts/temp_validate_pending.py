"""Quick validation of pending-items investigation claims."""
import os, sys, psycopg2, json, re

# Load .env manually — must be project root (.env is at parent of api/)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
env_path = os.path.join(project_root, '.env')
if os.path.exists(env_path):
    for line in open(env_path):
        stripped = line.strip()
        if '=' in stripped and not stripped.startswith('#'):
            key, val = stripped.split('=', 1)
            os.environ.setdefault(key, val)

print("DB_HOST:", os.environ.get('DB_HOST', 'NOT SET'))
print("DB_PORT:", os.environ.get('DB_PORT', 'NOT SET'))
print("DB_USER:", os.environ.get('DB_USER', 'NOT SET'))
print("DB_PASSWORD exists:", bool(os.environ.get('DB_PASSWORD', '')))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.database.connection import ephemeral_db_connection_context

def q(sql, params=None):
    with ephemeral_db_connection_context() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or {})
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
    return cols, rows

def row_dict(cols, row):
    return dict(zip(cols, row))

# 1. Real article counts
print("=== 1. Article row counts ===")
for schema in ['public', 'artificial_intelligence', 'medicine', 'legal']:
    try:
        cols, rows = q(f"SELECT COUNT(*) FROM {schema}.articles")
        print(f"  {schema}.articles: {rows[0][0]}")
    except Exception as e:
        print(f"  {schema}.articles: ERROR - {e}")

if rows[0][0] > 0:
    print("\n=== 2. public.articles by enrichment_status ===")
    cols, rows = q("SELECT enrichment_status, processing_status, COUNT(*) as cnt FROM public.articles GROUP BY 1,2 ORDER BY 1,2")
    for r in rows:
        print(f"  status={r['enrichment_status']}, proc={r['processing_status']}: {r['cnt']}")

print("\n=== Pending + content breakdown ===")
if rows[0][0] > 0:
    cols, rows = q("SELECT COUNT(*) as cnt FROM public.articles WHERE enrichment_status='pending' AND COALESCE(LENGTH(content),0)>=500")
    print(f"  Pending + content>=500chars: {rows[0][0]}")
    cols, rows = q("SELECT COUNT(*) as cnt FROM public.articles WHERE enrichment_status='pending' AND COALESCE(LENGTH(content),0)<500")
    print(f"  Pending + content<500chars: {rows[0][0]}")
    cols, rows = q("SELECT COUNT(*) FROM public.articles WHERE enrichment_status IS NULL")
    print(f"  NULL enrichment_status: {rows[0][0]}")

# 3. Automation run history summary
print("\n=== 3. Top automation phases by run count ===")
cols, rows = q("SELECT phase, COUNT(*) as cnt FROM public.automation_run_history GROUP BY phase ORDER BY cnt DESC LIMIT 15")
for r in rows:
    print(f"  {r['phase']}: {r['cnt']} runs")

# 4. RSS feeds
print("\n=== 4. RSS feeds ===")
cols, rows = q("SELECT COUNT(*) FROM public.rss_feeds")
print(f"  Public rss_feeds: {rows[0][0]}")

# Also check domain RSS feeds
for schema in ['public', 'artificial_intelligence', 'medicine', 'legal']:
    try:
        cols, rows = q(f"SELECT COUNT(*) FROM {schema}.rss_feeds WHERE is_active = true")
        print(f"  {schema}.rss_feeds (active): {rows[0][0]}")
    except Exception as e:
        print(f"  {schema}.rss_feeds: ERROR - {e}")

# 5. Check if any INSERT into public.articles happens in current code
print("\n=== 5. Code audit — where does each service INSERT articles? ===")
print("  See grep output below.")

print("\nDone.")
