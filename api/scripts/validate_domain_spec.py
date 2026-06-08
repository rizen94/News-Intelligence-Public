#!/usr/bin/env python3
"""Validate a domain onboarding JSON manifest (Pydantic + optional JSON Schema)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from shared.domain_registry_constants import RESERVED_SCHEMA_NAMES  # noqa: E402
from shared.domain_spec import DomainSpec, load_json_schema  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate api/config/domains/specs/*.domain.json")
    parser.add_argument("--spec", type=Path, required=True, help="Path to .domain.json")
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Warn if domain_key already exists in public.domains with different schema",
    )
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    if not spec_path.is_file():
        raise SystemExit(f"Not found: {spec_path}")

    raw = json.loads(spec_path.read_text(encoding="utf-8"))
    schema = load_json_schema()
    if schema:
        try:
            import jsonschema

            jsonschema.validate(instance=raw, schema=schema)
        except ImportError:
            print("  [note] jsonschema not installed; using Pydantic only")
        except jsonschema.ValidationError as e:
            raise SystemExit(f"JSON Schema validation failed: {e.message}") from e

    spec = DomainSpec.model_validate(raw)
    print(f"OK: {spec_path}")
    print(f"  domain_key={spec.domain_key!r} schema_name={spec.schema_name!r} is_active={spec.is_active}")

    if spec.schema_name in RESERVED_SCHEMA_NAMES and spec.domain_key not in ("politics", "finance"):
        print(f"  [warn] schema_name is in RESERVED_SCHEMA_NAMES")

    import yaml

    yaml.safe_load(spec.render_yaml().split("\n", 1)[-1])

    if args.check_db:
        import os

        try:
            from dotenv import load_dotenv

            load_dotenv(_API / ".env", override=False)
            load_dotenv(_API.parent / ".env", override=False)
        except ImportError:
            pass
        pw_file = _API.parent / ".db_password_widow"
        if not os.environ.get("DB_PASSWORD") and pw_file.is_file():
            os.environ["DB_PASSWORD"] = pw_file.read_text(encoding="utf-8").strip()
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT schema_name FROM public.domains WHERE domain_key = %s",
                        (spec.domain_key,),
                    )
                    row = cur.fetchone()
                    if row and str(row[0]) != spec.schema_name:
                        print(
                            f"  [warn] public.domains has schema {row[0]!r}, spec has {spec.schema_name!r}"
                        )
            finally:
                conn.close()


if __name__ == "__main__":
    main()
