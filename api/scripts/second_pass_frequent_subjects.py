#!/usr/bin/env python3
"""
Second pass: high-frequency strings from extracted_claims.subject_text or article_entities.entity_name
that are not yet good canonicals — seed as ``subject`` (or chosen type) to improve matching.

Skips very short strings, numeric-only, and common junk fragments.

  PYTHONPATH=api uv run python api/scripts/second_pass_frequent_subjects.py --source claims --min-count 8 --limit 200
  PYTHONPATH=api uv run python api/scripts/second_pass_frequent_subjects.py --source article_entities --schema politics
"""

from __future__ import annotations

import argparse
import os
import re
import sys

API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(API_ROOT)
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(API_ROOT, ".env"), override=False)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(PROJECT_ROOT, ".db_password_widow")
):
    try:
        with open(os.path.join(PROJECT_ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

SKIP_SUBSTRINGS = frozenset(
    x.lower()
    for x in (
        "no name",
        "mentioned",
        "unknown",
        "not specified",
        "the administration",
        "white house",
    )
)

STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "company",
        "administration",
        "government",
        "officials",
        "sources",
        "report",
    }
)


def _is_candidate(s: str) -> bool:
    t = (s or "").strip()
    if len(t) < 3 or len(t) > 120:
        return False
    low = t.lower()
    if low in STOPWORDS:
        return False
    if any(sw in low for sw in SKIP_SUBSTRINGS):
        return False
    if re.match(r"^[\d,.\s%$€£]+$", t):
        return False
    if low.startswith("the ") and len(t) < 12:
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=("claims", "article_entities"), default="claims")
    p.add_argument(
        "--schema",
        default="",
        help="Override schema for article_entities (default: from --domain)",
    )
    p.add_argument("--min-count", type=int, default=6)
    p.add_argument("--limit", type=int, default=250)
    p.add_argument("--domain", default="politics", help="domain_key for bulk_seed")
    p.add_argument("--type", default="subject", help="entity_type for seeded rows")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-sync", action="store_true")
    p.add_argument("--min-confidence", type=float, default=0.65, help="claims only: min ec.confidence")
    args = p.parse_args()

    from shared.database.connection import get_db_connection
    from shared.domain_registry import is_valid_domain_key, resolve_domain_schema

    from services.entity_seed_catalog_service import bulk_seed_canonical_entries

    if not is_valid_domain_key(args.domain):
        print(f"ERROR: invalid domain {args.domain}")
        return 1

    conn = get_db_connection()
    if not conn:
        print("ERROR: no DB")
        return 1

    rows: list[tuple[str, int]] = []
    try:
        with conn.cursor() as cur:
            if args.source == "claims":
                cur.execute(
                    """
                    SELECT MIN(ec.subject_text), COUNT(*)::int
                    FROM intelligence.extracted_claims ec
                    WHERE ec.confidence >= %s
                      AND length(trim(ec.subject_text)) >= 3
                    GROUP BY lower(trim(ec.subject_text))
                    ORDER BY 2 DESC
                    LIMIT 5000
                    """,
                    (args.min_confidence,),
                )
                rows = [(r[0], int(r[1])) for r in cur.fetchall() if r and r[0]]
            else:
                sch = (args.schema or "").strip() or resolve_domain_schema(args.domain)
                cur.execute(
                    f"""
                    SELECT MIN(ae.entity_name), COUNT(*)::int
                    FROM {sch}.article_entities ae
                    WHERE length(trim(ae.entity_name)) >= 3
                    GROUP BY lower(trim(ae.entity_name))
                    ORDER BY 2 DESC
                    LIMIT 5000
                    """
                )
                rows = [(r[0], int(r[1])) for r in cur.fetchall() if r and r[0]]
    finally:
        conn.close()

    picked: list[str] = []
    for text, cnt in rows:
        if cnt < args.min_count:
            continue
        display = (text or "").strip()
        if not _is_candidate(display):
            continue
        if display not in picked:
            picked.append(display)
        if len(picked) >= args.limit:
            break

    print(f"Candidates after filters: {len(picked)} (from {len(rows)} frequency groups)", flush=True)
    if args.dry_run:
        for x in picked[:40]:
            print(f"  {x}")
        if len(picked) > 40:
            print(f"  ... +{len(picked) - 40}")
        return 0

    entries = [{"name": p, "entity_type": args.type} for p in picked]
    out = bulk_seed_canonical_entries(
        args.domain,
        entries,
        sync_profiles=not args.no_sync,
    )
    print(out)
    return 0 if out.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
