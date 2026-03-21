"""
Metrics Middleware for News Intelligence System v3.0
Provides Prometheus metrics integration
"""

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Prometheus metrics
if PROMETHEUS_AVAILABLE:
    # HTTP request metrics
    http_requests_total = Counter(
        "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status_code"]
    )

    http_request_duration_seconds = Histogram(
        "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
    )

    http_requests_in_progress = Gauge(
        "http_requests_in_progress", "HTTP requests currently in progress", ["method", "endpoint"]
    )

    # Application metrics
    articles_processed_total = Counter(
        "articles_processed_total", "Total articles processed", ["status"]
    )

    ml_processing_duration_seconds = Histogram(
        "ml_processing_duration_seconds",
        "ML processing duration in seconds",
        ["model", "operation"],
    )

    active_connections = Gauge("active_connections", "Number of active connections")


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting Prometheus metrics"""

    def __init__(self, app):
        super().__init__(app)
        self.prometheus_available = PROMETHEUS_AVAILABLE

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.prometheus_available:
            return await call_next(request)

        # Extract endpoint name (remove query parameters and path parameters)
        endpoint = self._extract_endpoint(request.url.path)
        method = request.method

        # Increment requests in progress
        http_requests_in_progress.labels(method=method, endpoint=endpoint).inc()

        # Start timing
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=method, endpoint=endpoint, status_code=response.status_code
            ).inc()

            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

            return response

        except Exception:
            # Calculate duration for failed requests
            duration = time.time() - start_time

            # Record error metrics
            http_requests_total.labels(method=method, endpoint=endpoint, status_code=500).inc()

            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

            # Re-raise the exception
            raise

        finally:
            # Decrement requests in progress
            http_requests_in_progress.labels(method=method, endpoint=endpoint).dec()

    def _extract_endpoint(self, path: str) -> str:
        """Extract endpoint name from path, removing parameters"""
        # Remove common path parameters
        path = path.replace("/api/", "")

        # Remove trailing slashes
        path = path.rstrip("/")

        # Replace path parameters with placeholders
        import re

        path = re.sub(r"/\d+", "/{id}", path)
        path = re.sub(r"/[a-f0-9-]{36}", "/{uuid}", path)

        return path or "root"

    @staticmethod
    def get_metrics():
        """Get Prometheus metrics in text format"""
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus client not available\n"
        return generate_latest()

    @staticmethod
    def record_article_processed(status: str):
        """Record article processing metric"""
        if PROMETHEUS_AVAILABLE:
            articles_processed_total.labels(status=status).inc()

    @staticmethod
    def record_ml_processing(model: str, operation: str, duration: float):
        """Record ML processing metric"""
        if PROMETHEUS_AVAILABLE:
            ml_processing_duration_seconds.labels(model=model, operation=operation).observe(
                duration
            )

    @staticmethod
    def set_active_connections(count: int):
        """Set active connections metric"""
        if PROMETHEUS_AVAILABLE:
            active_connections.set(count)
