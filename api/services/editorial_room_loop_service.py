"""Shim — editorial_room_loop_service moved to api/_archived/editorial/.

Loads archived implementation when LEGACY_EDITORIAL_WRITERS_ENABLED or
EDITORIAL_ROOM_LOOP_ENABLED is on; otherwise returns a no-op.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.assembly_phase_order import editorial_room_loop_enabled
from shared.legacy_editorial_rollback import (
    legacy_editorial_writers_enabled,
    load_editorial_room_loop_service,
)

logger = logging.getLogger(__name__)


async def run_editorial_room_loop(*, shadow: bool = False, **kwargs: Any) -> dict[str, Any]:
    if not editorial_room_loop_enabled() or not legacy_editorial_writers_enabled():
        logger.info(
            "editorial_room_loop skipped (EDITORIAL_ROOM_LOOP_ENABLED / "
            "LEGACY_EDITORIAL_WRITERS_ENABLED off)"
        )
        return {
            "skipped": True,
            "reason": "legacy_editorial_writers_disabled",
            "shadow": shadow,
        }
    mod = load_editorial_room_loop_service()
    return await mod.run_editorial_room_loop(shadow=shadow, **kwargs)


def __getattr__(name: str) -> Any:
    if not legacy_editorial_writers_enabled():
        raise AttributeError(
            f"editorial_room_loop_service.{name} unavailable (archived)"
        )
    mod = load_editorial_room_loop_service()
    return getattr(mod, name)
