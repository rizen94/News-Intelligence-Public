#!/usr/bin/env python3
"""Refresh rolling 12m arcs (Phase B nightly planner entrypoint)."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "api"
for p in (str(ROOT), str(API)):
    if p not in sys.path:
        sys.path.insert(0, p)

logging.basicConfig(level=logging.INFO)


def main() -> int:
    from services.rolling_arc_service import refresh_default_rolling_arcs

    result = refresh_default_rolling_arcs()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
