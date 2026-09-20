"""
News Intelligence System - Services Package

Accessors are resolved lazily (PEP 562). Importing any leaf module — e.g.
``from services.backlog_metrics import get_all_pending_counts`` — must not drag in
``automation_manager``, ``rag``, or the monitoring stack, which every CLI script,
cron run, and PopOS worker previously paid for.
"""

from typing import Any

# Note: api_cache_service consolidated into smart_cache_service
# Note: monitoring_service and health_service consolidated into advanced_monitoring_service
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "get_advanced_monitoring_service": (
        "services.advanced_monitoring_service",
        "get_advanced_monitoring_service",
    ),
    "get_automation_manager": ("services.automation_manager", "get_automation_manager"),
    "get_circuit_breaker_service": (
        "services.circuit_breaker_service",
        "get_circuit_breaker_service",
    ),
    "get_distributed_cache_service": (
        "services.distributed_cache_service",
        "get_distributed_cache_service",
    ),
    "get_early_quality_service": ("services.early_quality_service", "get_early_quality_service"),
    "get_predictive_scaling_service": (
        "services.predictive_scaling_service",
        "get_predictive_scaling_service",
    ),
    "RAGService": ("services.rag", "RAGService"),
    "get_cache_service": ("services.smart_cache_service", "get_cache_service"),
    "get_smart_cache_service": ("services.smart_cache_service", "get_smart_cache_service"),
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_path, attr = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    from importlib import import_module

    value = getattr(import_module(module_path), attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
