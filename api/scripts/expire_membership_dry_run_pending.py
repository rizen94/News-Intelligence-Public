#!/usr/bin/env python3
"""Reclassify dry-run membership actions that were stored as pending (Monitor queue_depth)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))


def main() -> int:
    from services.storyline_membership_review_service import (
        expire_pending_dry_run_membership_actions,
    )

    result = expire_pending_dry_run_membership_actions()
    print(result)
    return 0 if int(result.get("updated", 0) or 0) >= 0 and not result.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
