#!/usr/bin/env python3
"""Generate slim onboarding YAML and silo SQL migration from a domain spec JSON file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
_REPO = _API.parent
_DOMAINS = _API / "config" / "domains"
_MIGRATIONS = _API / "database" / "migrations"
_SPECS = _DOMAINS / "specs"
_GENERATED = _SPECS / "generated"

if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from shared.domain_spec import DomainSpec  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate YAML + SQL from domain spec")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument(
        "--migration-number",
        type=int,
        help="Required for SQL output (e.g. 209 → 209_{schema}_domain_silo.sql)",
    )
    parser.add_argument("--out-yaml", type=Path, help="Default: api/config/domains/{domain_key}.yaml")
    parser.add_argument("--out-sql", type=Path, help="Default: api/database/migrations/NNN_{schema}_domain_silo.sql")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-synthesis-stub", action="store_true")
    args = parser.parse_args()

    spec_path = args.spec.resolve()
    spec = DomainSpec.from_json_file(spec_path)

    out_yaml = args.out_yaml or (_DOMAINS / f"{spec.domain_key}.yaml")
    if args.migration_number is not None:
        out_sql = args.out_sql or (
            _MIGRATIONS / f"{args.migration_number:03d}_{spec.schema_name}_domain_silo.sql"
        )
    else:
        out_sql = args.out_sql

    yaml_text = spec.render_yaml()
    sql_text = spec.render_sql_migration(args.migration_number) if args.migration_number else None

    if args.dry_run:
        print(f"Would write YAML: {out_yaml}")
        print(yaml_text[:500] + ("..." if len(yaml_text) > 500 else ""))
        if sql_text:
            print(f"\nWould write SQL: {out_sql}")
            print(sql_text[:800] + ("..." if len(sql_text) > 800 else ""))
        return

    if out_yaml.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite {out_yaml} (use --force)")
    out_yaml.write_text(yaml_text, encoding="utf-8")
    print(f"Wrote {out_yaml}")

    if sql_text and out_sql:
        if out_sql.exists() and not args.force:
            raise SystemExit(f"Refusing to overwrite {out_sql} (use --force)")
        out_sql.parent.mkdir(parents=True, exist_ok=True)
        out_sql.write_text(sql_text, encoding="utf-8")
        print(f"Wrote {out_sql}")

    if not args.no_synthesis_stub:
        _GENERATED.mkdir(parents=True, exist_ok=True)
        stub_path = _GENERATED / f"{spec.domain_key}.synthesis.stub.yaml"
        stub_path.write_text(spec.synthesis_stub_yaml(), encoding="utf-8")
        print(f"Wrote {stub_path}")


if __name__ == "__main__":
    main()
