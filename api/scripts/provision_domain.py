#!/usr/bin/env python3
"""
Provision a new domain silo in order: preflight → SQL → (commit) → RSS seed → (commit) → verify → success banner.
On failure after DB mutations, runs teardown for the target schema/domain_key only.

Usage (from repo root):
  PYTHONPATH=api uv run python api/scripts/provision_domain.py --config api/config/domains/legal.yaml \\
    --sql api/database/migrations/180_legal_domain_silo.sql \\
    --verify-cmd "PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py"

  --dry-run   Print phases only.
  --ack-backup  Required acknowledgement flag for production-style runs (no backup performed here).
  --teardown-only  Only run teardown for domain_key/schema_name from config (dangerous).
  --no-seed-rss / --skip-rss-seed  Skip inserting data_sources.rss.seed_feed_urls into {schema}.rss_feeds.
  --print-checklist-only  Print post-install checklist and exit (needs --config; no DB).
  --no-activate-in-db  Skip UPDATE public.domains SET is_active = TRUE (default is to activate).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    _api_dir = Path(__file__).resolve().parent.parent
    load_dotenv(_api_dir / ".env", override=False)
    load_dotenv(_api_dir.parent / ".env", override=False)
except ImportError:
    pass

if (
    not os.environ.get("DB_PASSWORD")
    and Path(Path(__file__).resolve().parent.parent.parent / ".db_password_widow").is_file()
):
    try:
        with open(Path(__file__).resolve().parent.parent.parent / ".db_password_widow") as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except OSError:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402
from psycopg2 import sql as psql  # noqa: E402
from shared.database.connection import get_db_connection  # noqa: E402
from shared.domain_registry import RESERVED_SCHEMA_NAMES  # noqa: E402
from shared.services.domain_rss_seed import seed_from_domain_config  # noqa: E402
from shared.services.domain_silo_post_migration import activate_domain_row  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_config(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data or not isinstance(data, dict):
        raise SystemExit(f"Invalid or empty YAML: {path}")
    return data


def _preflight_schema_empty(cur, schema_name: str) -> tuple[bool, str]:
    cur.execute(
        """
        SELECT EXISTS(
          SELECT 1 FROM information_schema.schemata WHERE schema_name = %s
        )
        """,
        (schema_name,),
    )
    exists = cur.fetchone()[0]
    if not exists:
        return True, "schema does not exist (ok for create)"
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        """,
        (schema_name,),
    )
    n = cur.fetchone()[0]
    if n == 0:
        return True, "schema exists but empty"
    return False, f"schema already has {n} tables — refuse without --teardown-only"


def _domain_row_matches(cur, domain_key: str, schema_name: str) -> bool:
    """True when public.domains already has this URL key + Postgres schema (e.g. after a numbered migration)."""
    cur.execute(
        "SELECT 1 FROM public.domains WHERE domain_key = %s AND schema_name = %s",
        (domain_key, schema_name),
    )
    return cur.fetchone() is not None


def _preflight_public_domains(cur, domain_key: str, schema_name: str) -> tuple[bool, str]:
    """Ensure YAML domain_key/schema_name does not conflict with existing public.domains rows."""
    cur.execute(
        "SELECT schema_name FROM public.domains WHERE domain_key = %s",
        (domain_key,),
    )
    row = cur.fetchone()
    if row and row[0] != schema_name:
        return (
            False,
            f"public.domains has domain_key={domain_key!r} with schema_name={row[0]!r}, "
            f"YAML has {schema_name!r}",
        )
    cur.execute(
        """
        SELECT domain_key FROM public.domains
        WHERE schema_name = %s AND domain_key <> %s
        """,
        (schema_name, domain_key),
    )
    row2 = cur.fetchone()
    if row2:
        return (
            False,
            f"schema_name {schema_name!r} already belongs to domain_key={row2[0]!r}",
        )
    return True, ""


def print_post_provision_checklist(
    domain_key: str,
    schema_name: str,
    *,
    config_path: str | None = None,
) -> None:
    cfg = f"\n  Config file: {config_path}" if config_path else ""
    print(
        """
--- Post-provision checklist ---
[ ] public.domains: row exists with is_active = TRUE (this script does that by default; use --no-activate-in-db to skip).
    Align YAML is_active: true so API/registry and RSS collection agree (see api/config/domains/README.md).
[ ] Onboarding YAML: set is_active: true; API domain path pattern accepts new keys without restart;
    is_valid_domain_key() reads YAML each call — reload workers only if they cache domain lists elsewhere.
[ ] api/config/domain_synthesis_config.yaml: add a block for this domain if synthesis/topic bias
    should differ from defaults (separate from api/config/domains/*.yaml).
[ ] Grep for hardcoded domain lists until fully centralized, e.g.:
      rg "science.tech|science_tech|politics.*finance" api web --glob "*.py" --glob "*.ts" --glob "*.tsx"
[ ] public.applied_migrations: register the silo migration if your ops require the ledger
    (api/scripts/register_applied_migration.py).
[ ] RSS: data_sources.rss.seed_feed_urls applied by this script unless --skip-rss-seed; backfill:
      PYTHONPATH=api uv run python api/scripts/seed_domain_rss_from_yaml.py --config <yaml>"""
        + cfg
        + f"""

Target: domain_key={domain_key!r}  schema_name={schema_name!r}
---"""
    )


