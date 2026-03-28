#!/usr/bin/env python3
"""
Mark many (subject_norm, domain_key) pairs as ``ignored`` in intelligence.claim_subject_gap_catalog
so claims→facts skips them (same logic as single-row POST .../ignore).

Reads one normalized subject per line from a file (or stdin). Lines starting with # are skipped.

  PYTHONPATH=api uv run python api/scripts/claim_subject_gap_bulk_ignore.py --domain-key politics --file subjects.txt
  cat subjects.txt | PYTHONPATH=api uv run python api/scripts/claim_subject_gap_bulk_ignore.py --domain-key finance --stdin

Use POST /api/context_centric/claim_subject_gaps/bulk_ignore for the same from the API.
"""

from __future__ import annotations

import argparse
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


def _read_lines(path: str | None, use_stdin: bool) -> list[str]:
    if use_stdin:
        return sys.stdin.read().splitlines()
    if not path:
        raise SystemExit("Provide --file or --stdin")
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--domain-key", required=True, help="URL domain key, e.g. politics, finance-2")
    p.add_argument("--file", help="Path to newline-delimited subject strings")
    p.add_argument("--stdin", action="store_true", help="Read subjects from stdin")
    p.add_argument("--notes", default="", help="Optional operator note stored on catalog rows")
    p.add_argument("--dry-run", action="store_true", help="Print count only, no DB writes")
    args = p.parse_args()

    raw = _read_lines(args.file, args.stdin)
    norms = []
    for line in raw:
        s = (line or "").strip()
        if not s or s.startswith("#"):
            continue
        norms.append(s)

    if args.dry_run:
        print(f"Would upsert {len(norms)} ignored row(s) for domain_key={args.domain_key!r}")
        return 0

    from services.claim_subject_gap_service import bulk_ignore_subjects

    out = bulk_ignore_subjects(
        args.domain_key.strip().lower(),
        norms,
        notes=(args.notes or None),
    )
    print(out)
    return 0 if out.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
