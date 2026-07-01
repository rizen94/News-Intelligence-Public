#!/usr/bin/env python3
from __future__ import annotations
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str
"""Verify dual-lane bulk catch-up: PopOS GPU + Widow local Ollama."""


import json
import os
import sys
import urllib.request
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


def _ollama_ps(url: str) -> dict:
    with urllib.request.urlopen(f"{url.rstrip('/')}/api/ps", timeout=5) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    _load_env()
    from shared.bulk_catchup_llm_routing import (
        assign_extraction_lane,
        bulk_dual_lane_catchup_active,
        parse_lane_parallel,
    )
    from shared.services.llm_service import LLMService, pop_llm_execution_lane, push_llm_execution_lane
    from shared.services.ollama_model_caller import OllamaModelCaller
    from shared.services.ollama_model_policy import InvocationKind

    pop = env_str("OLLAMA_GPU_HOST") or env_str("OLLAMA_POP_OS_HOST", "http://192.168.93.99:11434")
    local = env_str("OLLAMA_CPU_HOST") or env_str("OLLAMA_HOST", "http://localhost:11434")
    dual = bulk_dual_lane_catchup_active()
    gpu_p, cpu_p, dual_parsed = parse_lane_parallel(parallel=int(env_str("BULK_GPU_PARALLEL", "4")))

    print("=== Dual-lane catch-up verification ===")
    print(f"BULK_DUAL_LANE_CATCHUP: {env_str('BULK_DUAL_LANE_CATCHUP', '(unset)')} -> active={dual}")
    print(f"OLLAMA_DUAL_HOST_ROUTING_ENABLED: {env_str('OLLAMA_DUAL_HOST_ROUTING_ENABLED', '(unset)')}")
    print(f"GPU lane (PopOS):  {pop}  parallel={gpu_p}")
    print(f"CPU lane (Widow):  {local}  parallel={cpu_p}")
    print(f"Sample assignment: {[assign_extraction_lane(i, gpu_parallel=gpu_p, cpu_parallel=cpu_p) for i in range(10)]}")

    svc = LLMService()
    for lane in ("gpu", "cpu"):
        token = push_llm_execution_lane(lane)
        try:
            resolved = OllamaModelCaller._execution_lane_for_kind(InvocationKind.STRUCTURED_EXTRACTION)
            url, _, key = svc._resolve_execution_target(execution_lane=resolved)
            print(f"  route lane={lane} -> {key} @ {url}")
        finally:
            pop_llm_execution_lane(token)

    ok = True
    for label, url in (("PopOS", pop), ("Widow", local)):
        try:
            ps = _ollama_ps(url)
            models = ps.get("models") or []
            print(f"\n{label} Ollama ({url}):")
            if models:
                for m in models:
                    vram = m.get("size_vram") or 0
                    print(f"  loaded: {m.get('name')}  vram={vram // 1_000_000}MB")
            else:
                print("  loaded: (idle — no model in VRAM right now)")
        except Exception as e:
            print(f"\n{label} Ollama ({url}): UNREACHABLE — {e}")
            ok = False

    if not dual_parsed:
        print("\nWARN: dual-lane not active — bulk will not split across PopOS + Widow")
        ok = False
    elif ok:
        print("\nOK: dual-lane routing configured; both Ollama endpoints reachable")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
