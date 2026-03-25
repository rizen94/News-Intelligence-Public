#!/usr/bin/env python3
"""
Fetch ISO country list from restcountries.com (public JSON, no API key) and seed
``entity_canonical`` as ``subject`` for each active domain — strong alias coverage
(cca2, cca3, common name, native names).

  PYTHONPATH=api uv run python api/scripts/restcountries_seed.py
  PYTHONPATH=api uv run python api/scripts/restcountries_seed.py --domains legal,medicine
  PYTHONPATH=api uv run python api/scripts/restcountries_seed.py --dry-run
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

RESTCOUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=name,cca2,cca3,altSpellings"


def _resolve_seed_domain_keys(domains_arg: str) -> set[str]:
    """``all`` or empty = every key from ``get_active_domain_keys()`` (all onboarded silos)."""
    from shared.domain_registry import get_active_domain_keys

    raw = (domains_arg or "").strip()
    if not raw or raw.lower() == "all":
        return set(get_active_domain_keys())
    return {x.strip() for x in raw.split(",") if x.strip()}


def _aliases_from_country(obj: dict) -> list[str]:
    out: list[str] = []
    name = obj.get("name") or {}
    common = (name.get("common") or "").strip()
    official = (name.get("official") or "").strip()
    for s in (common, official):
        if s and s not in out:
            out.append(s)
    nat = name.get("nativeName") or {}
    for _code, blob in nat.items():
        if isinstance(blob, dict):
            for k in ("common", "official"):
                v = (blob.get(k) or "").strip()
                if v and v not in out:
                    out.append(v)
    cca2 = (obj.get("cca2") or "").strip().upper()
    cca3 = (obj.get("cca3") or "").strip().upper()
    for s in (cca2, cca3):
        if s and len(s) >= 2 and s not in out:
            out.append(s)
    for a in obj.get("altSpellings") or []:
        if isinstance(a, str) and len(a.strip()) >= 2:
            t = a.strip()
            if t.lower() not in {x.lower() for x in out}:
                out.append(t)
    # canonical is common name
    primary = common or official or (out[0] if out else "")
    aliases = [a for a in out if primary and a.lower() != primary.lower()]
    return primary, aliases


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Fetch and print counts only")
    p.add_argument("--no-sync", action="store_true", help="Skip entity_profile_sync")
    p.add_argument(
        "--domains",
        default="all",
        help="Comma-separated domain_key list, or 'all' (default): every active silo from domain_registry",
    )
    args = p.parse_args()

    want = _resolve_seed_domain_keys(args.domains)
    print(f"Target silos: {', '.join(sorted(want))}", flush=True)

    import requests

    r = requests.get(
        RESTCOUNTRIES_URL,
        timeout=120,
        headers={
            "User-Agent": "NewsIntelligence-restcountries-seed/1.0 (entity matching; open data)",
            "Accept": "application/json",
        },
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        print("ERROR: unexpected JSON shape")
        return 1

    entries: list[dict] = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        primary, aliases = _aliases_from_country(obj)
        if len(primary) < 2:
            continue
        entries.append(
            {
                "name": primary,
                "entity_type": "subject",
                "aliases": aliases[:40],
            }
        )

    print(f"RestCountries: {len(entries)} countries with aliases", flush=True)
    if args.dry_run:
        print("Dry-run — no DB writes")
        return 0

    from shared.domain_registry import get_active_domain_keys, is_valid_domain_key

    from services.entity_seed_catalog_service import bulk_seed_canonical_entries

    total_ins = 0
    for dk in get_active_domain_keys():
        if dk not in want:
            continue
        if not is_valid_domain_key(dk):
            continue
        out = bulk_seed_canonical_entries(
            dk,
            entries,
            sync_profiles=not args.no_sync,
        )
        print(f"{dk}: {out}", flush=True)
        if out.get("success"):
            total_ins += int(out.get("inserted", 0) or 0)
    print(f"Done. Sum inserted (new rows): {total_ins}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
