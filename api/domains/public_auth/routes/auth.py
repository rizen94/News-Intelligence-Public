"""Login / logout / session introspection for public web deployments."""

from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from config.settings import (
    news_intel_auth_cookie_max_age_seconds,
    news_intel_auth_cookie_name,
    news_intel_auth_cookie_samesite,
    news_intel_auth_cookie_secure,
    news_intel_public_web_auth_enabled,
)
from shared.database.connection import get_db_connection
from shared.middleware.public_web_auth import attach_public_web_auth_state
from shared.services.public_web_auth_service import (
    hash_password,
    issue_session_token_with_exp,
    resolve_session_role,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/auth", tags=["Public auth"])


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=1024)


@router.get("/me")
async def auth_me(request: Request):
    attach_public_web_auth_state(request)
    auth_on = news_intel_public_web_auth_enabled()
    if not auth_on:
        return {
            "success": True,
            "data": {
                "auth_enabled": False,
                "role": "admin",
                "authenticated": False,
                "username": None,
            },
            "message": "ok",
            "timestamp": datetime.now().isoformat(),
        }
    return {
        "success": True,
        "data": {
            "auth_enabled": True,
            "role": getattr(request.state, "ni_role", "guest"),
            "authenticated": getattr(request.state, "ni_authenticated", False),
            "username": getattr(request.state, "ni_username", None),
        },
        "message": "ok",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/login")
async def auth_login(request: Request, response: Response, body: LoginBody):
    if not news_intel_public_web_auth_enabled():
        raise HTTPException(status_code=503, detail="Public web auth is not enabled")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, username, password_hash, roles, is_active
                FROM user_profiles
                WHERE username = %s
                LIMIT 1
                """,
                (body.username.strip(),),
            )
            row = cur.fetchone()
            if not row or not row[1]:
                raise HTTPException(status_code=401, detail="Invalid username or password")
            user_id, username, password_hash, roles, is_active = row
            if is_active is False:
                raise HTTPException(status_code=403, detail="Account disabled")

            if not verify_password(body.password, password_hash):
                raise HTTPException(status_code=401, detail="Invalid username or password")

            role = resolve_session_role(roles)
            new_hash = None
            if password_hash and not password_hash.startswith("$2"):
                try:
                    new_hash = hash_password(body.password)
                except ValueError:
                    new_hash = None

            now = datetime.now()
            cur.execute(
                """
                UPDATE user_profiles
                SET last_login = %s, updated_at = %s
                WHERE id = %s
                """,
                (now, now, user_id),
            )
            if new_hash:
                cur.execute(
                    "UPDATE user_profiles SET password_hash = %s WHERE id = %s",
                    (new_hash, user_id),
                )
            conn.commit()

        token, _exp = issue_session_token_with_exp(user_id=user_id, username=username, role=role)
        max_age = news_intel_auth_cookie_max_age_seconds()
        response.set_cookie(
            key=news_intel_auth_cookie_name(),
            value=token,
            max_age=max_age,
            httponly=True,
            secure=news_intel_auth_cookie_secure(),
            samesite=news_intel_auth_cookie_samesite(),  # type: ignore[arg-type]
            path="/",
        )

        return {
            "success": True,
            "data": {"username": username, "role": role},
            "message": "ok",
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.exception("auth_login failed: %s", e)
        raise HTTPException(status_code=500, detail="Login failed") from e
    finally:
        conn.close()


@router.post("/logout")
async def auth_logout(response: Response):
    response.delete_cookie(
        key=news_intel_auth_cookie_name(),
        path="/",
        secure=news_intel_auth_cookie_secure(),
        samesite=news_intel_auth_cookie_samesite(),  # type: ignore[arg-type]
    )
    return {
        "success": True,
        "data": None,
        "message": "logged out",
        "timestamp": datetime.now().isoformat(),
    }
