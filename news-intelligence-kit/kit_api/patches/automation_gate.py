"""Defer AutomationManager until kit setup is complete."""

from __future__ import annotations

import logging

from config.runtime import env_bool, env_str

logger = logging.getLogger(__name__)


def apply_automation_gate() -> None:
    if env_str("NEWS_INTEL_KIT_MODE", "true").lower() not in ("1", "true", "yes"):
        return
    if env_bool("NEWS_INTEL_FORCE_AUTOMATION", False):
        return

    from kit_api.services.setup_state import is_setup_complete

    import services.automation_manager as am

    _orig_start = am.AutomationManager.start

    async def _gated_start(self, *args, **kwargs):
        if not is_setup_complete():
            logger.info("Kit setup incomplete — AutomationManager idle (run setup then enable_automation.sh)")
            self.is_running = False
            return
        return await _orig_start(self, *args, **kwargs)

    am.AutomationManager.start = _gated_start  # type: ignore[method-assign]
    logger.info("kit automation_gate applied")
