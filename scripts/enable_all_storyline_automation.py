#!/usr/bin/env python3
"""
Enable RAG storyline automation for **all** storylines in each domain schema.

The automation manager picks rows with `automation_enabled = true` for:
  - `storyline_automation` — discover related articles (feeds the suggestions queue unless auto_approve)
  - `storyline_enrichment` — full-history discovery (requires at least one `storyline_articles` row)

Non-`auto_approve` modes call `_store_suggestions` → `public.storyline_article_suggestions` (pending review).

From repo root:
  PYTHONPATH=api uv run python scripts/enable_all_storyline_automation.py
  PYTHONPATH=api uv run python scripts/enable_all_storyline_automation.py --dry-run
  PYTHONPATH=api uv run python scripts/enable_all_storyline_automation.py --mode suggest_only --no-reset-schedule
  # --no-reset-schedule keeps last_automation_run (respects automation_frequency_hours until due)

See also: PUT /api/{domain}/storylines/{id}/automation/settings
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

SCHEMAS = ("politics", "finance", "science_tech")
VALID_MODES = ("suggest_only", "review_queue", "manual", "auto_approve")


def main() -> int:
    p = argparse.ArgumentParser(description="Enable storyline automation flags for all storylines.")
    p.add_argument(
        "--mode",
        choices=VALID_MODES,
        default="review_queue",
        help="review_queue/suggest_only/manual → suggestions queue; auto_approve → auto-add above thresholds",
    )
    p.add_argument(
        "--frequency-hours",
        type=int,
        default=6,
        help="Minimum hours between discovery runs per storyline (automation_frequency_hours)",
    )
    p.add_argument(
        "--no-reset-schedule",
        action="store_true",
        help="Keep last_automation_run unchanged (default: clear it so the next automation batch is not skipped)",
    )
    p.add_argument("--dry-run", action="store_true", help="Print counts only, no UPDATE")
    args = p.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return 1

    settings_merge = json.dumps({"min_quality_tier": 2})
    reset_schedule = not args.no_reset_schedule

    try:
        with conn.cursor() as cur:
            for sch in SCHEMAS:
                cur.execute(f"SELECT COUNT(*) FROM {sch}.storylines")
                total = cur.fetchone()[0]
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {sch}.storylines
                    WHERE automation_enabled IS TRUE AND automation_mode = %s
                    """,
                    (args.mode,),
                )
                already = cur.fetchone()[0]

                if args.dry_run:
                    print(f"[dry-run] {sch}: storylines={total}, already mode={args.mode!r} enabled={already}")
                    continue

                reset_sql = "last_automation_run = NULL, " if reset_schedule else ""
                cur.execute(
                    f"""
                    UPDATE {sch}.storylines
                    SET
                        automation_enabled = TRUE,
                        automation_mode = %s,
                        automation_frequency_hours = %s,
                        {reset_sql}
                        automation_settings = COALESCE(automation_settings, '{{}}'::jsonb) || %s::jsonb,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (args.mode, args.frequency_hours, settings_merge),
                )
                updated = cur.rowcount
                print(f"{sch}: updated {updated} storylines (total in schema: {total})")

            if not args.dry_run:
                conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        return 1
    finally:
        conn.close()

    if args.dry_run:
        print("\nDry-run only. Re-run without --dry-run to apply.")
        print(f"Would set: automation_enabled=true, mode={args.mode!r}, frequency_hours={args.frequency_hours}")
        if reset_schedule:
            print("Would clear: last_automation_run (so next automation batch can run immediately)")
        return 0

    print("\nDone. `storyline_automation` / `storyline_enrichment` will pick these up on their next runs.")
    if args.mode == "auto_approve":
        print("Note: auto_approve adds articles directly when scores pass gates (no suggestion queue).")
    else:
        print("Article matches go to public.storyline_article_suggestions (status=pending) for review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
