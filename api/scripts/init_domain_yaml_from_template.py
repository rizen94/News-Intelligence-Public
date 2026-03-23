#!/usr/bin/env python3
"""
Create ``api/config/domains/{domain_key}.yaml`` from ``_template.example.yaml``.

Fills ``domain_key``, ``schema_name``, and ``display_name``; keeps comments and
the rest of the template body. Refuses to overwrite unless ``--force``.

  PYTHONPATH=api uv run python api/scripts/init_domain_yaml_from_template.py \\
    --domain-key medicine --schema-name medicine --display-name "Medicine & Health"

After migration + provision_domain.py, run:

  PYTHONPATH=api uv run python api/scripts/verify_domain_provision.py --domain-key medicine [--strict]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "domains"
_TEMPLATE = _CONFIG_DIR / "_template.example.yaml"


def _yaml_scalar_line(key: str, value: str) -> str:
    """Emit ``key: value`` with quoting when the scalar needs it for YAML 1.1."""
    if value == "":
        return f"{key}: ''\n"
    if re.search(r"[:#\n\r\t&]", value) or value != value.strip():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key}: "{escaped}"\n'
    return f"{key}: {value}\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new domain onboarding YAML from _template.example.yaml"
    )
    parser.add_argument(
        "--domain-key",
        required=True,
        help="URL segment (e.g. medicine, legal-news); hyphens OK, no underscores",
    )
    parser.add_argument(
        "--schema-name",
        required=True,
        help="Postgres schema (e.g. medicine, legal); underscores OK, no hyphens",
    )
    parser.add_argument("--display-name", required=True, help="≤100 chars; becomes public.domains.name")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output path (default: {_CONFIG_DIR}/{{domain_key}}.yaml)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing file")
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Keep is_active: false (draft silo). Default is is_active: true after generation.",
    )
    args = parser.parse_args()

    dk = args.domain_key.strip()
    sn = args.schema_name.strip()
    dn = args.display_name.strip()
    if not dk or not sn or not dn:
        raise SystemExit("domain_key, schema_name, and display_name must be non-empty")
    if len(dn) > 100:
        raise SystemExit("display_name must be ≤ 100 characters (public.domains.name)")
    if not re.fullmatch(r"[a-z0-9-]+", dk):
        raise SystemExit("domain_key must match ^[a-z0-9-]+$")
    if not re.fullmatch(r"[a-z0-9_]+", sn) or "-" in sn:
        raise SystemExit("schema_name must match ^[a-z0-9_]+$ (no hyphens)")
    if not sn.islower():
        raise SystemExit("schema_name must be lowercase")

    out_path = args.out if args.out is not None else _CONFIG_DIR / f"{dk}.yaml"
    if out_path.exists() and not args.force:
        raise SystemExit(f"Refusing: {out_path} exists (use --force to overwrite)")

    if not _TEMPLATE.is_file():
        raise SystemExit(f"Template missing: {_TEMPLATE}")

    body = _TEMPLATE.read_text(encoding="utf-8")
    lines = body.splitlines(keepends=True)
    out_lines: list[str] = []
    replaced = {"domain_key": False, "schema_name": False, "display_name": False}
    for line in lines:
        if line.startswith("domain_key:"):
            out_lines.append(_yaml_scalar_line("domain_key", dk))
            replaced["domain_key"] = True
        elif line.startswith("schema_name:"):
            out_lines.append(_yaml_scalar_line("schema_name", sn))
            replaced["schema_name"] = True
        elif line.startswith("display_name:"):
            out_lines.append(_yaml_scalar_line("display_name", dn))
            replaced["display_name"] = True
        else:
            out_lines.append(line)

    if not all(replaced.values()):
        raise SystemExit(
            "Template is missing one of domain_key / schema_name / display_name lines — "
            "fix _template.example.yaml"
        )

    if not args.inactive:
        for i, line in enumerate(out_lines):
            if line.strip().startswith("is_active:"):
                out_lines[i] = "is_active: true\n"
                break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(out_lines), encoding="utf-8")
    print(f"Wrote {out_path}")
    if args.inactive:
        print(
            "Next: edit seed_feed_urls; migration + provision_domain; "
            "verify_domain_provision.py --domain-key …; then set is_active: true."
        )
    else:
        print(
            "Next: edit data_sources.rss.seed_feed_urls; apply migration + provision_domain; "
            "verify_domain_provision.py --domain-key …; ensure_domain_silo_alignment.py on each host."
        )


if __name__ == "__main__":
    main()
