#!/usr/bin/env python3
"""Recompose ready_for_editor (and section-only closed_thin) packages.

Dry-run by default. Apply with --apply.

  PYTHONPATH=api python3 api/scripts/recompose_ready_packages.py --all
  PYTHONPATH=api python3 api/scripts/recompose_ready_packages.py --all --apply
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("recompose_ready_packages")


def _reopen_section_thin(cur, *, apply: bool) -> int:
    cur.execute(
        """
        SELECT id
        FROM intelligence.editorial_packages
        WHERE status = 'closed_thin'
          AND COALESCE(metadata->'thin_close'->>'reason', '') = 'thin_no_stakes'
          AND working_title !~* '(^|[^A-Za-z])NCT[0-9]{5,}'
          AND working_title !~* 'trial registration'
          AND working_title !~* '^Ongoing:'
        ORDER BY id
        """
    )
    ids = [int(r[0]) for r in cur.fetchall() or []]
    if apply and ids:
        cur.execute(
            """
            UPDATE intelligence.editorial_packages
            SET status = 'ready_for_editor',
                updated_at = NOW()
            WHERE id = ANY(%s)
            """,
            (ids,),
        )
    return len(ids)


def main() -> int:
    ap = argparse.ArgumentParser(description="Recompose parked editorial packages")
    ap.add_argument("--all", action="store_true", help="Process every matching package")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument(
        "--extractive",
        action="store_true",
        help="Skip Ollama; synthesize reader sections from package evidence",
    )
    args = ap.parse_args()

    if args.extractive:
        import os

        os.environ["EDITORIAL_COMPOSE_SKIP_LLM"] = "1"

    from shared.database.connection import get_ui_db_connection_context
    from services.editorial_package_compose_service import run_compose_pass_sync

    stats = {"reopened_thin": 0, "composed": 0, "ok": 0, "published": 0, "blocked": 0}

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            stats["reopened_thin"] = _reopen_section_thin(cur, apply=bool(args.apply))
            if args.apply:
                conn.commit()
            cur.execute(
                """
                SELECT id
                FROM intelligence.editorial_packages
                WHERE status IN ('ready_for_editor', 'in_editing')
                ORDER BY updated_at DESC NULLS LAST, id DESC
                LIMIT %s
                """,
                (100000 if args.all else max(1, args.limit),),
            )
            ids = [int(r[0]) for r in cur.fetchall() or []]

    logger.info(
        "reopened_thin=%s compose_candidates=%s apply=%s",
        stats["reopened_thin"],
        len(ids),
        args.apply,
    )
    if not args.apply:
        logger.info("dry-run; pass --apply to compose")
        return 0

    for pid in ids:
        stats["composed"] += 1
        try:
            result = run_compose_pass_sync(pid, force=True, mode="publish")
        except Exception as e:
            logger.warning("package %s failed: %s", pid, e)
            stats["blocked"] += 1
            continue
        if result.get("ok"):
            stats["ok"] += 1
            if (result.get("published") or {}).get("published"):
                stats["published"] += 1
            elif result.get("ok"):
                logger.info(
                    "package %s composed but not published cite_ok=%s refused=%s",
                    pid,
                    ((result.get("citation_check") or {}).get("ok")),
                    (result.get("citation_check") or {}).get("refused"),
                )
        else:
            stats["blocked"] += 1
            logger.info(
                "package %s blocked reason=%s checks=%s insuff=%s",
                pid,
                result.get("block_reason") or result.get("error") or result.get("reason"),
                {
                    k: v
                    for k, v in ((result.get("stakes") or {}).get("checks") or {}).items()
                    if v is False
                }
                or None,
                result.get("insufficient_evidence"),
            )

    logger.info("done %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
