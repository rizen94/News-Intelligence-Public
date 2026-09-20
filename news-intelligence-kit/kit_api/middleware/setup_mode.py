"""Block non-setup API routes until setup_complete (kit mode)."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from config.runtime import env_bool, env_str

logger = logging.getLogger(__name__)

_SETUP_PREFIXES = (
    "/api/setup",
    "/api/vault",
    "/api/agent",
    "/api/system_monitoring/kit_status",
    "/api/system_monitoring/health",
    "/api/system_monitoring/registry_domains",
    "/docs",
    "/openapi.json",
    "/redoc",
)

_ALWAYS_ALLOWED = (
    "/api/setup/complete",
)


def _kit_setup_mode() -> bool:
    if env_str("NEWS_INTEL_KIT_MODE", "true").lower() not in ("1", "true", "yes"):
        return False
    if env_bool("NEWS_INTEL_FORCE_SETUP_OPEN", False):
        return False
    return True


def _path_allowed(path: str) -> bool:
    if path in _ALWAYS_ALLOWED:
        return True
    return any(path.startswith(p) for p in _SETUP_PREFIXES)


class SetupModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _kit_setup_mode():
            return await call_next(request)

        from kit_api.services.setup_state import is_setup_complete

        if is_setup_complete():
            return await call_next(request)

        path = request.url.path
        if _path_allowed(path):
            return await call_next(request)

        if path.startswith("/api/"):
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Setup incomplete",
                    "setup_url": "/setup/",
                    "setup_complete": False,
                },
            )

        if path == "/" or path.startswith("/api"):
            return await call_next(request)

        return RedirectResponse(url="/setup/", status_code=307)
