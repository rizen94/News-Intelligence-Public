#!/usr/bin/env python3
"""
Print storyline historical memory stats (entities, facts, events, article span).

Usage:
  PYTHONPATH=api uv run python api/scripts/verify_storyline_historical_context.py politics 123
"""

from __future__ import annotations

import json
import sys

from services.storyline_historical_context_service import build_storyline_historical_context


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: verify_storyline_historical_context.py <domain_key> <storyline_id>", file=sys.stderr)
        return 2
    domain_key = sys.argv[1]
    storyline_id = int(sys.argv[2])
    ctx = build_storyline_historical_context(domain_key, storyline_id)
    if not ctx.get("success"):
        print(json.dumps(ctx, indent=2))
        return 1
    out = {
        "domain_key": domain_key,
        "storyline_id": storyline_id,
        "title": ctx.get("storyline_title"),
        "spine_summary": ctx.get("spine_summary"),
        "token_budget": ctx.get("token_budget"),
        "rendered_chars": len(ctx.get("rendered") or ""),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
