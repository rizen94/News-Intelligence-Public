"""Process RSS helpers for health and controller gates."""

from __future__ import annotations

# Phases that may still start when the API process is over AUTOMATION_RSS_PAUSE_MB.
# Keep this list to light DB/ops work — never LLM / torch / PDF heaps.
AUTOMATION_RSS_PAUSE_EXEMPT_PHASES: frozenset[str] = frozenset(
    {
        "health_check",
        "pending_db_flush",
        "rss_feed_health",
        "monitor_backlog_snapshot",
        # Structure drains that are mostly SQL merges / event linking (no big heap).
        "graph_connection_distillation",
        "event_tracking",
        "claims_to_facts",
        "spine_sql_tail",
        "entity_profile_sync",
        "context_sync",
    }
)


def process_rss_mb() -> float | None:
    """Current resident set size in MiB (Linux VmRSS). Falls back to ru_maxrss peak."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except Exception:
        pass
    try:
        import resource

        # Linux: ru_maxrss is KiB peak, not current — last resort only
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    except Exception:
        return None


def process_anon_mb() -> float | None:
    """Anonymous RSS in MiB from /proc (Linux)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("RssAnon:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except Exception:
        return None
