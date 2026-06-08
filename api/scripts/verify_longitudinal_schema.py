#!/usr/bin/env python3
"""
Verify longitudinal intelligence DB objects (migrations 221–225).

Exit 0 when all required objects exist; 1 lists missing items.

  PYTHONPATH=api uv run python api/scripts/verify_longitudinal_schema.py
"""

from __future__ import annotations

import sys

from shared.database.connection import get_ui_db_connection_context

REQUIRED_TABLES = (
    "intelligence.reference_events",
    "intelligence.arc_definitions",
    "intelligence.arc_reports",
    "intelligence.macro_series_observations",
    "intelligence.external_events",
    "intelligence.sanctions_actions",
    "intelligence.citation_registry",
    "intelligence.embedding_chunks",
    "intelligence.arc_report_feedback",
    "intelligence.reference_event_flags",
    "intelligence.cross_domain_correlations",
)

REQUIRED_COLUMNS = (
    ("intelligence.versioned_facts", "ingestion_date"),
    ("intelligence.arc_reports", "report_type"),
    ("intelligence.embedding_chunks", "embedding"),
)

REQUIRED_MATVIEWS = (
    "intelligence.mv_arc_spine_events",
    "intelligence.mv_tension_heatmap_monthly",
)

REQUIRED_EXTENSION = "vector"


def _table_exists(cur, qualified: str) -> bool:
    schema, table = qualified.split(".", 1)
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        LIMIT 1
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def _column_exists(cur, qualified: str, column: str) -> bool:
    schema, table = qualified.split(".", 1)
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (schema, table, column),
    )
    return cur.fetchone() is not None


def _matview_exists(cur, qualified: str) -> bool:
    schema, name = qualified.split(".", 1)
    cur.execute(
        """
        SELECT 1 FROM pg_matviews
        WHERE schemaname = %s AND matviewname = %s
        LIMIT 1
        """,
        (schema, name),
    )
    return cur.fetchone() is not None


def _extension_exists(cur, name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM pg_extension WHERE extname = %s LIMIT 1",
        (name,),
    )
    return cur.fetchone() is not None


def _cross_domain_table_ok(cur) -> bool:
    if not _table_exists(cur, "intelligence.cross_domain_correlations"):
        return False
    return _column_exists(cur, "intelligence.cross_domain_correlations", "correlation_id")


def _quarantine_allowed(cur) -> bool:
    cur.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'intelligence.arc_reports'::regclass
          AND conname = 'arc_reports_report_type_check'
        LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        return False
    return "quarantine" in (row[0] or "")


def main() -> int:
    missing: list[str] = []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                if not _extension_exists(cur, REQUIRED_EXTENSION):
                    missing.append(f"extension {REQUIRED_EXTENSION}")

                for t in REQUIRED_TABLES:
                    if t == "intelligence.cross_domain_correlations":
                        if not _cross_domain_table_ok(cur):
                            missing.append(f"table {t} (context-centric schema)")
                        continue
                    if not _table_exists(cur, t):
                        missing.append(f"table {t}")

                for t, c in REQUIRED_COLUMNS:
                    if not _column_exists(cur, t, c):
                        missing.append(f"column {t}.{c}")

                for mv in REQUIRED_MATVIEWS:
                    if not _matview_exists(cur, mv):
                        missing.append(f"matview {mv}")

                if not _quarantine_allowed(cur):
                    missing.append("constraint arc_reports_report_type_check (quarantine)")

                cur.execute(
                    "SELECT COUNT(*) FROM intelligence.reference_events WHERE superseded_by_id IS NULL"
                )
                ref_count = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM intelligence.arc_definitions WHERE is_active")
                arc_count = cur.fetchone()[0] or 0
    except Exception as e:
        print(f"FAIL: cannot connect or query DB: {e}")
        return 1

    if missing:
        print("FAIL missing longitudinal objects:")
        for m in missing:
            print(f"  - {m}")
        print("\nApply pending migrations 221–225 and run scripts/resume_longitudinal_widow.sh")
        return 1

    print(
        f"OK longitudinal schema — reference_events={ref_count} active_arcs={arc_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
