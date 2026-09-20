"""
News Intelligence Prometheus exposition for Homelab Grafana (v11).

Cached gauges from Monitor SSOTs (queue depths, UIE backlog, intake latency)
plus curated DB inventory (live rows / relation size) and content/event signals.
Homelab Prometheus scrapes GET /api/system_monitoring/prometheus.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

from config.runtime import env_bool, env_float, env_int, env_str

logger = logging.getLogger(__name__)

_CACHE_LOCK = threading.Lock()
_CACHE_BODY: str | None = None
_CACHE_AT: float = 0.0

# Curated inventory — significant NI tables for size/row watch.
_INVENTORY_RELATIONS: tuple[tuple[str, str], ...] = (
    ("politics", "articles"),
    ("politics", "storylines"),
    ("finance", "articles"),
    ("finance", "storylines"),
    ("legal", "articles"),
    ("legal", "storylines"),
    ("medicine", "articles"),
    ("medicine", "storylines"),
    ("artificial_intelligence", "articles"),
    ("artificial_intelligence", "storylines"),
    ("public", "chronological_events"),
    ("public", "automation_run_history"),
    ("intelligence", "tracked_events"),
    ("intelligence", "extracted_claims"),
    ("intelligence", "embedding_chunks"),
    ("intelligence", "editorial_packages"),
    ("intelligence", "editorial_package_members"),
    ("intelligence", "package_evidence_briefs"),
    ("intelligence", "news_stories"),
    ("intelligence", "rag_evidence_pull_queue"),
)

_LABEL_SAFE = re.compile(r'[^a-zA-Z0-9_:\-./]')


def is_enabled() -> bool:
    return env_bool("NI_PROMETHEUS_METRICS_ENABLED", True)


def cache_ttl_seconds() -> float:
    return max(30.0, float(env_int("NI_PROMETHEUS_METRICS_CACHE_SECONDS", 60)))


def scrape_token() -> str:
    return (env_str("NI_PROMETHEUS_SCRAPE_TOKEN", "") or "").strip()


def _esc_label(val: Any) -> str:
    s = str(val if val is not None else "")
    s = s.replace("\\", "\\\\").replace("\n", " ").replace('"', '\\"')
    return _LABEL_SAFE.sub("_", s)[:120]


def _gauge(name: str, help_text: str, samples: list[tuple[dict[str, str], float]]) -> list[str]:
    out = [f"# HELP {name} {help_text}", f"# TYPE {name} gauge"]
    for labels, value in samples:
        if value is None:
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        if labels:
            lab = ",".join(f'{k}="{_esc_label(v)}"' for k, v in sorted(labels.items()))
            out.append(f"{name}{{{lab}}} {num}")
        else:
            out.append(f"{name} {num}")
    return out


def _collect_queue_metrics() -> list[str]:
    lines: list[str] = []
    try:
        from shared.pipeline_queue_counts import (
            get_all_phase_queue_depths,
            get_unified_intake_breakdown,
        )

        depths = get_all_phase_queue_depths() or {}
        lines.extend(
            _gauge(
                "ni_queue_depth",
                "Per-phase actionable queue_depth (Monitor SSOT).",
                [({"phase": str(p)}, float(v or 0)) for p, v in depths.items()],
            )
        )
        try:
            from services.backlog_metrics import get_all_backlog_counts

            backlog = get_all_backlog_counts() or {}
            lines.extend(
                _gauge(
                    "ni_scheduling_backlog",
                    "Per-phase scheduling_backlog (excess beyond one batch).",
                    [({"phase": str(p)}, float(v or 0)) for p, v in backlog.items()],
                )
            )
        except Exception as e:
            logger.debug("ni prom scheduling_backlog: %s", e)

        br = get_unified_intake_breakdown() or {}
        lines.extend(
            _gauge(
                "ni_actionable_unified_intake",
                "Actionable unified intake LLM work remaining.",
                [({}, float(br.get("actionable_unified_intake") or 0))],
            )
        )
        lines.extend(
            _gauge(
                "ni_inventory_missing_pass",
                "Inventory missing unified pass markers (not ETA).",
                [({}, float(br.get("inventory_missing_pass") or br.get("total_missing_unified_pass") or 0))],
            )
        )
    except Exception as e:
        logger.warning("ni prom queue metrics: %s", e)
    return lines


def _collect_latency_metrics() -> list[str]:
    lines: list[str] = []
    try:
        from shared.intake_catchup_latency import compute_intake_catchup_latency

        snap = compute_intake_catchup_latency(use_cache=True) or {}
        sla = float(snap.get("sla_hours") or env_float("CATCHUP_SLA_HOURS", 6.0))
        samples = []
        if snap.get("p50_hours") is not None:
            samples.append(({"quantile": "0.5"}, float(snap["p50_hours"])))
        if snap.get("p95_hours") is not None:
            samples.append(({"quantile": "0.95"}, float(snap["p95_hours"])))
        lines.extend(
            _gauge(
                "ni_intake_catchup_latency_hours",
                "RSS→full-process catchup latency hours.",
                samples,
            )
        )
        lines.extend(
            _gauge(
                "ni_intake_catchup_sla_hours",
                "Configured catchup SLA hours.",
                [({}, sla)],
            )
        )
        ok = 1.0 if snap.get("within_sla") or snap.get("ok") else 0.0
        lines.extend(
            _gauge(
                "ni_intake_catchup_within_sla",
                "1 if intake catchup within SLA.",
                [({}, ok)],
            )
        )
    except Exception as e:
        logger.debug("ni prom latency: %s", e)
    return lines


def _collect_inventory_metrics() -> list[str]:
    lines: list[str] = []
    try:
        from shared.database.connection import get_ui_db_connection_context

        row_samples: list[tuple[dict[str, str], float]] = []
        size_samples: list[tuple[dict[str, str], float]] = []
        wanted = {(s, t) for s, t in _INVENTORY_RELATIONS}
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_database_size(current_database())")
                db_size = float(cur.fetchone()[0] or 0)
                lines.extend(
                    _gauge(
                        "ni_db_size_bytes",
                        "news_intel database size bytes.",
                        [({}, db_size)],
                    )
                )
                # One scan of pg_stat_user_tables for curated relations.
                schemas = sorted({s for s, _ in _INVENTORY_RELATIONS})
                cur.execute(
                    """
                    SELECT s.schemaname, s.relname,
                           coalesce(s.n_live_tup, 0)::bigint AS live_rows,
                           pg_total_relation_size(
                             (quote_ident(s.schemaname) || '.' || quote_ident(s.relname))::regclass
                           ) AS rel_bytes
                    FROM pg_stat_user_tables s
                    WHERE s.schemaname = ANY(%s)
                    """,
                    (schemas,),
                )
                for schema, table, live_rows, rel_bytes in cur.fetchall():
                    if (schema, table) not in wanted:
                        continue
                    labels = {"schema": schema, "table": table}
                    row_samples.append((labels, float(live_rows or 0)))
                    size_samples.append((labels, float(rel_bytes or 0)))
        lines.extend(
            _gauge(
                "ni_table_live_rows",
                "Estimated live tuples for curated NI tables.",
                row_samples,
            )
        )
        lines.extend(
            _gauge(
                "ni_table_size_bytes",
                "Total relation size bytes for curated NI tables.",
                size_samples,
            )
        )
    except Exception as e:
        logger.warning("ni prom inventory: %s", e)
    return lines


def _collect_content_and_run_metrics() -> list[str]:
    lines: list[str] = []
    try:
        from shared.database.connection import get_ui_db_connection_context

        content_samples: list[tuple[dict[str, str], float]] = []
        run_samples: list[tuple[dict[str, str], float]] = []
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                for kind, sql in (
                    (
                        "chronological_event",
                        "SELECT COUNT(*)::bigint FROM public.chronological_events",
                    ),
                    (
                        "tracked_event",
                        "SELECT COUNT(*)::bigint FROM intelligence.tracked_events",
                    ),
                    (
                        "editorial_package",
                        "SELECT COUNT(*)::bigint FROM intelligence.editorial_packages",
                    ),
                    (
                        "news_story",
                        "SELECT COUNT(*)::bigint FROM intelligence.news_stories",
                    ),
                    (
                        "evidence_brief",
                        "SELECT COUNT(*)::bigint FROM intelligence.package_evidence_briefs",
                    ),
                ):
                    try:
                        cur.execute(sql)
                        content_samples.append(
                            ({"kind": kind}, float(cur.fetchone()[0] or 0))
                        )
                    except Exception as e:
                        logger.debug("ni prom content %s: %s", kind, e)
                        try:
                            conn.rollback()
                        except Exception:
                            pass

                # Growth in last 24h where timestamps exist
                for kind, sql in (
                    (
                        "chronological_event",
                        """
                        SELECT COUNT(*)::bigint FROM public.chronological_events
                        WHERE coalesce(created_at, event_date, actual_event_date)
                              >= NOW() - interval '24 hours'
                        """,
                    ),
                    (
                        "tracked_event",
                        """
                        SELECT COUNT(*)::bigint FROM intelligence.tracked_events
                        WHERE coalesce(updated_at, created_at)
                              >= NOW() - interval '24 hours'
                        """,
                    ),
                    (
                        "editorial_package",
                        """
                        SELECT COUNT(*)::bigint FROM intelligence.editorial_packages
                        WHERE created_at >= NOW() - interval '24 hours'
                        """,
                    ),
                    (
                        "news_story",
                        """
                        SELECT COUNT(*)::bigint FROM intelligence.news_stories
                        WHERE coalesce(published_at, created_at, updated_at)
                              >= NOW() - interval '24 hours'
                        """,
                    ),
                ):
                    try:
                        cur.execute(sql)
                        content_samples.append(
                            ({"kind": kind, "window": "24h"}, float(cur.fetchone()[0] or 0))
                        )
                    except Exception as e:
                        logger.debug("ni prom content 24h %s: %s", kind, e)
                        try:
                            conn.rollback()
                        except Exception:
                            pass

                try:
                    cur.execute(
                        """
                        SELECT phase_name,
                               COUNT(*) FILTER (
                                 WHERE started_at >= NOW() - interval '1 hour'
                               )::bigint AS n_1h,
                               COUNT(*) FILTER (
                                 WHERE started_at >= NOW() - interval '24 hours'
                                   AND coalesce(success, true)
                               )::bigint AS ok_24h,
                               COUNT(*) FILTER (
                                 WHERE started_at >= NOW() - interval '24 hours'
                                   AND success IS FALSE
                               )::bigint AS fail_24h
                        FROM public.automation_run_history
                        WHERE phase_name IS NOT NULL
                          AND started_at >= NOW() - interval '24 hours'
                        GROUP BY phase_name
                        ORDER BY ok_24h DESC
                        LIMIT 40
                        """
                    )
                    for phase, n1, ok24, fail24 in cur.fetchall():
                        pk = str(phase)
                        run_samples.append(
                            ({"phase": pk, "window": "1h", "outcome": "ok"}, float(n1 or 0))
                        )
                        run_samples.append(
                            ({"phase": pk, "window": "24h", "outcome": "ok"}, float(ok24 or 0))
                        )
                        run_samples.append(
                            (
                                {"phase": pk, "window": "24h", "outcome": "fail"},
                                float(fail24 or 0),
                            )
                        )
                except Exception as e:
                    logger.debug("ni prom runs: %s", e)
                    try:
                        conn.rollback()
                    except Exception:
                        pass

        lines.extend(
            _gauge(
                "ni_content_rows",
                "Content object counts (total or windowed growth).",
                content_samples,
            )
        )
        lines.extend(
            _gauge(
                "ni_automation_runs",
                "Measurable automation_run_history counts by phase/window/outcome.",
                run_samples,
            )
        )
    except Exception as e:
        logger.warning("ni prom content/runs: %s", e)
    return lines


def build_prometheus_metrics(*, force: bool = False) -> str:
    """Return Prometheus text exposition (cached)."""
    global _CACHE_BODY, _CACHE_AT
    if not is_enabled():
        return "# NI Prometheus metrics disabled (NI_PROMETHEUS_METRICS_ENABLED=false)\n"

    now = time.monotonic()
    with _CACHE_LOCK:
        if (
            not force
            and _CACHE_BODY is not None
            and (now - _CACHE_AT) < cache_ttl_seconds()
        ):
            return _CACHE_BODY

    chunks: list[str] = [
        "# News Intelligence Monitor-parity metrics",
        f"# generated_at_unix {int(time.time())}",
    ]
    chunks.extend(_collect_queue_metrics())
    chunks.extend(_collect_latency_metrics())
    chunks.extend(_collect_inventory_metrics())
    chunks.extend(_collect_content_and_run_metrics())
    chunks.append("")
    body = "\n".join(chunks)

    with _CACHE_LOCK:
        _CACHE_BODY = body
        _CACHE_AT = time.monotonic()
    return body
