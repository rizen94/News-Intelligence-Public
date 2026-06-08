"""FastAPI dependencies for NEWS_INTEL_PUBLIC_WEB_AUTH."""

from __future__ import annotations

from fastapi import HTTPException, Request

from config.settings import news_intel_public_web_auth_enabled


async def require_public_web_admin(request: Request) -> None:
    if not news_intel_public_web_auth_enabled():
        return
    role = getattr(request.state, "ni_role", None)
    if role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator session required for this endpoint",
        )
