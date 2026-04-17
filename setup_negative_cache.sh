#!/usr/bin/env bash
set -euo pipefail

DB_HOST="192.168.93.101"
DB_PORT="5432"
DB_NAME="news_intel"
DB_USER="newsapp"
DB_PASS="v4xB--yiRtQ5b1eact_l5K7jnq6mVPtw"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=== Setting up in: $PROJECT_DIR ==="

# ── 1. Create directories ────────────────────────────────────────
mkdir -p migrations lib scripts
touch lib/__init__.py

# ── 2. Write the SQL migration ───────────────────────────────────
cat > migrations/007_wikipedia_negative_cache.sql << 'SQLEOF'
BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.wikipedia_negative_cache (
    title_lower         TEXT PRIMARY KEY,
    entity_type         TEXT,
    reason              TEXT NOT NULL,
    methods_tried       TEXT[] NOT NULL DEFAULT '{}',
    attempts            INTEGER NOT NULL DEFAULT 1,
    sample_source_id    BIGINT,
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempted      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE intelligence.wikipedia_negative_cache IS
    'Entities that have been tried and confirmed unresolvable to Wikipedia.';

COMMENT ON COLUMN intelligence.wikipedia_negative_cache.reason IS
    'Why this entity was blocklisted: no_results, too_ambiguous, generic_term, ner_artifact, too_short, manual_block';

CREATE INDEX IF NOT EXISTS idx_neg_cache_reason
    ON intelligence.wikipedia_negative_cache (reason);
CREATE INDEX IF NOT EXISTS idx_neg_cache_last_attempted
    ON intelligence.wikipedia_negative_cache (last_attempted);

COMMIT;
SQLEOF

echo "✓ Created migrations/007_wikipedia_negative_cache.sql"

# ── 3. Write the entity pre-filter library ───────────────────────
cat > lib/entity_filters.py << 'PYEOF'
"""
Pattern-based pre-filters that identify entities not worth looking up.
These go straight into the negative cache without hitting Wikipedia at all.
"""

import re

# Common roles, titles, and generic phrases NER loves to extract
GENERIC_BLOCKLIST = frozenset([
    "president", "prime minister", "the president", "the government",
    "the company", "the state", "the city", "the country",
    "officials", "authorities", "police", "military", "the court",
    "spokesperson", "sources", "analysts", "residents", "witnesses",
    "the ministry", "the department", "the agency", "the committee",
    "the white house", "the pentagon", "the kremlin",
    "mr", "mrs", "dr", "sir", "prof",
    "the united nations",
])

# Patterns that indicate NER garbage
_GARBAGE_PATTERNS = [
    re.compile(r"^\d+$"),                                      # pure numbers
    re.compile(r"^[^a-zA-Z]*$"),                               # no letters at all
    re.compile(r"^(the|a|an)\s*$", re.I),                      # bare articles
    re.compile(r"[@#]"),                                        # social media handles/hashtags
    re.compile(r"^https?://"),                                  # URLs
    re.compile(r"\b(said|says|told|according)\b", re.I),        # sentence fragments
]


def classify_bad_entity(name, entity_type=None):
    """
    Returns a reason string if this entity should be blocklisted,
    or None if it's worth trying to resolve.
    """
    if not name or not name.strip():
        return "empty"

    cleaned = name.strip()

    # Too short to be meaningful
    if len(cleaned) < 3:
        return "too_short"

    # Too long — probably a sentence fragment the NER grabbed
    if len(cleaned) > 120:
        return "ner_artifact"

    # Generic terms
    if cleaned.lower() in GENERIC_BLOCKLIST:
        return "generic_term"

    # Single-word "person" names are almost never resolvable
    if " " not in cleaned and entity_type == "person":
        return "generic_term"

    # Garbage patterns
    for pat in _GARBAGE_PATTERNS:
        if pat.search(cleaned):
            return "ner_artifact"

    return None
PYEOF

echo "✓ Created lib/entity_filters.py"

# ── 4. Write the resolver script ─────────────────────────────────
cat > scripts/resolve_entities_wikipedia.py << 'PYEOF'
"""
Multi-strategy Wikipedia entity resolver with negative caching.

Pipeline per entity:
  1. Check positive cache  -> already resolved, skip
  2. Check negative cache  -> already failed, skip
  3. Pre-filter patterns   -> obvious junk, blocklist immediately
  4. Exact title lookup    -> hit? cache it
  5. Search API            -> hit? cache it
  6. Quoted search API     -> hit? cache it
  7. All failed            -> insert into negative cache
"""

import argparse
import logging
import sys
import os
import time
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import requests

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.entity_filters import classify_bad_entity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "NewsIntelBot/1.0 (news-intelligence project; pete@localhost)"})


