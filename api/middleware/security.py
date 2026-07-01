"""
Security Middleware for News Intelligence System v3.0
Provides rate limiting, security headers, and request validation
"""

import ipaddress
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for security features including rate limiting"""

    def __init__(
        self,
        app,
        rate_limit_per_minute: int = 100,
        *,
        exempt_private_lan: bool = True,
    ):
        super().__init__(app)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.exempt_private_lan = exempt_private_lan
        self.rate_limit_storage: dict[str, list] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)

        if not self._is_rate_limit_exempt(client_ip):
            if not self._check_rate_limit(client_ip):
                # BaseHTTPMiddleware + HTTPException surfaces as 500; return 429 explicitly.
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "Rate limit exceeded. Please try again later.",
                    },
                )

        response = await call_next(request)
        self._add_security_headers(response)
        return response

    def _is_rate_limit_exempt(self, client_ip: str) -> bool:
        if self.exempt_private_lan and self._is_private_or_loopback(client_ip):
            return True
        return False

    @staticmethod
    def _is_private_or_loopback(ip: str) -> bool:
        if not ip or ip == "unknown":
            return False
        try:
            addr = ipaddress.ip_address(ip.strip())
        except ValueError:
            return False
        return bool(addr.is_loopback or addr.is_private or addr.is_link_local)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limit"""
        current_time = time.time()
        minute_ago = current_time - 60

        # Clean old entries
        if client_ip in self.rate_limit_storage:
            self.rate_limit_storage[client_ip] = [
                timestamp
                for timestamp in self.rate_limit_storage[client_ip]
                if timestamp > minute_ago
            ]
        else:
            self.rate_limit_storage[client_ip] = []

        # Check if under limit
        if len(self.rate_limit_storage[client_ip]) >= self.rate_limit_per_minute:
            return False

        # Add current request
        self.rate_limit_storage[client_ip].append(current_time)
        return True

    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Strict transport security (HTTPS only)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content security policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "speaker=()"
        )
