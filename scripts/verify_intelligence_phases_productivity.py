#!/usr/bin/env python3
"""
Verify that "less noticeable" intelligence phases are actually producing data.

Checks automation_run_history (are they running?) + output tables (are they writing?).

From repo root:
  PYTHONPATH=api uv run python scripts/verify_intelligence_phases_productivity.py
  PYTHONPATH=api uv run python scripts/verify_intelligence_phases_productivity.py --write-report docs/generated/INTELLIGENCE_PHASES_PRODUCTIVITY_REPORT.md
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone, timedelta

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

# Typical workflow output first; optional phases are cost/latency audits if you do not use those features.
PHASE_OUTPUT_ORDER_CORE = (
    "entity_enrichment",
    "claims_to_facts",
    "pattern_recognition",
    "event_coherence_review",
    "pattern_matching",
    "content_refinement_queue",
)
PHASE_OUTPUT_ORDER_OPTIONAL = (
    "cross_domain_synthesis",
    "fact_verification",
    "story_enhancement",
    "research_topic_refinement",
    "investigation_report_refresh",
    "rag_enhancement",
    "timeline_generation",
)

PHASES = {
    "entity_enrichment": {
        "output_table": "intelligence.entity_profiles",
        "output_columns": ["sections", "updated_at"],
        "recent_column": "updated_at",
        "filter": "sections IS NOT NULL AND sections::text != '[]' AND sections::text != '{}'",
        "_custom_metrics": True,
    },
    "claims_to_facts": {
        "output_table": "intelligence.versioned_facts",
        "output_columns": ["id", "entity_profile_id", "fact_type", "extraction_method"],
        "recent_column": "created_at",
        "filter": "extraction_method != 'wikipedia'",  # entity_enrichment also writes here
    },
    "pattern_recognition": {
        "output_table": "intelligence.pattern_discoveries",
        "output_columns": ["id", "pattern_type", "domain_key", "confidence"],
        "recent_column": "created_at",
    },
    "event_coherence_review": {
        "output_table": "intelligence.tracked_events",
        "output_columns": ["id", "context_ids"],
        "recent_column": "updated_at",
        "note": "Writes `last_coherence_review` on event_chronicles.analysis; tracked_events.updated_at may lag.",
        "_custom_metrics": True,
    },
    "pattern_matching": {
        "output_table": "intelligence.pattern_matches",
        "output_columns": ["id", "watchlist_id", "alert_created"],
        "recent_column": "created_at",
    },
    "content_refinement_queue": {
        "output_table": "intelligence.content_refinement_queue",
        "output_columns": ["id", "job_type", "status", "completed_at"],
        "recent_column": "completed_at",
        "note": "RAG, ~70B narrative finisher, timeline narratives; UI reads stored storylines columns.",
        "_custom_metrics": True,
    },
    "cross_domain_synthesis": {
        "output_table": "intelligence.cross_domain_correlations",
        "output_columns": ["correlation_id", "domain_1", "domain_2", "correlation_strength"],
        "recent_column": "discovered_at",
        "note": "Optional: cross-domain event correlations—skip or throttle if unused.",
    },
    "fact_verification": {
        "_custom_metrics": True,
        "note": "Optional: LLM corroboration over `extracted_claims`; weak durable footprint—audit run history + API logs.",
    },
    "story_enhancement": {
        "output_table": "intelligence.fact_change_log",
        "output_columns": ["id", "processed", "processed_at"],
        "recent_column": "processed_at",
        "filter": "processed = TRUE",
        "note": "Optional: orchestrates fact_change_log, story_update_queue, enrich/build batches.",
    },
    "research_topic_refinement": {
        "output_table": "finance.research_topics",
        "output_columns": ["id", "topic", "last_refined_at"],
        "recent_column": "updated_at",
        "note": "Optional: finance-only idle orchestrator submits analysis tasks.",
    },
    "investigation_report_refresh": {
        "output_table": "intelligence.event_reports",
        "output_columns": ["id", "event_id", "updated_at"],
        "recent_column": "updated_at",
        "note": "Optional: gated by context_centric_config; may be idle if event_reports already fresh.",
    },
    "rag_enhancement": {
        "_custom_metrics": True,
        "note": "Optional: per-domain `storylines` RAG pass (`rag_enhanced_at`).",
    },
    "timeline_generation": {
        "_custom_metrics": True,
        "note": "Optional: fills `storylines.timeline_summary` from `public.chronological_events`.",
    },
}

# Phases not in PHASES output table loop but useful in automation_run_history
_AUTOMATION_HISTORY_EXTRA = (
    "event_extraction",
    "event_tracking",
    "topic_clustering",
    "quality_scoring",
    "sentiment_analysis",
    "nightly_enrichment_context",
    "collection_cycle",
    "context_sync",
    "content_enrichment",
    "ml_processing",
    "entity_extraction",
)


def _write_entity_enrichment_section(
    cur, lines: list[str], hours: int, since: datetime
) -> None:
    lines.append("### `entity_enrichment`")
    lines.append("")
    lines.append(
        "**Output:** `intelligence.entity_profiles` (Wikipedia section) + "
        "`intelligence.versioned_facts` (`extraction_method = wikipedia`)"
    )
    lines.append("")
    cur.execute(
        """
        SELECT COUNT(*) FROM intelligence.entity_profiles
        WHERE sections IS NOT NULL
          AND sections::text ILIKE '%%Background (Wikipedia)%%'
        """
    )
    total_wiki = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*) FROM intelligence.entity_profiles
        WHERE sections IS NOT NULL
          AND sections::text ILIKE '%%Background (Wikipedia)%%'
          AND updated_at >= %s
        """,
        (since,),
    )
    recent_wiki_section = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*) FROM intelligence.versioned_facts
        WHERE extraction_method = 'wikipedia' AND created_at >= %s
        """,
        (since,),
    )
    recent_wiki_facts = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*) FROM intelligence.entity_profiles ep
        WHERE ep.updated_at >= %s
          AND (
            ep.sections::text ILIKE '%%Background (Wikipedia)%%'
            OR EXISTS (
              SELECT 1 FROM intelligence.versioned_facts vf
              WHERE vf.entity_profile_id = ep.id
                AND vf.extraction_method = 'wikipedia'
                AND vf.created_at >= %s
            )
          )
        """,
        (since, since),
    )
    profiles_activity = cur.fetchone()[0]
    ok_recent = recent_wiki_section > 0 or recent_wiki_facts > 0
    status = "✅" if ok_recent else ("⚠️" if total_wiki > 0 else "❌")
    lines.append(f"- **Status:** {status}")
    lines.append(f"- **Profiles with Wikipedia section (total):** {total_wiki:,}")
    lines.append(
        f"- **Profiles: Wikipedia section updated (last {hours}h):** {recent_wiki_section:,}"
    )
    lines.append(f"- **versioned_facts Wikipedia rows (last {hours}h):** {recent_wiki_facts:,}")
    lines.append(
        f"- **Profiles touched (wiki section or new wiki facts, last {hours}h):** {profiles_activity:,}"
    )
    lines.append("")
    if not ok_recent and total_wiki > 0:
        lines.append(
            "  > ⚠️ **No recent wiki writes** — check Wikipedia/connector failures or enrichment queue."
        )
        lines.append("")


