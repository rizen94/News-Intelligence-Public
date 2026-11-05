#!/usr/bin/env python3
"""One-shot TTL cleanup: expire stale pending article suggestions."""
import os, sys, time, psycopg2

DB = dict(host='192.168.93.101', port=6432, dbname='news_intel',
          user='newsapp', password='v4xB--yiRtQ5b1eact_l5K7jnq6mVPtw')

def main():
    print("=" * 70)
    print("TTL Cleanup: Expiring stale pending article suggestions")
    print(f"Target DB : {DB['host']}:{DB['port']}")
    print("=" * 70)
    conn = psycopg2.connect(**DB, connect_timeout=10)
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM public.storyline_article_suggestions WHERE status = 'pending' AND expires_at < NOW()")
        stale_before = cur.fetchone()[0]
        print(f"Stale pending rows (expires_at < NOW()): {stale_before}")
        if stale_before == 0:
            print("No stale rows found. Nothing to clean up.")
            return
        batch_size = int(os.environ.get("TTL_BATCH", "5000"))
        print(f"Batch size : {batch_size}")
        print("-" * 70)
        updated = 0; start = time.time()
        while True:
            cur.execute(
                "UPDATE public.storyline_article_suggestions SET status = 'expired' "
                "WHERE ctid IN (SELECT ctid FROM public.storyline_article_suggestions "
                "WHERE status = 'pending' AND expires_at < NOW() LIMIT %s)",
                [batch_size])
            bu = cur.rowcount; updated += bu; conn.commit()
            print(f"  Batch #{updated//batch_size + 1}: {bu} rows | total={updated}/{stale_before}")
            if bu == 0: break
        elapsed = time.time() - start
        print("-" * 70)
        print(f"Cleanup complete: {updated} rows expired in {elapsed:.1f}s")
        cur.execute("SELECT count(*) FROM public.storyline_article_suggestions WHERE status = 'pending' AND expires_at < NOW()")
        remaining = cur.fetchone()[0]
        print(f"Remaining stale: {remaining} (expected ~0)")
    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()