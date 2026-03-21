#!/usr/bin/env python3
"""
Populate intelligence.wikipedia_knowledge.aliases from Wikipedia redirects.

Pages that redirect to a Wikipedia article (e.g. "GOP" → "Republican Party (United States)")
are stored as aliases so lookup_entity() can match by redirect name. Run after
load_wikipedia_dump.py so the local table has rows. Uses MediaWiki API
list=backlinks&blfilterredir=redirects (rate-limited).

Usage (from project root; DB from .env):
  PYTHONPATH=api python scripts/populate_wikipedia_aliases.py [--limit N] [--delay 1.0]

  --limit   Max number of wiki rows to process (default: 500)
  --delay   Seconds between API calls (default: 1.0)
  --dry-run Print would-be aliases, do not update DB
"""

import argparse
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isfile(os.path.join(ROOT, ".env")):
    with open(os.path.join(ROOT, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())

sys.path.insert(0, os.path.join(ROOT, "api"))

import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "NewsIntelligenceSystem/1.0 (https://newsintelligence.com)"}


def fetch_redirects(title: str, limit: int = 100) -> list[str]:
    """Return list of page titles that redirect to the given title (lowercased)."""
    out = []
    try:
        params = {
            "action": "query",
            "format": "json",
            "list": "backlinks",
            "bltitle": title,
            "blfilterredir": "redirects",
            "bllimit": limit,
            "blnamespace": 0,
        }
        r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        for item in data.get("query", {}).get("backlinks", []):
            t = (item.get("title") or "").strip()
            if t and t != title:
                out.append(t.lower())
    except Exception as e:
        pass  # skip on error
    return out


def main():
    parser = argparse.ArgumentParser(description="Populate wikipedia_knowledge.aliases from redirects")
    parser.add_argument("--limit", type=int, default=500, help="Max rows to process")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Do not update DB")
    args = parser.parse_args()

    from shared.database.connection import get_db_connection
    conn = get_db_connection()
    if not conn:
        print("ERROR: No database connection")
        sys.exit(1)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, page_id, title
            FROM intelligence.wikipedia_knowledge
            ORDER BY id
            LIMIT %s
            """,
            (args.limit,),
        )
        rows = cur.fetchall()

    if not rows:
        print("No rows in intelligence.wikipedia_knowledge. Run load_wikipedia_dump.py first.")
        sys.exit(0)

    updated = 0
    for i, (pk, page_id, title) in enumerate(rows):
        if not title:
            continue
        redirects = fetch_redirects(title)
        if not redirects:
            time.sleep(args.delay)
            continue
        # Dedupe and keep lowercased
        aliases = list(dict.fromkeys(r.lower() for r in redirects))
        if args.dry_run:
            print(f"  {title!r} -> aliases {aliases[:10]}{'...' if len(aliases) > 10 else ''}")
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.wikipedia_knowledge
                    SET aliases = %s
                    WHERE id = %s
                    """,
                    (aliases, pk),
                )
            conn.commit()
            updated += 1
        if (i + 1) % 50 == 0:
            print(f"Processed {i + 1}/{len(rows)} (updated {updated})")
        time.sleep(args.delay)

    print(f"Done. Updated aliases for {updated} rows.")
    conn.close()


if __name__ == "__main__":
    main()
