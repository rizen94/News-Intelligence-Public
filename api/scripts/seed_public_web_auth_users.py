#!/usr/bin/env python3
"""Create or update admin + guest users for NEWS_INTEL_PUBLIC_WEB_AUTH (bcrypt passwords).

Reads passwords from env (never logged):
  NEWS_INTEL_BOOTSTRAP_ADMIN_PASSWORD
  NEWS_INTEL_BOOTSTRAP_GUEST_PASSWORD (optional)

Example:
  NEWS_INTEL_BOOTSTRAP_ADMIN_PASSWORD='...' \\
  NEWS_INTEL_BOOTSTRAP_GUEST_PASSWORD='...' \\
  PYTHONPATH=api uv run python api/scripts/seed_public_web_auth_users.py

Requires migration 217 applied (user_profiles.roles).
"""

from __future__ import annotations

import json
import os
import sys

_API_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API_ROOT)

from datetime import datetime

from shared.database.connection import get_db_connection
from shared.migration_sql_runner import bootstrap_migration_env
from shared.services.public_web_auth_service import hash_password


def upsert_user(cur, *, username: str, email: str, password: str, roles: list[str], full_name: str) -> None:
    ph = hash_password(password)
    roles_json = json.dumps(roles)
    now = datetime.now()
    cur.execute("SELECT id FROM user_profiles WHERE username = %s LIMIT 1", (username,))
    row = cur.fetchone()
    if row:
        cur.execute(
            """
            UPDATE user_profiles
            SET email = %s, password_hash = %s, full_name = %s, updated_at = %s, roles = %s::jsonb
            WHERE id = %s
            """,
            (email, ph, full_name, now, roles_json, row[0]),
        )
    else:
        cur.execute(
            """
            INSERT INTO user_profiles (username, email, password_hash, full_name, created_at, updated_at, roles)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (username, email, ph, full_name, now, now, roles_json),
        )


def main() -> int:
    bootstrap_migration_env()
    admin_pw = os.environ.get("NEWS_INTEL_BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    guest_pw = os.environ.get("NEWS_INTEL_BOOTSTRAP_GUEST_PASSWORD", "").strip()
    if not admin_pw:
        print(
            "ERROR: Set NEWS_INTEL_BOOTSTRAP_ADMIN_PASSWORD in the environment.",
            file=sys.stderr,
        )
        return 1

    conn = get_db_connection()
    if not conn:
        print("ERROR: Database connection failed", file=sys.stderr)
        return 1
    try:
        with conn.cursor() as cur:
            upsert_user(
                cur,
                username=os.environ.get("NEWS_INTEL_BOOTSTRAP_ADMIN_USERNAME", "admin"),
                email=os.environ.get("NEWS_INTEL_BOOTSTRAP_ADMIN_EMAIL", "admin@local"),
                password=admin_pw,
                roles=["admin"],
                full_name=os.environ.get("NEWS_INTEL_BOOTSTRAP_ADMIN_FULL_NAME", "Administrator"),
            )
            if guest_pw:
                upsert_user(
                    cur,
                    username=os.environ.get("NEWS_INTEL_BOOTSTRAP_GUEST_USERNAME", "guest"),
                    email=os.environ.get("NEWS_INTEL_BOOTSTRAP_GUEST_EMAIL", "guest@local"),
                    password=guest_pw,
                    roles=["guest"],
                    full_name=os.environ.get("NEWS_INTEL_BOOTSTRAP_GUEST_FULL_NAME", "Guest"),
                )
            conn.commit()
        print("OK: bootstrap user(s) upserted.")
        return 0
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
