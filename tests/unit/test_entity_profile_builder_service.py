"""Unit tests for entity profile builder scalability (hybrid fast/full, parallel, drain)."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_EPBS = Path(__file__).resolve().parents[2] / "api" / "services" / "entity_profile_builder_service.py"
_spec = importlib.util.spec_from_file_location("entity_profile_builder_service", _EPBS)
assert _spec and _spec.loader
epb = importlib.util.module_from_spec(_spec)
sys.modules["entity_profile_builder_service"] = epb
_spec.loader.exec_module(epb)

ProfileBuilderBatchResult = epb.ProfileBuilderBatchResult
ProfileBuildResult = epb.ProfileBuildResult
_sections_empty = epb._sections_empty
build_profile_sections = epb.build_profile_sections
drain_entity_profile_build = epb.drain_entity_profile_build
entity_profile_build_drain_enabled = epb.entity_profile_build_drain_enabled
get_entity_profile_build_parallel = epb.get_entity_profile_build_parallel
run_profile_builder_batch = epb.run_profile_builder_batch


def test_sections_empty():
    assert _sections_empty(None) is True
    assert _sections_empty([]) is True
    assert _sections_empty("[]") is True
    assert _sections_empty([{"title": "Summary"}]) is False


def test_fast_path_single_llm_call(monkeypatch):
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_FAST_CONTEXT_LIMIT", "10")
    contexts = [(i, f"Title {i}", f"Content {i}") for i in range(5)]

    llm_calls: list[str] = []

    async def _fake_ollama(_model, prompt):
        llm_calls.append(prompt)
        return '{"sections": [{"title": "Summary", "content": "ok"}], "relationships": []}'

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.side_effect = [
        (1, "legal", "Acme Corp", "organization", None),
    ]

    with (
        patch.object(epb, "get_db_connection", return_value=mock_conn),
        patch.object(
            epb,
            "get_contexts_for_entity_profile",
            return_value=contexts,
        ),
        patch.object(epb, "LLMService") as mock_llm_cls,
    ):
        mock_llm_cls.return_value._call_ollama = AsyncMock(side_effect=_fake_ollama)
        result = asyncio.run(build_profile_sections(1))

    assert result.success is True
    assert result.tier == "fast"
    assert result.contexts_used == 5
    assert len(llm_calls) == 1
    assert "Summarize in 2-4 sentences" not in llm_calls[0]


def test_full_path_iterative_when_many_contexts(monkeypatch):
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_ITERATIVE_MIN_CONTEXTS", "30")
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_FULL_CONTEXT_LIMIT", "75")
    contexts = [(i, f"Title {i}", f"Content {i}") for i in range(40)]
    llm_calls: list[str] = []

    async def _fake_ollama(_model, prompt):
        llm_calls.append(prompt)
        if "Summarize in 2-4 sentences" in prompt:
            return "Chunk summary about the entity."
        return '{"sections": [{"title": "Summary", "content": "ok"}], "relationships": []}'

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchone.side_effect = [
        (
            2,
            "legal",
            "Jane Doe",
            "person",
            [{"title": "Summary", "content": "existing"}],
        ),
    ]

    with (
        patch.object(epb, "get_db_connection", return_value=mock_conn),
        patch.object(
            epb,
            "get_contexts_for_entity_profile",
            return_value=contexts,
        ),
        patch.object(epb, "LLMService") as mock_llm_cls,
    ):
        mock_llm_cls.return_value._call_ollama = AsyncMock(side_effect=_fake_ollama)
        result = asyncio.run(build_profile_sections(2))

    assert result.success is True
    assert result.tier == "full"
    assert result.contexts_used == 40
    assert len(llm_calls) > 1
    assert any("Summarize in 2-4 sentences" in p for p in llm_calls)


def test_parallel_batch_limits_concurrency(monkeypatch):
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_PARALLEL", "2")
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def _slow_build(_eid: int) -> ProfileBuildResult:
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1
        return ProfileBuildResult(True, tier="fast", contexts_used=1)

    with (
        patch.object(
            epb,
            "get_entity_profile_ids_to_build",
            return_value=[1, 2, 3, 4],
        ),
        patch.object(
            epb,
            "build_profile_sections",
            side_effect=_slow_build,
        ),
    ):
        result = asyncio.run(run_profile_builder_batch(limit=4))

    assert result.updated == 4
    assert result.fast_updated == 4
    assert peak <= 2


def test_drain_stops_when_batch_updates_zero():
    batch_results = [
        ProfileBuilderBatchResult(updated=2, attempted=2, fast_updated=2),
        ProfileBuilderBatchResult(updated=0, attempted=2),
    ]
    call_count = 0

    async def _fake_batch(limit: int = 15):
        nonlocal call_count
        idx = min(call_count, len(batch_results) - 1)
        call_count += 1
        return batch_results[idx]

    expired_checks = 0

    class _Budget:
        def __init__(self, _sec: int) -> None:
            pass

        def expired(self) -> bool:
            nonlocal expired_checks
            expired_checks += 1
            return expired_checks > 10

    with (
        patch.object(epb, "run_profile_builder_batch", side_effect=_fake_batch),
        patch("shared.pipeline_batch_drain.RunBudget", _Budget),
        patch("shared.pipeline_batch_drain.DrainStallTracker") as mock_stall_cls,
    ):
        mock_stall_cls.return_value.record_round.return_value = False
        stats = asyncio.run(drain_entity_profile_build(budget_seconds=600, batch_limit=5))

    assert stats["profiles_updated"] == 2
    assert stats["rounds"] == 2
    assert call_count == 2


def test_entity_profile_build_drain_enabled_default(monkeypatch):
    monkeypatch.delenv("ENTITY_PROFILE_BUILD_DRAIN", raising=False)
    assert entity_profile_build_drain_enabled() is True
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_DRAIN", "false")
    assert entity_profile_build_drain_enabled() is False


def test_get_entity_profile_build_parallel_default(monkeypatch):
    monkeypatch.delenv("ENTITY_PROFILE_BUILD_PARALLEL", raising=False)
    assert get_entity_profile_build_parallel() == 3
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_PARALLEL", "5")
    assert get_entity_profile_build_parallel() == 5
