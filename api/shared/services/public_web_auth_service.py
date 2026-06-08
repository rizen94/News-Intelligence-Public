"""
JWT session cookie + password helpers for NEWS_INTEL_PUBLIC_WEB_AUTH.

See docs/PUBLIC_DEPLOYMENT.md and docs/SECURITY_OPERATIONS.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import bcrypt
import jwt

from config.settings import (
    news_intel_auth_cookie_max_age_seconds,
    news_intel_auth_jwt_secret,
)

logger = logging.getLogger(__name__)

JWT_ALG = "HS256"
JWT_ISS = "news-intelligence"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, stored: str | None) -> bool:
    if not stored or not plain:
        return False
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("ascii"))
        except ValueError:
            return False
    legacy = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return legacy == stored


def normalize_roles(roles_val: Any) -> list[str]:
    if roles_val is None:
        return ["guest"]
    if isinstance(roles_val, list):
        return [str(x).strip().lower() for x in roles_val if str(x).strip()]
    if isinstance(roles_val, str):
        return [roles_val.strip().lower()] if roles_val.strip() else ["guest"]
    return ["guest"]


def roles_include_admin(roles_val: Any) -> bool:
    return "admin" in normalize_roles(roles_val)


def resolve_session_role(roles_val: Any) -> str:
    return "admin" if roles_include_admin(roles_val) else "guest"


def decode_session_token(token: str | None) -> dict[str, Any] | None:
    if not token or not str(token).strip():
        return None
    secret = news_intel_auth_jwt_secret()
    if not secret:
        return None
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALG],
            issuer=JWT_ISS,
            options={"require": ["exp", "sub", "role"]},
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("session jwt invalid: %s", e)
        return None


def issue_session_token_with_exp(*, user_id: int, username: str, role: str) -> tuple[str, int]:
    """Return (encoded_jwt, expires_at_unix)."""
    secret = news_intel_auth_jwt_secret()
    if not secret:
        raise RuntimeError("JWT secret not configured")
    max_age = news_intel_auth_cookie_max_age_seconds()
    import time

    now = int(time.time())
    exp = now + max_age
    token = jwt.encode(
        {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "iss": JWT_ISS,
            "iat": now,
            "exp": exp,
        },
        secret,
        algorithm=JWT_ALG,
        headers={"typ": "JWT", "alg": JWT_ALG},
    )
    return token, exp
