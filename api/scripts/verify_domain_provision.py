#!/usr/bin/env python3
"""
Final check for a new (or existing) domain silo: YAML, registry, Postgres schema,
catalog row, core tables, RSS seeds, and optional synthesis config.

Usage (from repo root):

  PYTHONPATH=api uv run python api/scripts/verify_domain_provision.py --config api/config/domains/legal.yaml
  PYTHONPATH=api uv run python api/scripts/verify_domain_provision.py --domain-key legal
  PYTHONPATH=api uv run python api/scripts/verify_domain_provision.py --domain-key legal --strict

  --strict   Also fail (exit 1) when there are warnings only (e.g. empty feeds, missing synthesis block).
  --yaml-only   Do not connect to the database (YAML + registry checks only).

Exits:
  0 — no errors (warnings may have been printed unless --strict)
  1 — any error-level check failed; or --strict with any warning; or invalid args / missing config
"""

from __future__ import annotations

import argparse
import os
import re
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

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

_CONFIG_DIR = _API / "config" / "domains"
_SYNTHESIS_CONFIG = _API / "config" / "domain_synthesis_config.yaml"

# Minimum silo surface for pipeline + UI (migration 180-style parity).
_CRITICAL_TABLES = frozenset(
    {"articles", "rss_feeds", "storylines", "topics"},
)
# Full parity with create_domain_table + story_entity_index pattern (migration 180).
_EXTENDED_TABLES = frozenset(
    {
        "article_topic_assignments",
        "storyline_articles",
        "topic_clusters",
        "topic_cluster_memberships",
        "topic_learning_history",
        "entity_canonical",
        "article_entities",
        "story_entity_index",
    }
)


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as e:
        raise SystemExit(f"PyYAML required: {e}") from e
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Invalid or empty YAML: {path}")
    return data


