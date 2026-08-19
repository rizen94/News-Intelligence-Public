#!/usr/bin/env python3
"""
Run core dissimilar prune for one storyline (Pillar B / mega harden).

Default is dry-run (no destructive writes; rolls back). Use --apply only after
reviewing would-unlink samples. Caps still apply via env
STORYLINE_CORE_PRUNE_MAX_UNLINKS (default 40) and
STORYLINE_MEMBERSHIP_MIN_REMAINING (default 3).

  PYTHONPATH=api python3 api/scripts/run_storyline_core_prune.py \\
      --domain politics --storyline-id 3570

  # Apply clear unlinks (still capped; raise MAX_UNLINKS for a larger pass):
  STORYLINE_CORE_PRUNE_MAX_UNLINKS=200 \\
  PYTHONPATH=api python3 api/scripts/run_storyline_core_prune.py \\
      --domain politics --storyline-id 3570 --apply

Do NOT mass-apply on Iran LIVE UPDATES (~8k) without an explicit operator plan.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("run_storyline_core_prune")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True, help="Domain key, e.g. politics")
    parser.add_argument("--storyline-id", type=int, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply high-confidence unlinks (requires STORYLINE_CORE_PRUNE_AUTO_APPLY!=false)",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Lightweight scan (no membership action inserts / no samples)",
    )
    parser.add_argument(
        "--max-unlinks",
        type=int,
        default=None,
        help="Override STORYLINE_CORE_PRUNE_MAX_UNLINKS for this process",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full stats JSON",
    )
    args = parser.parse_args()

    if args.max_unlinks is not None:
        os.environ["STORYLINE_CORE_PRUNE_MAX_UNLINKS"] = str(int(args.max_unlinks))

    from services.storyline_core_prune_service import (
        core_prune_auto_apply,
        core_prune_enabled,
        prune_dissimilar_parts,
        should_gate_synthesis,
    )

    dry_run = not args.apply
    if args.apply and not core_prune_enabled():
        logger.error("STORYLINE_CORE_PRUNE_ENABLED is false; refusing --apply")
        return 2
    if args.apply and not core_prune_auto_apply():
        logger.error(
            "STORYLINE_CORE_PRUNE_AUTO_APPLY is false; refusing --apply "
            "(mid-band would only queue). Set AUTO_APPLY=true to unlink."
        )
        return 2

    gated, gate_info = should_gate_synthesis(args.domain, args.storyline_id)
    stats = prune_dissimilar_parts(
        args.domain,
        args.storyline_id,
        dry_run=dry_run,
        count_only=bool(args.count_only),
    )

    summary = {
        "domain": args.domain,
        "storyline_id": args.storyline_id,
        "dry_run": dry_run or args.count_only,
        "gate_synthesis": gated,
        "gate_info": {
            k: gate_info.get(k)
            for k in ("gated", "outliers", "reason", "mega_floor", "outlier_gate")
            if k in gate_info
        },
        "title": stats.get("title"),
        "article_count": stats.get("article_count"),
        "kitchen_sink": stats.get("kitchen_sink"),
        "kitchen_sink_reason": stats.get("kitchen_sink_reason"),
        "polluted_body": stats.get("polluted_body"),
        "core_tokens_sample": stats.get("core_tokens_sample"),
        "core_entities_sample": stats.get("core_entities_sample"),
        "scored_members": stats.get("scored_members"),
        "kept_members": stats.get("kept_members"),
        "would_unlink": stats.get("would_unlink"),
        "unlinked": stats.get("unlinked"),
        "queued": stats.get("queued"),
        "protected_kept": stats.get("protected_kept"),
        "title_anchor_kept": stats.get("title_anchor_kept"),
        "title_anchors_sample": stats.get("title_anchors_sample"),
        "sample_protected": stats.get("sample_protected"),
        "events_scored": stats.get("events_scored"),
        "would_detach_events": stats.get("would_detach_events"),
        "events_detached": stats.get("events_detached"),
        "chunks_scored": stats.get("chunks_scored"),
        "chunks_queued": stats.get("chunks_queued"),
        "chunks_deprecated": stats.get("chunks_deprecated"),
        "sample_would_unlink": stats.get("sample_would_unlink"),
        "sample_kept": stats.get("sample_kept"),
        "sample_demote": stats.get("sample_demote"),
        "error": stats.get("error"),
    }
    if args.json:
        print(json.dumps(stats, default=str, indent=2))
    else:
        print(json.dumps(summary, default=str, indent=2))

    if stats.get("error"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
