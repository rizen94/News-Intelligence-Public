#!/usr/bin/env python3
"""Batch-requeue comprehensive_rag for politics storylines with Global-framed summaries."""
from __future__ import annotations

import json
import sys

# Worst offenders (article_count > 0) from DB scan 2026-07-22
DEFAULT_IDS = [
    3672,  # Ongoing: Andy Burnham
    3688,  # Ongoing: GAZA
    3675,  # Ongoing: Ukraine
    3669,  # Ongoing: China
    3729,  # US-Iran / China policy
    3727,  # Ongoing: Netanyahu
    3664,  # Ongoing: Lgbtq
    3720,  # US-Iran oil
    3687,  # Trump Israel policy
    3610,  # Ongoing: Trump
    3552,  # Iran LIVE UPDATES
    3587,  # Kash Patel
    3638,  # Naidu
    3649,  # Air Canada
    3617,  # Ravi Kishan
]


def main() -> int:
    ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else list(DEFAULT_IDS)
    from services.content_refinement_queue_service import (
        JOB_COMPREHENSIVE_RAG,
        enqueue_content_refinement,
    )

    results = []
    for sid in ids:
        r = enqueue_content_refinement(
            "politics",
            sid,
            JOB_COMPREHENSIVE_RAG,
            priority="high",
            metadata={"reason": "batch_requeue_global_summary"},
        )
        results.append({"storyline_id": sid, **r})
        print(json.dumps({"storyline_id": sid, **r}, default=str))

    enqueued = sum(1 for r in results if r.get("success") and not r.get("already_queued"))
    already = sum(1 for r in results if r.get("already_queued"))
    failed = sum(1 for r in results if not r.get("success"))
    print(
        json.dumps(
            {
                "enqueued": enqueued,
                "already_queued": already,
                "failed": failed,
                "total": len(results),
            }
        )
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
