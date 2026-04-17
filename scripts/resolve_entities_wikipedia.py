"""
Multi-strategy Wikipedia entity resolver.

Pipeline per entity:
  1. Check negative cache  -> already processed (resolved or failed), skip
  2. Pre-filter patterns   -> obvious junk, negative-cache immediately
  3. Exact title lookup    -> hit? cache it  (trust Wikipedia redirects)
  4. Search API            -> hit? validate relevance, then cache
  5. Quoted search API     -> hit? validate relevance, then cache
  6. All failed            -> negative-cache  (unless rate-limited)

Successfully resolved entities go into wikipedia_knowledge (keyed by page_id)
AND into wikipedia_negative_cache with reason='resolved' to track the entity
string. This avoids needing a unique constraint on title_lower in the
knowledge table, since multiple entity strings can map to the same page.
"""

import argparse
import logging
import re
import sys
import os
import time

import psycopg2
import psycopg2.extras
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.entity_filters import classify_bad_entity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "NewsIntelBot/1.0 (news-intelligence project; pete@localhost)",
})


class APIUnavailable(Exception):
    """All retries exhausted (rate-limited or server error)."""
    pass


# ── HTTP helper ──────────────────────────────────────────────────

def wiki_get(params, max_retries=4):
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")

    for attempt in range(max_retries):
        try:
            resp = SESSION.get(WIKI_API, params=params, timeout=15)
        except requests.RequestException as exc:
            log.warning("Request error (attempt %d/%d): %s",
                        attempt + 1, max_retries, exc)
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429 or resp.status_code >= 500:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
            log.warning("HTTP %d (attempt %d/%d), retrying in %ds",
                        resp.status_code, attempt + 1, max_retries,
                        retry_after)
            time.sleep(retry_after)
            continue

        log.error("HTTP %d for params %s", resp.status_code, params)
        raise APIUnavailable(f"HTTP {resp.status_code}")

    raise APIUnavailable(f"Exhausted {max_retries} retries")


# ── Wikipedia lookups ────────────────────────────────────────────

def lookup_exact(title):
    """Exact title lookup with redirect following."""
    data = wiki_get({
        "action": "query",
        "titles": title,
        "redirects": "1",
        "prop": "extracts|info|categories",
        "exintro": "1",
        "explaintext": "1",
        "exsentences": "5",
        "inprop": "url",
        "cllimit": "20",
    })

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None

    page = pages[0]
    if page.get("missing", False) or "pageid" not in page:
        return None

    categories = [
        c["title"].replace("Category:", "")
        for c in page.get("categories", [])
    ]

    return (
        page["pageid"],
        page["title"],
        page.get("fullurl",
                  f"https://en.wikipedia.org/wiki/"
                  f"{page['title'].replace(' ', '_')}"),
        (page.get("extract") or "")[:4000],
        categories,
    )


def search_wiki(term, quoted=False):
    """Search Wikipedia. Returns list of (page_id, title, snippet)."""
    query = f'"{term}"' if quoted else term
    data = wiki_get({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": "3",
        "srprop": "snippet",
    })
    results = data.get("query", {}).get("search", [])
    return [
        (r["pageid"], r["title"], r.get("snippet", ""))
        for r in results
    ]


def fetch_page_detail(page_id):
    """Fetch extract, URL, and categories for a known page ID."""
    data = wiki_get({
        "action": "query",
        "pageids": str(page_id),
        "prop": "extracts|info|categories",
        "exintro": "1",
        "explaintext": "1",
        "exsentences": "5",
        "inprop": "url",
        "cllimit": "20",
    })
    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None, None, []
    page = pages[0]
    categories = [
        c["title"].replace("Category:", "")
        for c in page.get("categories", [])
    ]
    return (
        page.get("fullurl", ""),
        (page.get("extract") or "")[:4000],
        categories,
    )


# ── Relevance heuristic ─────────────────────────────────────────

