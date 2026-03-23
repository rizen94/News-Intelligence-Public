"""
Resource manager for GPU VRAM and system RAM allocation.

Monitors available resources, enforces allocation limits per workload,
and prevents out-of-memory conditions by checking before loading models.

Adapted for News Intelligence: Ollama models (primary, secondary slot, nomic-embed-text; see config.settings.MODELS).
"""

import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum

from config.settings import MODELS

logger = logging.getLogger(__name__)

# Optional: psutil for RAM stats (already in project deps)
try:
    import psutil
except ImportError:
    psutil = None


class WorkloadProfile(Enum):
    """Workload types for resource budgeting."""

    BATCH_PROCESSING = "batch_processing"
    REAL_TIME = "real_time"
    REPORT_GENERATION_HIGH = "report_generation_high"
    REPORT_GENERATION_FAST = "report_generation_fast"
    IDLE = "idle"


@dataclass
class ResourceBudget:
    """Defines the resource limits for a workload."""

    max_vram_gb: float
    max_ram_gb: float
    models: list[dict]
    description: str


@dataclass
class ResourceState:
    """Current snapshot of system resource usage."""

    total_vram_gb: float
    used_vram_gb: float
    free_vram_gb: float
    total_ram_gb: float
    used_ram_gb: float
    free_ram_gb: float
    gpu_utilization_pct: float
    gpu_temperature_c: float
    loaded_models: list[str]


# News Intelligence workload budgets (RTX 5090 32GB, 62GB RAM)
WORKLOAD_BUDGETS: dict[WorkloadProfile, ResourceBudget] = {
    WorkloadProfile.BATCH_PROCESSING: ResourceBudget(
        max_vram_gb=12.0,
        max_ram_gb=16.0,
        models=[
            {"name": "nomic-embed-text", "vram_gb": 0.5, "ram_gb": 0.2, "role": "embedding"},
            {"name": MODELS["secondary"], "vram_gb": 8.0, "ram_gb": 0.5, "role": "batch"},
            {"name": "llama3.1:8b", "vram_gb": 5.0, "ram_gb": 0.5, "role": "alternative"},
        ],
        description="RSS processing, entity extraction, topic clustering",
    ),
    WorkloadProfile.REAL_TIME: ResourceBudget(
        max_vram_gb=8.0,
        max_ram_gb=12.0,
        models=[
            {"name": "llama3.1:8b", "vram_gb": 5.0, "ram_gb": 0.5, "role": "realtime"},
        ],
        description="Quick summaries, real-time API responses",
    ),
    WorkloadProfile.REPORT_GENERATION_HIGH: ResourceBudget(
        max_vram_gb=32.0,
        max_ram_gb=30.0,
        models=[
            {
                "name": "qwen2.5:72b-instruct-q4_K_M",
                "vram_gb": 32.0,
                "ram_gb": 12.0,
                "role": "generation",
            },
        ],
        description="Future: high-quality report generation",
    ),
    WorkloadProfile.REPORT_GENERATION_FAST: ResourceBudget(
        max_vram_gb=28.0,
        max_ram_gb=15.0,
        models=[
            {
                "name": "qwen2.5:32b-instruct-q5_K_M",
                "vram_gb": 24.0,
                "ram_gb": 1.0,
                "role": "generation",
            },
            {"name": "nomic-embed-text", "vram_gb": 0.5, "ram_gb": 0.2, "role": "embedding"},
        ],
        description="Future: fast report generation with retrieval",
    ),
    WorkloadProfile.IDLE: ResourceBudget(
        max_vram_gb=0.0, max_ram_gb=5.0, models=[], description="No models loaded"
    ),
}

VRAM_SAFETY_MARGIN_GB = 1.5
RAM_SAFETY_MARGIN_GB = 8.0


