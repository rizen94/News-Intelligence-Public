#!/usr/bin/env python3
"""One-shot maintenance: episode assembly + package storyline_id backfill.

  PYTHONPATH=api python3 api/scripts/run_data_utilization_maintenance.py --apply

Delegates orphan linkage to episode_assembly_maintenance_service (same path as
automation_manager ``episode_assembly_maintenance`` phase).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection  # noqa: E402
from services.episode_assembly_maintenance_service import (  # noqa: E402
    _maintenance_limits,
    run_episode_assembly_maintenance,
)


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


async def _run_assembly(conn, *, apply: bool, skip_cluster: bool) -> dict:
    limits = _maintenance_limits()
    if skip_cluster:
        limits = dict(limits)
        limits["cluster_limit"] = 0
    if limits.get("cluster_limit", 0) <= 0:
        limits = dict(limits)
        limits["cluster_limit"] = 0
    return await run_episode_assembly_maintenance(conn, apply=apply, limits=limits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--skip-repair", action="store_true")
    ap.add_argument("--skip-cluster", action="store_true")
    ap.add_argument("--skip-dossier", action="store_true")
    ap.add_argument("--skip-assembly", action="store_true")
    args = ap.parse_args()
    out: dict = {"apply": args.apply}

    out["package_storyline_backfill"] = backfill_package_storyline_ids(apply=args.apply)

    def _repair_args() -> list[str]:
        return ["--all"] if args.apply else ["--all", "--dry-run"]

    def _promote_args() -> list[str]:
        return ["--all"] if args.apply else ["--all", "--dry-run"]

    def _seed_args() -> list[str]:
        return ["--all", "--limit", "20"] if args.apply else ["--all", "--limit", "20", "--dry-run"]

    steps = []
    if not args.skip_repair:
        steps.append(("repair_duplicate_episodes.py", _repair_args()))
    steps.append(("promote_eel_links.py", _promote_args()))
    if not args.skip_cluster:
        steps.append(
            (
                "backfill_event_episode_links.py",
                (
                    ["--all", "--limit-episodes", "500", "--bag-orphans-only"]
                    + (["--apply"] if args.apply else ["--dry-run"])
                ),
            )
        )
    steps.append(("seed_watchlist_from_daily.py", _seed_args()))

    out["scripts"] = [run_script(name, script_args) for name, script_args in steps]

    if not args.skip_assembly:
        conn = get_db_connection()
        if not conn:
            out["episode_assembly"] = {"error": "no_db"}
        else:
            try:
                out["episode_assembly"] = asyncio.run(
                    _run_assembly(conn, apply=args.apply, skip_cluster=args.skip_cluster)
                )
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    if args.apply and not args.skip_dossier:
        out["dossier_catchup"] = run_script(
            "run_major_backlog_catchup.py",
            ["--phases", "entity_dossier_compile", "--loops", "3", "--force"],
        )

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
