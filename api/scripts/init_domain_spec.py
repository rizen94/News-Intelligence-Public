#!/usr/bin/env python3
"""Create specs/{domain_key}.domain.json from _template.domain.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
_SPECS = _API / "config" / "domains" / "specs"
_TEMPLATE = _SPECS / "_template.domain.json"

if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from shared.domain_spec import DomainSpec  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a new domain spec JSON file")
    parser.add_argument("--domain-key", required=True)
    parser.add_argument("--schema-name", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--inactive", action="store_true", help="is_active: false (default)")
    parser.add_argument("--active", action="store_true", help="is_active: true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not _TEMPLATE.is_file():
        raise SystemExit(f"Missing template: {_TEMPLATE}")

    data = json.loads(_TEMPLATE.read_text(encoding="utf-8"))
    data["domain_key"] = args.domain_key.strip()
    data["schema_name"] = args.schema_name.strip()
    data["display_name"] = args.display_name.strip()
    data["is_active"] = bool(args.active and not args.inactive)

    spec = DomainSpec.model_validate(data)
    out = _SPECS / f"{spec.domain_key}.domain.json"
    if out.exists() and not args.force:
        raise SystemExit(f"Refusing: {out} exists (use --force)")

    out.write_text(json.dumps(spec.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    print(
        "Next: edit feeds; validate_domain_spec.py; generate_domain_artifacts.py "
        f"--spec {out} --migration-number NNN"
    )


if __name__ == "__main__":
    main()
