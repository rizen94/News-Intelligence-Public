"""Host-aware resource probes for major backlog catch-up auto-tuning.

The catch-up script runs on Widow (orchestrator + DB). GPU LLM work may run on PopOS
(OLLAMA_GPU_HOST). Auto-tune must read GPU metrics from the GPU host, not local nvidia-smi.
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)

GPU_HEAVY_PHASES = frozenset({"entity_profile_build", "story_enhancement", "event_extraction"})
DB_HEAVY_PHASES = frozenset({"entity_dossier_compile", "entity_profile_build", "story_enhancement"})


@dataclass
class RoutingContext:
    popos_gpu: bool = False
    dual_lane: bool = False
    gpu_ollama_url: str = ""
    cpu_ollama_url: str = ""


_routing = RoutingContext()


def set_routing_context(ctx: RoutingContext) -> None:
    global _routing
    _routing = ctx


def get_routing_context() -> RoutingContext:
    return _routing


@dataclass
class ResourceSnapshot:
    """Metrics tagged by where work actually runs."""

    local_cpu_percent: float | None
    local_memory_percent: float | None
    db_worker_util: float
    gpu_host: str
    gpu_util_percent: float | None
    gpu_temp_c: int | None
    gpu_vram_percent: float | None
    gpu_probe_source: str
    cpu_llm_cpu_percent: float | None
    local_cpu_headroom: float
    local_memory_headroom: float
    db_headroom: float
    gpu_llm_headroom: float
    cpu_llm_headroom: float

    def phase_headroom(self, phase: str) -> float:
        parts: list[float] = [self.local_memory_headroom, self.db_headroom]
        if phase in GPU_HEAVY_PHASES:
            parts.append(self.gpu_llm_headroom)
            if _routing.dual_lane:
                parts.append(self.cpu_llm_headroom)
        else:
            parts.append(self.local_cpu_headroom)
        if phase in DB_HEAVY_PHASES:
            parts.append(self.db_headroom)
        return min(parts)

    def to_log_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, float):
                d[k] = round(v, 3)
        return d


def _parse_ollama_host(url: str) -> tuple[str, int]:
    parsed = urllib.parse.urlparse(url or "http://localhost:11434")
    host = parsed.hostname or "localhost"
    port = parsed.port or 11434
    return host, port


def _nvidia_smi_dict(util: float, mem_used_mb: int, mem_total_mb: int, temp: int | None) -> dict[str, Any]:
    vram_pct = round(100.0 * mem_used_mb / mem_total_mb, 1) if mem_total_mb else None
    return {
        "gpu_utilization_percent": float(util),
        "gpu_vram_percent": vram_pct,
        "gpu_temperature_c": temp,
        "gpu_memory_used_mb": mem_used_mb,
        "gpu_memory_total_mb": mem_total_mb,
    }


def _probe_nvidia_smi_local() -> dict[str, Any] | None:
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        parts = [p.strip() for p in proc.stdout.strip().split(",")]
        if len(parts) < 3:
            return None
        util = float(parts[0])
        mem_used = int(float(parts[1]))
        mem_total = int(float(parts[2]))
        temp = int(float(parts[3])) if len(parts) >= 4 and parts[3] else None
        out = _nvidia_smi_dict(util, mem_used, mem_total, temp)
        out["source"] = "local-nvidia-smi"
        return out
    except Exception as e:
        logger.debug("local nvidia-smi: %s", e)
        return None


def _probe_nvidia_smi_ssh(host: str, user: str) -> dict[str, Any] | None:
    from config.runtime import env_str

    target = env_str("MAJOR_CATCHUP_GPU_METRICS_SSH", "").strip()
    if not target:
        target = f"{user}@{host}" if user else host
    try:
        proc = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "StrictHostKeyChecking=accept-new",
                target,
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=12,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            logger.debug("ssh nvidia-smi %s: %s", target, (proc.stderr or proc.stdout)[:200])
            return None
        parts = [p.strip() for p in proc.stdout.strip().split(",")]
        if len(parts) < 3:
            return None
        util = float(parts[0])
        mem_used = int(float(parts[1]))
        mem_total = int(float(parts[2]))
        temp = int(float(parts[3])) if len(parts) >= 4 and parts[3] else None
        out = _nvidia_smi_dict(util, mem_used, mem_total, temp)
        out["source"] = f"ssh-nvidia-smi:{target}"
        return out
    except Exception as e:
        logger.debug("ssh nvidia-smi %s: %s", target, e)
        return None


def _probe_gpu_via_ollama(ollama_url: str) -> dict[str, Any] | None:
    """VRAM / load proxy when nvidia-smi on the GPU host is unreachable."""
    from config.runtime import env_str

    base = (ollama_url or "").rstrip("/")
    if not base:
        return None
    try:
        req = urllib.request.Request(f"{base}/api/ps", method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        models = data.get("models") or []
        try:
            total_mb = int(env_str("MAJOR_CATCHUP_GPU_VRAM_TOTAL_MB", "32768"))
        except ValueError:
            total_mb = 32768
        loaded_bytes = sum(int(m.get("size_vram") or 0) for m in models)
        loaded_mb = loaded_bytes / (1024 * 1024)
        vram_pct = min(100.0, round(100.0 * loaded_mb / total_mb, 1)) if total_mb else None
        if not models:
            util_pct = 0.0
        else:
            util_pct = min(100.0, max(35.0, (vram_pct or 35.0) * 0.85 + len(models) * 8.0))
        host, _ = _parse_ollama_host(base)
        return {
            "gpu_utilization_percent": util_pct,
            "gpu_vram_percent": vram_pct,
            "gpu_temperature_c": None,
            "gpu_memory_used_mb": int(loaded_mb),
            "gpu_memory_total_mb": total_mb,
            "source": f"ollama-ps:{host}",
            "ollama_models_loaded": len(models),
        }
    except Exception as e:
        logger.debug("ollama ps probe %s: %s", base, e)
        return None


def _probe_gpu_llm_host(gpu_ollama_url: str, *, use_remote: bool) -> dict[str, Any]:
    host, _ = _parse_ollama_host(gpu_ollama_url)
    from config.runtime import env_str

    user = env_str("MAJOR_CATCHUP_GPU_METRICS_SSH_USER", "pete")

    if not use_remote or host in ("localhost", "127.0.0.1"):
        local = _probe_nvidia_smi_local()
        if local:
            local["gpu_host"] = "local"
            return local
        ollama = _probe_gpu_via_ollama(gpu_ollama_url or "http://localhost:11434")
        if ollama:
            ollama["gpu_host"] = "local"
            return ollama
        return {
            "gpu_host": "local",
            "gpu_utilization_percent": None,
            "gpu_vram_percent": None,
            "gpu_temperature_c": None,
            "source": "unavailable",
        }

    ssh = _probe_nvidia_smi_ssh(host, user)
    if ssh:
        ssh["gpu_host"] = host
        return ssh
    ollama = _probe_gpu_via_ollama(gpu_ollama_url)
    if ollama:
        ollama["gpu_host"] = host
        return ollama
    return {
        "gpu_host": host,
        "gpu_utilization_percent": None,
        "gpu_vram_percent": None,
        "gpu_temperature_c": None,
        "source": "unavailable",
    }


def sample_resources() -> ResourceSnapshot:
    cpu_percent: float | None = None
    memory_percent: float | None = None
    try:
        import psutil

        cpu_percent = float(psutil.cpu_percent(interval=0.1))
        memory_percent = float(psutil.virtual_memory().percent)
    except Exception:
        pass

    db_worker_util = 0.0
    try:
        from shared.database.connection import get_db_pool_snapshot

        snap = get_db_pool_snapshot()
        db_worker_util = float((snap.get("worker") or {}).get("utilization") or 0.0)
    except Exception:
        pass

    gpu_url = _routing.gpu_ollama_url or "http://localhost:11434"
    gpu_raw = _probe_gpu_llm_host(gpu_url, use_remote=_routing.popos_gpu)

    cpu_llm_cpu: float | None = None
    if _routing.dual_lane:
        cpu_llm_cpu = cpu_percent

    local_cpu_headroom = max(0.0, min(1.0, 1.0 - ((cpu_percent or 0.0) / 100.0)))
    local_memory_headroom = max(0.0, min(1.0, 1.0 - ((memory_percent or 0.0) / 100.0)))
    db_headroom = max(0.0, min(1.0, 1.0 - db_worker_util))

    gpu_util = gpu_raw.get("gpu_utilization_percent")
    gpu_headroom = (
        max(0.0, min(1.0, 1.0 - (float(gpu_util) / 100.0))) if gpu_util is not None else 0.55
    )
    cpu_llm_headroom = (
        max(0.0, min(1.0, 1.0 - ((cpu_llm_cpu or 0.0) / 100.0))) if _routing.dual_lane else 1.0
    )

    return ResourceSnapshot(
        local_cpu_percent=cpu_percent,
        local_memory_percent=memory_percent,
        db_worker_util=db_worker_util,
        gpu_host=str(gpu_raw.get("gpu_host") or "local"),
        gpu_util_percent=float(gpu_util) if gpu_util is not None else None,
        gpu_temp_c=gpu_raw.get("gpu_temperature_c"),
        gpu_vram_percent=gpu_raw.get("gpu_vram_percent"),
        gpu_probe_source=str(gpu_raw.get("source") or "unknown"),
        cpu_llm_cpu_percent=cpu_llm_cpu,
        local_cpu_headroom=local_cpu_headroom,
        local_memory_headroom=local_memory_headroom,
        db_headroom=db_headroom,
        gpu_llm_headroom=gpu_headroom,
        cpu_llm_headroom=cpu_llm_headroom,
    )


def merge_resource_snapshots(a: ResourceSnapshot, b: ResourceSnapshot) -> ResourceSnapshot:
    """Conservative merge across start/end of a loop."""
    gpu_temp = None
    temps = [t for t in (a.gpu_temp_c, b.gpu_temp_c) if t is not None]
    if temps:
        gpu_temp = max(temps)
    return ResourceSnapshot(
        local_cpu_percent=max(a.local_cpu_percent or 0, b.local_cpu_percent or 0) or None,
        local_memory_percent=max(a.local_memory_percent or 0, b.local_memory_percent or 0) or None,
        db_worker_util=max(a.db_worker_util, b.db_worker_util),
        gpu_host=a.gpu_host or b.gpu_host,
        gpu_util_percent=max(a.gpu_util_percent or 0, b.gpu_util_percent or 0) or None,
        gpu_temp_c=gpu_temp,
        gpu_vram_percent=max(a.gpu_vram_percent or 0, b.gpu_vram_percent or 0) or None,
        gpu_probe_source=a.gpu_probe_source,
        cpu_llm_cpu_percent=max(a.cpu_llm_cpu_percent or 0, b.cpu_llm_cpu_percent or 0) or None,
        local_cpu_headroom=min(a.local_cpu_headroom, b.local_cpu_headroom),
        local_memory_headroom=min(a.local_memory_headroom, b.local_memory_headroom),
        db_headroom=min(a.db_headroom, b.db_headroom),
        gpu_llm_headroom=min(a.gpu_llm_headroom, b.gpu_llm_headroom),
        cpu_llm_headroom=min(a.cpu_llm_headroom, b.cpu_llm_headroom),
    )


# Batch auto-tune tracks (which host metrics govern each knob).
TRACK_ENRICH = "enrich"  # Widow: Wikipedia HTTP + light DB
TRACK_BUILD = "build"  # PopOS GPU LLM (profile sections)
TRACK_LOCAL = "local"  # Widow CPU/DB (dossier with LLM narrative, fact triggers)
TRACK_DOSSIER_FAST = "dossier_fast"  # Dossier compile without LLM narrative (DB/CPU only)
TRACK_GPU = "gpu"  # GPU LLM (event extraction standalone)


def headroom_for_track(track: str, resources: ResourceSnapshot) -> float:
    if track == TRACK_ENRICH:
        return min(
            resources.local_memory_headroom,
            resources.local_cpu_headroom,
            resources.db_headroom,
        )
    if track == TRACK_BUILD:
        parts = [
            resources.gpu_llm_headroom,
            resources.local_memory_headroom,
            resources.db_headroom,
        ]
        if _routing.dual_lane:
            parts.append(resources.cpu_llm_headroom)
        return min(parts)
    if track == TRACK_LOCAL:
        return min(
            resources.local_cpu_headroom,
            resources.local_memory_headroom,
            resources.db_headroom,
        )
    if track == TRACK_DOSSIER_FAST:
        # Skip memory % — Linux file cache often reads high while dossier fast mode is DB-bound.
        return min(resources.local_cpu_headroom, resources.db_headroom)
    if track == TRACK_GPU:
        return min(
            resources.gpu_llm_headroom,
            resources.local_memory_headroom,
            resources.db_headroom,
        )
    return resources.phase_headroom("story_enhancement")


def _track_batch_bounds(
    track: str, tuning_config: dict[str, int | float]
) -> tuple[int, int, int]:
    batch_min = int(tuning_config["batch_min"])
    step = int(tuning_config["batch_step"])
    if track == TRACK_BUILD:
        return batch_min, int(tuning_config["build_batch_max"]), step
    if track == TRACK_ENRICH:
        return batch_min, int(tuning_config["enrich_batch_max"]), step
    if track == TRACK_DOSSIER_FAST:
        fast_min = int(tuning_config.get("dossier_fast_batch_min", batch_min))
        return max(batch_min, fast_min), int(tuning_config["batch_max"]), step
    return batch_min, int(tuning_config["batch_max"]), step


def tune_batch_track(
    track: str,
    current: int,
    resources: ResourceSnapshot,
    *,
    auto_tune: bool,
    tuning_config: dict[str, int | float],
) -> tuple[int, str, dict[str, Any]]:
    """Tune one batch knob using metrics from the host that runs that work."""
    batch_min, batch_max, step = _track_batch_bounds(track, tuning_config)
    current = max(batch_min, min(batch_max, current))

    if not auto_tune:
        return current, "hold_fixed", {"track": track, "headroom": headroom_for_track(track, resources)}

    headroom = headroom_for_track(track, resources)
    mem_pct = resources.local_memory_percent or 0.0
    gpu_temp = resources.gpu_temp_c
    meta: dict[str, Any] = {
        "track": track,
        "headroom": round(headroom, 3),
        "local_mem_pct": resources.local_memory_percent,
        "gpu_host": resources.gpu_host,
        "gpu_util_pct": resources.gpu_util_percent,
        "gpu_temp_c": gpu_temp,
        "gpu_probe": resources.gpu_probe_source,
    }

    decrease = False
    reasons: list[str] = []
    if headroom < float(tuning_config["decrease_headroom"]):
        decrease = True
        reasons.append(f"headroom<{tuning_config['decrease_headroom']}")

    memory_sensitive = (TRACK_ENRICH, TRACK_LOCAL, TRACK_BUILD, TRACK_GPU)
    if track in memory_sensitive:
        if mem_pct >= float(tuning_config["memory_critical_pct"]):
            decrease = True
            reasons.append(f"local_mem>={tuning_config['memory_critical_pct']}%")
    if track in (TRACK_BUILD, TRACK_GPU):
        if gpu_temp is not None and gpu_temp >= int(tuning_config["gpu_temp_decrease_c"]):
            decrease = True
            reasons.append(f"gpu_temp@{resources.gpu_host}>={tuning_config['gpu_temp_decrease_c']}C")

    if decrease:
        new_batch = max(batch_min, current - step)
        action = "decrease" if new_batch < current else "hold_floor"
        meta["reason"] = ",".join(reasons)
        meta["action"] = action
        return new_batch, action, meta

    can_increase = headroom >= float(tuning_config["increase_headroom"])
    if track in memory_sensitive:
        if mem_pct >= float(tuning_config["memory_pressure_pct"]):
            can_increase = False
            reasons.append(f"local_mem>={tuning_config['memory_pressure_pct']}%")
    if track in (TRACK_BUILD, TRACK_GPU):
        if gpu_temp is not None and gpu_temp >= int(tuning_config["gpu_temp_increase_max_c"]):
            can_increase = False
            reasons.append(f"gpu_temp>={tuning_config['gpu_temp_increase_max_c']}C")
        if resources.gpu_probe_source == "unavailable":
            can_increase = False
            reasons.append("gpu_metrics_unavailable")

    if can_increase and current < batch_max:
        new_batch = min(batch_max, current + step)
        meta["reason"] = "headroom_ok"
        meta["action"] = "increase"
        return new_batch, "increase", meta

    meta["reason"] = ",".join(reasons) if reasons else "headroom_marginal"
    meta["action"] = "hold"
    return current, "hold", meta


def _dossier_fast_tune_enabled() -> bool:
    try:
        from config.runtime import env_bool

        return bool(
            env_bool("DOSSIER_CATCHUP_SKIP_NARRATIVE", False)
            or env_bool("BULK_CATCHUP_ACTIVE", False)
        )
    except Exception:
        return False


def tune_batch_size(
    phase: str,
    current: int,
    resources: ResourceSnapshot,
    *,
    auto_tune: bool,
    tuning_config: dict[str, int | float],
) -> tuple[int, str, dict[str, Any]]:
    """Single-knob phases: map phase → resource track."""
    track_by_phase = {
        "entity_dossier_compile": TRACK_LOCAL,
        "entity_dossier_narrative": TRACK_GPU,
        "entity_profile_build": TRACK_BUILD,
        "event_extraction": TRACK_GPU,
    }
    track = track_by_phase.get(phase, TRACK_LOCAL)
    if phase == "entity_dossier_compile" and _dossier_fast_tune_enabled():
        track = TRACK_DOSSIER_FAST
    new_batch, action, meta = tune_batch_track(
        track, current, resources, auto_tune=auto_tune, tuning_config=tuning_config
    )
    meta["phase"] = phase
    return new_batch, action, meta
