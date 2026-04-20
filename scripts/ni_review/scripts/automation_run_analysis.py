#!/usr/bin/env python3
"""
Analyze automation_run_history for the last N hours: run counts per phase,
actual vs estimated duration, and phases that should have run in a 2h window but didn't.
Use to tune schedule intervals and PHASE_ESTIMATED_DURATION_SECONDS.

  cd /path/to/News Intelligence
  PYTHONPATH=api uv run python scripts/automation_run_analysis.py [--hours 3] [--window-2h]

Output: per-phase runs, avg duration (actual vs estimated), and recommendations.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _get_db_config():
    """Load DB config from .env (same pattern as last_24h_activity_report)."""
    env_file = os.path.join(PROJECT_ROOT, ".env")
    if os.path.isfile(env_file):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k.startswith("DB_"):
                            os.environ.setdefault(k, v)
    return {
        "host": os.getenv("DB_HOST", "192.168.93.101"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME", "news_intel"),
        "user": os.getenv("DB_USER", "newsapp"),
        "password": os.getenv("DB_PASSWORD", ""),
        "connect_timeout": 10,
    }


# Schedule interval (seconds) and estimated duration (seconds) — from automation_manager
# Phases with interval <= 7200 (2h) are expected to run at least once per 2h window.
SCHEDULE_INTERVAL_SECONDS: dict[str, int] = {
    "collection_cycle": int(os.environ.get("COLLECTION_CYCLE_INTERVAL_SECONDS", "7200")),
    "document_processing": 600,
    "context_sync": 900,
    "entity_profile_sync": 21600,
    "claim_extraction": 1800,
    "claims_to_facts": 3600,
    "event_tracking": 900,
    "event_coherence_review": 7200,
    "investigation_report_refresh": 7200,
    "cross_domain_synthesis": 1800,
    "entity_profile_build": 900,
    "pattern_recognition": 7200,
    "entity_dossier_compile": 3600,
    "entity_position_tracker": 7200,
    "metadata_enrichment": 900,
    "entity_organizer": 600,
    "ml_processing": 300,
    "topic_clustering": 300,
    "entity_extraction": 300,
    "quality_scoring": 300,
    "sentiment_analysis": 300,
    "storyline_discovery": 14400,
    "proactive_detection": 7200,
    "fact_verification": 14400,
    "storyline_processing": 300,
    "storyline_automation": 300,
    "storyline_enrichment": 43200,
    "rag_enhancement": 300,
    "event_extraction": 300,
    "event_deduplication": 600,
    "story_continuation": 600,
    "timeline_generation": 300,
    "entity_enrichment": 1800,
    "story_enhancement": 300,
    "cache_cleanup": 3600,
    "editorial_document_generation": 1800,
    "editorial_briefing_generation": 1800,
    "digest_generation": 3600,
    "watchlist_alerts": 3600,
    "data_cleanup": 86400,
    "health_check": 30,
}

PHASE_ESTIMATED_DURATION_SECONDS: dict[str, int] = {
    "collection_cycle": 1800,
    "context_sync": 60,
    "entity_profile_sync": 120,
    "claim_extraction": 60,
    "claims_to_facts": 30,
    "event_tracking": 120,
    "event_coherence_review": 180,
    "investigation_report_refresh": 300,
    "cross_domain_synthesis": 120,
    "entity_profile_build": 600,
    "pattern_recognition": 120,
    "entity_dossier_compile": 90,
    "entity_position_tracker": 300,
    "metadata_enrichment": 90,
    "entity_organizer": 180,
    "ml_processing": 240,
    "topic_clustering": 180,
    "entity_extraction": 120,
    "quality_scoring": 90,
    "sentiment_analysis": 120,
    "storyline_discovery": 600,
    "proactive_detection": 300,
    "fact_verification": 120,
    "storyline_processing": 300,
    "storyline_automation": 180,
    "storyline_enrichment": 600,
    "rag_enhancement": 600,
    "event_extraction": 300,
    "event_deduplication": 120,
    "story_continuation": 300,
    "timeline_generation": 300,
    "entity_enrichment": 180,
    "story_enhancement": 300,
    "cache_cleanup": 60,
    "editorial_document_generation": 300,
    "editorial_briefing_generation": 300,
    "digest_generation": 180,
    "watchlist_alerts": 60,
    "data_cleanup": 300,
    "health_check": 10,
    "content_enrichment": 120,
    "document_processing": 180,
    "storyline_synthesis": 600,
    "daily_briefing_synthesis": 300,
    "research_topic_refinement": 60,
}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Analyze automation_run_history for schedule tuning")
    ap.add_argument("--hours", type=int, default=3, help="Look-back window in hours (default 3)")
    ap.add_argument("--window-2h", action="store_true", help="Also report phases expected in 2h that did not run")
    args = ap.parse_args()

    hours = max(1, args.hours)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)

    cfg = _get_db_config()
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("psycopg2 required: uv add psycopg2-binary", file=sys.stderr)
        return 1

    connect_kw = {k: v for k, v in cfg.items() if k != "connect_timeout"}
    connect_kw["connect_timeout"] = cfg.get("connect_timeout", 10)
    try:
        conn = psycopg2.connect(**connect_kw)
    except Exception as e:
        print(f"Database connection failed: {e}", file=sys.stderr)
        return 1

    # Query all runs in window
    runs: list[dict] = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT phase_name, started_at, finished_at, success, error_message
                FROM automation_run_history
                WHERE finished_at >= %s
                ORDER BY finished_at ASC
                """,
                (cutoff,),
            )
            runs = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    # Aggregate by phase: count, total_sec, success_count
    by_phase: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_sec": 0.0, "success": 0})
    for r in runs:
        name = r["phase_name"]
        started = r["started_at"]
        finished = r["finished_at"]
        if started and finished:
            delta = (finished - started).total_seconds()
            by_phase[name]["total_sec"] += delta
        by_phase[name]["count"] += 1
        if r.get("success"):
            by_phase[name]["success"] += 1

    # All phase names we care about (scheduled + any that ran)
    all_phases = sorted(set(SCHEDULE_INTERVAL_SECONDS.keys()) | set(by_phase.keys()))

    print("=" * 72)
    print(f"Automation run analysis — last {hours} hours")
    print(f"Cutoff (UTC): {cutoff.isoformat()}")
    print(f"Total runs in window: {len(runs)}")
    print("=" * 72)

    # Table: phase, interval (2h?), runs, avg_duration, estimated, ratio, success_rate
    print(f"\n{'Phase':<32} {'Intv':>6} {'Runs':>4} {'Avg(s)':>7} {'Est(s)':>6} {'Ratio':>6} {'OK%':>5}")
    print("-" * 72)

    not_run_in_2h: list[tuple[str, int]] = []  # (phase, interval)
    duration_tweaks: list[tuple[str, float, float]] = []  # (phase, actual_avg, estimated)

    for name in all_phases:
        interval = SCHEDULE_INTERVAL_SECONDS.get(name)
        est = PHASE_ESTIMATED_DURATION_SECONDS.get(name)
        data = by_phase.get(name, {"count": 0, "total_sec": 0.0, "success": 0})
        count = data["count"]
        total_sec = data["total_sec"]
        success = data["success"]
        avg_sec = total_sec / count if count else 0
        ratio = (avg_sec / est) if (est and est > 0 and count) else 0
        ok_pct = (100 * success / count) if count else 0
        intv_str = f"{interval // 60}m" if interval else "—"
        if interval and interval <= 7200 and count == 0 and args.window_2h:
            not_run_in_2h.append((name, interval))
        if count and est and (ratio > 1.5 or (ratio < 0.5 and ratio > 0)):
            duration_tweaks.append((name, avg_sec, float(est)))
        print(f"{name:<32} {intv_str:>6} {count:>4} {avg_sec:>7.0f} {est or 0:>6} {ratio:>5.2f} {ok_pct:>5.1f}")

    # Phases that should run in 2h but didn't run in the analysis window
    if args.window_2h or hours >= 2:
        expected_in_2h = [
            (name, SCHEDULE_INTERVAL_SECONDS[name])
            for name in all_phases
            if SCHEDULE_INTERVAL_SECONDS.get(name) and SCHEDULE_INTERVAL_SECONDS[name] <= 7200
            and by_phase[name]["count"] == 0
        ]
        if expected_in_2h:
            print("\n--- Phases with interval ≤ 2h that did NOT run in this window ---")
            for name, interval in sorted(expected_in_2h, key=lambda x: x[1]):
                print(f"  {name}: interval {interval}s ({interval // 60}m)")

    # Duration recommendations (actual vs estimated)
    if duration_tweaks:
        print("\n--- Suggested duration tweaks (actual avg vs estimated) ---")
        for name, actual_avg, estimated in sorted(duration_tweaks, key=lambda x: -x[1]):
            ratio = actual_avg / estimated
            if ratio > 1.5:
                print(f"  {name}: actual avg {actual_avg:.0f}s >> estimated {estimated:.0f}s — consider increasing PHASE_ESTIMATED_DURATION_SECONDS['{name}'] to ~{int(actual_avg)}")
            elif ratio < 0.5:
                print(f"  {name}: actual avg {actual_avg:.0f}s << estimated {estimated:.0f}s — consider decreasing PHASE_ESTIMATED_DURATION_SECONDS['{name}'] to ~{int(actual_avg)}")

    # Summary: any phase with high run count (might need longer interval) or zero runs (might need shorter or dependency check)
    print("\n--- Summary ---")
    high_freq = [(name, by_phase[name]["count"]) for name in all_phases if by_phase[name]["count"] >= 10 and hours <= 6]
    if high_freq:
        print("  High run count (consider longer interval or step budget):")
        for name, count in sorted(high_freq, key=lambda x: -x[1]):
            intv = SCHEDULE_INTERVAL_SECONDS.get(name)
            print(f"    {name}: {count} runs in {hours}h (interval {(intv or 0) // 60}m)")
    zero_runs = [name for name in all_phases if name in SCHEDULE_INTERVAL_SECONDS and by_phase[name]["count"] == 0]
    if zero_runs:
        print("  Phases with 0 runs in window (check dependencies / enabled flag):")
        for name in zero_runs[:20]:
            intv = SCHEDULE_INTERVAL_SECONDS.get(name)
            print(f"    {name} (interval {intv // 60}m)")
        if len(zero_runs) > 20:
            print(f"    ... and {len(zero_runs) - 20} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