def _write_event_coherence_section(
    cur, conn, lines: list[str], hours: int, since: datetime
) -> None:
    from shared.domain_registry import get_schema_names_active

    lines.append("### `event_coherence_review`")
    lines.append("")
    lines.append(
        "**Effect:** updates `intelligence.event_chronicles` (`analysis.last_coherence_review`, developments)."
    )
    lines.append("")
    lines.append("**Upstream (stable events before coherence):**")
    lines.append("")
    chrono_total = chrono_recent = None
    try:
        cur.execute("SELECT COUNT(*) FROM public.chronological_events")
        chrono_total = cur.fetchone()[0]
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM public.chronological_events
                WHERE created_at >= %s
                """,
                (since,),
            )
            chrono_recent = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            chrono_recent = None
    except Exception as e:
        conn.rollback()
        lines.append(f"- **`public.chronological_events`:** not available — {e}")
    else:
        if chrono_recent is not None:
            lines.append(
                f"- **`public.chronological_events` (v5 extraction sink):** {chrono_total:,} total; "
                f"{chrono_recent:,} rows with `created_at` in last {hours}h"
            )
        else:
            lines.append(
                f"- **`public.chronological_events`:** {chrono_total:,} total "
                f"(no `created_at` window metric — check row growth vs `event_extraction` runs)"
            )
    try:
        cur.execute("SELECT COUNT(*) FROM intelligence.tracked_events")
        te_all = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM intelligence.event_chronicles")
        ec_all = cur.fetchone()[0]
        lines.append(
            f"- **`event_tracking` sinks:** `tracked_events` {te_all:,} rows; `event_chronicles` {ec_all:,} rows"
        )
    except Exception as e:
        conn.rollback()
        lines.append(f"- **event_tracking tables:** error — {e}")
    pending_extract = 0
    try:
        for schema in get_schema_names_active():
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.articles a
                WHERE a.timeline_processed = false
                  AND a.content IS NOT NULL
                  AND LENGTH(a.content) > 100
                  AND (
                      a.processing_status = 'completed'
                      OR a.enrichment_status IN ('completed', 'enriched')
                  )
                """
            )
            pending_extract += int(cur.fetchone()[0] or 0)
        lines.append(
            f"- **`event_extraction` backlog (articles matching automation predicate, all domains):** {pending_extract:,}"
        )
    except Exception as e:
        conn.rollback()
        lines.append(f"- **event_extraction backlog:** error — {e}")
    lines.append("")
    chron_recent = 0
    try:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM intelligence.event_chronicles ec
            WHERE ec.analysis IS NOT NULL
              AND (ec.analysis::jsonb ? 'last_coherence_review')
              AND NULLIF(trim(ec.analysis::jsonb ->> 'last_coherence_review'), '') IS NOT NULL
              AND (ec.analysis::jsonb ->> 'last_coherence_review')::timestamptz >= %s
            """,
            (since,),
        )
        chron_recent = cur.fetchone()[0]
    except Exception as e:
        conn.rollback()
        lines.append(f"- **Chronicle coherence metric:** error — {e}")
        lines.append("")
    cur.execute(
        """
        SELECT COUNT(*), MAX(updated_at) FROM intelligence.tracked_events
        WHERE updated_at >= %s
        """,
        (since,),
    )
    te_recent, te_max = cur.fetchone()
    te_max_str = te_max.isoformat() if te_max else "never"
    status = "✅" if chron_recent > 0 else "⚠️"
    lines.append(f"- **Status:** {status}")
    lines.append(
        f"- **Chronicles with `last_coherence_review` in window (last {hours}h):** {chron_recent:,}"
    )
    lines.append(
        f"- **tracked_events rows updated (last {hours}h):** {te_recent:,} (max `updated_at` {te_max_str})"
    )
    lines.append("")
    if chron_recent == 0:
        lines.append(
            "  > ℹ️ Prefer **chronicles** count above; `tracked_events.updated_at` may lag when only developments change."
        )
        lines.append("")


def _write_content_refinement_section(
    cur, conn, lines: list[str], hours: int, since: datetime
) -> None:
    from shared.domain_registry import get_schema_names_active

    lines.append("### `content_refinement_queue`")
    lines.append("")
    lines.append(
        "**Output:** queue rows in `intelligence.content_refinement_queue`; "
        "narratives land on `{schema}.storylines` (`canonical_narrative`, `narrative_finisher_at`, timeline text)."
    )
    lines.append("")
    try:
        cur.execute(
            """
            SELECT status, COUNT(*) FROM intelligence.content_refinement_queue
            GROUP BY status ORDER BY status
            """
        )
        for st, cnt in cur.fetchall() or []:
            lines.append(f"- **Queue `{st}`:** {int(cnt):,}")
        cur.execute(
            """
            SELECT job_type, status, COUNT(*)
            FROM intelligence.content_refinement_queue
            WHERE completed_at >= %s
            GROUP BY job_type, status
            ORDER BY job_type, status
            """,
            (since,),
        )
        rows = cur.fetchall() or []
        if rows:
            lines.append(f"- **Completions in last {hours}h (by job_type × status):**")
            for jt, st, cnt in rows:
                lines.append(f"  - `{jt}` / `{st}`: {int(cnt):,}")
        else:
            lines.append(f"- **Completions in last {hours}h:** none")
        cur.execute(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at)))
            FROM intelligence.content_refinement_queue
            WHERE status = 'completed'
              AND job_type IN ('narrative_finisher', 'headline_refiner')
              AND completed_at >= %s
              AND started_at IS NOT NULL
            """,
            (since,),
        )
        avg_sec = cur.fetchone()[0]
        if avg_sec is not None:
            lines.append(
                f"- **Mean wall time (completed ~70B jobs in window):** {float(avg_sec):.0f}s "
                f"(`narrative_finisher` + `headline_refiner`)"
            )
    except Exception as e:
        conn.rollback()
        lines.append(f"- **Queue metrics:** error — {e}")
    lines.append("")
    lines.append("**Stored narratives (what the UI reads, not Ollama time):**")
    lines.append("")
    try:
        filled = finisher_at = 0
        for schema in get_schema_names_active():
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storylines
                WHERE canonical_narrative IS NOT NULL AND btrim(canonical_narrative) <> ''
                """
            )
            filled += int(cur.fetchone()[0] or 0)
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storylines
                WHERE narrative_finisher_at >= %s
                """,
                (since,),
            )
            finisher_at += int(cur.fetchone()[0] or 0)
        lines.append(
            f"- **Storylines with non-empty `canonical_narrative` (all domains):** {filled:,}"
        )
        lines.append(
            f"- **Storylines with `narrative_finisher_at` in window:** {finisher_at:,}"
        )
    except Exception as e:
        conn.rollback()
        lines.append(f"- **Storyline narrative columns:** error — {e}")
    lines.append("")


