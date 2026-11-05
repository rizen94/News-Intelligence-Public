#!/usr/bin/env python3
"""
Pipeline Monitor: fire RSS ingestion and watch the full enrichment pipeline.

Usage (on Widow):
    cd /home/pete/Documents/projects/news_intelligence
    PYTHONPATH=api uv run python api/scripts/pipeline_monitor.py --mode all

Modes:
    trigger   - start RSS processing via /system_monitoring/monitoring/trigger_phase
    poll      - poll API + DB to watch status change over time
    status    - one-shot overview of current state (API + DB)
    query     - run SQL queries for enrichment counts by stage
    all       - trigger -> poll (default) -> status -> query in sequence

Flags:
    --api-url URL        API base URL   (default http://localhost:8000)
    --poll-iterations N  Number of poll cycles (default 6, 15s apart)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
)
logger = logging.getLogger(__name__)

_API = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_API))

import requests

def _get(api_url: str, path: str, **kw) -> dict:
    url = f"{api_url}/api{path}"
    try:
        r = requests.get(url, timeout=15, **kw)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("GET %s -> %s", url, exc)
        return {}

def _post(api_url: str, path: str, payload=None) -> dict:
    url = f"{api_url}/api{path}"
    try:
        r = requests.post(url, json=payload or {}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("POST %s -> %s", url, exc)
        return {}

def _query_sql(sql, params=None):
    """Run a SQL query against the news_intel DB and return list of dicts."""
    try:
        from shared.database import get_db_connection_context
        with get_db_connection_context() as conn:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return rows
    except Exception as exc:
        logger.warning("SQL error: %s", exc)
        return []

def _active_domain_keys():
    try:
        from shared.domain_registry import get_pipeline_active_domain_keys
        return get_pipeline_active_domain_keys()
    except Exception:
        return []

def mode_trigger(api_url):
    logger.info("=== PHASE 1: Triggering RSS processing ===")
    result = _post(api_url, "/system_monitoring/monitoring/trigger_phase", {"phase": "rss_processing"})
    logger.info("Trigger response:")
    print(json.dumps(result, indent=2, default=str))
    return result

def mode_status(api_url):
    logger.info("=== MONITORING STATUS ===")
    status = _get(api_url, "/system_monitoring/status")
    db_conn = _get(api_url, "/system_monitoring/database/connections")
    auto_status = _get(api_url, "/system_monitoring/automation/status")
    sources = _get(api_url, "/system_monitoring/sources_collected", params={"minutes": 60})
    overview = {
        "monitoring_status": status,
        "db_connections": db_conn,
        "automation_status": auto_status,
        "sources_in_last_hour": sources.get("summary", []),
    }
    for k, v in overview.items():
        print(f"\n--- {k} ---")
        if isinstance(v, (list, dict)):
            print(json.dumps(v, indent=2, default=str)[:3000])
        else:
            print(v)
    return overview

def mode_poll(api_url, iterations=6):
    logger.info("=== POLLING (iterations=%d, 15s apart) ===", iterations)
    results = []
    for i in range(iterations):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        cycle = {"cycle": i + 1, "timestamp": ts}
        api_status = _get(api_url, "/system_monitoring/status")
        cycle["api_enriched"] = (
            api_status.get("enrichment", {}).get("count", "?")
            if isinstance(api_status, dict) else "?"
        )
        cycle["db_status"] = json.dumps(_get(api_url, "/system_monitoring/database/connections"), default=str)
        active_domains = _active_domain_keys()
        enrich_counts = {}
        for dk in (active_domains or ["default"]):
            sql = (
                "SELECT enrichment_status, timeline_processed, COUNT(*)::int AS cnt "
                "FROM articles GROUP BY enrichment_status, timeline_processed ORDER BY 1, 2"
            )
            rows = _query_sql(sql)
            if rows:
                enrich_counts["articles"] = rows
        cycle["db_enrichment_breakdown"] = enrich_counts
        timeline_rows = _query_sql(
            "SELECT CASE WHEN timeline_processed THEN 'extracted' ELSE 'pending' END AS stage, COUNT(*)::int AS cnt FROM articles GROUP BY timeline_processed ORDER BY 1"
        )
        cycle["timeline_status"] = timeline_rows
        results.append(cycle)
        print(f"\n--- Cycle {i+1}/{iterations} @ {ts} ---")
        print(json.dumps(cycle, indent=2, default=str)[:4000])
        if i < iterations - 1:
            time.sleep(15)
    return results

def mode_query(api_url):
    logger.info("=== SQL QUERIES ===")
    queries = [
        ("enrichment_status_distribution",
         "SELECT enrichment_status, COUNT(*)::int AS cnt FROM articles GROUP BY enrichment_status ORDER BY cnt DESC"),
        ("timeline_processed_split",
         "SELECT CASE WHEN timeline_processed THEN 'extracted' ELSE 'pending' END AS stage, COUNT(*)::int AS cnt FROM articles GROUP BY timeline_processed ORDER BY 1"),
        ("recently_collected_articles",
         "SELECT source_url, enrichment_status, timeline_processed, created_at FROM articles WHERE created_at > NOW() - INTERVAL '30 minutes' ORDER BY created_at DESC LIMIT 20"),
        ("pipeline_checkpoints_recent",
         "SELECT stage, COUNT(*)::int AS cnt, MIN(timestamp) AS first_ts, MAX(timestamp) AS last_ts FROM pipeline_checkpoints WHERE timestamp > NOW() - INTERVAL '2 hours' GROUP BY stage ORDER BY cnt DESC"),
        ("articles_needing_enrichment_summary",
         "SELECT COUNT(*)::int AS total, COUNT(*) FILTER (WHERE enrichment_status IS NULL OR enrichment_status = 'pending') AS pending, COUNT(*) FILTER (WHERE enrichment_status = 'enriched') AS enriched, COUNT(*) FILTER (WHERE timeline_processed = false) AS waiting_extraction FROM articles"),
    ]
    results = []
    for name, sql in queries:
        rows = _query_sql(sql)
        logger.info("Query '%s': %d rows", name, len(rows))
        print(f"\n--- {name} ({len(rows)} rows) ---")
        for row in (rows[:10] if len(rows) > 10 else rows):
            print(json.dumps(row, default=str))
        results.append({"name": name, "sql": sql, "rows": rows})
    return results

def main():
    parser = argparse.ArgumentParser(description="RSS pipeline monitor")
    parser.add_argument("--mode", choices=["trigger", "poll", "status", "query", "all"], default="all")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--poll-iterations", type=int, default=6, help="Poll cycle count")
    args = parser.parse_args()
    all_results = {}
    if args.mode in ("trigger", "all"):
        all_results["trigger"] = mode_trigger(args.api_url)
        time.sleep(2)
    if args.mode in ("poll", "all"):
        all_results["poll"] = mode_poll(args.api_url, args.poll_iterations)
    if args.mode in ("status", "all"):
        all_results["status"] = mode_status(args.api_url)
    if args.mode in ("query", "all"):
        all_results["query"] = mode_query(args.api_url)
    out_path = Path(f"/tmp/pipeline_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json").expanduser()
    try:
        out_path.write_text(json.dumps(all_results, indent=2, default=str))
        logger.info("Results saved to %s", out_path)
    except Exception:
        pass
    print("\n" + "=" * 60)
    print("PIPELINE MONITOR COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
