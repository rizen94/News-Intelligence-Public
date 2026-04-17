#!/usr/bin/env python3
"""
Pre-seed intelligence.wikipedia_knowledge via MediaWiki action=query API.
Fetches up to 20 page extracts per request (batch mode).
Optional --search-fallback does a second pass with opensearch for misses.

Usage:
  DB_PASSWORD='xxx' python scripts/preseed_wikipedia_cache.py --types person organization --dry-run
  DB_PASSWORD='xxx' python scripts/preseed_wikipedia_cache.py --types person --limit 200 --randomize
  DB_PASSWORD='xxx' python scripts/preseed_wikipedia_cache.py --types person organization --search-fallback
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

WIKIPEDIA_API  = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_REST = "https://en.wikipedia.org/api/rest_v1/page/summary"
USER_AGENT     = "NewsIntelligenceBot/1.0 (pre-seed; mailto:admin@localhost)"
BATCH_SIZE     = 20   # max extracts per request with exintro
VALID_TYPES    = ("person", "organization", "recurring_event", "family", "subject")

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST", "192.168.93.101"),
    "port":     int(os.environ.get("DB_PORT", "5432")),
    "dbname":   os.environ.get("DB_NAME", "news_intel"),
    "user":     os.environ.get("DB_USER", "newsapp"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

_conn = None


def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(**DB_CONFIG)
        _conn.autocommit = False
    return _conn


def get_uncached_names(types, limit=0, randomize=False):
    conn = get_conn()
    with conn.cursor() as cur:
        base = """
            SELECT DISTINCT lower(trim(ep.metadata->>'canonical_name')) AS name
            FROM intelligence.entity_profiles ep
            WHERE ep.metadata->>'canonical_name' IS NOT NULL
              AND trim(ep.metadata->>'canonical_name') != ''
              AND ep.metadata->>'entity_type' = ANY(%(types)s)
              AND trim(ep.metadata->>'canonical_name') !~ '^[0-9$#@+]'
              AND length(trim(ep.metadata->>'canonical_name')) BETWEEN 3 AND 200
              AND NOT EXISTS (
                  SELECT 1 FROM intelligence.wikipedia_knowledge wk
                  WHERE wk.title_lower = lower(trim(ep.metadata->>'canonical_name'))
              )
        """
        if randomize:
            sql = f"SELECT name FROM ({base}) sub ORDER BY random()"
        else:
            sql = f"{base} ORDER BY name"
        cur.execute(sql, {"types": types})
        names = [r[0] for r in cur.fetchall()]
    return names[:limit] if limit > 0 else names


# ── HTTP helper ───────────────────────────────────────────────────────

def _http_json(url, timeout=20):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        if e.code == 429:
            logger.warning("Rate-limited, sleeping 10s")
            time.sleep(10)
        return None
    except (URLError, OSError, json.JSONDecodeError):
        return None


# ── Batch fetch via action=query ──────────────────────────────────────

def _title_case(name):
    return " ".join(w.capitalize() for w in name.split())


def fetch_batch(names):
    """
    Query Wikipedia for up to BATCH_SIZE names at once using action=query
    with prop=extracts|info. Returns {original_name: summary_dict}.
    """
    if not names:
        return {}

    # Map title-cased version -> list of original lower-cased names
    tc_map = {}
    for n in names:
        tc = _title_case(n)
        tc_map.setdefault(tc, []).append(n)

    params = urlencode({
        "action":        "query",
        "prop":          "extracts|info",
        "exintro":       "1",
        "explaintext":   "1",
        "exlimit":       str(min(len(tc_map), BATCH_SIZE)),
        "inprop":        "url",
        "titles":        "|".join(tc_map),
        "format":        "json",
        "formatversion": "2",
        "redirects":     "1",
    })

    data = _http_json(f"{WIKIPEDIA_API}?{params}")
    if not data or "query" not in data:
        return {}

    q = data["query"]

    # Reverse maps for normalization and redirects
    norm  = {n["to"]: n["from"] for n in q.get("normalized", [])}
    redir = {r["to"]: r["from"] for r in q.get("redirects", [])}

    results = {}
    for page in q.get("pages", []):
        if page.get("missing"):
            continue
        extract = (page.get("extract") or "").strip()
        if not extract:
            continue

        wiki_title = page["title"]
        url = page.get("fullurl") or \
              f"https://en.wikipedia.org/wiki/{quote(wiki_title.replace(' ', '_'))}"

        # Trace back through redirects and normalization to our key
        src = redir.get(wiki_title, wiki_title)
        src = norm.get(src, src)

        orig_names = tc_map.get(src)
        if not orig_names:
            # Case-insensitive fallback
            for tc, ns in tc_map.items():
                if tc.lower() in (src.lower(), wiki_title.lower()):
                    orig_names = ns
                    break
        if not orig_names:
            continue

        summary = {
            "pageid":  page.get("pageid"),
            "title":   wiki_title,
            "extract": extract,
            "url":     url,
            "type":    "standard",
        }
        for n in orig_names:
            results[n] = summary

    return results


# ── Cache one result ──────────────────────────────────────────────────

def cache_one(name, summary):
    title   = (summary.get("title") or "").strip()
    extract = (summary.get("extract") or "").strip()
    if not title or not extract:
        return False

    page_id = summary.get("pageid")
    if not page_id:
        page_id = int(hashlib.sha256(title.lower().encode()).hexdigest()[:8], 16) % (2**31 - 1)

    url = summary.get("url") or \
          f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO intelligence.wikipedia_knowledge
                    (page_id, title, title_lower, abstract, page_url, page_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (page_id) DO UPDATE SET
                    abstract  = EXCLUDED.abstract,
                    page_url  = EXCLUDED.page_url,
                    loaded_at = NOW()
            """, (page_id, title[:500], title.lower()[:500],
                  extract[:10000], url[:500], summary.get("type", "other")))

            # Alias row so the entity's own lower-cased name also hits cache
            if name.strip().lower() != title.strip().lower():
                alias_id = int(
                    hashlib.sha256(name.strip().lower().encode()).hexdigest()[:8], 16
                ) % (2**31 - 1)
                if alias_id != page_id:
                    cur.execute("""
                        INSERT INTO intelligence.wikipedia_knowledge
                            (page_id, title, title_lower, abstract, page_url, page_type)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (page_id) DO NOTHING
                    """, (alias_id, name[:500], name.strip().lower()[:500],
                          extract[:10000], url[:500], summary.get("type", "other")))
        conn.commit()
        return True
    except Exception as e:
        logger.debug("Insert failed for %s: %s", name, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False


# ── Main batch runner ─────────────────────────────────────────────────

def run_batches(names):
    cached = skipped = 0
    missed = []
    n_batches = (len(names) + BATCH_SIZE - 1) // BATCH_SIZE

    for b, i in enumerate(range(0, len(names), BATCH_SIZE), 1):
        chunk = names[i:i + BATCH_SIZE]
        if b > 1:
            time.sleep(1)

        hits = fetch_batch(chunk)
        for n in chunk:
            if n in hits and cache_one(n, hits[n]):
                cached += 1
            else:
                skipped += 1
                if n not in hits:
                    missed.append(n)

        logger.info("Batch %d/%d  cached=%d  skipped=%d  hit=%.0f%%",
                     b, n_batches, cached, skipped,
                     cached / max(cached + skipped, 1) * 100)

    return cached, skipped, missed


# ── Search fallback for misses ────────────────────────────────────────

def search_one(name):
    """opensearch -> REST summary -> cache."""
    params = urlencode({
        "action": "opensearch", "search": name,
        "limit": "1", "namespace": "0", "format": "json",
    })
    data = _http_json(f"{WIKIPEDIA_API}?{params}")
    if not data or len(data) < 2 or not data[1]:
        return False

    found = data[1][0]
    enc = quote(found.replace(" ", "_"), safe="")
    s = _http_json(f"{WIKIPEDIA_REST}/{enc}")
    if not s or s.get("type") != "standard" or not s.get("extract"):
        return False

    return cache_one(name, {
        "pageid":  s.get("pageid"),
        "title":   s.get("title", found),
        "extract": s["extract"],
        "url":     s.get("content_urls", {}).get("desktop", {}).get("page", ""),
        "type":    "standard",
    })


def run_search_fallback(missed):
    if not missed:
        return 0
    logger.info("Search fallback: %d names ...", len(missed))
    found = 0
    for i, n in enumerate(missed, 1):
        time.sleep(0.2)
        if search_one(n):
            found += 1
        if i % 100 == 0:
            logger.info("  fallback %d/%d  found=%d", i, len(missed), found)
    logger.info("Search fallback done: found %d / %d", found, len(missed))
    return found


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Pre-seed Wikipedia cache")
    ap.add_argument("--types", nargs="+", default=["person", "organization"],
                    choices=VALID_TYPES)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--randomize", action="store_true")
    ap.add_argument("--search-fallback", action="store_true",
                    help="Second pass with opensearch for batch misses")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not DB_CONFIG["password"]:
        logger.error("DB_PASSWORD is required")
        sys.exit(1)

    logger.info("Types: %s", ", ".join(args.types))
    names = get_uncached_names(args.types, args.limit, args.randomize)
    logger.info("Found %d uncached names", len(names))

    if args.dry_run:
        for n in names[:30]:
            print(f"  {n}")
        est = (len(names) + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info("Would make ~%d batch API calls (~%.0fs est)", est, est * 1.5)
        return

    if not names:
        logger.info("All cached!")
        return

    t0 = time.time()
    cached, skipped, missed = run_batches(names)

    if args.search_fallback and missed:
        extra = run_search_fallback(missed)
        cached += extra
        skipped -= extra

    elapsed = time.time() - t0
    total = cached + skipped
    logger.info("Done %.0fs — cached=%d skipped=%d hit=%.0f%% rate=%.1f/s",
                elapsed, cached, skipped,
                cached / max(total, 1) * 100,
                len(names) / max(elapsed, 1))


if __name__ == "__main__":
    main()
