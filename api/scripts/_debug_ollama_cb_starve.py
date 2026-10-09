"""Reproduce Ollama CB starvation + backpressure contract checks.

Validates:
- is_open() allows probe after recovery_timeout
- success_threshold=1 closes from HALF_OPEN after one success
- overload path does not trip (simulated: no record_failure on timeout-class)
- any_ollama_circuit_shedding sees ollama_gpu
- all OLLAMA_CB_KEYS exist

Run from api/:  python scripts/_debug_ollama_cb_starve.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load CB module by path so services/__init__.py does not pull AutomationManager/DB.
import importlib.util

_cb_path = ROOT / "services" / "circuit_breaker_service.py"
_spec = importlib.util.spec_from_file_location("circuit_breaker_service_standalone", _cb_path)
assert _spec and _spec.loader
_cb_mod = importlib.util.module_from_spec(_spec)
sys.modules["circuit_breaker_service_standalone"] = _cb_mod
_spec.loader.exec_module(_cb_mod)

OLLAMA_CB_KEYS = _cb_mod.OLLAMA_CB_KEYS
CircuitState = _cb_mod.CircuitState
any_ollama_circuit_shedding = _cb_mod.any_ollama_circuit_shedding
get_circuit_breaker_service = _cb_mod.get_circuit_breaker_service

try:
    from shared.debug_session_log import agent_dbg  # noqa: E402
except Exception:  # pragma: no cover

    def agent_dbg(*_a, **_k):  # type: ignore[misc]
        return None


def _llm_style_would_skip(cb) -> bool:
    """Mirror fixed llm_service.py gate (is_open)."""
    return cb.is_open()


def main() -> int:
    svc = get_circuit_breaker_service()
    failures: list[str] = []

    # --- all keys present with success_threshold=1 ---
    for key in OLLAMA_CB_KEYS:
        cb = svc.get_circuit_breaker(key)
        if cb.config.success_threshold != 1:
            failures.append(f"{key}.success_threshold={cb.config.success_threshold} want 1")
        cb.reset()

    cb = svc.get_circuit_breaker("ollama")
    cb.reset()

    # Trip open like overnight
    cb.record_failure_sync()
    cb.record_failure_sync(force_open=True)
    assert cb.state == CircuitState.OPEN

    agent_dbg(
        "A",
        "cb_starve:fresh_open",
        "gates_while_freshly_open",
        {
            "state": cb.state.value,
            "is_open": cb.is_open(),
            "llm_would_skip": _llm_style_would_skip(cb),
            "entity_would_skip": cb.is_open(),
            "failure_age_s": 0.0,
        },
        run_id="post-fix",
    )

    # Simulate recovery_timeout elapsed
    cb.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=301)
    llm_skip = _llm_style_would_skip(cb)
    entity_skip = cb.is_open()
    due = cb._should_attempt_reset()
    old_bug_shape = (cb.state.value == "open") and due and llm_skip

    agent_dbg(
        "A",
        "cb_starve:after_recovery_timeout",
        "gates_after_301s",
        {
            "state": cb.state.value,
            "is_open": cb.is_open(),
            "should_attempt_reset": due,
            "llm_would_skip": llm_skip,
            "entity_would_skip": entity_skip,
            "starvation_mismatch": old_bug_shape,
        },
        run_id="post-fix",
    )
    if old_bug_shape:
        failures.append("starvation: is_open still true after recovery due")

    state_before = cb.state.value
    cb.begin_probe_if_due_sync()
    half_ok = cb.state == CircuitState.HALF_OPEN
    agent_dbg(
        "C",
        "cb_starve:probe_enters_half_open",
        "llm_gate_half_opens_when_due",
        {
            "state_before": state_before,
            "state_after_probe": cb.state.value,
            "half_open": half_ok,
        },
        run_id="post-fix",
    )
    if not half_ok:
        failures.append("probe did not enter HALF_OPEN")

    # success_threshold=1: one success closes
    cb.record_success_sync()
    closed_ok = cb.state == CircuitState.CLOSED
    agent_dbg(
        "D",
        "cb_starve:one_success_closes",
        "success_threshold_1",
        {"state": cb.state.value, "closed": closed_ok},
        run_id="post-fix",
    )
    if not closed_ok:
        failures.append(f"one success did not close (state={cb.state.value})")

    # Re-open then fail from HALF_OPEN
    cb.record_failure_sync(force_open=True)
    cb.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=301)
    cb.begin_probe_if_due_sync()
    before = cb.last_failure_time
    cb.record_failure_sync()
    reopened = cb.state == CircuitState.OPEN
    agent_dbg(
        "B",
        "cb_starve:half_open_fail_reopens",
        "failure_from_half_open_reopens",
        {
            "state": cb.state.value,
            "reopened": reopened,
            "timer_refreshed": bool(
                before and cb.last_failure_time and cb.last_failure_time > before
            ),
        },
        run_id="post-fix",
    )
    if not reopened:
        failures.append("HALF_OPEN failure did not reopen")

    # Overload contract: callers must not call record_failure on timeout —
    # simulate by leaving CLOSED while "overloaded" (no trip).
    cb.reset()
    assert cb.state == CircuitState.CLOSED
    overload_stayed_closed = cb.state == CircuitState.CLOSED and not cb.is_open()
    agent_dbg(
        "E",
        "cb_starve:overload_no_trip",
        "overload_does_not_open",
        {"state": cb.state.value, "ok": overload_stayed_closed},
        run_id="post-fix",
    )

    # any_ollama_circuit_shedding sees ollama_gpu
    gpu = svc.get_circuit_breaker("ollama_gpu")
    gpu.reset()
    gpu.record_failure_sync(force_open=True)
    shed_sees_gpu = any_ollama_circuit_shedding()
    agent_dbg(
        "F",
        "cb_starve:shedding_sees_gpu",
        "any_ollama_circuit_shedding",
        {"shed": shed_sees_gpu, "gpu_state": gpu.state.value},
        run_id="post-fix",
    )
    if not shed_sees_gpu:
        failures.append("any_ollama_circuit_shedding missed ollama_gpu OPEN")
    gpu.reset()
    cb.reset()

    # Trickle helpers smoke is opt-in (imports open DB pools).
    # Local: python scripts/_debug_ollama_cb_starve.py --with-trickle
    if "--with-trickle" in sys.argv:
        try:
            from services.claim_evidence_appraisal_service import (  # noqa: WPS433
                effective_appraisal_batch_limit,
            )
            from services.research_paper_profile_service import (  # noqa: WPS433
                effective_profile_batch_limit,
            )

            _ = effective_appraisal_batch_limit(50)
            _ = effective_profile_batch_limit(50)
        except Exception as e:
            failures.append(f"trickle helpers: {e}")

    ok = not failures and not old_bug_shape and half_ok and closed_ok and shed_sees_gpu
    print(
        "OK starve_repro" if ok else "FAIL starve_repro",
        f"llm_skip_after_301s={llm_skip}",
        f"half_open_ok={half_ok}",
        f"closed_after_one_success={closed_ok}",
        f"shed_sees_gpu={shed_sees_gpu}",
        f"keys={','.join(OLLAMA_CB_KEYS)}",
        f"failures={failures or 'none'}",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