def _synthesis_has_domain(domain_key: str) -> bool | None:
    """True if domain_key under ``domains:`` in domain_synthesis_config.yaml; None if file missing."""
    if not _SYNTHESIS_CONFIG.is_file():
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        raw = yaml.safe_load(_SYNTHESIS_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return None
    doms = (raw or {}).get("domains")
    if not isinstance(doms, dict):
        return False
    return domain_key in doms


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify domain onboarding: YAML, registry, DB schema, tables, RSS, synthesis hint."
    )
    parser.add_argument("--config", type=Path, help="Path to api/config/domains/<key>.yaml")
    parser.add_argument(
        "--domain-key",
        type=str,
        help="Domain URL key (loads api/config/domains/<domain-key>.yaml)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if there are warnings as well as errors (treat warnings as failures)",
    )
    parser.add_argument(
        "--yaml-only",
        action="store_true",
        help="Skip database checks (YAML + registry only)",
    )
    args = parser.parse_args()

    if bool(args.config) == bool(args.domain_key):
        raise SystemExit("Specify exactly one of --config or --domain-key")

    cfg_path = args.config if args.config else _CONFIG_DIR / f"{args.domain_key.strip()}.yaml"
    cfg_path = cfg_path.resolve()
    if not cfg_path.is_file():
        raise SystemExit(f"Config not found: {cfg_path}")

    data = _load_yaml(cfg_path)
    domain_key = (data.get("domain_key") or "").strip()
    schema_name = (data.get("schema_name") or "").strip()
    display_name = (data.get("display_name") or "").strip()
    is_active = data.get("is_active", True)

    errors: list[str] = []
    warnings: list[str] = []

    if not domain_key or not schema_name or not display_name:
        errors.append("YAML must define domain_key, schema_name, and display_name")
    if len(display_name) > 100:
        errors.append(f"display_name length {len(display_name)} exceeds 100 (public.domains.name)")

    if schema_name and not re.fullmatch(r"[a-z][a-z0-9_]*", schema_name):
        errors.append("schema_name must be lowercase snake_case (^[a-z][a-z0-9_]*$)")

    if domain_key == "science-tech":
        errors.append("Retired domain key science-tech — do not onboard; use split silos (e.g. artificial-intelligence).")

    # Registry (active YAML only)
    from shared.domain_registry import (
        RESERVED_SCHEMA_NAMES,
        get_domain_entries,
        resolve_domain_schema,
    )

    if schema_name in RESERVED_SCHEMA_NAMES and domain_key not in (
        "politics",
        "finance",
    ):
        errors.append(
            f"schema_name {schema_name!r} is in RESERVED_SCHEMA_NAMES — pick a different schema for a new silo"
        )

    if is_active:
        keys = {e["domain_key"] for e in get_domain_entries() if e.get("is_active", True)}
        if domain_key and domain_key not in keys:
            errors.append(
                f"domain_key {domain_key!r} not in domain_registry (active row in public.domains + optional YAML merge?)"
            )
        if domain_key and domain_key in keys and resolve_domain_schema(domain_key) != schema_name:
            errors.append(
                f"resolve_domain_schema({domain_key!r}) != schema_name in YAML (expected {schema_name!r})"
            )
    else:
        warnings.append("is_active: false — domain will not appear in registry_domains or RSS url_schema_pairs()")

    synth = _synthesis_has_domain(domain_key)
    if synth is False:
        warnings.append(
            f"No block under domains.{domain_key} in api/config/domain_synthesis_config.yaml "
            "(optional; add for topic/storyline bias)"
        )
    elif synth is None:
        warnings.append("domain_synthesis_config.yaml missing or unreadable (optional check skipped)")

    if args.yaml_only:
        _print_report(cfg_path, domain_key, schema_name, errors, warnings)
        _exit_with_status(errors, warnings, args.strict)

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        errors.append("No database connection (DB_* env / pool)")
        _print_report(cfg_path, domain_key, schema_name, errors, warnings)
        _exit_with_status(errors, warnings, args.strict)

    schema_exists = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                (schema_name,),
            )
            schema_exists = cur.fetchone() is not None
            if not schema_exists:
                errors.append(f"Postgres schema {schema_name!r} does not exist (apply migration + CREATE SCHEMA)")

            cur.execute(
                """
                SELECT domain_key, schema_name, is_active
                FROM public.domains
                WHERE domain_key = %s
                """,
                (domain_key,),
            )
            row = cur.fetchone()
            if not row:
                warnings.append(
                    "No row in public.domains for this domain_key — run migration + provision_domain.py "
                    "or insert catalog row (API may still resolve via registry + schema)"
                )
            else:
                db_schema, db_active = row[1], row[2]
                if str(db_schema) != schema_name:
                    errors.append(
                        f"public.domains.schema_name mismatch: DB has {db_schema!r}, YAML has {schema_name!r}"
                    )
                if db_active is False:
                    warnings.append(
                        "public.domains.is_active is FALSE — catalog drift; pipeline uses YAML + schema (see AGENTS.md)"
                    )

            have = set()
            if schema_exists:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_type = 'BASE TABLE'
                    """,
                    (schema_name,),
                )
                have = {r[0] for r in cur.fetchall()}

        missing_crit = sorted(_CRITICAL_TABLES - have)
        if missing_crit:
            errors.append(f"Missing critical tables in {schema_name}: {', '.join(missing_crit)}")

        missing_ext = sorted(_EXTENDED_TABLES - have)
        if missing_ext:
            warnings.append(
                f"Missing extended tables (migration parity): {', '.join(missing_ext)}"
            )

        n_feeds = 0
        n_articles = 0
        if "rss_feeds" in have:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {schema_name}.rss_feeds WHERE is_active = true"
                )
                n_feeds = cur.fetchone()[0]
        if "articles" in have:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.articles")
                n_articles = cur.fetchone()[0]

        if schema_exists:
            if "rss_feeds" not in have:
                warnings.append("Table rss_feeds missing — migration incomplete")
            elif n_feeds == 0:
                warnings.append(
                    f"No active rows in {schema_name}.rss_feeds — add feeds or run seed_domain_rss_from_yaml.py"
                )
            if "articles" in have and n_articles == 0:
                warnings.append(
                    f"{schema_name}.articles is empty — run collect_rss_feeds / automation after feeds exist"
                )

    finally:
        conn.close()

    _print_report(cfg_path, domain_key, schema_name, errors, warnings)
    _exit_with_status(errors, warnings, args.strict)


def _exit_with_status(
    errors: list[str], warnings: list[str], strict: bool
) -> None:
    """Fail on any error; with --strict, also fail when only warnings exist."""
    if errors:
        sys.exit(1)
    if strict and warnings:
        sys.exit(1)
    sys.exit(0)


def _print_report(
    cfg_path: Path,
    domain_key: str,
    schema_name: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    print("--- verify_domain_provision ---")
    print(f"  config:     {cfg_path}")
    print(f"  domain_key: {domain_key!r}")
    print(f"  schema:     {schema_name!r}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")
    if not errors and not warnings:
        print("\nOK — no issues reported.")
    print("---")


if __name__ == "__main__":
    main()
