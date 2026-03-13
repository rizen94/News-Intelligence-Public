"""
Health Monitor Orchestrator — polls configured health feeds and creates system alerts
when a feed fails its health check. Updates in-memory state for GET /api/system_monitoring/health/feeds.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)

# Config path: api/config/monitoring_devices.yaml
_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_api_root, "config", "monitoring_devices.yaml")


def _load_config() -> Dict[str, Any]:
    if not os.path.isfile(_CONFIG_PATH):
        return {"health_feeds": [], "health_check_interval_seconds": 60}
    try:
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning("Health monitor config load failed: %s", e)
        return {"health_feeds": [], "health_check_interval_seconds": 60}


def _check_one_feed_sync(name: str, url: str, base_url: str) -> Dict[str, Any]:
    """Synchronous check for one health feed (run in executor)."""
    import requests
    full_url = (base_url.rstrip("/") + url) if url.startswith("/") else url
    out = {
        "ok": False,
        "status_code": None,
        "message": None,
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }
    try:
        resp = requests.get(full_url, timeout=10)
        out["status_code"] = resp.status_code
        if resp.status_code != 200:
            out["message"] = f"HTTP {resp.status_code}"
            return out
        try:
            body = resp.json()
        except Exception:
            body = {}
        status = body.get("status") if isinstance(body, dict) else None
        if status is not None and status not in ("healthy", "degraded", "warning"):
            out["message"] = f"status={status}"
            return out
        out["ok"] = True
        out["message"] = "ok"
        return out
    except requests.exceptions.Timeout:
        out["message"] = "timeout"
        return out
    except Exception as e:
        out["message"] = str(e)[:200]
        return out


def _create_health_alert(feed_name: str, message: str) -> None:
    """Create a system_alert row for a failed health check (columns match existing create_system_alert)."""
    try:
        from shared.database.connection import get_db_connection
        import json
        conn = get_db_connection()
        if not conn:
            return
        try:
            now = datetime.utcnow()
            alert_data = json.dumps({"feed": feed_name})
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO system_alerts
                    (alert_type, severity, title, description, alert_data, created_at, updated_at, is_active)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, true)
                """, (
                    "health_check",
                    "high",
                    f"Health check failed: {feed_name}",
                    message,
                    alert_data,
                    now,
                    now,
                ))
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Failed to create health alert: %s", e)


class HealthMonitorOrchestrator:
    """Polls health feeds periodically and creates alerts on failure."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._last_results: Dict[str, Dict[str, Any]] = {}
        self._last_failed: Dict[str, bool] = {}  # track if we already alerted for this feed

    def get_last_results(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._last_results)

    async def _run_cycle(self) -> None:
        config = _load_config()
        feeds = config.get("health_feeds") or []
        if not feeds:
            return
        loop = asyncio.get_event_loop()
        results = {}
        for feed in feeds:
            name = feed.get("name") or feed.get("url") or "unknown"
            url = feed.get("url") or ""
            r = await loop.run_in_executor(
                None, _check_one_feed_sync, name, url, self.base_url
            )
            results[name] = r
            if not r["ok"]:
                if not self._last_failed.get(name):
                    _create_health_alert(name, r.get("message") or f"HTTP {r.get('status_code')}")
                    self._last_failed[name] = True
            else:
                self._last_failed[name] = False
        self._last_results = results
        try:
            from domains.system_monitoring.routes.resource_dashboard import set_health_feed_results
            set_health_feed_results(results)
        except Exception as e:
            logger.debug("Could not set health feed results: %s", e)

    async def _loop(self) -> None:
        config = _load_config()
        interval = max(30, int(config.get("health_check_interval_seconds") or 60))
        while not self._stop.is_set():
            try:
                await self._run_cycle()
            except Exception as e:
                logger.warning("Health monitor cycle error: %s", e)
            await asyncio.sleep(interval)

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("Health monitor orchestrator started (interval from config)")

    def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Health monitor orchestrator stopped")


# Singleton for lifespan
_health_monitor: HealthMonitorOrchestrator | None = None


def get_health_monitor(base_url: str = "http://127.0.0.1:8000") -> HealthMonitorOrchestrator:
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitorOrchestrator(base_url=base_url)
    return _health_monitor
