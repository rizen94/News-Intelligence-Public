"""
Circuit Breaker Service for News Intelligence System v3.0
Advanced error handling with circuit breakers, retry logic, and fallback mechanisms
"""

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""

    failure_threshold: int = 5  # Failures before opening circuit
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close circuit
    timeout: int = 30  # Request timeout in seconds
    retry_attempts: int = 3  # Number of retry attempts
    retry_delay: float = 1.0  # Base delay between retries
    max_retry_delay: float = 60.0  # Maximum retry delay
    backoff_multiplier: float = 2.0  # Exponential backoff multiplier
    jitter: bool = True  # Add random jitter to retries


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics"""

    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: datetime | None
    last_success_time: datetime | None
    total_requests: int
    total_failures: int
    total_successes: int
    circuit_opened_count: int
    circuit_closed_count: int


class CircuitBreaker:
    """Circuit breaker implementation with retry logic"""

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.circuit_opened_count = 0
        self.circuit_closed_count = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            self.total_requests += 1

            # Check if circuit should be opened
            if self.state == CircuitState.CLOSED and self._should_open_circuit():
                await self._open_circuit()

            # Check if circuit should be half-opened
            elif self.state == CircuitState.OPEN and self._should_attempt_reset():
                await self._half_open_circuit()

            # Handle different circuit states
            if self.state == CircuitState.OPEN:
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is OPEN")

            # Execute with retry logic
            return await self._execute_with_retry(func, *args, **kwargs)

    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened"""
        return self.failure_count >= self.config.failure_threshold

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset"""
        if not self.last_failure_time:
            return True

        time_since_failure = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        return time_since_failure >= self.config.recovery_timeout

    async def _open_circuit(self):
        """Open the circuit breaker"""
        self.state = CircuitState.OPEN
        self.circuit_opened_count += 1
        logger.warning(f"Circuit breaker {self.name} opened due to {self.failure_count} failures")

    async def _half_open_circuit(self):
        """Move circuit to half-open state"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        logger.info(f"Circuit breaker {self.name} moved to half-open state")

    async def _close_circuit(self):
        """Close the circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.circuit_closed_count += 1
        logger.info(f"Circuit breaker {self.name} closed after {self.success_count} successes")

    async def _execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None

        for attempt in range(self.config.retry_attempts + 1):
            try:
                # Execute function with timeout
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)

                # Success - update circuit breaker
                await self._record_success()
                return result

            except asyncio.TimeoutError:
                last_exception = Exception(f"Request timeout after {self.config.timeout}s")
                await self._record_failure()

            except Exception as e:
                last_exception = e
                await self._record_failure()

            # If not the last attempt, wait before retrying
            if attempt < self.config.retry_attempts:
                delay = self._calculate_retry_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed for {self.name}, retrying in {delay:.2f}s: {last_exception}"
                )
                await asyncio.sleep(delay)

        # All retries failed
        raise CircuitBreakerException(
            f"All {self.config.retry_attempts + 1} attempts failed for {self.name}", last_exception
        )

    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter"""
        delay = min(
            self.config.retry_delay * (self.config.backoff_multiplier**attempt),
            self.config.max_retry_delay,
        )

        if self.config.jitter:
            # Add random jitter (±25%)
            jitter = delay * 0.25 * (2 * random.random() - 1)
            delay += jitter

        return max(0, delay)

    async def _record_success(self):
        """Record successful operation"""
        self.success_count += 1
        self.total_successes += 1
        self.last_success_time = datetime.now(timezone.utc)

        # If in half-open state and enough successes, close circuit
        if (
            self.state == CircuitState.HALF_OPEN
            and self.success_count >= self.config.success_threshold
        ):
            await self._close_circuit()

    async def _record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = datetime.now(timezone.utc)

        # If in half-open state, open circuit immediately
        if self.state == CircuitState.HALF_OPEN:
            await self._open_circuit()

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics"""
        return CircuitBreakerStats(
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure_time=self.last_failure_time,
            last_success_time=self.last_success_time,
            total_requests=self.total_requests,
            total_failures=self.total_failures,
            total_successes=self.total_successes,
            circuit_opened_count=self.circuit_opened_count,
            circuit_closed_count=self.circuit_closed_count,
        )

    def reset(self):
        """Reset circuit breaker to initial state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        logger.info(f"Circuit breaker {self.name} reset")


class CircuitBreakerException(Exception):
    """Circuit breaker specific exception"""

    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception


class CircuitBreakerOpenException(CircuitBreakerException):
    """Exception raised when circuit breaker is open"""

    pass


class CircuitBreakerService:
    """Service for managing multiple circuit breakers"""

    def __init__(self):
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig()

        self.service_configs = {
            "database": CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30,
                timeout=10,
                retry_attempts=1,
            ),
            "ollama": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=60,
                timeout=60,
                retry_attempts=1,
            ),
            "wikipedia": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=30,
                timeout=10,
                retry_attempts=2,
            ),
            "gdelt": CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                timeout=15,
                retry_attempts=3,
            ),
            "newsapi": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=45,
                timeout=10,
                retry_attempts=2,
            ),
            "edgar": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=120,
                timeout=15,
                retry_attempts=2,
            ),
            "fred": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=120,
                timeout=15,
                retry_attempts=2,
            ),
        }

    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            config = self.service_configs.get(service_name, self.default_config)
            self.circuit_breakers[service_name] = CircuitBreaker(service_name, config)

        return self.circuit_breakers[service_name]

    async def call_with_circuit_breaker(
        self, service_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Call function with circuit breaker protection"""
        circuit_breaker = self.get_circuit_breaker(service_name)
        return await circuit_breaker.call(func, *args, **kwargs)

    def get_all_stats(self) -> dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers"""
        return {name: cb.get_stats() for name, cb in self.circuit_breakers.items()}

    def reset_all(self):
        """Reset all circuit breakers"""
        for cb in self.circuit_breakers.values():
            cb.reset()
        logger.info("All circuit breakers reset")

    def get_health_status(self) -> dict[str, Any]:
        """Get overall health status of circuit breakers"""
        stats = self.get_all_stats()

        total_requests = sum(s.total_requests for s in stats.values())
        total_failures = sum(s.total_failures for s in stats.values())
        open_circuits = sum(1 for s in stats.values() if s.state == CircuitState.OPEN)

        health_score = 1.0
        if total_requests > 0:
            health_score = 1.0 - (total_failures / total_requests)

        return {
            "overall_health_score": health_score,
            "total_requests": total_requests,
            "total_failures": total_failures,
            "open_circuits": open_circuits,
            "circuit_breakers": {
                name: {
                    "state": s.state.value,
                    "failure_rate": s.total_failures / max(s.total_requests, 1),
                    "last_failure": s.last_failure_time.isoformat()
                    if s.last_failure_time
                    else None,
                    "last_success": s.last_success_time.isoformat()
                    if s.last_success_time
                    else None,
                }
                for name, s in stats.items()
            },
        }


# Global instance
_circuit_breaker_service = None


def get_circuit_breaker_service() -> CircuitBreakerService:
    """Get global circuit breaker service instance"""
    global _circuit_breaker_service
    if _circuit_breaker_service is None:
        _circuit_breaker_service = CircuitBreakerService()
    return _circuit_breaker_service