def teardown_domain(cur, domain_key: str, schema_name: str) -> None:
    """Remove only this domain's silo and registry rows (order respects FKs)."""
    cur.execute("SELECT id FROM public.domains WHERE domain_key = %s", (domain_key,))
    row = cur.fetchone()
    if row:
        domain_id = row[0]
        cur.execute("DELETE FROM public.domain_metadata WHERE domain_id = %s", (domain_id,))
        cur.execute("DELETE FROM public.domains WHERE id = %s", (domain_id,))
    cur.execute(psql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(psql.Identifier(schema_name)))
    print(
        f"  [teardown] rolled back new domain only: domain_key={domain_key} schema={schema_name}",
        file=sys.stderr,
    )


def apply_sql_file(conn, sql_path: Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute(sql)


def run_verify(cmd: str) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(_REPO_ROOT / "api"))
    return subprocess.run(cmd, shell=True, cwd=str(_REPO_ROOT), env=env).returncode


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision domain silo (ordered + teardown on failure)"
    )
    parser.add_argument(
        "--config", required=True, type=Path, help="Path to api/config/domains/{key}.yaml"
    )
    parser.add_argument("--sql", type=Path, help="SQL migration file to apply")
    parser.add_argument(
        "--verify-cmd", type=str, default="", help="Shell command; non-zero triggers teardown"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--ack-backup",
        action="store_true",
        help="Acknowledge backup was taken (required if --require-backup-ack)",
    )
    parser.add_argument(
        "--require-backup-ack", action="store_true", help="Refuse unless --ack-backup"
    )
    parser.add_argument(
        "--skip-verify", action="store_true", help="Skip verify (disables rollback guarantee)"
    )
    parser.add_argument(
        "--teardown-only", action="store_true", help="Only run teardown for this domain"
    )
    parser.add_argument(
        "--no-seed-rss",
        "--skip-rss-seed",
        dest="skip_rss_seed",
        action="store_true",
        help="Do not insert data_sources.rss.seed_feed_urls into {schema}.rss_feeds after SQL",
    )
    parser.add_argument(
        "--print-checklist-only",
        action="store_true",
        help="Print post-install checklist for the domain in --config and exit (no DB)",
    )
    parser.add_argument(
        "--no-activate-in-db",
        action="store_true",
        help="Do not UPDATE public.domains SET is_active=TRUE after successful run (default activates)",
    )
    args = parser.parse_args()

    if args.require_backup_ack and not args.ack_backup:
        raise SystemExit("Refusing: use --ack-backup after taking a DB backup.")

    cfg = _load_config(args.config)
    domain_key = cfg.get("domain_key")
    schema_name = cfg.get("schema_name")
    if not domain_key or not schema_name:
        raise SystemExit("YAML must define domain_key and schema_name")

    if not schema_name.replace("_", "").isalnum() or not schema_name.islower():
        raise SystemExit("schema_name must be lowercase snake_case alphanumerics only")
    if domain_key in ("politics", "finance", "science-tech"):
        raise SystemExit("Refusing: core silos are not provisioned with this script")

    if args.print_checklist_only:
        print_post_provision_checklist(
            domain_key, schema_name, config_path=str(args.config.resolve())
        )
        return

    if args.dry_run:
        print("dry-run: would preflight, apply SQL, RSS seed, verify, or teardown-only")
        print(f"  domain_key={domain_key} schema_name={schema_name}")
        return

    conn = get_db_connection()
    if not conn:
        raise SystemExit("No database connection")

    try:
        with conn.cursor() as cur:
            if args.teardown_only:
                teardown_domain(cur, domain_key, schema_name)
                conn.commit()
                print("Teardown complete.")
                return

            already_registered = _domain_row_matches(cur, domain_key, schema_name)
            if not already_registered:
                if schema_name in RESERVED_SCHEMA_NAMES:
                    raise SystemExit(
                        "Refusing: schema_name is reserved (system/core). "
                        "Use a different schema_name for a new optional domain."
                    )
                ok, msg = _preflight_schema_empty(cur, schema_name)
                if not ok:
                    raise SystemExit(f"Preflight failed: {msg}")
            ok2, msg2 = _preflight_public_domains(cur, domain_key, schema_name)
            if not ok2:
                raise SystemExit(f"Preflight failed: {msg2}")

        if args.sql:
            try:
                apply_sql_file(conn, args.sql)
                conn.commit()
                if not args.skip_rss_seed:
                    added, skipped = seed_from_domain_config(conn, cfg, schema_name)
                    if added or skipped:
                        print(
                            f"  [rss] seeded {added} new feed(s), "
                            f"{skipped} already in {schema_name}.rss_feeds"
                        )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                with conn.cursor() as cur:
                    teardown_domain(cur, domain_key, schema_name)
                conn.commit()
                raise SystemExit(f"SQL or RSS seed failed, tore down target domain: {e}") from e

        if args.verify_cmd and not args.skip_verify:
            rc = run_verify(args.verify_cmd)
            if rc != 0:
                with conn.cursor() as cur:
                    teardown_domain(cur, domain_key, schema_name)
                conn.commit()
                raise SystemExit(f"Verify failed (exit {rc}), tore down target domain")

        if not args.no_activate_in_db:
            if activate_domain_row(conn, domain_key) == 0:
                print(
                    "  [warn] activate-in-db: no public.domains row updated "
                    f"(domain_key={domain_key!r} missing?)",
                    file=sys.stderr,
                )
            conn.commit()

        conn.commit()
        print("✅ Provision complete for", domain_key)
        print(
            "Next: set YAML is_active: true if not already; SPA loads domains from "
            "GET /api/system_monitoring/registry_domains. RSS/pipeline use url_schema_pairs() "
            "(reads YAML each run) once feeds exist."
        )
        print_post_provision_checklist(
            domain_key, schema_name, config_path=str(args.config.resolve())
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
