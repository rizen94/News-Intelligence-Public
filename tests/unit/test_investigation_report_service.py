"""Unit tests for investigation dossier prompt bounding / fail-fast / async + timeouts."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
_SVC = _ROOT / "api" / "services" / "investigation_report_service.py"
_MAIN = _ROOT / "api" / "main.py"


def _load_investigation_report_service():
    sys.modules.setdefault("shared.database.connection", MagicMock())
    llm_mod = ModuleType("shared.services.llm_service")

    class _ModelType:
        LLAMA_8B = "llama_8b"

    class _LLMService:
        async def _call_ollama(self, *a, **k):
            return "ok"

        async def close(self):
            return None

    llm_mod.LLMService = _LLMService
    llm_mod.ModelType = _ModelType
    sys.modules["shared.services.llm_service"] = llm_mod

    rt = ModuleType("config.runtime")
    rt.env_int = lambda _k, default=0: int(default)
    sys.modules["config.runtime"] = rt

    name = "investigation_report_service_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SVC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_resolve_request_timeout():
    """Extract resolve_request_timeout_seconds from main.py without importing FastAPI app."""
    src = _MAIN.read_text(encoding="utf-8")
    # Isolate the pure helper + REQUEST_TIMEOUT_SECONDS default for exec.
    start = src.index("REQUEST_TIMEOUT_SECONDS = 30")
    end = src.index("\ndef _request_timeout_seconds(")
    blob = src[start:end]
    ns: dict = {}
    exec(blob, ns)  # noqa: S102 — unit test loads local helper source
    return ns["resolve_request_timeout_seconds"], ns["REQUEST_TIMEOUT_SECONDS"]


irs = _load_investigation_report_service()
resolve_request_timeout_seconds, REQUEST_TIMEOUT_SECONDS = _load_resolve_request_timeout()


def test_select_contexts_prefers_newest():
    contexts = {
        1: {"title": "old", "created_at": "2026-01-01T00:00:00"},
        2: {"title": "mid", "created_at": "2026-06-01T00:00:00"},
        3: {"title": "new", "created_at": "2026-09-01T00:00:00"},
    }
    selected = irs._select_contexts_for_prompt(contexts, max_n=2)
    assert set(selected.keys()) == {2, 3}
    assert 1 not in selected


def test_select_contexts_noop_when_under_limit():
    contexts = {10: {"created_at": "2026-01-01T00:00:00"}}
    assert irs._select_contexts_for_prompt(contexts, max_n=5) is contexts


def test_generate_fails_fast_without_evidence():
    async def _run():
        with patch.object(
            irs,
            "_gather_event_data",
            return_value={
                "event_name": "Empty container",
                "event_type": "container_index",
                "geographic_scope": None,
                "start_date": "2026-08-18",
                "end_date": None,
                "chronicles": [],
                "contexts": {},
                "context_ids": [],
            },
        ):
            return await irs.generate_investigation_report(3011)

    result = asyncio.run(_run())
    assert result["success"] is False
    assert "chronicles" in (result.get("error") or "").lower()


def test_assess_context_coherence_refuses_kitchen_sink():
    ok, reason, meta = irs.assess_context_coherence(
        "CARD:Epi BioBERT AMR literature mining",
        {
            1: {"title": "SARS-CoV-2 wastewater surveillance in Boston"},
            2: {"title": "GBS ST1010 outbreak genomics"},
            3: {"title": "CsgA peptide heliomicin binding"},
            4: {"title": "Unrelated oncology biomarker panel"},
        },
    )
    assert ok is False
    assert "mixed" in reason.lower() or "overlaps" in reason.lower()
    assert meta["hit_count"] == 0


def test_assess_context_coherence_passes_aligned_titles():
    ok, reason, meta = irs.assess_context_coherence(
        "CARD:Epi BioBERT AMR literature mining",
        {
            1: {"title": "BioBERT fine-tuning for AMR gene extraction"},
            2: {"title": "CARD database updates for resistance literature"},
            3: {"title": "AMR text mining with BioBERT embeddings"},
            4: {"title": "Literature mining pipeline for CARD:Epi"},
        },
    )
    assert ok is True
    assert meta["hit_count"] >= 3


def test_generate_exposes_context_cap_counts():
    async def _run():
        contexts = {
            i: {
                "title": f"BioBERT AMR paper {i}",
                "created_at": f"2026-09-{i:02d}T00:00:00",
                "content": "x",
            }
            for i in range(1, 6)
        }
        with patch.object(
            irs,
            "_gather_event_data",
            return_value={
                "event_name": "BioBERT AMR literature mining",
                "event_type": "other",
                "geographic_scope": None,
                "start_date": "2026-08-18",
                "end_date": None,
                "chronicles": [{"update_date": "2026-09-01", "developments": [], "analysis": {}}],
                "contexts": contexts,
                "contexts_total": 20,
                "context_ids": list(contexts.keys()),
            },
        ):
            with patch.object(irs, "_build_cross_domain_link_block", return_value=""):
                return await irs.generate_investigation_report(3011)

    result = asyncio.run(_run())
    assert result["success"] is True
    assert result["contexts_total"] == 20
    assert result["contexts_included"] == result["context_count"]
    assert result["contexts_included"] <= 12
    assert result.get("status") == "ready"


def test_should_generate_async_threshold():
    threshold = irs.async_report_threshold()
    assert irs.should_generate_async(threshold) is False
    assert irs.should_generate_async(threshold + 1) is True
    assert irs.should_generate_async(0, force=True) is True
    assert irs.should_generate_async(None) is False


def test_is_report_job_active_states():
    assert irs.is_report_job_active(None) is False
    assert irs.is_report_job_active({"status": "ready"}) is False
    assert irs.is_report_job_active({"status": "failed"}) is False
    assert irs.is_report_job_active({"status": "queued"}) is True
    assert irs.is_report_job_active(
        {
            "status": "running",
            "updated_at": "2099-01-01T00:00:00+00:00",
        }
    ) is True


def test_enqueue_returns_queued_without_llm():
    created: list[asyncio.Task] = []

    def _fake_create_task(coro, **kwargs):
        # Drain the coroutine so we don't leak "never awaited" warnings.
        async def _noop():
            return None

        # Close the real coroutine (would call LLM / DB) and schedule a noop.
        if asyncio.iscoroutine(coro):
            coro.close()
        task = asyncio.get_event_loop().create_task(_noop())
        created.append(task)
        return task

    async def _run():
        with patch.object(irs, "get_investigation_report_job", return_value=None):
            with patch.object(irs, "_upsert_report_job", return_value=True) as upsert:
                with patch.object(irs.asyncio, "create_task", side_effect=_fake_create_task):
                    payload = irs.enqueue_investigation_report(42, contexts_total=99)
                    assert upsert.called
                    assert payload["success"] is True
                    assert payload["status"] == "queued"
                    assert payload["async"] is True
                    assert payload["contexts_total"] == 99
                    assert payload["already_queued"] is False
                    # Let the noop task finish.
                    if created:
                        await created[0]

    asyncio.run(_run())


def test_enqueue_dedupes_active_job():
    async def _run():
        existing = {
            "status": "running",
            "contexts_total": 50,
            "updated_at": "2099-01-01T00:00:00+00:00",
            "requested_at": "2099-01-01T00:00:00+00:00",
        }
        fake_task = MagicMock()
        fake_task.done.return_value = False
        irs._JOB_IN_FLIGHT[77] = fake_task
        try:
            with patch.object(irs, "get_investigation_report_job", return_value=existing):
                with patch.object(irs.asyncio, "create_task") as create_task:
                    payload = irs.enqueue_investigation_report(77, contexts_total=50)
                    create_task.assert_not_called()
                    assert payload["already_queued"] is True
                    assert payload["status"] == "running"
        finally:
            irs._JOB_IN_FLIGHT.pop(77, None)

    asyncio.run(_run())


def test_request_timeout_budget_post_vs_get_report():
    path = "/api/tracked_events/2532/report"
    assert resolve_request_timeout_seconds(path, method="POST") == 180.0
    assert resolve_request_timeout_seconds(path, method="GET") == float(
        REQUEST_TIMEOUT_SECONDS
    )
    assert resolve_request_timeout_seconds(path, method="get") == float(
        REQUEST_TIMEOUT_SECONDS
    )
    # Unrelated path still default.
    assert resolve_request_timeout_seconds("/api/health", method="GET") == float(
        REQUEST_TIMEOUT_SECONDS
    )


def test_request_timeout_budget_still_extends_other_llm_routes():
    assert (
        resolve_request_timeout_seconds("/api/research/assemble", method="POST") == 180.0
    )
    assert (
        resolve_request_timeout_seconds(
            "/api/editorial/packages/1/research/run", method="POST"
        )
        == 180.0
    )
