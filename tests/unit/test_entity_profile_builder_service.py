"""Unit tests for entity profile builder scalability (hybrid fast/full, parallel, drain)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
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
_run_profile_builder_batch_parallel = epb._run_profile_builder_batch_parallel
_parse_batched_response = epb._parse_batched_response
_prepare_profile_data_for_batch = epb._prepare_profile_data_for_batch


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
        result = asyncio.run(_run_profile_builder_batch_parallel(limit=4))

    assert result.updated == 4
    assert result.fast_updated == 4
    assert peak <= 2


def test_batched_path_honors_parallel_chunk_concurrency(monkeypatch):
    """Live batched path must run LLM chunks concurrently when PARALLEL>1."""
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_PARALLEL", "2")
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE", "5")
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def _slow_chunk(chunk, llm, *, on_profile_built, updated_so_far):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1
        return ProfileBuilderBatchResult(
            updated=len(chunk),
            attempted=len(chunk),
            fast_updated=len(chunk),
            contexts_used=len(chunk),
        )

    profile_data = [
        {
            "id": i,
            "name": f"E{i}",
            "etype": "person",
            "combined": "x",
            "is_first_pass": True,
            "contexts_used": 1,
        }
        for i in range(1, 11)
    ]

    with (
        patch.object(epb, "get_entity_profile_ids_to_build", return_value=list(range(1, 11))),
        patch.object(epb, "_prepare_profile_data_for_batch", return_value=profile_data),
        patch.object(epb, "_process_batched_profile_chunk", side_effect=_slow_chunk),
        patch.object(epb, "LLMService"),
    ):
        result = asyncio.run(epb.run_profile_builder_batch_batched(limit=10))

    assert result.updated == 10
    assert peak >= 2
    assert peak <= 2


def test_entity_profile_build_budget_default_900(monkeypatch):
    monkeypatch.delenv("ENTITY_PROFILE_BUILD_RUN_BUDGET_SECONDS", raising=False)
    monkeypatch.delenv("ASSEMBLY_ENTITY_PROFILE_BUILD_CYCLE_BUDGET_SECONDS", raising=False)
    with patch(
        "shared.pipeline_batch_drain.phase_run_budget_seconds",
        return_value=900,
    ):
        assert epb._entity_profile_build_budget_seconds(None) == 900


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


def test_parse_batched_response_array():
    raw = json.dumps(
        [
            {
                "sections": [{"title": "Summary", "content": "A leader in tech."}],
                "relationships": [{"target": "Acme", "relation": "CEO of"}],
            },
            {"sections": [], "relationships": []},
        ]
    )
    results = _parse_batched_response(raw, 2)
    assert results[0] is not None
    assert results[0][0][0]["title"] == "Summary"
    assert results[1] is None


def test_prepare_profile_data_uses_batched_db(monkeypatch):
    monkeypatch.setenv("ENTITY_PROFILE_BUILD_FAST_CONTEXT_LIMIT", "5")
    metadata = {
        1: ("Acme", "organization", None),
        2: ("Jane", "person", [{"title": "Summary", "content": "existing"}]),
    }
    contexts = {
        1: [(10, "T1", "C1")],
        2: [(20, "T2", "C2"), (21, "T3", "C3")],
    }
    with (
        patch.object(epb, "_get_profiles_metadata_batch", return_value=metadata),
        patch.object(epb, "get_contexts_for_entity_profiles_batch", return_value=contexts),
    ):
        data = _prepare_profile_data_for_batch([1, 2])
    assert len(data) == 2
    assert data[0]["name"] == "Acme"
    assert data[0]["is_first_pass"] is True
    assert data[1]["is_first_pass"] is False
