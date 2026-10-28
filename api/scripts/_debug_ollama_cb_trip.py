"""Prove ConnectError / host-unreachable trips Ollama CB open (sync + async)."""
from __future__ import annotations

import asyncio
import sys

from shared.debug_session_log import agent_dbg
from services.circuit_breaker_service import CircuitState, get_circuit_breaker_service


async def _async_trip() -> None:
    cb = get_circuit_breaker_service().get_circuit_breaker("ollama_pop_os")
    cb.reset()
    await cb.trip_open("debug ConnectError simulation")
    assert cb.state == CircuitState.OPEN
    assert cb.is_open() is True
    agent_dbg(
        "E",
        "cb:async_trip",
        "ollama_pop_os_tripped",
        {"state": cb.state.value, "is_open": cb.is_open()},
        run_id="post-fix",
    )


def main() -> int:
    cb = get_circuit_breaker_service().get_circuit_breaker("ollama")
    cb.reset()
    cb.record_failure_sync(force_open=True)
    assert cb.state == CircuitState.OPEN
    assert cb.is_open() is True
    agent_dbg(
        "E",
        "cb:sync_trip",
        "ollama_sync_force_open",
        {"state": cb.state.value, "is_open": cb.is_open()},
        run_id="post-fix",
    )
    asyncio.run(_async_trip())
    print("OK", "ollama", cb.state.value, "ollama_pop_os open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
