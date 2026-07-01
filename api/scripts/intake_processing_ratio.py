#!/usr/bin/env python3
"""
Intake-to-processing ratio report for signal-first steady-state tuning.

Prints 24h gross intake vs enrichment throughput, phase backlog breakdown,
bulk-tier pending totals, per-domain intake, and estimated full-LLM ratios
at quality-score cutoffs.

  cd /path/to/repo && PYTHONPATH=api uv run python api/scripts/intake_processing_ratio.py
  PYTHONPATH=api uv run python api/scripts/intake_processing_ratio.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    _api = Path(__file__).resolve().parent.parent
    load_dotenv(_api / ".env", override=False)
    load_dotenv(_api.parent / ".env", override=False)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_db_password() -> None:
    import os

    root = Path(__file__).resolve().parent.parent.parent
    pw_file = root / ".db_password_widow"
    if not os.environ.get("DB_PASSWORD") and pw_file.is_file():
        os.environ.setdefault("DB_PASSWORD", pw_file.read_text().splitlines()[0].strip())


def _intake_metrics(cur, schema: str) -> dict:
    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours')::bigint,
            COUNT(*) FILTER (
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND enrichment_status = 'enriched'
                  AND updated_at >= NOW() - INTERVAL '24 hours'
            )::bigint
        FROM {schema}.articles
        """
    )
    row = cur.fetchone()
    created_24h = int(row[0] or 0)
    enriched_24h = int(row[1] or 0)

    cur.execute(
        f"""
        SELECT COUNT(*) FROM {schema}.articles
        WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
          AND COALESCE(enrichment_attempts, 0) < 3
          AND url IS NOT NULL AND url != ''
        """
    )
    enrich_backlog = int(cur.fetchone()[0] or 0)

    cur.execute(
        f"""
        SELECT
            COUNT(*) FILTER (
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND COALESCE(quality_score, 0) >= %s
            )::bigint,
            COUNT(*) FILTER (
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND COALESCE(quality_score, 0) >= %s
            )::bigint,
            COUNT(*) FILTER (
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                  AND COALESCE(quality_score, 0) >= %s
            )::bigint
        FROM {schema}.articles
        """,
        (0.25, 0.35, 0.45),
    )
    r2 = cur.fetchone()
    above_025 = int(r2[0] or 0)
    above_035 = int(r2[1] or 0)
    above_045 = int(r2[2] or 0)

    return {
        "schema": schema,
        "articles_created_24h": created_24h,
        "enriched_last_24h": enriched_24h,
        "net_per_day": created_24h - enriched_24h,
        "enrichment_backlog": enrich_backlog,
        "full_llm_estimate": {
            "quality_gte_0.25": above_025,
            "quality_gte_0.35": above_035,
            "quality_gte_0.45": above_045,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Intake-to-processing ratio report")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    _load_db_password()

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_schema_names_active
    from shared.pipeline_resource_policy import (
        bulk_tier_pending_total,
        extract_bulk_pending_total,
    )

    report: dict = {"domains": [], "totals": {}, "phases": {}, "signal": {}}

    try:
        from services.backlog_metrics import get_all_pending_counts
        from services.phase_work_queue_metrics import get_all_phase_work_queues

        pending = get_all_pending_counts()
        work_queues = get_all_phase_work_queues(pending)
    except Exception as exc:
        pending = {}
        work_queues = {}
        report["phase_metrics_error"] = str(exc)[:200]

    report["bulk_tier_pending_total"] = bulk_tier_pending_total(pending)
    report["extract_bulk_pending_total"] = extract_bulk_pending_total(pending)

    phase_rows = []
    for name, wq in work_queues.items():
        phase_rows.append(
            {
                "phase": name,
                "total_pending": int(wq.get("total_pending", 0) or 0),
                "intake_first_pass": int(wq.get("intake_first_pass", 0) or 0),
                "first_pass": int(wq.get("first_pass", 0) or 0),
            }
        )
    phase_rows.sort(key=lambda x: x["total_pending"], reverse=True)
    report["phases"]["top_by_pending"] = phase_rows[:5]
    report["phases"]["top_by_intake_first_pass"] = sorted(
        phase_rows, key=lambda x: x["intake_first_pass"], reverse=True
    )[:5]
    report["phases"]["intake_first_pass_sum"] = sum(
        int(wq.get("intake_first_pass", 0) or 0) for wq in work_queues.values()
    )

    totals_created = 0
    totals_enriched = 0
    totals_above_045 = 0

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '15s'")
            for schema in get_pipeline_schema_names_active():
                try:
                    dm = _intake_metrics(cur, schema)
                    report["domains"].append(dm)
                    totals_created += dm["articles_created_24h"]
                    totals_enriched += dm["enriched_last_24h"]
                    totals_above_045 += dm["full_llm_estimate"]["quality_gte_0.45"]
                except Exception as exc:
                    report["domains"].append({"schema": schema, "error": str(exc)[:200]})

            try:
                from services.phase_work_queue_metrics import get_signal_lane_counts_24h

                report["signal"] = get_signal_lane_counts_24h(cur)
            except Exception:
                report["signal"] = {}

    net = totals_created - totals_enriched
    if totals_created == 0 and totals_enriched == 0:
        trend = "stable"
    elif net > 0:
        trend = "growing"
    elif net < 0:
        trend = "shrinking"
    else:
        trend = "stable"

    report["totals"] = {
        "articles_created_24h": totals_created,
        "enriched_last_24h": totals_enriched,
        "net_articles_per_day": net,
        "backlog_trend": trend,
        "signal_processing_ratio_at_0.45": round(
            totals_above_045 / totals_created, 3
        )
        if totals_created
        else None,
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    print("=== Intake-to-processing ratio ===")
    t = report["totals"]
    print(
        f"24h intake: {t['articles_created_24h']} created | "
        f"{t['enriched_last_24h']} enriched | net {t['net_articles_per_day']} ({t['backlog_trend']})"
    )
    if t.get("signal_processing_ratio_at_0.45") is not None:
        print(
            f"Estimated full-LLM ratio @ quality>=0.45: {t['signal_processing_ratio_at_0.45']:.1%}"
        )
    print(f"bulk_tier_pending: {report['bulk_tier_pending_total']}")
    print(f"extract_bulk_pending: {report['extract_bulk_pending_total']}")
    print(f"intake_first_pass sum: {report['phases'].get('intake_first_pass_sum', 0)}")

    print("\nPer domain:")
    for dm in report["domains"]:
        if "error" in dm:
            print(f"  {dm['schema']}: ERROR {dm['error']}")
            continue
        est = dm["full_llm_estimate"]
        print(
            f"  {dm['schema']}: +{dm['articles_created_24h']} / enrich {dm['enriched_last_24h']} "
            f"(net {dm['net_per_day']}) | full@0.45={est['quality_gte_0.45']}"
        )

    print("\nTop phases by pending:")
    for row in report["phases"].get("top_by_pending", []):
        print(
            f"  {row['phase']}: pending={row['total_pending']} "
            f"intake_first_pass={row['intake_first_pass']}"
        )

    sig = report.get("signal") or {}
    if sig:
        print(
            f"\nSignal lanes (24h): full={sig.get('signal_full_24h', 0)} "
            f"deferred={sig.get('signal_deferred_24h', 0)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
