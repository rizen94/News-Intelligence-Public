#!/usr/bin/env python3
"""
Drain the storyline review queue with an LLM agent (plus score fast-paths).

  cd /opt/news-intelligence
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_storyline_review_agent.py --dry-run
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_storyline_review_agent.py --loops 100
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_storyline_review_agent.py --domain politics --llm-only
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_REPO_ROOT = _API_ROOT.parent


def _load_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


async def _main_async(args: argparse.Namespace) -> int:
    from services.backlog_metrics import get_storyline_review_queue_pending
    from services.storyline_review_agent_service import (
        run_storyline_review_agent_all_domains,
        run_storyline_review_agent_for_domain,
    )

    pending_before = get_storyline_review_queue_pending()
    print(f"Pending review queue: {pending_before}")

    totals = {"approved": 0, "rejected": 0, "skipped": 0, "errors": 0, "llm_calls": 0}
    for loop in range(1, args.loops + 1):
        if args.domain:
            result = await run_storyline_review_agent_for_domain(
                args.domain,
                batch_limit=args.batch_size,
                dry_run=args.dry_run,
                llm_only=args.llm_only,
            )
        else:
            result = await run_storyline_review_agent_all_domains(
                batch_limit=args.batch_size,
                dry_run=args.dry_run,
                llm_only=args.llm_only,
            )

        for k in totals:
            totals[k] += int(result.get(k, 0) or 0)

        processed = int(result.get("approved", 0)) + int(result.get("rejected", 0))
        print(
            f"Loop {loop}: approved={result.get('approved')} rejected={result.get('rejected')} "
            f"skipped={result.get('skipped')} llm_calls={result.get('llm_calls')} errors={result.get('errors')}"
        )
        if processed == 0 and int(result.get("llm_calls", 0) or 0) == 0:
            print("No more work in this batch — stopping.")
            break

    pending_after = get_storyline_review_queue_pending()
    print(
        f"Done. totals={totals} pending {pending_before} -> {pending_after}"
        + (" (dry-run)" if args.dry_run else "")
    )
    return 0


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="LLM agent for storyline review queue")
    parser.add_argument("--domain", default=None, help="Single domain key (default: all active)")
    parser.add_argument("--loops", type=int, default=50, help="Max batch loops")
    parser.add_argument("--batch-size", type=int, default=60, help="Suggestions per loop per domain")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--llm-only",
        action="store_true",
        help="Skip score fast-path auto approve/reject",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
