#!/usr/bin/env python3
"""
Run Wikidata SPARQL (query.wikidata.org) and seed entity_canonical via bulk_seed_canonical_entries.

Presets (English labels):
  countries       — instance of country (Q6256)
  central_banks   — instance of central bank (Q66344)
  universities    — instance of university (Q3918), limit 400
  us_senate       — current US senators (position held P39 = US senator Q4416090)

  PYTHONPATH=api uv run python api/scripts/wikidata_sparql_seed.py --preset countries --domain politics
  PYTHONPATH=api uv run python api/scripts/wikidata_sparql_seed.py --sparql-file ./my.rq --domain politics --type organization

Respect https://wikimediafoundation.org/wiki/Policy:User-Agent — a descriptive UA is set below.
"""

from __future__ import annotations

import argparse
import json
import os
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

WD_SPARQL = "https://query.wikidata.org/sparql"
USER_AGENT = "NewsIntelligence-wikidata-seed/1.0 (https://github.com/; entity resolution)"

PRESETS: dict[str, str] = {
    "countries": """
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q6256 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 600
""",
    "central_banks": """
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q66344 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 400
""",
    "universities": """
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q3918 .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 400
""",
    "us_senate": """
SELECT DISTINCT ?person ?personLabel WHERE {
  ?person wdt:P31 wd:Q5 .
  ?person p:P39 ?stmt .
  ?stmt ps:P39 wd:Q4416090 .
  FILTER NOT EXISTS { ?stmt pq:P582 ?ended . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 150
""",
}


def _run_sparql(query: str) -> list[tuple[str, str]]:
    import requests

    r = requests.get(
        WD_SPARQL,
        params={"query": query, "format": "json"},
        timeout=180,
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
    )
    r.raise_for_status()
    js = r.json()
    bindings = (js.get("results") or {}).get("bindings") or []
    out: list[tuple[str, str]] = []
    for b in bindings:
        label = None
        uri = None
        for k, v in b.items():
            if not isinstance(v, dict):
                continue
            if k.endswith("Label") and v.get("value"):
                label = str(v["value"]).strip()
            if v.get("type") == "uri" and "wikidata.org" in str(v.get("value", "")):
                uri = v.get("value")
        if label and len(label) >= 2:
            out.append((uri or "", label))
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--preset", choices=sorted(PRESETS.keys()), help="Built-in SPARQL")
    p.add_argument("--sparql-file", help="Path to .rq file (overrides preset)")
    p.add_argument("--domain", required=True, help="domain_key e.g. politics")
    p.add_argument(
        "--type",
        default="organization",
        help="entity_type for preset rows: person | organization | subject (default organization)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-sync", action="store_true")
    p.add_argument("--output-csv", help="Write label list to CSV and exit (no DB)")
    args = p.parse_args()

    if args.sparql_file:
        with open(os.path.abspath(args.sparql_file), encoding="utf-8") as f:
            query = f.read()
    elif args.preset:
        query = PRESETS[args.preset]
    else:
        print("ERROR: provide --preset or --sparql-file")
        return 1

    rows = _run_sparql(query)
    # Dedupe by label case-insensitive
    seen: set[str] = set()
    unique: list[str] = []
    for _uri, lab in rows:
        k = lab.lower()
        if k in seen:
            continue
        seen.add(k)
        unique.append(lab)

    print(f"Wikidata: {len(unique)} unique labels", flush=True)
    if args.output_csv:
        import csv

        with open(args.output_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["canonical_name", "entity_type"])
            for lab in unique:
                w.writerow([lab, args.type])
        print(f"Wrote {args.output_csv}")
        return 0

    if args.dry_run:
        for lab in unique[:25]:
            print(f"  {lab}")
        if len(unique) > 25:
            print(f"  ... and {len(unique) - 25} more")
        return 0

    et_default = args.type
    if args.preset == "countries":
        et_default = "subject"
    elif args.preset == "us_senate":
        et_default = "person"
    elif args.preset in ("universities", "central_banks"):
        et_default = "organization"

    entries = [{"name": lab, "entity_type": et_default} for lab in unique]

    from shared.domain_registry import is_valid_domain_key

    from services.entity_seed_catalog_service import bulk_seed_canonical_entries

    if not is_valid_domain_key(args.domain):
        print(f"ERROR: invalid domain {args.domain}")
        return 1

    out = bulk_seed_canonical_entries(
        args.domain,
        entries,
        sync_profiles=not args.no_sync,
    )
    print(out)
    return 0 if out.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
