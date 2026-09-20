#!/usr/bin/env python3
"""Headless domain provision from JSON file (run inside api container or with PYTHONPATH set)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kit_api.services.provision_service import apply_setup_plan
from kit_api.services.setup_state import set_setup_complete


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: provision_from_spec.py domains.json", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    raw = json.loads(path.read_text(encoding="utf-8"))
    domains = raw if isinstance(raw, list) else raw.get("domains", [raw])
    draft = {"domains": domains}
    result = apply_setup_plan(draft)
    print(json.dumps(result, indent=2))
    if result.get("provisioned") and not result.get("errors"):
        set_setup_complete(True)
        return 0
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
