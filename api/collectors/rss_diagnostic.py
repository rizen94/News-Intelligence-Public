#!/usr/bin/env python3
"""
RSS Ingest Diagnostic — fetch a feed, run every gate on every entry, report where articles die.

Usage:
  python rss_diagnostic.py                          # test the first active ai domain feed found
  python rss_diagnostic.py --limit N                # only test first N entries
  python rss_diagnostic.py --all                    # test ALL feeds (slow)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Minimal bootstrap: avoid domain_registry DB import ──────────────────────
os.environ.setdefault("DEVELOPMENT_MODE", "false")
os.environ.setdefault("PRODUCTION_DOMAINS", "")

# ── imports (order matters: avoids circular DB init) ────────────────────────
import feedparser, time, argparse, statistics
from collections import Counter, defaultdict


def main():
    parser = argparse.ArgumentParser(description="RSS Ingest Diagnostic")
    parser.add_argument("--limit", type=int, default=20, help="Max entries per feed")
    parser.add_argument("--all", action="store_true", help="Test all active feeds (slow)")
    parser.add_argument("--url", default=None, help="Test a specific feed URL only")
    args = parser.parse_args()

    # ── 0. Get DB connection and find feeds ───────────────────────────────
    from api.shared.database.connection import get_db_connection
    conn = get_db_connection()
    if not conn:
        print("FATAL: cannot connect to DB")
        return
    cur = conn.cursor()

    feed_rows = []  # (schema, id, name, url)

    if args.url:
        for schema in ["artificial_intelligence", "intelligence", "legal", "medicine", "neurodiversity"]:
            try:
                cur.execute(
                    f"SELECT id, feed_name, feed_url FROM {schema}.rss_feeds WHERE is_active = true AND feed_url = %s LIMIT 1",
                    (args.url,),
                )
                r = cur.fetchone()
                if r:
                    feed_rows.append((schema, r[0], r[1], r[2]))
                    break
            except Exception:
                pass
        if not feed_rows:
            print(f"Feed URL not found in any active table: {args.url}")
            return
    elif args.all:
        for schema in ["artificial_intelligence", "intelligence", "legal", "medicine", "neurodiversity"]:
            try:
                cur.execute(f"SELECT id, feed_name, feed_url FROM {schema}.rss_feeds WHERE is_active = true")
                for r in cur.fetchall():
                    feed_rows.append((schema, r[0], r[1], r[2]))
            except Exception:
                pass
    else:
        # Default: first 3 active feeds from artificial_intelligence
        for schema in ["artificial_intelligence"]:
            try:
                cur.execute(f"SELECT id, feed_name, feed_url FROM {schema}.rss_feeds WHERE is_active = true LIMIT 5")
                for r in cur.fetchall():
                    feed_rows.append((schema, r[0], r[1], r[2]))
            except Exception:
                pass

    if not feed_rows:
        print("No active feeds found.")
        return

    # ── 1. Fetch and parse each feed ────────────────────────────────────────
    print(f"Testing {len(feed_rows)} feeds:")
    for schema, feed_id, feed_name, feed_url in feed_rows:
        print(f"  {schema}: {feed_name} ({feed_url})")

    # ── 2. Test each feed ───────────────────────────────────────────────────
    for schema, feed_id, feed_name, feed_url in feed_rows:
        print(f"\nTesting {schema}: {feed_name}")
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                print("  No entries found")
                continue
            print(f"  Found {len(feed.entries)} entries")

            # Test first N entries
            for i, entry in enumerate(feed.entries[:args.limit]):
                print(f"    Entry {i+1}: {entry.get(title, No title)}")
                if not entry.get("title"):
                    print("      ❌ No title")
                if not entry.get("published"):
                    print("      ❌ No published date")
                if not entry.get("link"):
                    print("      ❌ No link")

        except Exception as e:
            print(f"  Error fetching {feed_url}: {e}")

if __name__ == "__main__":
    main()
