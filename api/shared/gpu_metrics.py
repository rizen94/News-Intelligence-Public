"""
Shared GPU metrics (temperature, utilization, VRAM) via nvidia-smi or GPUtil.
Used by system_monitoring health and by automation_manager for temperature-based throttling.
"""

import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

# Above this temp (C), automation will pause Ollama work briefly to let GPU cool
GPU_TEMP_THROTTLE_C = 82

# Max seconds to wait when throttling before skipping this cycle
GPU_THROTTLE_SLEEP_SECONDS = 60


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


def should_throttle_ollama(max_temp_c: int = GPU_TEMP_THROTTLE_C) -> bool:
    """True if GPU temp is at or above max_temp_c (throttle Ollama work)."""
    metrics = get_gpu_metrics()
    temp = metrics.get("gpu_temperature_c")
    if temp is None:
        return False
    return temp >= max_temp_c