def is_relevant(entity, candidate_title, candidate_snippet=""):
    e_low = entity.lower()
    t_low = candidate_title.lower()

    if e_low == t_low or e_low in t_low or t_low in e_low:
        return True

    e_tokens = set(re.findall(r"\w+", e_low))
    t_tokens = set(re.findall(r"\w+", t_low))
    if e_tokens and len(e_tokens & t_tokens) / len(e_tokens) >= 0.6:
        return True

    if candidate_snippet and e_low in candidate_snippet.lower():
        return True

    return False


# ── Database helpers ─────────────────────────────────────────────

def fetch_unresolved(cur, limit, neg_cache_days):
    """
    Return distinct entity names not yet in the negative cache.
    Resolved entities stay cached forever. Failed entities expire
    after neg_cache_days so they can be retried.
    """
    cur.execute("""
        SELECT DISTINCT lower(trim(ec.subject_text)) AS entity
          FROM intelligence.extracted_claims ec
     LEFT JOIN intelligence.wikipedia_negative_cache nc
            ON nc.title_lower = lower(trim(ec.subject_text))
           AND (nc.reason = 'resolved'
                OR nc.last_attempted >= NOW() - INTERVAL '1 day' * %s)
         WHERE nc.title_lower IS NULL
           AND trim(ec.subject_text) != ''
           AND ec.subject_text != '_skip'
         ORDER BY entity
         LIMIT %s
    """, (neg_cache_days, limit))
    return [row[0] for row in cur.fetchall()]


def upsert_positive(cur, entity_lower, page_id, title, url,
                    abstract, categories, methods):
    """
    Store the Wikipedia article (ON CONFLICT page_id -> update),
    add the entity input as an alias, and mark the entity string
    as 'resolved' in the negative cache for tracking.
    """
    # Upsert the Wikipedia article
    cur.execute("""
        INSERT INTO intelligence.wikipedia_knowledge
               (page_id, title, title_lower, abstract, page_url,
                categories, aliases, loaded_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (page_id) DO UPDATE SET
               abstract   = EXCLUDED.abstract,
               page_url   = EXCLUDED.page_url,
               categories = EXCLUDED.categories,
               aliases    = (
                   SELECT array_agg(DISTINCT a)
                     FROM unnest(
                       COALESCE(intelligence.wikipedia_knowledge.aliases,
                                '{}')
                       || EXCLUDED.aliases
                     ) AS a
               ),
               loaded_at  = NOW()
    """, (page_id, title, title.lower(), abstract, url,
          categories, [entity_lower]))

    # Track this entity string as resolved
    cur.execute("""
        INSERT INTO intelligence.wikipedia_negative_cache
               (title_lower, reason, methods_tried, attempts,
                first_seen, last_attempted)
        VALUES (%s, 'resolved', %s, 1, NOW(), NOW())
        ON CONFLICT (title_lower) DO UPDATE SET
               reason         = 'resolved',
               methods_tried  = EXCLUDED.methods_tried,
               last_attempted = NOW(),
               attempts       = intelligence.wikipedia_negative_cache.attempts + 1
    """, (entity_lower, methods))


def upsert_negative(cur, entity_lower, reason, methods):
    cur.execute("""
        INSERT INTO intelligence.wikipedia_negative_cache
               (title_lower, reason, methods_tried, attempts,
                first_seen, last_attempted)
        VALUES (%s, %s, %s, 1, NOW(), NOW())
        ON CONFLICT (title_lower) DO UPDATE SET
               reason         = EXCLUDED.reason,
               methods_tried  = EXCLUDED.methods_tried,
               last_attempted = NOW(),
               attempts       = intelligence.wikipedia_negative_cache.attempts + 1
    """, (entity_lower, reason, methods))


# ── Resolve one entity ───────────────────────────────────────────

