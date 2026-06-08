#!/usr/bin/env python3
"""Pre-start DB probe for systemd (news-intelligence-api-public.service)."""
from __future__ import annotations

import sys
from pathlib import Path

# Load project .env when run from repo root on Widow
_root = Path(__file__).resolve().parent.parent
_api = _root / "api"
if _api.is_dir():
    sys.path.insert(0, str(_api))

try:
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("systemd_db_probe: database connection failed", file=sys.stderr)
        sys.exit(1)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
except Exception as exc:
    print(f"systemd_db_probe: {exc}", file=sys.stderr)
    sys.exit(1)

print("systemd_db_probe: database OK")
sys.exit(0)