def _write_rag_enhancement_section(
    cur, conn, lines: list[str], hours: int, since: datetime
) -> None:
    from shared.domain_registry import get_schema_names_active

    lines.append("### `rag_enhancement`")
    lines.append("")
    lines.append("**Output:** per-domain `storylines` (`rag_enhanced_at`, RAG metadata).")
    lines.append("")
    lines.append("*Optional / cost-latency: disable or widen interval if you do not read RAG-enhanced storylines.*")
    lines.append("")
    recent = 0
    total_enh = 0
    try:
        for schema in get_schema_names_active():
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storylines
                WHERE rag_enhanced_at IS NOT NULL
                """
            )
            total_enh += int(cur.fetchone()[0] or 0)
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storylines
                WHERE rag_enhanced_at >= %s
                """,
                (since,),
            )
            recent += int(cur.fetchone()[0] or 0)
        st = "✅" if recent > 0 else ("⚠️" if total_enh > 0 else "❌")
        lines.append(f"- **Status:** {st}")
        lines.append(f"- **Storylines ever RAG-touched (`rag_enhanced_at` set):** {total_enh:,}")
        lines.append(f"- **RAG touches in last {hours}h:** {recent:,}")
    except Exception as e:
        conn.rollback()
        lines.append(f"- **rag_enhancement metrics:** error — {e}")
    lines.append("")


