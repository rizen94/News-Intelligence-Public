"""
Optional guest vs admin enforcement for browser-facing deployments.

When NEWS_INTEL_PUBLIC_WEB_AUTH is enabled, attaches role to request.state and
blocks guests from ops routes and mutating methods.

Middleware order: register *before* DemoReadOnlyMiddleware so outer stack runs
DemoReadOnly first, then this runs closer to routes (inner). Starlette: last
registered wraps outer — DemoReadOnly added last = outermost.

Actually: last added = outermost. DemoReadOnly is added last → runs first on request.

This middleware is added *before* DemoReadOnly → runs *after* DemoReadOnly on request.

Incoming: DemoReadOnly → … → PublicWebAuth (inner). Good: login POST passes DemoReadOnly via allowlist, then auth middleware runs.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config.settings import (
    news_intel_allow_anonymous_guest,
    news_intel_auth_cookie_name,
    news_intel_public_web_auth_enabled,
)
from shared.services.public_web_auth_service import decode_session_token

logger = logging.getLogger(__name__)

# Paths starting with these are denied for guests (403).
_GUEST_DENY_PREFIXES: tuple[str, ...] = (
    "/api/system_monitoring",
    "/api/orchestrator",
    "/api/user_management",
)


def _json_401() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "success": False,
            "data": None,
            "message": "Authentication required",
            "error": "auth_required",
        },
    )


def _json_403_guest() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "data": None,
            "message": "This action requires an administrator session",
            "error": "guest_forbidden",
        },
    )


def _unauthenticated_allowlisted(method: str, path: str) -> bool:
    if method == "OPTIONS":
        return True
    if method == "GET" and path.startswith("/api/public/demo_config"):
        return True
    if method == "GET" and path.startswith("/api/public/auth/me"):
        return True
    if method == "POST" and path.rstrip("/").startswith("/api/public/auth/login"):
        return True
    if method == "POST" and path.rstrip("/").startswith("/api/public/auth/logout"):
        return True
    return False


def _guest_post_allowed(path: str) -> bool:
    p = path.rstrip("/")
    return p.startswith("/api/public/auth/login") or p.startswith("/api/public/auth/logout")


def _guest_denied_path(path: str) -> bool:
    return any(path == pref or path.startswith(pref + "/") for pref in _GUEST_DENY_PREFIXES)


def attach_public_web_auth_state(request: Request) -> None:
    """Populate request.state ni_* fields (call from handlers if middleware skipped)."""
    request.state.ni_public_auth_enabled = news_intel_public_web_auth_enabled()
    request.state.ni_authenticated = False
    request.state.ni_username = None
    request.state.ni_user_id = None

    if not request.state.ni_public_auth_enabled:
        request.state.ni_role = "admin"
        return

    cookie_name = news_intel_auth_cookie_name()
    raw = request.cookies.get(cookie_name)
    payload = decode_session_token(raw)
    if payload:
        request.state.ni_authenticated = True
        request.state.ni_role = payload.get("role") if payload.get("role") in ("admin", "guest") else "guest"
        request.state.ni_username = str(payload.get("username") or "")
        try:
            raw_sub = payload.get("sub")
            request.state.ni_user_id = int(raw_sub) if raw_sub is not None else None
        except (TypeError, ValueError):
            request.state.ni_user_id = None
        return

    if news_intel_allow_anonymous_guest():
        request.state.ni_role = "guest"
    else:
        request.state.ni_role = "guest"


class PublicWebAuthRbacMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        method = (request.method or "GET").upper()
        path = request.url.path or "/"

        attach_public_web_auth_state(request)

        if not request.state.ni_public_auth_enabled:
            return await call_next(request)

        auth_enabled = True
        anon_guest = news_intel_allow_anonymous_guest()
        authenticated = request.state.ni_authenticated

        if not anon_guest and not authenticated and not _unauthenticated_allowlisted(method, path):
            logger.debug("public web auth: unauthenticated blocked %s %s", method, path)
            return _json_401()

        role = request.state.ni_role
        if role == "guest":
            if _guest_denied_path(path):
                logger.debug("public web auth: guest blocked path %s", path)
                return _json_403_guest()
            if method not in ("GET", "HEAD", "OPTIONS") and not _guest_post_allowed(path):
                logger.debug("public web auth: guest blocked method %s %s", method, path)
                return _json_403_guest()

        return await call_next(request)
