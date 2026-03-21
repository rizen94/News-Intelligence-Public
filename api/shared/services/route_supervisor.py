#!/usr/bin/env python3
"""
Route Supervisor Service
Manages consistency between routes, monitors database connections, and logs breaks/disconnects.
"""

import asyncio

# Max response time (ms) above which a route is considered slow; used in health checks
DEFAULT_MAX_RESPONSE_TIME_MS = 5000
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from shared.database.connection import get_db_connection
from shared.services.domain_aware_service import validate_domain

logger = logging.getLogger(__name__)


class RouteStatus(Enum):
    """Route health status"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ConnectionStatus(Enum):
    """Database connection status"""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SLOW = "slow"
    ERROR = "error"


@dataclass
class RouteHealth:
    """Health status for a route"""

    route_path: str
    method: str
    status: RouteStatus
    last_check: datetime
    response_time_ms: float | None = None
    error_message: str | None = None
    database_connected: bool = False
    schema_valid: bool = False
    consecutive_failures: int = 0


@dataclass
class DatabaseConnectionHealth:
    """Health status for database connection"""

    domain: str | None
    schema: str | None
    status: ConnectionStatus
    last_check: datetime
    response_time_ms: float | None = None
    error_message: str | None = None
    connection_pool_size: int | None = None
    active_connections: int | None = None


@dataclass
class FrontendHealth:
    """Health status for frontend"""

    url: str
    status: RouteStatus
    last_check: datetime
    response_time_ms: float | None = None
    error_message: str | None = None
    api_connection: bool = False
    consecutive_failures: int = 0


@dataclass
class RouteSupervisorReport:
    """Comprehensive supervisor report"""

    timestamp: datetime
    total_routes: int
    healthy_routes: int
    degraded_routes: int
    unhealthy_routes: int
    database_connections: list[DatabaseConnectionHealth]
    route_health: list[RouteHealth]
    frontend_health: FrontendHealth | None = None
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class RouteSupervisor:
    """
    Route Supervisor Service
    Monitors route consistency, database connections, and logs issues
    """

    def __init__(self, check_interval_seconds: int = 60):
        self.check_interval = check_interval_seconds
        self.route_health: dict[str, RouteHealth] = {}
        self.db_connections: dict[str, DatabaseConnectionHealth] = {}
        self.frontend_health: FrontendHealth | None = None
        self.issues_log: list[dict] = []
        self.is_running = False
        self.last_full_check: datetime | None = None
        self.frontend_url = "http://localhost:3000"

        # Configuration (tune via DEFAULT_MAX_RESPONSE_TIME_MS if needed)
        self.max_response_time_ms = DEFAULT_MAX_RESPONSE_TIME_MS
        self.max_consecutive_failures = 3
        self.db_timeout_seconds = 5

    async def check_database_connection(
        self, domain: str | None = None
    ) -> DatabaseConnectionHealth:
        """Check database connection health for a domain"""
        schema = domain.replace("-", "_") if domain else "public"
        key = f"{domain or 'public'}"

        start_time = time.perf_counter()
        status = ConnectionStatus.CONNECTED
        error_message = None
        connection_pool_size = None
        active_connections = None
        conn = None

        try:
            conn = get_db_connection()
            if not conn:
                status = ConnectionStatus.DISCONNECTED
                error_message = "Failed to get database connection"
            else:
                with conn.cursor() as cur:
                    if domain:
                        cur.execute(f"SET search_path TO {schema}, public")

                    cur.execute("SELECT 1")
                    cur.fetchone()

                    try:
                        cur.execute("""
                            SELECT count(*)
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                        """)
                        result = cur.fetchone()
                        active_connections = result[0] if result else None
                    except Exception as _e:
                        logger.debug("pg_stat_activity check skip: %s", _e)

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                if elapsed_ms > 1000:
                    status = ConnectionStatus.SLOW

        except Exception as e:
            status = ConnectionStatus.ERROR
            error_message = str(e)
            logger.error(f"Database connection check failed for {key}: {e}")
        finally:
            if conn:
                conn.close()

        response_time_ms = (time.perf_counter() - start_time) * 1000

        health = DatabaseConnectionHealth(
            domain=domain,
            schema=schema,
            status=status,
            last_check=datetime.now(),
            response_time_ms=response_time_ms,
            error_message=error_message,
            connection_pool_size=connection_pool_size,
            active_connections=active_connections,
        )

        self.db_connections[key] = health

        # Log issues
        if status != ConnectionStatus.CONNECTED:
            self._log_issue(
                "database_connection",
                f"Database connection issue for {key}",
                {
                    "domain": domain,
                    "schema": schema,
                    "status": status.value,
                    "error": error_message,
                    "response_time_ms": response_time_ms,
                },
            )

        return health

    async def check_route_health(
        self, route_path: str, method: str = "GET", domain: str | None = None
    ) -> RouteHealth:
        """Check health of a specific route"""
        import requests

        route_key = f"{method}:{route_path}"

        # Substitute path parameters
        test_path = route_path
        if "{domain}" in test_path:
            test_path = test_path.replace("{domain}", domain or "politics")
        if "{article_id}" in test_path:
            test_path = test_path.replace("{article_id}", "1")
        if "{storyline_id}" in test_path:
            test_path = test_path.replace("{storyline_id}", "1")
        if "{topic_name}" in test_path:
            test_path = test_path.replace("{topic_name}", "test")

        start_time = time.perf_counter()
        status = RouteStatus.UNKNOWN
        error_message = None
        database_connected = False
        schema_valid = False

        try:
            url = f"http://localhost:8000{test_path}"
            response = requests.request(method, url, timeout=5, allow_redirects=False)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                status = RouteStatus.HEALTHY
                if elapsed_ms > self.max_response_time_ms:
                    status = RouteStatus.DEGRADED
            elif response.status_code in [400, 422]:
                # Validation errors are expected for some routes
                status = RouteStatus.HEALTHY
            elif response.status_code == 404:
                status = RouteStatus.UNHEALTHY
                error_message = "Route not found"
            elif response.status_code == 500:
                status = RouteStatus.UNHEALTHY
                try:
                    error_detail = response.json().get("detail", "Server error")
                    error_message = error_detail

                    # Check if it's a database error
                    if "column" in error_detail.lower() or "relation" in error_detail.lower():
                        schema_valid = False
                        self._log_issue(
                            "schema_mismatch",
                            f"Schema mismatch in {route_path}",
                            {"route": route_path, "method": method, "error": error_detail},
                        )
                except:
                    error_message = "Server error"
            else:
                status = RouteStatus.DEGRADED
                error_message = f"Unexpected status: {response.status_code}"

            # Check database connection for domain routes
            if domain:
                db_health = await self.check_database_connection(domain)
                database_connected = db_health.status == ConnectionStatus.CONNECTED
                schema_valid = database_connected and db_health.status != ConnectionStatus.ERROR

        except requests.exceptions.Timeout:
            status = RouteStatus.DEGRADED
            error_message = "Request timeout"
        except requests.exceptions.ConnectionError:
            status = RouteStatus.UNHEALTHY
            error_message = "Cannot connect to API server"
        except Exception as e:
            status = RouteStatus.UNHEALTHY
            error_message = str(e)
            logger.error(f"Route health check failed for {route_key}: {e}")

        response_time_ms = (time.perf_counter() - start_time) * 1000

        # Update or create route health
        if route_key in self.route_health:
            existing = self.route_health[route_key]
            if status == RouteStatus.UNHEALTHY:
                existing.consecutive_failures += 1
            else:
                existing.consecutive_failures = 0
        else:
            existing = RouteHealth(
                route_path=route_path,
                method=method,
                status=status,
                last_check=datetime.now(),
                consecutive_failures=1 if status == RouteStatus.UNHEALTHY else 0,
            )

        existing.status = status
        existing.last_check = datetime.now()
        existing.response_time_ms = response_time_ms
        existing.error_message = error_message
        existing.database_connected = database_connected
        existing.schema_valid = schema_valid

        self.route_health[route_key] = existing

        # Log issues
        if status == RouteStatus.UNHEALTHY:
            self._log_issue(
                "route_unhealthy",
                f"Route {route_path} is unhealthy",
                {
                    "route": route_path,
                    "method": method,
                    "error": error_message,
                    "consecutive_failures": existing.consecutive_failures,
                },
            )

        return existing

    def _log_issue(self, issue_type: str, message: str, details: dict):
        """Log an issue"""
        issue = {
            "timestamp": datetime.now().isoformat(),
            "type": issue_type,
            "message": message,
            "details": details,
        }

        self.issues_log.append(issue)

        # Keep only last 1000 issues
        if len(self.issues_log) > 1000:
            self.issues_log = self.issues_log[-1000:]

        # Log to logger
        logger.warning(f"[Route Supervisor] {message}: {details}")

    async def check_all_database_connections(self) -> list[DatabaseConnectionHealth]:
        """Check database connections for all domains"""
        domains = ["politics", "finance", "science-tech"]
        results = []

        # Check public schema
        results.append(await self.check_database_connection(None))

        # Check each domain
        for domain in domains:
            if validate_domain(domain):
                results.append(await self.check_database_connection(domain))

        return results

    async def check_frontend_health(self) -> FrontendHealth:
        """Check frontend health"""
        start_time = time.perf_counter()
        status = RouteStatus.UNKNOWN
        error_message = None
        api_connection = False

        try:
            import requests

            # Check if frontend is accessible
            response = requests.get(self.frontend_url, timeout=5, allow_redirects=False)

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 200:
                status = RouteStatus.HEALTHY
                if elapsed_ms > self.max_response_time_ms:
                    status = RouteStatus.DEGRADED
            else:
                status = RouteStatus.UNHEALTHY
                error_message = f"Frontend returned status {response.status_code}"

            # Check if frontend can connect to API
            try:
                api_response = requests.get(
                    f"{self.frontend_url}/api/system_monitoring/health",
                    timeout=3,
                    allow_redirects=False,
                )
                api_connection = api_response.status_code in [
                    200,
                    404,
                ]  # 404 is OK, means frontend is up
            except:
                api_connection = False

        except requests.exceptions.Timeout:
            status = RouteStatus.DEGRADED
            error_message = "Frontend request timeout"
        except requests.exceptions.ConnectionError:
            status = RouteStatus.UNHEALTHY
            error_message = "Cannot connect to frontend"
        except Exception as e:
            status = RouteStatus.UNHEALTHY
            error_message = str(e)
            logger.error(f"Frontend health check failed: {e}")

        response_time_ms = (time.perf_counter() - start_time) * 1000

        # Update or create frontend health
        if self.frontend_health:
            existing = self.frontend_health
            if status == RouteStatus.UNHEALTHY:
                existing.consecutive_failures += 1
            else:
                existing.consecutive_failures = 0
        else:
            existing = FrontendHealth(
                url=self.frontend_url,
                status=status,
                last_check=datetime.now(),
                consecutive_failures=1 if status == RouteStatus.UNHEALTHY else 0,
            )

        existing.status = status
        existing.last_check = datetime.now()
        existing.response_time_ms = response_time_ms
        existing.error_message = error_message
        existing.api_connection = api_connection

        self.frontend_health = existing

        # Log issues
        if status == RouteStatus.UNHEALTHY:
            self._log_issue(
                "frontend_unhealthy",
                f"Frontend at {self.frontend_url} is unhealthy",
                {
                    "url": self.frontend_url,
                    "error": error_message,
                    "consecutive_failures": existing.consecutive_failures,
                    "api_connection": api_connection,
                },
            )

        return existing

    async def check_critical_routes(self) -> list[RouteHealth]:
        """Check critical routes for all domains"""
        critical_routes = [
            ("/api/{domain}/articles", "GET"),
            ("/api/{domain}/storylines", "GET"),
            ("/api/{domain}/content_analysis/topics", "GET"),
            ("/api/{domain}/rss_feeds", "GET"),
            ("/api/system_monitoring/health", "GET"),
            ("/api/system_monitoring/status", "GET"),
        ]

        domains = ["politics", "finance", "science-tech"]
        results = []

        for route_path, method in critical_routes:
            if "{domain}" in route_path:
                for domain in domains:
                    if validate_domain(domain):
                        results.append(await self.check_route_health(route_path, method, domain))
            else:
                results.append(await self.check_route_health(route_path, method))

        return results

    async def generate_report(self) -> RouteSupervisorReport:
        """Generate comprehensive supervisor report"""
        # Check all database connections
        db_health = await self.check_all_database_connections()

        # Check frontend health
        frontend_health = await self.check_frontend_health()

        # Check critical routes
        route_health = await self.check_critical_routes()

        # Calculate statistics
        total_routes = len(route_health)
        healthy = sum(1 for r in route_health if r.status == RouteStatus.HEALTHY)
        degraded = sum(1 for r in route_health if r.status == RouteStatus.DEGRADED)
        unhealthy = sum(1 for r in route_health if r.status == RouteStatus.UNHEALTHY)

        # Collect issues and warnings
        issues = []
        warnings = []

        # Database connection issues
        for db in db_health:
            if db.status != ConnectionStatus.CONNECTED:
                issues.append(
                    f"Database connection issue for {db.domain or 'public'}: {db.error_message}"
                )

        # Frontend issues
        if frontend_health.status == RouteStatus.UNHEALTHY:
            issues.append(
                f"Frontend at {frontend_health.url} is unhealthy: {frontend_health.error_message}"
            )
        elif frontend_health.status == RouteStatus.DEGRADED:
            warnings.append(
                f"Frontend at {frontend_health.url} is slow: {frontend_health.response_time_ms}ms"
            )

        if not frontend_health.api_connection and frontend_health.status == RouteStatus.HEALTHY:
            warnings.append("Frontend cannot connect to API")

        # Route issues
        for route in route_health:
            if route.status == RouteStatus.UNHEALTHY:
                issues.append(f"Route {route.method} {route.route_path}: {route.error_message}")
            elif route.status == RouteStatus.DEGRADED:
                warnings.append(
                    f"Route {route.method} {route.route_path} is slow: {route.response_time_ms}ms"
                )

            if not route.schema_valid and route.database_connected:
                issues.append(f"Schema mismatch in {route.route_path}")

        # Recent issues from log
        recent_issues = [
            i
            for i in self.issues_log
            if datetime.fromisoformat(i["timestamp"]) > datetime.now() - timedelta(hours=1)
        ]
        for issue in recent_issues[-10:]:  # Last 10 issues
            if issue["type"] in ["schema_mismatch", "route_unhealthy", "database_connection"]:
                issues.append(f"{issue['message']}: {issue['details']}")

        report = RouteSupervisorReport(
            timestamp=datetime.now(),
            total_routes=total_routes,
            healthy_routes=healthy,
            degraded_routes=degraded,
            unhealthy_routes=unhealthy,
            database_connections=db_health,
            route_health=route_health,
            frontend_health=frontend_health,
            issues=issues,
            warnings=warnings,
        )

        self.last_full_check = datetime.now()

        return report

    async def start_monitoring(self):
        """Start continuous monitoring"""
        self.is_running = True
        logger.info("Route Supervisor started monitoring")

        while self.is_running:
            try:
                report = await self.generate_report()

                # Log summary
                logger.info(
                    f"Route Supervisor Check: "
                    f"{report.healthy_routes}/{report.total_routes} healthy, "
                    f"{report.unhealthy_routes} unhealthy, "
                    f"{len(report.issues)} issues"
                )

                # Log critical issues
                if report.issues:
                    for issue in report.issues[:5]:  # Top 5 issues
                        logger.warning(f"Route Supervisor Issue: {issue}")

                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Route Supervisor monitoring error: {e}")
                await asyncio.sleep(self.check_interval)

    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info("Route Supervisor stopped monitoring")

    def get_recent_issues(self, hours: int = 24) -> list[dict]:
        """Get recent issues from log"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            issue
            for issue in self.issues_log
            if datetime.fromisoformat(issue["timestamp"]) > cutoff
        ]

    def get_route_health_summary(self) -> dict:
        """Get summary of route health"""
        total = len(self.route_health)
        if total == 0:
            return {"status": "unknown", "total": 0}

        healthy = sum(1 for r in self.route_health.values() if r.status == RouteStatus.HEALTHY)
        degraded = sum(1 for r in self.route_health.values() if r.status == RouteStatus.DEGRADED)
        unhealthy = sum(1 for r in self.route_health.values() if r.status == RouteStatus.UNHEALTHY)

        return {
            "status": "healthy"
            if unhealthy == 0
            else ("degraded" if degraded > 0 else "unhealthy"),
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "last_check": self.last_full_check.isoformat() if self.last_full_check else None,
        }

    def get_database_health_summary(self) -> dict:
        """Get summary of database health"""
        total = len(self.db_connections)
        if total == 0:
            return {"status": "unknown", "total": 0}

        connected = sum(
            1 for db in self.db_connections.values() if db.status == ConnectionStatus.CONNECTED
        )
        disconnected = sum(
            1 for db in self.db_connections.values() if db.status == ConnectionStatus.DISCONNECTED
        )
        errors = sum(
            1 for db in self.db_connections.values() if db.status == ConnectionStatus.ERROR
        )

        return {
            "status": "healthy" if disconnected == 0 and errors == 0 else "unhealthy",
            "total": total,
            "connected": connected,
            "disconnected": disconnected,
            "errors": errors,
        }


# Global supervisor instance
_route_supervisor: RouteSupervisor | None = None


def get_route_supervisor() -> RouteSupervisor:
    """Get or create global route supervisor instance"""
    global _route_supervisor
    if _route_supervisor is None:
        _route_supervisor = RouteSupervisor(check_interval_seconds=120)
    return _route_supervisor