def _write_timeline_generation_section(
    cur, conn, lines: list[str], hours: int, since: datetime
) -> None:
    from shared.domain_registry import get_schema_names_active

    lines.append("### `timeline_generation`")
    lines.append("")
    lines.append("**Output:** per-domain `storylines.timeline_summary` (from `public.chronological_events`).")
    lines.append("")
    lines.append("*Optional / cost-latency: overlaps with timeline narratives from refinement queue on some installs.*")
    lines.append("")
    recent = 0
    total_nonempty = 0
    try:
        for schema in get_schema_names_active():
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storylines
                WHERE timeline_summary IS NOT NULL
                  AND LENGTH(TRIM(COALESCE(timeline_summary, ''))) >= 100
                """
            )
            total_nonempty += int(cur.fetchone()[0] or 0)
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storylines
                WHERE timeline_summary IS NOT NULL
                  AND LENGTH(TRIM(COALESCE(timeline_summary, ''))) >= 100
                  AND updated_at >= %s
                """,
                (since,),
            )
            recent += int(cur.fetchone()[0] or 0)
        st = "✅" if recent > 0 else ("⚠️" if total_nonempty > 0 else "❌")
        lines.append(f"- **Status:** {st}")
        lines.append(f"- **Storylines with substantive `timeline_summary`:** {total_nonempty:,}")
        lines.append(f"- **Summaries touched in last {hours}h (`updated_at`):** {recent:,}")
    except Exception as e:
        conn.rollback()
        lines.append(f"- **timeline_generation metrics:** error — {e}")
    lines.append("")


def _write_fact_verification_audit_section(
    cur, conn, lines: list[str], hours: int, since: datetime
) -> None:
    lines.append("### `fact_verification`")
    lines.append("")
    lines.append(
        "**Output:** automation calls `verify_recent_claims` per domain; results are primarily **diagnostic** "
        "(check API / service logs for `claims_verified` and status summaries)."
    )
    lines.append("")
    lines.append("*Optional / cost-latency: each run issues LLM work over recent `extracted_claims` without a single summary table.*")
    lines.append("")
    try:
        cur.execute(
            """
            SELECT COUNT(*) FROM intelligence.extracted_claims
            WHERE confidence >= 0.5 AND created_at >= %s
            """,
            (since,),
        )
        pool = cur.fetchone()[0]
        lines.append(
            f"- **High-confidence claims in window (candidate pool):** {int(pool):,} — verification consumes these when scheduled."
        )
    except Exception as e:
        conn.rollback()
        lines.append(f"- **Claim pool hint:** error — {e}")
    lines.append("")


