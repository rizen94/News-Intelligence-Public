"""Centralized cache TTL configuration — single source for all background-cache intervals."""

from __future__ import annotations

import os
from typing import NamedTuple


class _CacheTTLs(NamedTuple):
    backlog_counts: int = 90
    pending_counts: int = 90
    prometheus_metrics: int = 60
    pipeline_queue_depths: int = 120
    monitor_dashboard: int = 30
    phase_names: int = 120
    pipeline_throughput: int = 30
    unified_intake_stats: int = 300
    catchup_latency: int = 90
    trending_signal: int = 3600


def _env_int(name: str, default: int) -> int:
    try:
        return max(5, int((os.environ.get(name) or str(default)).strip()))
    except (TypeError, ValueError):
        return default


# Module-level constants — callers should read from these, not compute their own.
BACKLOG_CACHE_TTL = _env_int("BACKLOG_CACHE_TTL_SECONDS", 90)
PENDING_CACHE_TTL = BACKLOG_CACHE_TTL
PROMETHEUS_METRICS_CACHE_S = _env_int("NI_PROMETHEUS_METRICS_CACHE_SECONDS", 60)
PIPELINE_QUEUE_DEPTH_CACHE_S = _env_int("PIPELINE_QUEUE_DEPTH_CACHE_SECONDS", 120)
MONITOR_DASHBOARD_CACHE_S = _env_int("MONITOR_DASHBOARD_CACHE_SECONDS", 30)


def get_backlog_ttl_seconds() -> int:
    """Return cache TTL for backlog/pending counts."""
    return BACKLOG_CACHE_TTL


def get_prometheus_cache_ttl_s() -> float:
    """Return cache TTL for Prometheus scrape body in seconds."""
    return float(PROMETHEUS_METRICS_CACHE_S)


def get_pipeline_queue_depth_ttl_s() -> int:
    """Return cache TTL for pipeline queue depth values."""
    return PIPELINE_QUEUE_DEPTH_CACHE_S


# ---------------------------------------------------------------------------
# Pipeline metrics (via Monitor / pipeline_metrics.py)
# ---------------------------------------------------------------------------

PHASE_NAMES_CACHE_TTL = _env_int("PHASE_NAMES_CACHE_TTL_SECONDS", 120)


def get_phase_names_ttl_s() -> int:
    """Return cache TTL for phase-name list in pipeline_metrics."""
    return PHASE_NAMES_CACHE_TTL


# ---------------------------------------------------------------------------
# Pipeline throughput (via Monitor / pipeline_throughput.py)
# ---------------------------------------------------------------------------

PIPELINE_THROUGHPUT_CACHE_S = _env_int("PIPELINE_THROUGHPUT_CACHE_SECONDS", 30)


def get_pipeline_throughput_cache_ttl_s() -> int:
    """Return cache TTL for pipeline-throughput estimates."""
    return PIPELINE_THROUGHPUT_CACHE_S


# ---------------------------------------------------------------------------
# Unified intake stats (via unified_intake_backlog.py)
# ---------------------------------------------------------------------------

UNIFIED_INTAKE_STATS_CACHE_TTL = _env_int(
    "UNIFIED_INTAKE_BACKLOG_STATS_TTL_SECONDS", 300
)


def get_unified_intake_stats_ttl_s() -> int:
    """Return cache TTL for unified intake backlog stats."""
    return UNIFIED_INTAKE_STATS_CACHE_TTL


# ---------------------------------------------------------------------------
# Catchup latency samples (via intake_catchup_latency.py)
# ---------------------------------------------------------------------------

CATCHUP_LATENCY_CACHE_TTL = _env_int("CATCHUP_LATENCY_CACHE_TTL_SECONDS", 90)


def get_catchup_latency_cache_ttl_s() -> int:
    """Return cache TTL for intake catchup-latency samples."""
    return CATCHUP_LATENCY_CACHE_TTL


# ---------------------------------------------------------------------------
# Trending signal cache (via article_signal_gate.py)
# ---------------------------------------------------------------------------

TRENDING_SIGNAL_CACHE_TTL = _env_int("TRENDING_SIGNAL_CACHE_TTL_SECONDS", 3600)


def get_trending_signal_cache_ttl_s() -> int:
    """Return cache TTL for trending-signal gate data."""
    return TRENDING_SIGNAL_CACHE_TTL
