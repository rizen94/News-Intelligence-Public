"""Standard service result envelope for batch/background workers."""

from __future__ import annotations

from typing import Any


def service_ok(**fields: Any) -> dict[str, Any]:
    return {"success": True, **fields}


def service_err(message: str, *, recoverable: bool = True, **fields: Any) -> dict[str, Any]:
    return {
        "success": False,
        "error": message,
        "recoverable": recoverable,
        **fields,
    }
