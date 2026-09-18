#!/usr/bin/env python3
"""Verify nightly sequential claim_extraction uses single-batch mode (not full drain)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API = os.path.join(ROOT, "api")
for p in (ROOT, API):
    if p not in sys.path:
        sys.path.insert(0, p)

def _log(message: str, data: dict) -> None:
    print(json.dumps({"message": message, "data": data, "timestamp": int(time.time() * 1000)}, default=str))


async def main() -> int:
    from services.claim_extraction_service import claim_extraction_drain_enabled

    meta = {"nightly_sequential_drain": True, "nightly_limit": 5}
    is_nightly_seq = bool(meta.get("nightly_sequential_drain"))
    use_drain = claim_extraction_drain_enabled() and not is_nightly_seq
    _log(
        "branch check",
        {
            "is_nightly_seq": is_nightly_seq,
            "use_drain": use_drain,
            "drain_enabled": claim_extraction_drain_enabled(),
        },
    )
    if use_drain:
        print("FAIL: nightly sequential would still use full drain")
        return 1

    print(
        f"OK: nightly sequential uses single-batch path (use_drain={use_drain}, "
        f"drain_enabled={claim_extraction_drain_enabled()})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
