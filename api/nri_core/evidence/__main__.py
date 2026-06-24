"""Evidence CLI — mention resolution batches."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NRI evidence adapter")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_p = sub.add_parser("resolve", help="Run mention resolver batch or budgeted drain")
    resolve_p.add_argument("--limit", type=int, default=None, help="Max mentions per batch")
    resolve_p.add_argument(
        "--budget-seconds",
        type=float,
        default=None,
        help="Drain until idle or budget (default from NRI_MENTION_RESOLVE_BUDGET_SECONDS)",
    )
    resolve_p.add_argument(
        "--single-batch",
        action="store_true",
        help="One batch only (legacy); default is budgeted drain",
    )

    args = parser.parse_args(argv)

    if args.command == "resolve":
        from nri_core.evidence.mention_resolver import resolve_batch, resolve_drain

        if args.single_batch:
            from nri_core.evidence.mention_resolver import _resolve_batch_limit

            lim = args.limit if args.limit is not None else _resolve_batch_limit()
            result = resolve_batch(limit=lim)
        else:
            result = resolve_drain(
                limit=args.limit,
                budget_seconds=args.budget_seconds,
            )
        print(json.dumps(result))
        if result.get("skipped"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
