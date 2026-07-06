"""Kit-only patches: no baked-in politics/finance defaults."""

from __future__ import annotations

import logging

from config.runtime import env_str

logger = logging.getLogger(__name__)

_KIT_FALLBACK = env_str("NEWS_INTEL_DEFAULT_DOMAIN_FALLBACK", "").strip()


def apply_domain_hardening() -> None:
    """Patch NI helpers so empty registry does not fall back to politics."""
    import shared.domain_registry as dr

    _orig_first = dr.first_active_domain_key

    def _kit_first_active_domain_key(fallback: str = "politics") -> str:
        fb = _KIT_FALLBACK or fallback
        keys = dr.get_active_domain_keys()
        if keys:
            return keys[0]
        if fb:
            return fb
        return ""

    dr.first_active_domain_key = _kit_first_active_domain_key  # type: ignore[method-assign]

    try:
        import shared.domain_registry_constants as drc

        if hasattr(drc, "DEFAULT_DOMAIN_KEYS"):
            drc.DEFAULT_DOMAIN_KEYS = ()  # type: ignore[attr-defined]
    except ImportError:
        pass

    logger.info("kit domain_hardening applied (fallback=%r)", _KIT_FALLBACK or "(none)")
