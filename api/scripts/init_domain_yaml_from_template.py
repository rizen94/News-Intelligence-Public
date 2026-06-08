#!/usr/bin/env python3
"""
DEPRECATED: use init_domain_spec.py and generate_domain_artifacts.py instead.

This wrapper forwards to init_domain_spec.py for backward compatibility.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="(Deprecated) Create domain spec JSON — use init_domain_spec.py"
    )
    parser.add_argument("--domain-key", required=True)
    parser.add_argument("--schema-name", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--out", type=Path, default=None, help="Ignored; spec path is fixed")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--inactive", action="store_true")
    args = parser.parse_args()

    print(
        "Note: init_domain_yaml_from_template.py is deprecated. "
        "Using init_domain_spec.py + generate_domain_artifacts.py.",
        file=sys.stderr,
    )
    cmd = [
        sys.executable,
        str(_API / "scripts" / "init_domain_spec.py"),
        "--domain-key",
        args.domain_key,
        "--schema-name",
        args.schema_name,
        "--display-name",
        args.display_name,
    ]
    if args.force:
        cmd.append("--force")
    if args.inactive:
        cmd.append("--inactive")
    raise SystemExit(subprocess.call(cmd, cwd=str(_API.parent)))


if __name__ == "__main__":
    main()