def _write_nightly_enrichment_context_section(
    cur, conn, lines: list[str], hours: int, since: datetime
) -> None:
    import os

    from services.nightly_ingest_window_service import (
        in_nightly_enrichment_context_window_est,
        in_nightly_pipeline_window_est,
        nightly_automation_tz,
        nightly_ingest_exclusive_automation_enabled,
    )

    lines.append("### `nightly_enrichment_context`")
    lines.append("")
    lines.append(
        "**Role:** unified local-night drain — kickoff RSS (once/day) → `content_enrichment` → "
        "`context_sync` → `NIGHTLY_SEQUENTIAL_PHASES` → `content_refinement_queue` (higher GPU caps). "
        "Daytime `content_refinement_queue` skips during this window."
    )
    lines.append("")
    zi = nightly_automation_tz()
    start_h = int(os.environ.get("NIGHTLY_PIPELINE_START_HOUR", "2"))
    end_h = int(os.environ.get("NIGHTLY_PIPELINE_END_HOUR", "7"))
    sub_s = int(os.environ.get("NIGHTLY_ENRICHMENT_CONTEXT_START_HOUR", "2"))
    sub_e = int(os.environ.get("NIGHTLY_ENRICHMENT_CONTEXT_END_HOUR", "7"))
    tz_key = getattr(zi, "key", None) or str(zi)
    lines.append(f"- **Timezone:** `{tz_key}` (env: `NIGHTLY_PIPELINE_TZ` / `NIGHTLY_INGEST_TZ`)")
    lines.append(
        f"- **Unified pipeline window [start, end):** {start_h:02d}:00–{end_h:02d}:00 local — "
        f"**in window now:** `{in_nightly_pipeline_window_est()}`"
    )
    lines.append(
        f"- **Ingest exclusive sub-window:** {sub_s:02d}:00–{sub_e:02d}:00 local — "
        f"**in sub-window now:** `{in_nightly_enrichment_context_window_est()}`"
    )
    lines.append(
        f"- **NIGHTLY_INGEST_EXCLUSIVE_AUTOMATION:** `{nightly_ingest_exclusive_automation_enabled()}`"
    )
    lines.append(
        f"- **NIGHTLY_INGEST_ALLOW:** `{os.environ.get('NIGHTLY_INGEST_ALLOW', 'nightly_enrichment_context,content_enrichment,health_check,pending_db_flush,collection_cycle')}`"
    )
    lines.append("")
    try:
        cur.execute(
            """
            SELECT COUNT(*), COUNT(*) FILTER (WHERE success), COUNT(*) FILTER (WHERE NOT success),
                   MAX(finished_at)
            FROM public.automation_run_history
            WHERE phase_name = 'nightly_enrichment_context' AND finished_at >= %s
            """,
            (since,),
        )
        r = cur.fetchone()
        tot, okc, bad, last = r[0], r[1], r[2], r[3]
        last_str = last.isoformat() if last else "never"
        lines.append(
            f"- **Runs in report window:** {tot} (success {okc}, failed {bad}); last `{last_str}`"
        )
    except Exception as e:
        conn.rollback()
        lines.append(f"- **automation_run_history:** error — {e}")
    lines.append("")
    lines.append("**GPU / queue visibility (same table as daytime refinement):**")
    lines.append("")
    try:
        cur.execute(
            """
            SELECT COUNT(*), job_type
            FROM intelligence.content_refinement_queue
            WHERE status = 'completed'
              AND completed_at >= %s
              AND EXTRACT(HOUR FROM completed_at AT TIME ZONE %s) >= %s
              AND EXTRACT(HOUR FROM completed_at AT TIME ZONE %s) < %s
            GROUP BY job_type
            ORDER BY job_type
            """,
            (since, tz_key, start_h, tz_key, end_h),
        )
        rows = cur.fetchall() or []
        if rows:
            lines.append(
                f"- **Refinement jobs completed during local night hours ({start_h:02d}:00–{end_h:02d}:00 {tz_key}) "
                f"within the last {hours}h wall window:**"
            )
            for cnt, jt in rows:
                lines.append(f"  - `{jt}`: {int(cnt):,}")
        else:
            lines.append(
                f"- **Refinement completions in local night slot:** none in last {hours}h wall-clock slice "
                f"(expected 0 if the report window does not overlap your night hours)."
            )
    except Exception as e:
        conn.rollback()
        lines.append(f"- **Night-hour refinement slice:** error — {e}")
    lines.append("")
    lines.append(
        "> **GPU contention:** nightly drain raises finisher/job caps (`content_refinement_queue_service`); "
        "overlaps with manual Monitor runs only if you force the phase outside the clock window."
    )
    lines.append("")


