#!/usr/bin/env python3
"""One-shot maintenance: package storyline_id backfill + optional SQL fixes.

  PYTHONPATH=api python3 api/scripts/run_data_utilization_maintenance.py --apply
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection  # noqa: E402


def backfill_package_storyline_ids(*, apply: bool) -> dict:
    conn = get_db_connection()
    if not conn:
        return {"error": "no_db", "updated": 0}
    try:
        with conn.cursor() as cur:
            if not apply:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM intelligence.editorial_packages
                    WHERE metadata->>'source_storyline_id' ~ '^[0-9]+$'
                      AND (
                        metadata->>'storyline_id' IS NULL
                        OR metadata->>'storyline_id' = ''
                      )
                    """
                )
                return {"updated": int((cur.fetchone() or [0])[0] or 0), "dry_run": True}
            cur.execute(
                """
                UPDATE intelligence.editorial_packages
                SET metadata = metadata || jsonb_build_object(
                  'storyline_id', metadata->>'source_storyline_id'
                )
                WHERE metadata->>'source_storyline_id' ~ '^[0-9]+$'
                  AND (
                    metadata->>'storyline_id' IS NULL
                    OR metadata->>'storyline_id' = ''
                  )
                """
            )
            updated = int(cur.rowcount or 0)
        conn.commit()
        return {"updated": updated, "dry_run": False}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_script(name: str, args: list[str]) -> dict:
    cmd = [sys.executable, str(ROOT / "api" / "scripts" / name), *args]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    return {
        "script": name,
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:] if proc.stdout else "",
        "stderr": proc.stderr[-2000:] if proc.stderr else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--skip-repair", action="store_true")
    ap.add_argument("--skip-cluster", action="store_true")
    ap.add_argument("--skip-dossier", action="store_true")
    args = ap.parse_args()
    apply_flag = ["--apply"] if args.apply else ["--dry-run"]
    out: dict = {"apply": args.apply}

    out["package_storyline_backfill"] = backfill_package_storyline_ids(apply=args.apply)

    # Scripts that take --apply vs those that run on absence of --dry-run
    def _repair_args() -> list[str]:
        return ["--all"] if args.apply else ["--all", "--dry-run"]

    def _promote_args() -> list[str]:
        return ["--all"] if args.apply else ["--all", "--dry-run"]

    def _seed_args() -> list[str]:
        return ["--all", "--limit", "20"] if args.apply else ["--all", "--limit", "20", "--dry-run"]

    steps = []
    if not args.skip_repair:
        steps.append(("repair_duplicate_episodes.py", _repair_args()))
    steps.extend(
        [
            ("promote_eel_links.py", _promote_args()),
            (
                "backfill_event_episode_links.py",
                (["--all", "--limit-episodes", "500", "--bag-orphans-only"]
                 + (["--apply"] if args.apply else ["--dry-run"])),
            ),
        ]
    )
    if not args.skip_cluster:
        steps.append(
            (
                "link_clustered_events_to_episodes.py",
                (["--all", "--limit-clusters", "500"]
                 + (["--apply"] if args.apply else ["--dry-run"])),
            )
        )
    steps.extend(
        [
            (
                "bridge_tracked_events_to_episodes.py",
                (["--all", "--limit", "500"]
                 + (["--apply"] if args.apply else ["--dry-run"])),
            ),
            ("seed_watchlist_from_daily.py", _seed_args()),
        ]
    )

    out["scripts"] = [run_script(name, script_args) for name, script_args in steps]

    if args.apply and not args.skip_dossier:
        out["dossier_catchup"] = run_script(
            "run_major_backlog_catchup.py",
            ["--phases", "entity_dossier_compile", "--loops", "3", "--force"],
        )

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