def resolve_one(entity_name, request_delay=0.1):
    methods = []

    # Pre-filter
    bad_reason = classify_bad_entity(entity_name)
    if bad_reason:
        return ("negative", f"pre-filter: {bad_reason}", ["pre-filter"])

    # Exact title lookup
    methods.append("exact")
    time.sleep(request_delay)
    hit = lookup_exact(entity_name)
    if hit:
        page_id, title, url, abstract, categories = hit
        log.info("  exact-hit: %s -> %s", entity_name, title)
        return ("positive", page_id, title, url, abstract,
                categories, methods)

    # Title-cased fallback (entities come in lowercase from query)
    if entity_name != entity_name.title():
        time.sleep(request_delay)
        hit = lookup_exact(entity_name.title())
        if hit:
            page_id, title, url, abstract, categories = hit
            log.info("  exact-hit (title-cased): %s -> %s",
                     entity_name, title)
            return ("positive", page_id, title, url, abstract,
                    categories, methods)

    # Search (unquoted)
    methods.append("search")
    time.sleep(request_delay)
    for page_id, title, snippet in search_wiki(entity_name, quoted=False):
        if is_relevant(entity_name, title, snippet):
            time.sleep(request_delay)
            url, abstract, categories = fetch_page_detail(page_id)
            log.info("  search-hit: %s -> %s", entity_name, title)
            return ("positive", page_id, title, url or "",
                    abstract or "", categories, methods)

    # Quoted search
    methods.append("quoted_search")
    time.sleep(request_delay)
    for page_id, title, snippet in search_wiki(entity_name, quoted=True):
        if is_relevant(entity_name, title, snippet):
            time.sleep(request_delay)
            url, abstract, categories = fetch_page_detail(page_id)
            log.info("  quoted-hit: %s -> %s", entity_name, title)
            return ("positive", page_id, title, url or "",
                    abstract or "", categories, methods)

    return ("negative", "no relevant result found", methods)


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Resolve entities against Wikipedia")
    parser.add_argument("--limit", type=int, default=500,
                        help="Max entities per run (default: 500)")
    parser.add_argument("--neg-cache-days", type=int, default=7,
                        help="Re-attempt failed entries older than N days")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Seconds between API requests (default: 0.1)")
    parser.add_argument("--db-host",
                        default=os.getenv("DB_HOST", "192.168.93.101"))
    parser.add_argument("--db-port", type=int,
                        default=int(os.getenv("DB_PORT", "5432")))
    parser.add_argument("--db-name",
                        default=os.getenv("DB_NAME", "news_intel"))
    parser.add_argument("--db-user",
                        default=os.getenv("DB_USER", "newsapp"))
    parser.add_argument("--db-password",
                        default=os.getenv("DB_PASSWORD", ""))
    args = parser.parse_args()

    conn = psycopg2.connect(
        host=args.db_host, port=args.db_port,
        dbname=args.db_name, user=args.db_user,
        password=args.db_password,
    )
    conn.autocommit = False
    cur = conn.cursor()

    log.info("Fetching up to %d unresolved entities ...", args.limit)
    entities = fetch_unresolved(cur, args.limit, args.neg_cache_days)
    log.info("Found %d entities to resolve.", len(entities))

    resolved = 0
    failed = 0
    api_errors = 0

    for i, name in enumerate(entities, 1):
        log.info("[%d/%d] %s", i, len(entities), name)
        try:
            result = resolve_one(name, request_delay=args.delay)
        except APIUnavailable as exc:
            log.error("  API unavailable: %s", exc)
            api_errors += 1
            if api_errors >= 3:
                log.error(
                    "Too many consecutive API errors -- aborting run.")
                break
            continue

        api_errors = 0

        if result[0] == "positive":
            _, page_id, title, url, abstract, categories, methods = result
            upsert_positive(cur, name, page_id, title, url, abstract,
                            categories, methods)
            resolved += 1
        else:
            _, reason, methods = result
            upsert_negative(cur, name, reason, methods)
            failed += 1
            log.info("  negative-cached: %s (%s)",
                     reason, ", ".join(methods))

        if i % 25 == 0:
            conn.commit()

    conn.commit()
    cur.close()
    conn.close()

    log.info("Done.  resolved=%d  failed=%d  api_errors=%d  total=%d",
             resolved, failed, api_errors, len(entities))


if __name__ == "__main__":
    main()