def _emit(lines: list[str], path: str | None) -> None:
    text = "\n".join(lines) + "\n"
    print(text.rstrip())
    if path:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        preamble = (
            "<!-- Auto-generated by scripts/verify_intelligence_phases_productivity.py -->\n\n"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(preamble)
            f.write(text)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--write-report",
        metavar="PATH",
        help="Write markdown report (e.g. docs/generated/INTELLIGENCE_PHASES_PRODUCTIVITY_REPORT.md)",
    )
    p.add_argument("--hours", type=int, default=48, help="Window for recent activity (default: 48)")
    args = p.parse_args()

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        print("ERROR: no database connection")
        return 1

    lines: list[str] = []
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=args.hours)
    cutoff_str = since.isoformat()

    lines.append(f"# Intelligence phases productivity ({now.isoformat()})")
    lines.append("")
    lines.append(f"Window: last **{args.hours} hours** (since {cutoff_str})")
    lines.append("")

    cur = conn.cursor()
    ok = True
    try:
        lines.append("## Automation run history (are phases executing?)")
        lines.append("")
        lines.append(f"| Phase | Runs ({args.hours}h) | Success | Failed | Last run |")
        lines.append("|-------|------------|---------|--------|----------|")

        history_phases = sorted(set(PHASES.keys()) | set(_AUTOMATION_HISTORY_EXTRA))
        for phase_name in history_phases:
            cur.execute(
                """
                SELECT COUNT(*), COUNT(*) FILTER (WHERE success), COUNT(*) FILTER (WHERE NOT success),
                       MAX(finished_at)
                FROM public.automation_run_history
                WHERE phase_name = %s AND finished_at >= %s
                """,
                (phase_name, since),
            )
            r = cur.fetchone()
            total, ok_count, fail_count, last = r[0], r[1], r[2], r[3]
            last_str = last.isoformat() if last else "never"
            lines.append(f"| `{phase_name}` | {total} | {ok_count} | {fail_count} | {last_str} |")

        lines.append("")
        lines.append("## Output tables — core workflow")
        lines.append("")

        def emit_phase_output(phase_name: str) -> None:
            nonlocal ok
            info = PHASES[phase_name]
            if info.get("_custom_metrics") and phase_name == "rag_enhancement":
                _write_rag_enhancement_section(cur, conn, lines, args.hours, since)
                return
            if info.get("_custom_metrics") and phase_name == "timeline_generation":
                _write_timeline_generation_section(cur, conn, lines, args.hours, since)
                return
            if info.get("_custom_metrics") and phase_name == "fact_verification":
                _write_fact_verification_audit_section(cur, conn, lines, args.hours, since)
                return

            table = info["output_table"]
            recent_col = info.get("recent_column", "created_at")
            filter_clause = f"WHERE {info['filter']} AND" if info.get("filter") else "WHERE"

            lines.append(f"### `{phase_name}`")
            lines.append("")
            lines.append(f"**Output:** `{table}`")
            if info.get("note"):
                lines.append(f"*Note: {info['note']}*")
            lines.append("")

            try:
                if info.get("_custom_metrics") and phase_name == "entity_enrichment":
                    _write_entity_enrichment_section(cur, lines, args.hours, since)
                    return
                if info.get("_custom_metrics") and phase_name == "event_coherence_review":
                    _write_event_coherence_section(
                        cur, conn, lines, args.hours, since
                    )
                    return
                if info.get("_custom_metrics") and phase_name == "content_refinement_queue":
                    _write_content_refinement_section(
                        cur, conn, lines, args.hours, since
                    )
                    return
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {table}
                    """
                )
                total_rows = cur.fetchone()[0]

                where_base = filter_clause if info.get("filter") else "WHERE"
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {table}
                    {where_base} {recent_col} >= %s
                    """,
                    (since,),
                )
                recent_rows = cur.fetchone()[0]

                max_where = ""
                if info.get("filter"):
                    max_where = f"WHERE {info['filter']}"
                cur.execute(
                    f"""
                    SELECT MAX({recent_col}) FROM {table}
                    {max_where}
                    """
                )
                max_ts = cur.fetchone()[0]
                max_str = max_ts.isoformat() if max_ts else "never"

                status = "✅" if recent_rows > 0 else ("⚠️" if total_rows > 0 else "❌")
                lines.append(f"- **Status:** {status}")
                lines.append(f"- **Total rows:** {total_rows:,}")
                lines.append(f"- **Rows in last {args.hours}h:** {recent_rows:,}")
                lines.append(f"- **Most recent:** {max_str}")
                lines.append("")

                if total_rows == 0 and phase_name in ("pattern_recognition", "pattern_matching"):
                    lines.append(
                        f"  > ⚠️ **No rows** — table may be empty or phase hasn't produced output yet."
                    )
                    lines.append("")
                elif recent_rows == 0 and total_rows > 0:
                    lines.append(
                        f"  > ⚠️ **No recent activity** — phase may be idle or only processing when conditions are met."
                    )
                    lines.append("")

                if phase_name == "pattern_matching":
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM intelligence.pattern_matches
                        WHERE significance_score >= 0.5
                          AND storyline_id IS NULL
                          AND created_at >= %s
                        """,
                        (since,),
                    )
                    hi_no_sid = cur.fetchone()[0]
                    lines.append(
                        f"- **Matches significance≥0.5 with `storyline_id` NULL (last {args.hours}h):** "
                        f"{hi_no_sid:,} — `watchlist_alerts` need a linked storyline on `watchlist`."
                    )
                    lines.append("")

            except Exception as e:
                conn.rollback()
                lines.append(f"  ❌ **Error querying table:** {e}")
                lines.append("")
                ok = False

        for phase_name in PHASE_OUTPUT_ORDER_CORE:
            emit_phase_output(phase_name)

        lines.append("## Output tables — optional (cost / latency if not in your workflow)")
        lines.append("")
        for phase_name in PHASE_OUTPUT_ORDER_OPTIONAL:
            emit_phase_output(phase_name)

        lines.append("## Nightly unified pipeline (`nightly_enrichment_context`)")
        lines.append("")
        _write_nightly_enrichment_context_section(cur, conn, lines, args.hours, since)

        lines.append("## Cross-checks")
        lines.append("")

        # Scheduler pending counts (same queries as backlog_metrics — foundation + storyline pool)
        try:
            from services.backlog_metrics import (
                get_all_pending_counts,
                invalidate_backlog_metrics_cache,
            )

            invalidate_backlog_metrics_cache()
            pend = get_all_pending_counts()
            lines.append("### Foundation + document backlog (scheduler `pending`)")
            lines.append("")
            for key in (
                "content_enrichment",
                "context_sync",
                "ml_processing",
                "metadata_enrichment",
                "entity_extraction",
                "document_processing",
            ):
                lines.append(f"- **`{key}` pending:** {int(pend.get(key, 0) or 0):,}")
            ce = int(pend.get("content_enrichment", 0) or 0)
            cs = int(pend.get("context_sync", 0) or 0)
            dp = int(pend.get("document_processing", 0) or 0)
            lines.append(
                f"- **`collection_cycle` throttle default sum** (enrichment+context_sync+docs): **{ce + cs + dp:,}** "
                f"(threshold 500; set `COLLECTION_THROTTLE_EXTRA_PHASES` to add more phases)"
            )
            lines.append("")
            lines.append("### Storyline pool (scheduler `pending`)")
            lines.append("")
            for key in (
                "storyline_discovery",
                "proactive_detection",
                "storyline_automation",
                "storyline_processing",
            ):
                lines.append(f"- **`{key}` pending:** {int(pend.get(key, 0) or 0):,}")
            lines.append("")
        except Exception as e:
            conn.rollback()
            lines.append(f"- **Backlog cross-check:** error — {e}")
            lines.append("")

        # versioned_facts: both claims_to_facts AND entity_enrichment write here
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.versioned_facts
                WHERE created_at >= %s AND extraction_method = 'claim_extraction'
                """,
                (since,),
            )
            from_claims = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.versioned_facts
                WHERE created_at >= %s AND extraction_method = 'wikipedia'
                """,
                (since,),
            )
            from_wiki = cur.fetchone()[0]
            lines.append(
                f"- **`versioned_facts`** (last {args.hours}h): {from_claims} from `claims_to_facts`, {from_wiki} from `entity_enrichment`"
            )
        except Exception as e:
            conn.rollback()
            lines.append(f"- **`versioned_facts` breakdown:** error — {e}")

        # Claims pipeline: promotable queue vs recent promotions
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims ec
                WHERE ec.confidence >= 0.7
                  AND NOT EXISTS (
                      SELECT 1 FROM intelligence.versioned_facts vf
                      WHERE vf.metadata->>'source_claim_id' = ec.id::text
                  )
                """
            )
            promotable = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims
                WHERE created_at >= %s
                """,
                (since,),
            )
            claims_new = cur.fetchone()[0]
            lines.append(
                f"- **`extracted_claims`:** {promotable:,} high-confidence (≥0.7) not yet in `versioned_facts`; "
                f"{claims_new:,} new rows (last {args.hours}h)"
            )
        except Exception as e:
            conn.rollback()
            lines.append(f"- **`extracted_claims` / claims queue:** error — {e}")

        # pattern_matches with alerts
        try:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.pattern_matches
                WHERE created_at >= %s AND alert_created = TRUE
                """,
                (since,),
            )
            with_alerts = cur.fetchone()[0]
            lines.append(
                f"- **`pattern_matches` with alerts created:** {with_alerts} (last {args.hours}h)"
            )
        except Exception as e:
            conn.rollback()
            lines.append(f"- **`pattern_matches` alerts:** error — {e}")

        # Topic / quality / sentiment — consumed in Articles UI, filters, storyline cards
        lines.append("")
        lines.append("### Topic / quality / sentiment (product surface)")
        lines.append("")
        try:
            from shared.domain_registry import get_schema_names_active

            q_scored = s_scored = ata_rows = 0
            for schema in get_schema_names_active():
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE quality_score IS NOT NULL
                    """
                )
                q_scored += int(cur.fetchone()[0] or 0)
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles
                    WHERE sentiment_score IS NOT NULL OR sentiment_label IS NOT NULL
                    """
                )
                s_scored += int(cur.fetchone()[0] or 0)
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {schema}.article_topic_assignments")
                    ata_rows += int(cur.fetchone()[0] or 0)
                except Exception:
                    conn.rollback()
            lines.append(
                f"- **Articles with `quality_score` set (all domains):** {q_scored:,} — shown on Articles, "
                "Storyline detail, filters (`min_quality_score` / `max_quality_score`)."
            )
            lines.append(
                f"- **Articles with sentiment (`sentiment_score` or `sentiment_label`):** {s_scored:,} — "
                "chips + quick filters on Articles."
            )
            lines.append(
                f"- **`article_topic_assignments` rows (topic_clustering output):** {ata_rows:,} — "
                "drives topic backlog metrics; topic UX varies by page."
            )
            lines.append(
                "- **Inert check:** if these counts grow but UI never changes, confirm API fields are mapped "
                "in `web/src` article types and list endpoints return scores."
            )
        except Exception as e:
            conn.rollback()
            lines.append(f"- **Topic/quality/sentiment cross-check:** error — {e}")

        lines.append("")
        lines.append("## Interpretation")
        lines.append("")
        lines.append(
            "- **✅ = productive:** Phase is running and writing data in the window."
        )
        lines.append(
            "- **⚠️ = idle or conditional:** Phase runs but produced no output recently (may require specific conditions, thresholds, or backlog)."
        )
        lines.append(
            "- **❌ = no data ever:** Table is empty — phase may not have run successfully or output format changed."
        )
        lines.append("")
        lines.append(
            "**Note:** Some phases are **conditional** (e.g. `event_coherence_review` only when contexts change, "
            "`pattern_matching` only when watchlists exist). Check automation_run_history success rate to confirm "
            "they're executing even if output is sparse."
        )
        lines.append("")
        lines.append(
            "**Optional output section:** Phases under *optional (cost / latency)* are useful for **turn-off or throttle "
            "decisions** when they are not part of your workflow. **`nightly_enrichment_context`** is clock-gated; "
            "its metrics tie refinement completions to your configured local night hours."
        )
        lines.append("")
        lines.append("**Claims → facts:** If `versioned_facts` from `claim_extraction` stays low while `claims_to_facts` succeeds, see "
                     "[docs/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md](../docs/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md), "
                     "`scripts/diagnose_claims_to_facts.py`, and `scripts/validate_claims_to_facts.py`.")
        lines.append("")

    finally:
        cur.close()
        conn.close()

    out_path = None
    if args.write_report:
        out_path = args.write_report if os.path.isabs(args.write_report) else os.path.join(ROOT, args.write_report)
    _emit(lines, out_path)
    if out_path:
        print(f"\nWrote {out_path}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
