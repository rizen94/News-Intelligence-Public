"""
Health + pause gate for the dedicated embeddings Ollama host (Dockside).

When ``OLLAMA_EMBEDDINGS_HOST`` is set:
- Probe ``/api/tags`` (or version) on a short cadence
- Pause embeddings work after consecutive failures (no per-chunk CB spam)
- Recover automatically after a successful probe
- Export counters/gauges for Homelab Grafana via ni_prometheus_metrics_service

Embeddings CB key ``ollama_embeddings`` stays fail-fast inside llm_service; this
layer short-circuits the worker so AutomationManager does not burn cycles.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import httpx

from api.config.runtime import env_float, env_int, env_str

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingsHostSnapshot:
    configured: bool
    host: str
    up: bool
    paused: bool
    pause_reason: str
    consecutive_failures: int
    consecutive_successes: int
    last_ok_unix: float | None
    last_fail_unix: float | None
    last_error: str
    last_probe_latency_ms: float | None
    success_total: int
    fail_total: int
    probe_ok_total: int
    probe_fail_total: int
    yield_total: int


class EmbeddingsHostHealthService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_probe_mono: float = 0.0
        # Unknown until first successful probe/embed — avoids false "up" after restart.
        self._up: bool = False
        self._paused: bool = False
        self._pause_reason: str = ""
        self._consec_fail: int = 0
        self._consec_ok: int = 0
        self._last_ok_unix: float | None = None
        self._last_fail_unix: float | None = None
        self._last_error: str = ""
        self._last_probe_latency_ms: float | None = None
        self._success_total: int = 0
        self._fail_total: int = 0
        self._probe_ok_total: int = 0
        self._probe_fail_total: int = 0
        self._yield_total: int = 0

    def configured_host(self) -> str:
        return env_str("OLLAMA_EMBEDDINGS_HOST", "").strip().rstrip("/")

    def _fail_threshold(self) -> int:
        # Default 1: pause on first confirmed miss so we do not burn embed cycles.
        return max(1, env_int("EMBEDDINGS_HOST_FAIL_THRESHOLD", 1))

    def _recovery_needed(self) -> int:
        return max(1, env_int("EMBEDDINGS_HOST_RECOVERY_SUCCESSES", 1))

    def _probe_interval(self) -> float:
        return max(5.0, env_float("EMBEDDINGS_HOST_PROBE_INTERVAL_SEC", 30.0))

    def _probe_timeout(self) -> float:
        return max(1.0, env_float("EMBEDDINGS_HOST_PROBE_TIMEOUT_SEC", 5.0))

    def snapshot(self) -> EmbeddingsHostSnapshot:
        host = self.configured_host()
        with self._lock:
            return EmbeddingsHostSnapshot(
                configured=bool(host),
                host=host or "",
                up=bool(self._up) if host else True,
                paused=bool(self._paused) if host else False,
                pause_reason=self._pause_reason if host else "",
                consecutive_failures=self._consec_fail,
                consecutive_successes=self._consec_ok,
                last_ok_unix=self._last_ok_unix,
                last_fail_unix=self._last_fail_unix,
                last_error=self._last_error,
                last_probe_latency_ms=self._last_probe_latency_ms,
                success_total=self._success_total,
                fail_total=self._fail_total,
                probe_ok_total=self._probe_ok_total,
                probe_fail_total=self._probe_fail_total,
                yield_total=self._yield_total,
            )

    def should_pause_embeddings(self, *, force_probe: bool = False) -> tuple[bool, str]:
        """Return (pause, reason). No dedicated host → never pause here."""
        host = self.configured_host()
        if not host:
            return False, ""
        self.ensure_probed(force=force_probe)
        with self._lock:
            if self._paused:
                return True, self._pause_reason or "embeddings_host_paused"
            return False, ""

    def note_worker_yielded(self, reason: str) -> None:
        with self._lock:
            self._yield_total += 1
        logger.info("embeddings host gate yielded: %s", reason)

    def ensure_probed(self, *, force: bool = False) -> EmbeddingsHostSnapshot:
        host = self.configured_host()
        if not host:
            return self.snapshot()
        now = time.monotonic()
        with self._lock:
            due = force or (now - self._last_probe_mono) >= self._probe_interval()
            if not due:
                return self.snapshot()
            self._last_probe_mono = now
        self._run_probe(host)
        return self.snapshot()

    def _run_probe(self, host: str) -> None:
        timeout = self._probe_timeout()
        t0 = time.perf_counter()
        err = ""
        ok = False
        try:
            with httpx.Client(timeout=timeout) as client:
                # Prefer /api/tags (cheap); fall back to /api/version
                r = client.get(f"{host}/api/tags")
                if r.status_code != 200:
                    r = client.get(f"{host}/api/version")
                ok = r.status_code == 200
                if not ok:
                    err = f"http_{r.status_code}"
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:240]
            ok = False
        latency_ms = (time.perf_counter() - t0) * 1000.0
        now_unix = time.time()
        with self._lock:
            self._last_probe_latency_ms = latency_ms
            if ok:
                self._up = True
                self._consec_ok += 1
                self._consec_fail = 0
                self._last_ok_unix = now_unix
                self._last_error = ""
                self._probe_ok_total += 1
                if self._paused and self._consec_ok >= self._recovery_needed():
                    self._paused = False
                    self._pause_reason = ""
                    logger.info("embeddings host recovered: %s", host)
                    try:
                        from services.circuit_breaker_service import get_circuit_breaker_service

                        get_circuit_breaker_service().get_circuit_breaker(
                            "ollama_embeddings"
                        ).reset()
                    except Exception:
                        pass
            else:
                self._up = False
                self._consec_fail += 1
                self._consec_ok = 0
                self._last_fail_unix = now_unix
                self._last_error = err
                self._probe_fail_total += 1
                if self._consec_fail >= self._fail_threshold():
                    if not self._paused:
                        logger.warning(
                            "embeddings host PAUSED after %s failures (%s): %s",
                            self._consec_fail,
                            host,
                            err,
                        )
                    self._paused = True
                    self._pause_reason = f"embeddings_host_unreachable:{err or 'unknown'}"

    def record_embed_success(self) -> None:
        with self._lock:
            self._success_total += 1
            self._up = True
            self._consec_ok += 1
            self._consec_fail = 0
            self._last_ok_unix = time.time()
            if self._paused and self._consec_ok >= self._recovery_needed():
                self._paused = False
                self._pause_reason = ""

    def record_embed_failure(self, exc: BaseException | str | None = None) -> None:
        msg = ""
        if isinstance(exc, BaseException):
            msg = f"{type(exc).__name__}: {exc}"[:240]
        elif exc:
            msg = str(exc)[:240]
        with self._lock:
            self._fail_total += 1
            self._consec_fail += 1
            self._consec_ok = 0
            self._last_fail_unix = time.time()
            self._last_error = msg or self._last_error
            self._up = False
            if self._consec_fail >= self._fail_threshold():
                self._paused = True
                self._pause_reason = f"embeddings_host_errors:{msg or 'fail'}"

    def prometheus_samples(self) -> dict[str, Any]:
        # Never HTTP-probe on the scrape path — worker/AM probes; Grafana reads last state.
        snap = self.snapshot()
        return {
            "configured": 1.0 if snap.configured else 0.0,
            "up": 1.0 if snap.up else 0.0,
            "paused": 1.0 if snap.paused else 0.0,
            "consecutive_failures": float(snap.consecutive_failures),
            "success_total": float(snap.success_total),
            "fail_total": float(snap.fail_total),
            "probe_ok_total": float(snap.probe_ok_total),
            "probe_fail_total": float(snap.probe_fail_total),
            "yield_total": float(snap.yield_total),
            "probe_latency_ms": (
                float(snap.last_probe_latency_ms)
                if snap.last_probe_latency_ms is not None
                else None
            ),
            "host": snap.host,
            "pause_reason": snap.pause_reason,
            "last_error": snap.last_error,
        }

    def start_background_probe_loop(self) -> None:
        """Periodic probe so Grafana + pause gate stay current when worker is idle."""
        host = self.configured_host()
        if not host:
            return

        def _loop() -> None:
            while True:
                try:
                    self.ensure_probed(force=True)
                except Exception as e:
                    logger.debug("embeddings host bg probe: %s", e)
                # While paused/down, re-check faster for recovery + Grafana alerts.
                with self._lock:
                    down = self._paused or not self._up
                interval = 10.0 if down else self._probe_interval()
                time.sleep(max(5.0, interval))

        threading.Thread(
            target=_loop, name="embeddings-host-probe-loop", daemon=True
        ).start()


_svc: EmbeddingsHostHealthService | None = None
_svc_lock = threading.Lock()


_bg_probe_started = False


def get_embeddings_host_health() -> EmbeddingsHostHealthService:
    global _svc, _bg_probe_started
    with _svc_lock:
        if _svc is None:
            _svc = EmbeddingsHostHealthService()
        svc = _svc
        start_probe = False
        if not _bg_probe_started and svc.configured_host():
            _bg_probe_started = True
            start_probe = True
    if start_probe:
        svc.start_background_probe_loop()
    return svc