# ── Database ─────────────────────────────────────────────────────

def get_connection(host, port, dbname, user, password):
    return psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password,
    )


# ── Wikipedia lookup strategies ──────────────────────────────────

def try_exact(title):
    """Strategy 1: exact title match via query + extracts + pageprops."""
    try:
        resp = SESSION.get(WIKI_API, params={
            "action": "query",
            "titles": title,
            "prop": "extracts|info|pageprops",
            "exintro": True,
            "explaintext": True,
            "inprop": "url",
            "redirects": 1,
            "format": "json",
            "formatversion": 2,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("API error for exact lookup '%s': %s", title, e)
        return None

    pages = data.get("query", {}).get("pages", [])
    for page in pages:
        if not page.get("missing") and page.get("extract"):
            return page
    return None


def try_search(title, quoted=False):
    """Strategy 2/3: search API, optionally with quotes for exact phrase."""
    search_term = '"{}"'.format(title) if quoted else title
    try:
        resp = SESSION.get(WIKI_API, params={
            "action": "query",
            "list": "search",
            "srsearch": search_term,
            "srlimit": 1,
            "format": "json",
            "formatversion": 2,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("API error for search '%s': %s", search_term, e)
        return None

    results = data.get("query", {}).get("search", [])
    if not results:
        return None
    # Fetch full page data for the top result
    return try_exact(results[0]["title"])


# ── Cache operations ─────────────────────────────────────────────

def get_unresolved_entities(conn, entity_types=None, limit=100, randomize=False):
    """Get entity names not already in positive or negative cache."""
    type_filter = ""
    params = []
    if entity_types:
        type_filter = "AND ep.metadata->>'entity_type' = ANY(%s)"
        params.append(entity_types)

    order = "ORDER BY random()" if randomize else "ORDER BY ep.id"
    params.append(limit)

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT ON (lower(trim(ep.metadata->>'canonical_name')))
                   lower(trim(ep.metadata->>'canonical_name')) AS name,
                   ep.metadata->>'entity_type' AS etype,
                   ep.id AS sample_id
            FROM intelligence.entity_profiles ep
            WHERE ep.metadata->>'canonical_name' IS NOT NULL
              AND length(trim(ep.metadata->>'canonical_name')) > 0
              AND NOT EXISTS (
                  SELECT 1 FROM intelligence.wikipedia_knowledge wk
                  WHERE wk.title_lower = lower(trim(ep.metadata->>'canonical_name'))
              )
              AND NOT EXISTS (
                  SELECT 1 FROM intelligence.wikipedia_negative_cache nc
                  WHERE nc.title_lower = lower(trim(ep.metadata->>'canonical_name'))
              )
              {}
            {}
            LIMIT %s
        """.format(type_filter, order), params)
        return cur.fetchall()


def cache_positive(conn, name, page_data):
    """Insert a successful Wikipedia resolution."""
    url = page_data.get("fullurl") or page_data.get("canonicalurl", "")
    extract = page_data.get("extract", "")
    wiki_title = page_data.get("title", "")

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO intelligence.wikipedia_knowledge
                (title_lower, wikipedia_title, extract, url, fetched_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (title_lower) DO NOTHING
        """, (name, wiki_title, extract, url))
    conn.commit()


def cache_negative(conn, name, entity_type, reason, methods_tried, sample_id):
    """Insert a failed resolution into the negative cache."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO intelligence.wikipedia_negative_cache
                (title_lower, entity_type, reason, methods_tried, sample_source_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (title_lower) DO UPDATE SET
                attempts = intelligence.wikipedia_negative_cache.attempts + 1,
                last_attempted = now(),
                methods_tried = EXCLUDED.methods_tried
        """, (name, entity_type, reason, methods_tried, sample_id))
    conn.commit()


# ── Resolve one entity ───────────────────────────────────────────

def resolve_one(name, entity_type):
    """
    Try all strategies in order.
    Returns (page_data, methods_tried, failure_reason).
    """
    methods = []

    # Strategy 1: exact title (try Title Case)
    methods.append("exact")
    page = try_exact(name.title())
    if page:
        return page, methods, None
    time.sleep(0.1)

    # Strategy 2: open search
    methods.append("search")
    page = try_search(name)
    if page:
        return page, methods, None
    time.sleep(0.1)

    # Strategy 3: quoted search for exact phrase
    methods.append("search_quoted")
    page = try_search(name, quoted=True)
    if page:
        return page, methods, None

    return None, methods, "no_results"


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Resolve entities to Wikipedia with negative caching"
    )
    parser.add_argument("--db-host", default="192.168.93.101")
    parser.add_argument("--db-port", type=int, default=5432)
    parser.add_argument("--db-name", default="news_intel")
    parser.add_argument("--db-user", default="newsapp")
    parser.add_argument("--db-password", required=True)
    parser.add_argument("--types", nargs="*",
                        help="Entity types to filter, e.g. person org location")
    parser.add_argument("--limit", type=int, default=100,
                        help="Max entities to process this run")
    parser.add_argument("--randomize", action="store_true",
                        help="Randomize candidate order")
    parser.add_argument("--retry-stale-days", type=int, default=0,
                        help="Re-try negative cache entries older than N days")
    args = parser.parse_args()

    conn = get_connection(
        args.db_host, args.db_port, args.db_name, args.db_user, args.db_password,
    )
    log.info("Connected to %s:%s/%s", args.db_host, args.db_port, args.db_name)

    # Optionally clear stale negative-cache entries for retry
    if args.retry_stale_days > 0:
        cutoff = datetime.utcnow() - timedelta(days=args.retry_stale_days)
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM intelligence.wikipedia_negative_cache
                WHERE last_attempted < %s AND reason = 'no_results'
            """, (cutoff,))
            cleared = cur.rowcount
        conn.commit()
        log.info("Cleared %d stale negative-cache entries for retry", cleared)

    # Fetch candidates
    candidates = get_unresolved_entities(
        conn,
        entity_types=args.types,
        limit=args.limit,
        randomize=args.randomize,
    )
    log.info("Found %d candidates to resolve", len(candidates))

    stats = {"resolved": 0, "prefiltered": 0, "failed": 0}

    for i, row in enumerate(candidates):
        name = row["name"]
        etype = row["etype"]
        sample_id = row["sample_id"]

        # Pre-filter obvious junk
        bad_reason = classify_bad_entity(name, etype)
        if bad_reason:
            cache_negative(conn, name, etype, bad_reason, ["prefilter"], sample_id)
            stats["prefiltered"] += 1
            log.debug("Prefiltered '%s': %s", name, bad_reason)
            continue

        # Try Wikipedia
        page_data, methods, failure_reason = resolve_one(name, etype)

        if page_data:
            cache_positive(conn, name, page_data)
            stats["resolved"] += 1
            log.debug("Resolved '%s' -> '%s'", name, page_data.get("title"))
        else:
            cache_negative(conn, name, etype, failure_reason, methods, sample_id)
            stats["failed"] += 1
            log.debug("Failed '%s': %s (tried %s)", name, failure_reason, methods)

        if (i + 1) % 10 == 0:
            log.info(
                "Progress %d/%d  resolved=%d  prefiltered=%d  failed=%d",
                i + 1, len(candidates),
                stats["resolved"], stats["prefiltered"], stats["failed"],
            )

        time.sleep(0.15)

    log.info(
        "Done -- resolved=%d  prefiltered=%d  failed=%d",
        stats["resolved"], stats["prefiltered"], stats["failed"],
    )
    conn.close()


if __name__ == "__main__":
    main()
PYEOF

echo "✓ Created scripts/resolve_entities_wikipedia.py"

# ── 5. Run the migration ─────────────────────────────────────────
echo ""
echo "=== Running migration against $DB_HOST:$DB_PORT/$DB_NAME ==="
PGPASSWORD="$DB_PASS" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -f migrations/007_wikipedia_negative_cache.sql

echo ""
echo "=== All done! ==="
echo ""
echo "To run the resolver:"
echo "  python3 scripts/resolve_entities_wikipedia.py --db-password '$DB_PASS' --limit 100 --randomize"
echo ""
echo "To check results afterward:"
echo "  PGPASSWORD='$DB_PASS' psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c \\"
echo "    \"SELECT reason, count(*) FROM intelligence.wikipedia_negative_cache GROUP BY reason ORDER BY count DESC;\""

