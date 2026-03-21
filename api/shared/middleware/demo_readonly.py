"""
Read-only demo mode for public HTTPS deployments.

When NEWS_INTEL_DEMO_READ_ONLY=true and the request Host matches NEWS_INTEL_DEMO_HOSTS
(or NEWS_INTEL_DEMO_READ_ONLY_ALL=true with empty hosts), block mutating HTTP methods.

See docs/PUBLIC_DEPLOYMENT.md and docs/SECURITY_OPERATIONS.md.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


def _parse_host_header(host: str | None) -> str:
    if not host:
        return ""
    return host.split(":")[0].strip().lower()


def news_intel_demo_readonly_enabled() -> bool:
    return os.environ.get("NEWS_INTEL_DEMO_READ_ONLY", "").lower() in ("1", "true", "yes")


def news_intel_demo_hosts_list() -> list[str]:
    raw = os.environ.get("NEWS_INTEL_DEMO_HOSTS", "").strip()
    out: list[str] = []
    for part in raw.split(","):
        p = part.strip()
        if p:
            out.append(_parse_host_header(p))
    return out


def news_intel_demo_readonly_all_hosts() -> bool:
    """If true with empty DEMO_HOSTS, apply read-only to every Host (single-purpose demo server)."""
    return os.environ.get("NEWS_INTEL_DEMO_READ_ONLY_ALL", "").lower() in ("1", "true", "yes")


def news_intel_demo_post_allowlist_prefixes() -> tuple[str, ...]:
    raw = os.environ.get("NEWS_INTEL_DEMO_POST_ALLOWLIST", "").strip()
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def should_apply_demo_readonly(request: Request) -> bool:
    if not news_intel_demo_readonly_enabled():
        return False
    hosts = news_intel_demo_hosts_list()
    h = _parse_host_header(request.headers.get("host"))
    if hosts:
        return h in hosts
    if news_intel_demo_readonly_all_hosts():
        return True
    return False


def demo_readonly_response() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "success": False,
            "data": None,
            "message": "This deployment is read-only (public demo). Mutations and background jobs are disabled.",
            "error": "demo_readonly",
        },
    )


class DemoReadOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not should_apply_demo_readonly(request):
            return await call_next(request)

        method = (request.method or "GET").upper()
        path = request.url.path or "/"

        if method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        if method in ("PUT", "PATCH", "DELETE"):
            logger.debug("demo_readonly: blocked %s %s", method, path)
            return demo_readonly_response()

        if method == "POST":
            for prefix in news_intel_demo_post_allowlist_prefixes():
                if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                    return await call_next(request)
            logger.debug("demo_readonly: blocked POST %s", path)
            return demo_readonly_response()

        return await call_next(request)
