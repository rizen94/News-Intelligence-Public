#!/usr/bin/env python3
"""Verify PopOS GPU-only backlog sprint routing."""

from __future__ import annotations

import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_REPO_ROOT = _API_ROOT.parent


def _load_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


def main() -> int:
    _load_env()
    from config.runtime import env_str
    from shared.backlog_orchestration import BacklogRunProfile, apply_sprint_base, sprint_gpu_only
    from shared.services.llm_service import LLMService, pop_llm_execution_lane, push_llm_execution_lane
    from shared.services.ollama_model_caller import OllamaModelCaller
    from shared.services.ollama_model_policy import InvocationKind

    profile = BacklogRunProfile.from_env()
    apply_sprint_base(profile)

    print("=== GPU sprint routing verification ===")
    print(f"BACKLOG_SPRINT_GPU_ONLY: {sprint_gpu_only()}")
    print(f"BULK_DUAL_LANE_CATCHUP: {env_str('BULK_DUAL_LANE_CATCHUP', '(unset)')}")
    print(f"OLLAMA_GPU_HOST: {env_str('OLLAMA_GPU_HOST')}")
    print(f"OLLAMA_MODEL_EXTRACTION: {env_str('OLLAMA_MODEL_EXTRACTION')}")
    print(f"OLLAMA_GPU_CONCURRENCY: {env_str('OLLAMA_GPU_CONCURRENCY')}")

    svc = LLMService()
    token = push_llm_execution_lane("gpu")
    try:
        lane = OllamaModelCaller._execution_lane_for_kind(InvocationKind.STRUCTURED_EXTRACTION)
        url, _, key = svc._resolve_execution_target(execution_lane=lane)
        print(f"STRUCTURED_EXTRACTION -> lane={lane} key={key} url={url}")
    finally:
        pop_llm_execution_lane(token)

    pop = profile.gpu_host.rstrip("/")
    ok = True
    if lane != "gpu":
        print("FAIL: expected gpu lane")
        ok = False
    if pop not in url:
        print(f"FAIL: expected PopOS host {pop} in {url}")
        ok = False
    if env_str("BULK_DUAL_LANE_CATCHUP", "").lower() in ("1", "true", "yes"):
        print("FAIL: dual lane should be off for GPU sprint")
        ok = False

    try:
        import urllib.request

        with urllib.request.urlopen(f"{pop}/api/tags", timeout=5) as resp:
            import json

            tags = json.loads(resp.read().decode())
        names = {m.get("name", "") for m in tags.get("models") or []}
        for model in (profile.gpu_model_extraction, profile.gpu_model_fast):
            if model not in names and f"{model}:latest" not in names:
                print(f"WARN: {model} not on PopOS — pull before sprint")
    except Exception as e:
        print(f"FAIL: PopOS unreachable: {e}")
        ok = False

    if ok:
        print("OK: GPU-only sprint routing configured")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
