"""
Shared GPU metrics (temperature, utilization, VRAM) via nvidia-smi or GPUtil.
Used by system_monitoring health and by automation_manager for temperature-based throttling.
"""

import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except (TypeError, ValueError):
        return default


# Above this temp (C), automation will pause Ollama work briefly to let GPU cool
GPU_TEMP_THROTTLE_C = _env_int("GPU_TEMP_THROTTLE_C", 82, minimum=60)

# Max seconds to wait when throttling before skipping this cycle
GPU_THROTTLE_SLEEP_SECONDS = _env_int("GPU_THROTTLE_SLEEP_SECONDS", 60, minimum=5)


def get_gpu_metrics() -> dict[str, Any]:
    """
    Get GPU utilization, VRAM, and temperature. Tries nvidia-smi first, then GPUtil.
    Returns dict with gpu_utilization_percent, gpu_vram_percent, gpu_temperature_c, etc.
    All keys may be None if unavailable.
    """
    result: dict[str, Any] = {
        "gpu_utilization_percent": None,
        "gpu_vram_percent": None,
        "gpu_temperature_c": None,
        "gpu_memory_used_mb": None,
        "gpu_memory_total_mb": None,
    }
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parts = [p.strip() for p in proc.stdout.strip().split(",")]
            if len(parts) >= 3:
                util = parts[0].strip().replace(" %", "")
                mem_used = parts[1].strip().replace(" MiB", "").replace(" ", "")
                mem_total = parts[2].strip().replace(" MiB", "").replace(" ", "")
                result["gpu_utilization_percent"] = float(util) if util.isdigit() else None
                try:
                    u_mb = int(mem_used)
                    t_mb = int(mem_total)
                    result["gpu_memory_used_mb"] = u_mb
                    result["gpu_memory_total_mb"] = t_mb
                    result["gpu_vram_percent"] = round(100.0 * u_mb / t_mb, 1) if t_mb else None
                except (ValueError, TypeError):
                    pass
                if len(parts) >= 4:
                    temp = parts[3].strip().replace(" C", "")
                    try:
                        result["gpu_temperature_c"] = int(temp)
                    except (ValueError, TypeError):
                        pass
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            result["gpu_utilization_percent"] = round((gpu.load or 0) * 100, 1)
            result["gpu_vram_percent"] = round((gpu.memoryUtil or 0) * 100, 1)
            if getattr(gpu, "memoryUsed", None) is not None:
                result["gpu_memory_used_mb"] = int(gpu.memoryUsed)
            if getattr(gpu, "memoryTotal", None) is not None:
                result["gpu_memory_total_mb"] = int(gpu.memoryTotal)
            if getattr(gpu, "temperature", None) is not None:
                result["gpu_temperature_c"] = int(gpu.temperature)
    except ImportError:
        pass
    except Exception:
        pass
    return result


def maybe_record_gpu_metric_sample() -> None:
    """
    Insert one row into public.gpu_metric_samples if the table exists and the last
    sample is older than GPU_METRIC_SAMPLE_MIN_SECONDS (default 55s). Best-effort;
    skips when nvidia-smi unavailable or DB errors.
    """
    min_sec = _env_int("GPU_METRIC_SAMPLE_MIN_SECONDS", 55, minimum=15)
    metrics = get_gpu_metrics()
    if metrics.get("gpu_memory_total_mb") is None:
        return
    try:
        from shared.database.connection import get_ui_db_connection

        conn = get_ui_db_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT 1 FROM public.gpu_metric_samples
                    WHERE sampled_at >= NOW() - (%s * INTERVAL '1 second')
                    LIMIT 1
                    """,
                    (min_sec,),
                )
                if cur.fetchone():
                    return
            except Exception:
                conn.rollback()
                return
            cur.execute(
                """
                INSERT INTO public.gpu_metric_samples (
                    gpu_utilization_percent,
                    gpu_vram_percent,
                    gpu_memory_used_mb,
                    gpu_memory_total_mb,
                    gpu_temperature_c
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    metrics.get("gpu_utilization_percent"),
                    metrics.get("gpu_vram_percent"),
                    metrics.get("gpu_memory_used_mb"),
                    metrics.get("gpu_memory_total_mb"),
                    metrics.get("gpu_temperature_c"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("maybe_record_gpu_metric_sample: %s", exc)


def fetch_gpu_metric_hourly_buckets(*, hours: int = 72) -> list[dict[str, Any]]:
    """
    Hourly aggregates for Monitor charts. Returns [] if table missing or DB down.
    """
    h = max(1, min(int(hours), 168))
    out: list[dict[str, Any]] = []
    try:
        from shared.database.connection import get_ui_db_connection

        conn = get_ui_db_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute("SET LOCAL TIME ZONE 'UTC'")
            except Exception:
                pass
            cur.execute(
                """
                SELECT
                    date_trunc('hour', sampled_at) AS hour_utc,
                    AVG(gpu_utilization_percent)::float,
                    AVG(gpu_vram_percent)::float,
                    AVG(gpu_memory_used_mb)::float,
                    MAX(gpu_memory_total_mb)::int,
                    AVG(gpu_temperature_c)::float,
                    COUNT(*)::bigint
                FROM public.gpu_metric_samples
                WHERE sampled_at >= NOW() - (%s * INTERVAL '1 hour')
                GROUP BY 1
                ORDER BY 1 ASC
                """,
                (h,),
            )
            for row in cur.fetchall() or []:
                hr, u, vp, mu, mt, temp, n = row
                out.append(
                    {
                        "hour_utc": hr.isoformat() if hasattr(hr, "isoformat") else str(hr),
                        "avg_gpu_utilization_percent": round(u, 1) if u is not None else None,
                        "avg_gpu_vram_percent": round(vp, 1) if vp is not None else None,
                        "avg_gpu_memory_used_mb": round(mu, 0) if mu is not None else None,
                        "gpu_memory_total_mb": mt,
                        "avg_gpu_temperature_c": round(temp, 1) if temp is not None else None,
                        "sample_count": int(n) if n is not None else 0,
                    }
                )
        finally:
            conn.close()
    except Exception as exc:
        logger.debug("fetch_gpu_metric_hourly_buckets: %s", exc)
    return out


def should_throttle_ollama(max_temp_c: int = GPU_TEMP_THROTTLE_C) -> bool:
    """True if GPU temp is at or above max_temp_c (throttle Ollama work)."""
    metrics = get_gpu_metrics()
    temp = metrics.get("gpu_temperature_c")
    if temp is None:
        return False
    return temp >= max_temp_c
