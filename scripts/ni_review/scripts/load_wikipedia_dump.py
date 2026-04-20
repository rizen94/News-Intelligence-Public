#!/usr/bin/env python3
"""
Load Wikipedia abstract dump into intelligence.wikipedia_knowledge.

Downloads enwiki-latest-abstract.xml.gz from dumps.wikimedia.org, parses it,
and batch-inserts into PostgreSQL. Run migration 170 first.

Usage (from project root):
  PYTHONPATH=api python scripts/load_wikipedia_dump.py [--limit N] [--batch-size 5000] [--url URL]

Optional:
  --limit       Max number of articles to load (default: no limit)
  --batch-size  Rows per INSERT batch (default: 5000)
  --url         Override dump URL (default may 404; abstract dumps were discontinued)
  --file        Use local .xml.gz file instead of downloading (recommended if you have a dump)
  --dry-run     Parse and print sample, do not connect to DB

After loading, run scripts/populate_wikipedia_aliases.py to fill aliases from redirects
for smarter matching (e.g. "GOP" -> "Republican Party (United States)").

Alternate if default URL 404s: (1) Use backfill with --api-fallback (no dump). (2) Use --file
with a local abstract-format .xml.gz if you have one. (3) Cirrus/search dumps use a different
format and would need a separate parser; full enwiki pages-articles are large (~20GB+ bz2).
"""

import argparse
import gzip
import hashlib
import logging
import os
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, Generator, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Abstract dump was discontinued; use --file with a local dump or another source.
DEFAULT_URL = "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-abstract.xml.gz"
BATCH_SIZE_DEFAULT = 5000


def _normalize_title(raw: str) -> str:
    """Strip 'Wikipedia: ' prefix and strip whitespace."""
    t = (raw or "").strip()
    if t.startswith("Wikipedia:"):
        t = t[10:].strip()
    return t


def _title_to_page_id(title_lower: str) -> int:
    """Deterministic stable integer from title for use as page_id when dump has no id."""
    h = hashlib.sha256(title_lower.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % (2**31 - 1)


def _stream_download(url: str, dest: str) -> str:
    """Download url to dest; return path to local file."""
    import urllib.request
    logger.info("Downloading %s -> %s", url, dest)
    urllib.request.urlretrieve(url, dest)
    return dest


def load_into_db(
    rows: Generator[Dict[str, Any], None, None],
    batch_size: int = BATCH_SIZE_DEFAULT,
    conn=None,
) -> int:
    """Insert rows into intelligence.wikipedia_knowledge. UPSERT by page_id."""
    if conn is None:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
        from shared.database.connection import get_db_connection
        conn = get_db_connection()
    if not conn:
        raise RuntimeError("No database connection")
    cur = conn.cursor()
    total = 0
    batch = []
    for row in rows:
        batch.append((
            row["page_id"],
            row["title"],
            row["title_lower"],
            row["abstract"],
            row.get("page_url") or "",
        ))
        if len(batch) >= batch_size:
            _upsert_batch(cur, batch)
            conn.commit()
            total += len(batch)
            logger.info("Inserted %d rows (total %d)", len(batch), total)
            batch = []
    if batch:
        _upsert_batch(cur, batch)
        conn.commit()
        total += len(batch)
    cur.close()
    return total


def _upsert_batch(cur, batch: list) -> None:
    """Execute INSERT ... ON CONFLICT (page_id) DO UPDATE for batch."""
    from psycopg2.extras import execute_values
    sql = """
    INSERT INTO intelligence.wikipedia_knowledge (page_id, title, title_lower, abstract, page_url)
    VALUES %s
    ON CONFLICT (page_id) DO UPDATE SET
        title = EXCLUDED.title,
        title_lower = EXCLUDED.title_lower,
        abstract = EXCLUDED.abstract,
        page_url = EXCLUDED.page_url,
        loaded_at = NOW()
    """
    execute_values(cur, sql, batch, page_size=len(batch))


def main():
    parser = argparse.ArgumentParser(description="Load Wikipedia abstract dump into PostgreSQL")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to load")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT, help="Batch size for INSERT")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help="URL of abstract dump")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no DB")
    parser.add_argument("--file", type=str, default=None, help="Use local file instead of downloading")
    args = parser.parse_args()

    path = args.file
    if not path:
        dest = os.path.join(os.path.dirname(__file__), "..", "data", "enwiki-latest-abstract.xml.gz")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if not os.path.isfile(dest):
            path = _stream_download(args.url, dest)
        else:
            path = dest
            logger.info("Using existing file %s", path)

    # Parse abstract dump: <doc> or <page> with <title>, <url>, <abstract>
    def parse_iterparse():
        open_fn = gzip.open if path.endswith(".gz") else open
        count = 0
        limit = args.limit
        with open_fn(path, "rb") as f:
            for _event, elem in ET.iterparse(f, events=("end",)):
                if elem.tag in ("doc", "page"):
                    title_el = elem.find("title")
                    url_el = elem.find("url")
                    abstract_el = elem.find("abstract")
                    if title_el is not None and title_el.text:
                        title = _normalize_title(title_el.text)
                        if title:
                            title_lower = title.lower()
                            abstract = (abstract_el.text or "").strip() if abstract_el is not None and abstract_el.text else title
                            page_url = (url_el.text or "").strip() if url_el is not None and url_el.text else ""
                            page_id = _title_to_page_id(title_lower)
                            yield {
                                "page_id": page_id,
                                "title": title[:500],
                                "title_lower": title_lower[:500],
                                "abstract": abstract or title,
                                "page_url": page_url[:500] if page_url else None,
                            }
                            count += 1
                            if limit and count >= limit:
                                return
                elem.clear()

    try:
        rows = parse_iterparse()
        if args.dry_run:
            for i, row in enumerate(rows):
                print(row)
                if i >= 4:
                    break
            logger.info("Dry run done")
            return
        total = load_into_db(rows, batch_size=args.batch_size)
        logger.info("Loaded %d rows into intelligence.wikipedia_knowledge", total)
    except Exception as e:
        logger.exception("%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
