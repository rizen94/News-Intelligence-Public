"""Shim — editorial_document_service moved to api/_archived/editorial/.

Load real module only when LEGACY_EDITORIAL_WRITERS_ENABLED=1 (or room-loop on).
"""

from __future__ import annotations

import logging
from typing import Any

from shared.legacy_editorial_rollback import (
    legacy_editorial_writers_enabled,
    load_editorial_document_service,
)

logger = logging.getLogger(__name__)
_warned = False


def _warn_once() -> None:
    global _warned
    if not _warned:
        logger.warning(
            "editorial_document_service is archived; enabling requires "
            "LEGACY_EDITORIAL_WRITERS_ENABLED=1"
        )
        _warned = True


def __getattr__(name: str) -> Any:
    _warn_once()
    if not legacy_editorial_writers_enabled():
        raise AttributeError(
            f"editorial_document_service.{name} unavailable "
            "(archived; set LEGACY_EDITORIAL_WRITERS_ENABLED=1)"
        )
    mod = load_editorial_document_service()
    return getattr(mod, name)
