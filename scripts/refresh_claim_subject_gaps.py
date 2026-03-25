#!/usr/bin/env python3
"""Rebuild intelligence.claim_subject_gap_catalog (same logic as POST /api/context_centric/claim_subject_gaps/refresh)."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--min-confidence", type=float, default=None)
    p.add_argument("--max-per-domain", type=int, default=2000)
    args = p.parse_args()

    from services.claim_subject_gap_service import refresh_claim_subject_gap_catalog

    out = refresh_claim_subject_gap_catalog(
        min_confidence=args.min_confidence,
        max_per_domain=args.max_per_domain,
    )
    print(out)


if __name__ == "__main__":
    main()
