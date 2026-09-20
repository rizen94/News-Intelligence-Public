"""
News Intelligence Prometheus exposition for Homelab Grafana.

Cached gauges from Monitor SSOTs (queue depths / scheduling backlog) plus
curated DB inventory, content/event signals, and light RSS feed counts.
Homelab Prometheus scrapes GET /api/system_monitoring/prometheus.

Ported for main from release/12.0; uses backlog_metrics directly (no v12
pipeline_queue_counts / intake_catchup modules required). Optional latency
gauges are emitted when shared.intake_catchup_latency is available.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_LOCK = threading.Lock()
_CACHE_BODY: str | None = None
_CACHE_AT: float = 0.0

# Curated inventory — significant NI tables for size/row watch.
# Domains/schemas that do not exist are simply omitted by the pg_stat scan.
_INVENTORY_RELATIONS: tuple[tuple[str, str], ...] = (
    ("politics", "articles"),
    ("politics", "storylines"),
    ("politics", "rss_feeds"),
    ("finance", "articles"),
    ("finance", "storylines"),
    ("finance", "rss_feeds"),
    ("public", "automation_run_history"),
    ("intelligence", "tracked_events"),
    ("intelligence", "extracted_claims"),
    ("intelligence", "embedding_chunks"),
)

_LABEL_SAFE = re.compile(r"[^a-zA-Z0-9_:\-./]")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or str(default)).strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float((os.environ.get(name) or str(default)).strip())
    except (TypeError, ValueError):
        return default


def _env_str(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def is_enabled() -> bool:
    return _env_bool("NI_PROMETHEUS_METRICS_ENABLED", True)


def cache_ttl_seconds() -> float:
    return max(30.0, float(_env_int("NI_PROMETHEUS_METRICS_CACHE_SECONDS", 60)))


def scrape_token() -> str:
    return _env_str("NI_PROMETHEUS_SCRAPE_TOKEN", "")


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
        from services.backlog_metrics import get_all_backlog_counts, get_all_pending_counts

        depths = get_all_pending_counts() or {}
        lines.extend(
            _gauge(
                "ni_queue_depth",
                "Per-phase actionable queue_depth (Monitor SSOT).",
                [({"phase": str(p)}, float(v or 0)) for p, v in depths.items()],
            )
        )
        backlog = get_all_backlog_counts() or {}
        lines.extend(
            _gauge(
                "ni_scheduling_backlog",
                "Per-phase scheduling_backlog (excess beyond one batch).",
                [({"phase": str(p)}, float(v or 0)) for p, v in backlog.items()],
            )
        )

        # Optional v12-style unified intake breakdown when modules exist.
        try:
            from shared.pipeline_queue_counts import get_unified_intake_breakdown

            br = get_unified_intake_breakdown() or {}
            if isinstance(br, dict):
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
                        [
                            (
                                {},
                                float(
                                    br.get("inventory_missing_pass")
                                    or br.get("total_missing_unified_pass")
                                    or 0
                                ),
                            )
                        ],
                    )
                )
        except Exception as e:
            logger.debug("ni prom unified_intake optional: %s", e)
    except Exception as e:
        logger.warning("ni prom queue metrics: %s", e)
    return lines


def _collect_latency_metrics() -> list[str]:
    """Emit intake catchup gauges when shared.intake_catchup_latency is present."""
    lines: list[str] = []
    try:
        from shared.intake_catchup_latency import compute_intake_catchup_latency

        snap = compute_intake_catchup_latency(use_cache=True) or {}
        sla = float(snap.get("sla_hours") or _env_float("CATCHUP_SLA_HOURS", 6.0))
        samples: list[tuple[dict[str, str], float]] = []
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
        logger.debug("ni prom latency (optional): %s", e)
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


def _collect_rss_metrics() -> list[str]:
    """Light RSS gauges aligned with Homelab scrape (replaces orphan advanced_monitoring names)."""
    lines: list[str] = []
    try:
        from shared.database.connection import get_ui_db_connection_context
        from shared.domain_registry import iter_url_schema_pairs

        feed_samples: list[tuple[dict[str, str], float]] = []
        article_samples: list[tuple[dict[str, str], float]] = []
        pairs = list(iter_url_schema_pairs()) or [
            ("politics", "politics"),
            ("finance", "finance"),
        ]
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                for dk, schema in pairs:
                    try:
                        cur.execute(
                            f"""
                            SELECT
                              COUNT(*)::bigint,
                              COUNT(*) FILTER (WHERE is_active IS TRUE)::bigint
                            FROM {schema}.rss_feeds
                            """
                        )
                        total, active = cur.fetchone()
                        feed_samples.append(
                            ({"domain": dk, "status": "total"}, float(total or 0))
                        )
                        feed_samples.append(
                            ({"domain": dk, "status": "active"}, float(active or 0))
                        )
                    except Exception as e:
                        logger.debug("ni prom rss feeds %s: %s", dk, e)
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                    try:
                        cur.execute(
                            f"""
                            SELECT COUNT(*)::bigint FROM {schema}.articles
                            WHERE created_at >= NOW() - interval '24 hours'
                            """
                        )
                        article_samples.append(
                            ({"domain": dk, "window": "24h"}, float(cur.fetchone()[0] or 0))
                        )
                    except Exception as e:
                        logger.debug("ni prom rss articles %s: %s", dk, e)
                        try:
                            conn.rollback()
                        except Exception:
                            pass
        lines.extend(
            _gauge(
                "ni_rss_feeds",
                "RSS feed counts by domain and status (total/active).",
                feed_samples,
            )
        )
        lines.extend(
            _gauge(
                "ni_articles_created",
                "Articles created in window by domain.",
                article_samples,
            )
        )
    except Exception as e:
        logger.warning("ni prom rss: %s", e)
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
                        "tracked_event",
                        "SELECT COUNT(*)::bigint FROM intelligence.tracked_events",
                    ),
                    (
                        "extracted_claim",
                        "SELECT COUNT(*)::bigint FROM intelligence.extracted_claims",
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

                for kind, sql in (
                    (
                        "tracked_event",
                        """
                        SELECT COUNT(*)::bigint FROM intelligence.tracked_events
                        WHERE coalesce(updated_at, created_at)
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
    chunks.extend(_collect_rss_metrics())
    chunks.extend(_collect_content_and_run_metrics())
    chunks.append("")
    body = "\n".join(chunks)

    with _CACHE_LOCK:
        _CACHE_BODY = body
        _CACHE_AT = time.monotonic()
    return body