class ResourceManager:
    """
    Manages GPU and RAM allocation for different workload profiles.

    Usage:
        rm = ResourceManager()
        state = rm.get_current_state()
        rm.validate_workload(WorkloadProfile.BATCH_PROCESSING)
        rm.switch_workload(WorkloadProfile.BATCH_PROCESSING)
    """

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.current_workload = WorkloadProfile.IDLE
        self._verify_gpu()

    def _verify_gpu(self) -> None:
        """Verify NVIDIA GPU is accessible and get baseline specs."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version,compute_cap",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            parts = [p.strip() for p in result.stdout.strip().split(",")]
            self.gpu_name = parts[0] if len(parts) > 0 else "Unknown"
            self.total_vram_mb = float(parts[1]) if len(parts) > 1 else 0
            self.driver_version = parts[2] if len(parts) > 2 else "Unknown"
            self.compute_cap = parts[3] if len(parts) > 3 else "Unknown"

            logger.info("GPU verified: %s", self.gpu_name)
            logger.info("  VRAM: %.1f GB", self.total_vram_mb / 1024)
            logger.info("  Driver: %s", self.driver_version)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise RuntimeError(
                "nvidia-smi failed. Ensure NVIDIA drivers are installed and the GPU is accessible."
            ) from e

    def get_current_state(self) -> ResourceState:
        """Get current resource utilization snapshot."""
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]

        if psutil:
            ram = psutil.virtual_memory()
            total_ram_gb = ram.total / (1024**3)
            used_ram_gb = ram.used / (1024**3)
            free_ram_gb = ram.available / (1024**3)
        else:
            total_ram_gb = used_ram_gb = free_ram_gb = 0.0

        return ResourceState(
            total_vram_gb=float(parts[0]) / 1024,
            used_vram_gb=float(parts[1]) / 1024,
            free_vram_gb=float(parts[2]) / 1024,
            total_ram_gb=total_ram_gb,
            used_ram_gb=used_ram_gb,
            free_ram_gb=free_ram_gb,
            gpu_utilization_pct=float(parts[3]) if len(parts) > 3 else 0.0,
            gpu_temperature_c=float(parts[4]) if len(parts) > 4 else 0.0,
            loaded_models=self._get_loaded_models(),
        )

    def _get_loaded_models(self) -> list[str]:
        """Query Ollama for currently loaded models."""
        try:
            import requests

            resp = requests.get(f"{self.ollama_host}/api/ps", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def _unload_all_models(self) -> None:
        """Unload all models from Ollama to free VRAM."""
        loaded = self._get_loaded_models()
        if not loaded:
            return

        import requests

        for model_name in loaded:
            try:
                requests.post(
                    f"{self.ollama_host}/api/generate",
                    json={"model": model_name, "keep_alive": 0},
                    timeout=30,
                )
                logger.info("Unloaded model: %s", model_name)
            except Exception as e:
                logger.warning("Failed to unload %s: %s", model_name, e)

    def validate_workload(self, profile: WorkloadProfile) -> tuple[bool, str]:
        """
        Check whether the system can support a workload profile.
        Returns (can_run: bool, reason: str)
        """
        budget = WORKLOAD_BUDGETS[profile]
        state = self.get_current_state()

        available_vram = state.total_vram_gb - VRAM_SAFETY_MARGIN_GB
        available_ram = (
            state.total_ram_gb - RAM_SAFETY_MARGIN_GB if state.total_ram_gb > 0 else 64.0
        )

        if budget.max_vram_gb > available_vram:
            return False, (
                f"Workload requires {budget.max_vram_gb:.1f} GB VRAM but only "
                f"{available_vram:.1f} GB available (after {VRAM_SAFETY_MARGIN_GB} GB safety margin)"
            )

        if budget.max_ram_gb > available_ram:
            return False, (
                f"Workload requires {budget.max_ram_gb:.1f} GB RAM but only "
                f"{available_ram:.1f} GB available (after {RAM_SAFETY_MARGIN_GB} GB safety margin)"
            )

        return True, f"Workload {profile.value} can run. {budget.description}"

    def switch_workload(self, profile: WorkloadProfile) -> ResourceState:
        """Switch to a new workload profile. Unloads current models and updates tracking."""
        can_run, reason = self.validate_workload(profile)
        if not can_run:
            raise RuntimeError(f"Cannot switch to workload {profile.value}: {reason}")

        logger.info("Switching workload: %s -> %s", self.current_workload.value, profile.value)

        self._unload_all_models()

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except ImportError:
            pass

        self.current_workload = profile
        time.sleep(2)

        new_state = self.get_current_state()
        logger.info(
            "Workload switched. VRAM free: %.1f GB, RAM free: %.1f GB",
            new_state.free_vram_gb,
            new_state.free_ram_gb,
        )
        return new_state

    def get_model_config_for_workload(self) -> list[dict]:
        """Return model configuration for the current workload."""
        return WORKLOAD_BUDGETS[self.current_workload].models.copy()

    def monitor(self) -> dict:
        """Return a monitoring snapshot suitable for logging or display."""
        state = self.get_current_state()
        budget = WORKLOAD_BUDGETS[self.current_workload]

        return {
            "workload": self.current_workload.value,
            "gpu": {
                "name": self.gpu_name,
                "vram_total_gb": round(state.total_vram_gb, 1),
                "vram_used_gb": round(state.used_vram_gb, 1),
                "vram_free_gb": round(state.free_vram_gb, 1),
                "vram_budget_gb": budget.max_vram_gb,
                "utilization_pct": state.gpu_utilization_pct,
                "temperature_c": state.gpu_temperature_c,
            },
            "ram": {
                "total_gb": round(state.total_ram_gb, 1),
                "used_gb": round(state.used_ram_gb, 1),
                "free_gb": round(state.free_ram_gb, 1),
                "ram_budget_gb": budget.max_ram_gb,
            },
            "models_loaded": state.loaded_models,
            "models_expected": [m["name"] for m in budget.models],
        }
