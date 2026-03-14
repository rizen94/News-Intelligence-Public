"""
Finance orchestrator — central controller for finance domain workflow.
Holds references to all infrastructure. Plans, executes, evaluates, decides.
"""

import asyncio
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, date
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from domains.finance.orchestrator_logger import log_event, log_queue_decision, TASK_ACCEPTED, TASK_PLANNED, WORKER_DISPATCHED, WORKER_COMPLETED, WORKER_FAILED, EVAL_PASSED, EVAL_FAILED, TASK_COMPLETED, TASK_FAILED, SOURCE_SKIPPED
from shared.logging.trace_logger import span_context
from shared.logging.decision_logger import log_decision, log_decision_outcome
from domains.finance.orchestrator_utils import normalize_to_data_result
from domains.finance.orchestrator_types import (
    Task,
    TaskContext,
    TaskResult,
    TaskStatus,
    TaskType,
    TaskPriority,
    ResultStatus,
    RefreshSummary,
    EvidenceIndexEntry,
    VerificationResult,
    ClaimCheck,
    ClaimVerdict,
    QualityCriteria,
)


def _status_to_phase(status: TaskStatus, task_type: TaskType) -> str:
    """Map TaskStatus to frontend phase for progress stepper."""
    if status == TaskStatus.planning:
        return "planning"
    if status == TaskStatus.executing:
        return "synthesizing" if task_type == TaskType.analysis else "fetching"
    if status == TaskStatus.evaluating:
        return "verifying"
    if status == TaskStatus.revising:
        return "revising"
    if status == TaskStatus.complete:
        return "complete"
    if status == TaskStatus.failed:
        return "failed"
    return "queued"


def _default_quality_criteria() -> QualityCriteria:
    return QualityCriteria(
        min_sources=1,
        min_evidence_chunks=1,
        require_stat_validation=False,
        max_unsupported_claims=5,
        max_fabricated_claims=0,
    )


class FinanceOrchestrator:
    """
    Central controller for finance domain. Owns task ordering, iteration, quality.
    Routes validate input, submit tasks, return what the orchestrator delivers.
    """

    def __init__(
        self,
        *,
        source_loader: Any = None,
        market_data_store: Any = None,
        vector_store: Any = None,
        evidence_ledger: Any = None,
        embedding_module: Any = None,
        stats_module: Any = None,
        llm_wrapper: Any = None,
        cpu_concurrency: int = 4,
        quality_criteria: QualityCriteria | None = None,
    ):
        self.source_loader = source_loader
        self.market_data_store = market_data_store
        self.vector_store = vector_store
        self.evidence_ledger = evidence_ledger
        self.embedding_module = embedding_module
        self.stats_module = stats_module
        self.llm_wrapper = llm_wrapper
        self.cpu_concurrency = cpu_concurrency
        self.quality_criteria = quality_criteria or _default_quality_criteria()

        self._tasks: dict[str, Task] = {}
        self._task_order: list[str] = []
        self._executor = ThreadPoolExecutor(max_workers=cpu_concurrency, thread_name_prefix="fin_orch")
        self._gpu_lock = asyncio.Lock()
        self._schedule_last_run: dict[str, datetime] = {}
        self._schedule_task: asyncio.Task | None = None
        self._schedule_stop = asyncio.Event()
        # Queue worker: runs user-submitted queued tasks (e.g. analysis with wait=false)
        self._queue_task: asyncio.Task | None = None
        self._queue_stop = asyncio.Event()
        # Stale data check: (timestamp, evidence_index) per topic; reused if within threshold
        self._evidence_cache: dict[str, tuple[datetime, list[Any]]] = {}
        self._evidence_cache_ttl_seconds = 3600  # 1 hour

        logger.info(
            "FinanceOrchestrator initialized: sources=%s",
            self.source_loader is not None,
        )

    async def run_task(self, task_id: str) -> TaskResult | None:
        """
        Execute a queued task to completion. Async — runs sync workers in executor.
        Returns TaskResult when done. Caller should await this after submit_task.
        """
        task = self._tasks.get(task_id)
        if not task:
            return None
        if task.status != TaskStatus.queued:
            return self.get_task_result(task_id)

        loop = asyncio.get_event_loop()
        try:
            task.update_status(TaskStatus.planning)
            log_event(TASK_PLANNED, task_id, {"type": task.task_type.value})
            logger.info("Task %s: planning", task_id)

            if task.task_type == TaskType.refresh:
                plan = self._plan_refresh(task)
                task.update_status(TaskStatus.executing)
                log_event(WORKER_DISPATCHED, task_id, {"phase": "refresh", "actions": plan.get("actions", [])})
                await self._execute_refresh(task, plan)
                task.update_status(TaskStatus.evaluating)
                met = self._evaluate_refresh(task)
                summary = task.context.fetched_data.get("refresh_summary")
                any_succeeded = summary and any(s.get("success") for s in summary.sources.values())
                if met:
                    log_event(EVAL_PASSED, task_id, {"phase": "refresh"})
                    task.update_status(TaskStatus.complete)
                elif any_succeeded:
                    log_event(EVAL_FAILED, task_id, {"phase": "refresh", "note": "partial_accepted"})
                    task.update_status(TaskStatus.complete)
                else:
                    log_event(EVAL_FAILED, task_id, {"phase": "refresh", "note": "all_sources_failed"})
                    task.update_status(TaskStatus.failed)
                log_event(WORKER_COMPLETED, task_id, {"phase": "refresh"})
                self._build_evidence_index(task)
            elif task.task_type == TaskType.ingest:
                task.update_status(TaskStatus.executing)
                log_event(WORKER_DISPATCHED, task_id, {"phase": "ingest"})
                await self._execute_ingest(task)
                self._build_evidence_index(task)
                log_event(WORKER_COMPLETED, task_id, {"phase": "ingest"})
                task.update_status(TaskStatus.complete)
            elif task.task_type == TaskType.analysis:
                plan = self._plan_analysis(task)
                while task.current_iteration < task.iteration_budget:
                    task.update_status(TaskStatus.executing)
                    log_event(WORKER_DISPATCHED, task_id, {"phase": "analysis", "iteration": task.current_iteration + 1})
                    is_revision = task.current_iteration > 0
                    with span_context(task_id, "analysis" + ("_revision" if is_revision else ""), span_type="phase"):
                        await self._execute_analysis(task, plan, is_revision=is_revision)
                    task.update_status(TaskStatus.evaluating)
                    vr = self._extract_and_verify_claims(task)
                    task.context.verification_result = vr
                    passed = self._evaluate_analysis(task)
                    dec_id = log_decision(
                        task_id=task_id,
                        decision_point="eval_gate",
                        current_phase="analysis",
                        chosen_option="accept" if passed else "revise",
                        rationale="Verification passed" if passed else f"Unsupported/fabricated: {vr.unsupported}/{vr.fabricated}",
                        available_options=["accept", "revise"],
                        iterations_so_far=task.current_iteration + 1,
                        eval_score=vr.verified / max(vr.total_claims, 1) if vr else 0,
                        eval_threshold=0.75,
                        unsupported=vr.unsupported if vr else 0,
                        fabricated=vr.fabricated if vr else 0,
                    )
                    if passed:
                        log_decision_outcome(dec_id, "success")
                        log_event(EVAL_PASSED, task_id, {"phase": "analysis", "iteration": task.current_iteration + 1})
                        task.update_status(TaskStatus.complete)
                        break
                    if task.current_iteration + 1 >= task.iteration_budget:
                        log_decision_outcome(dec_id, "partial")
                        task.update_status(TaskStatus.complete)
                        task.context.revision_notes.append("Iteration budget exhausted")
                        log_event(EVAL_FAILED, task_id, {"phase": "analysis", "note": "budget_exhausted"})
                        break
                    task.current_iteration += 1
                    task.update_status(TaskStatus.revising)
                    self._build_revision_prompt(task)
                log_event(WORKER_COMPLETED, task_id, {"phase": "analysis"})
            else:
                logger.warning("Task %s: unsupported type %s", task_id, task.task_type.value)
                log_event(TASK_FAILED, task_id, {"reason": "unsupported_type"})
                task.update_status(TaskStatus.failed)
        except Exception as e:
            logger.exception("Task %s failed: %s", task_id, e)
            log_event(TASK_FAILED, task_id, {"error": str(e)}, level="error")
            task.update_status(TaskStatus.failed)
            task.context.revision_notes.append(str(e))
        finally:
            task.updated_at = datetime.now(timezone.utc)

        tr = self._build_task_result(task)
        if tr and task.status == TaskStatus.complete:
            log_event(TASK_COMPLETED, task_id, {"duration_ms": tr.duration_ms})
        return tr

    def _plan_refresh(self, task: Task) -> dict[str, Any]:
        """Determine which sources to fetch for topic. Returns plan dict."""
        topic = (task.parameters.get("topic") or "gold").lower()
        start = task.parameters.get("start_date") or task.parameters.get("start")
        end = task.parameters.get("end_date") or task.parameters.get("end")
        if topic == "all":
            return {
                "actions": ["gold", "edgar"],
                "start": start,
                "end": end,
                "filings_per_company": task.parameters.get("filings_per_company", 1),
            }
        if topic in ("gold", "silver", "platinum"):
            return {"actions": [topic], "start": start, "end": end}
        if topic == "edgar":
            return {"actions": ["edgar"], "filings_per_company": task.parameters.get("filings_per_company", 1)}
        if topic == "fred":
            symbol = task.parameters.get("symbol")
            return {"actions": ["fred"], "symbol": symbol, "start": start, "end": end}
        return {"actions": ["gold"], "start": start, "end": end}

    async def _execute_refresh(self, task: Task, plan: dict[str, Any]) -> None:
        """Run refresh actions in parallel via executor."""
        actions = plan.get("actions", [])
        results: dict[str, Any] = {}

        async def _run_gold() -> dict[str, Any]:
            def _sync():
                from domains.finance.gold_amalgamator import fetch_all
                start = plan.get("start")
                end = plan.get("end")
                out = fetch_all(start=start, end=end, store=True)
                return {"results": out, "report_id": f"gold_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"}
            return await asyncio.get_event_loop().run_in_executor(self._executor, _sync)

        async def _run_commodity(commodity: str) -> dict[str, Any]:
            def _sync():
                from domains.finance.commodity_fetcher import fetch_commodity
                start = plan.get("start")
                end = plan.get("end")
                out = fetch_commodity(topic=commodity, start=start, end=end, store=True)
                return {"results": out, "report_id": f"{commodity}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"}
            return await asyncio.get_event_loop().run_in_executor(self._executor, _sync)

        async def _run_edgar() -> dict[str, Any]:
            def _sync():
                from domains.finance.data_sources.edgar import ingest_edgar_10ks
                filings = plan.get("filings_per_company", 1)
                count, chunk_ids = ingest_edgar_10ks(filings_per_company=filings, record_ledger=True)
                return {"chunks_embedded": count, "chunk_ids": chunk_ids}
            return await asyncio.get_event_loop().run_in_executor(self._executor, _sync)

        async def _run_fred() -> dict[str, Any]:
            def _sync():
                from domains.finance.data_sources import get_source
                from domains.finance.data_sources.fred import get_client
                client = get_source("fred") or get_client()
                symbol = plan.get("symbol") or "IQ12260"
                r = client.fetch_observations(symbol, start=plan.get("start"), end=plan.get("end"), store=True)
                if r.success and r.data:
                    return {"symbol": symbol, "observations": r.data, "success": True}
                return {"symbol": symbol, "observations": [], "success": False, "error": r.error}
            return await asyncio.get_event_loop().run_in_executor(self._executor, _sync)

        tasks_to_run = []
        if "gold" in actions:
            tasks_to_run.append(("gold", _run_gold()))
        for commodity in ("silver", "platinum"):
            if commodity in actions:
                tasks_to_run.append((commodity, _run_commodity(commodity)))
        if "edgar" in actions:
            tasks_to_run.append(("edgar", _run_edgar()))
        if "fred" in actions:
            tasks_to_run.append(("fred", _run_fred()))

        for name, coro in tasks_to_run:
            try:
                results[name] = await coro
                self._ledger_record(task, name, "success")
            except Exception as e:
                err_msg = str(e)
                dr = normalize_to_data_result(e)
                task.context.errors.append({"source": name, "error": dr.error, "error_type": dr.error_type})
                is_404 = "404" in err_msg
                logger.warning("Refresh %s failed: %s", name, e)
                results[name] = {"success": False, "error": err_msg}
                self._ledger_record(task, name, "error", error=err_msg)
                if is_404:
                    log_event(SOURCE_SKIPPED, task.task_id, {"source": name, "reason": "404"})
                else:
                    log_event(WORKER_FAILED, task.task_id, {"source": name, "error": err_msg})

        # Store in context for TaskResult
        task.context.fetched_data["refresh_results"] = results

    def _evaluate_refresh(self, task: Task) -> bool:
        """Check if refresh met quality criteria. Build RefreshSummary into context."""
        results = task.context.fetched_data.get("refresh_results") or {}
        sources_summary: dict[str, dict[str, Any]] = {}
        total_obs = 0
        chunks_embedded = 0
        chunk_ids: list[str] = []

        for name, data in results.items():
            if name == "gold" or name in ("silver", "platinum"):
                r = data.get("results") or {}
                for sid, obs_list in r.items():
                    count = len(obs_list) if isinstance(obs_list, list) else 0
                    total_obs += count
                    sources_summary[sid] = {"success": count > 0, "count": count}
            elif name == "edgar":
                chunks_embedded = data.get("chunks_embedded", 0)
                chunk_ids = data.get("chunk_ids", [])
                sources_summary["edgar"] = {"success": chunks_embedded > 0, "chunks_embedded": chunks_embedded}
            elif name == "fred":
                obs_list = data.get("observations") or []
                count = len(obs_list) if isinstance(obs_list, list) else 0
                total_obs += count
                sources_summary["fred"] = {"success": count > 0, "count": count, "error": data.get("error")}

        task.context.fetched_data["refresh_summary"] = RefreshSummary(
            sources=sources_summary,
            total_observations=total_obs,
            chunks_embedded=chunks_embedded,
            chunk_ids=chunk_ids,
        )
        met = len([s for s in sources_summary.values() if s.get("success")]) >= self.quality_criteria.min_sources
        return met

    def _build_evidence_index(self, task: Task) -> list[EvidenceIndexEntry]:
        """
        Extract verifiable facts from refresh_results into EvidenceIndexEntry list.
        Gold/FRED: each observation; EDGAR: summary entry. Stored in task.context.
        """
        results = task.context.fetched_data.get("refresh_results") or {}
        entries: list[EvidenceIndexEntry] = []
        ref_counter = [0]

        def _add(source: str, identifier: str, d: str, value: float | str, unit: str, context: str = ""):
            ref_counter[0] += 1
            ref_id = f"REF-{ref_counter[0]:03d}"
            try:
                dt = datetime.fromisoformat(d.replace("Z", "+00:00")).date() if d else date.today()
            except (ValueError, TypeError):
                dt = date.today()
            entries.append(EvidenceIndexEntry(
                ref_id=ref_id, source=source, identifier=identifier,
                date=dt, value=value, unit=unit, context=context,
            ))

        # Gold: observations from each source
        gold_data = results.get("gold", {}).get("results") or {}
        max_per_source = 100
        for metal in ("silver", "platinum"):
            metal_raw = results.get(metal) or {}
            metal_data = metal_raw.get("results") if isinstance(metal_raw.get("results"), dict) else metal_raw
            if isinstance(metal_data, dict):
                for sid, obs_list in metal_data.items():
                    if not isinstance(obs_list, list):
                        continue
                    for o in obs_list[:max_per_source]:
                        d = o.get("date", "")
                        v = o.get("value")
                        unit = o.get("unit", "USD/toz")
                        if d and v is not None:
                            _add(metal, sid, d, float(v), unit, "{} price {}".format(metal.capitalize(), unit))
        for sid, obs_list in gold_data.items():
            if not isinstance(obs_list, list):
                continue
            for o in obs_list[:max_per_source]:
                d = o.get("date", "")
                v = o.get("value")
                unit = o.get("unit", "USD/oz")
                if d and v is not None:
                    _add("gold", sid, d, float(v), unit, f"Gold price {unit}")

        # FRED: observations
        fred_data = results.get("fred", {})
        fred_obs = fred_data.get("observations") or []
        symbol = fred_data.get("symbol", "fred")
        for o in fred_obs[:max_per_source]:
            d = o.get("date", "")
            v = o.get("value")
            if d and v is not None:
                _add("fred", symbol, d, float(v), "index", f"FRED {symbol}")

        # EDGAR: summary (from refresh or standalone ingest)
        edgar_data = results.get("edgar", {})
        ingest_data = task.context.fetched_data.get("ingest_results") or {}
        chunks = edgar_data.get("chunks_embedded", 0) or ingest_data.get("chunks_embedded", 0)
        if chunks > 0:
            _add("edgar_10k", "mining_companies", str(date.today()), chunks, "chunks", "EDGAR 10-K sections ingested")

        task.context.evidence_index = entries
        return entries

    def _append_rss_and_historic_evidence(self, task: Task) -> None:
        """
        Append RSS snippets and historic context events to task.context.evidence_index
        so they appear in the Evidence list on the result page (additional sources).
        REF-ids continue from current max (e.g. REF-074, REF-075, ...).
        """
        entries = list(task.context.evidence_index or [])
        ref_counter = len(entries)

        def _next_ref() -> str:
            nonlocal ref_counter
            ref_counter += 1
            return f"REF-{ref_counter:03d}"

        def _parse_date(d: Any) -> date:
            if hasattr(d, "date"):
                return d.date() if hasattr(d, "date") else d
            if isinstance(d, str) and len(d) >= 10:
                try:
                    return datetime.fromisoformat(d.replace("Z", "+00:00")).date()
                except (ValueError, TypeError):
                    pass
            return date.today()

        rss_snippets = getattr(task.context, "rss_snippets", None) or []
        for s in rss_snippets[:20]:
            title = (s.get("title") or "News")[:200]
            snippet = (s.get("snippet") or "")[:500]
            pub = s.get("published_at") or ""
            url = s.get("url") or s.get("id") or ""
            entries.append(EvidenceIndexEntry(
                ref_id=_next_ref(),
                source="rss",
                identifier=url[:100] if url else "news",
                date=_parse_date(pub) if pub else date.today(),
                value=title,
                unit="",
                context=snippet,
            ))

        historic_events = getattr(task.context, "historic_context_events", None) or []
        for ev in historic_events[:15]:
            summary = (ev.get("event_summary") or ev.get("summary") or "")[:300]
            date_approx = ev.get("date_approx")
            source_ids = ev.get("source_ids") or []
            agreement = ev.get("agreement_count") or 0
            identifier = ",".join(source_ids)[:80] if source_ids else "historic"
            entries.append(EvidenceIndexEntry(
                ref_id=_next_ref(),
                source="historic",
                identifier=identifier,
                date=_parse_date(date_approx) if date_approx else date.today(),
                value=summary,
                unit=f"{agreement} sources" if agreement else "",
                context=summary,
            ))

        if entries != (task.context.evidence_index or []):
            task.context.evidence_index = entries
            logger.info(
                "Appended RSS/historic evidence: %d RSS, %d historic; total evidence entries %d",
                min(len(rss_snippets), 20),
                min(len(historic_events), 15),
                len(entries),
            )

    def _run_causes_focused_historic_if_needed(
        self, task: Task, query: str, topic: str, start: str, end: str
    ) -> None:
        """
        If the query suggests we care about causes (e.g. price drop/rise, why), run a second
        historic-context search with a causes-focused query and merge the summary into context
        so the LLM can explain why the move happened.
        """
        q = (query or "").lower()
        cause_terms = ("drop", "fall", "decline", "rise", "why", "reason", "cause", "driver", "driven")
        if not any(t in q for t in cause_terms) and len(q.split()) < 4:
            return
        causes_query = f"{query} causes reasons drivers" if len(query or "") > 10 else f"{topic or 'price'} decline causes reasons"
        try:
            from services.historic_context_orchestrator import run_historic_context
            h = run_historic_context(
                query=causes_query,
                start_date=start,
                end_date=end,
                topic=topic,
                trigger_type="analysis",
                trigger_id=task.task_id,
                max_expansions=0,
            )
            if h.get("success") and h.get("summary"):
                extra = (h.get("summary") or "").strip()[:2500]
                if extra:
                    existing = getattr(task.context, "historic_context_summary", None) or ""
                    task.context.historic_context_summary = f"{existing}\n\n## Causes-focused search\n{extra}"
                    logger.info("Merged causes-focused historic context: %d chars", len(extra))
        except Exception as e:
            logger.debug("Causes-focused historic context failed: %s", e)

    async def _execute_ingest(self, task: Task) -> None:
        """Run EDGAR ingest (standalone, not chained from refresh)."""
        plan = {"filings_per_company": task.parameters.get("filings_per_company", 1)}

        def _sync():
            from domains.finance.data_sources.edgar import ingest_edgar_10ks
            return ingest_edgar_10ks(filings_per_company=plan["filings_per_company"], record_ledger=True)

        loop = asyncio.get_event_loop()
        try:
            count, chunk_ids = await loop.run_in_executor(self._executor, _sync)
            self._ledger_record(task, "edgar", "success")
            task.context.fetched_data["ingest_results"] = {"chunks_embedded": count, "chunk_ids": chunk_ids}
            task.context.fetched_data["refresh_summary"] = RefreshSummary(
                sources={"edgar": {"success": count > 0, "chunks_embedded": count}},
                total_observations=0,
                chunks_embedded=count,
                chunk_ids=chunk_ids,
            )
        except Exception as e:
            dr = normalize_to_data_result(e)
            task.context.errors.append({"source": "edgar", "error": dr.error, "error_type": dr.error_type})
            self._ledger_record(task, "edgar", "error", error=str(e))
            raise

    def _plan_analysis(self, task: Task) -> dict[str, Any]:
        """Determine data needs for analysis. May queue refresh if stale."""
        query = task.parameters.get("query", "")
        topic = task.parameters.get("topic") or "gold"
        return {"query": query, "topic": topic, "n_chunks": 5}

    async def _execute_analysis(self, task: Task, plan: dict[str, Any], is_revision: bool = False) -> None:
        """Run refresh/retrieve/stats/build prompt + LLM. If is_revision, only call LLM with revision prompt."""
        if is_revision and task.context.llm_prompt:
            prompt = task.context.llm_prompt
            async with self._gpu_lock:
                if self.llm_wrapper:
                    try:
                        from domains.finance.llm import generate
                        response = await generate(
                            prompt, system_prompt=None,
                            task_id=task.task_id, phase="revision", prompt_template_id="revision",
                        )
                        task.context.llm_response = response
                    except Exception as e:
                        logger.warning("LLM revision failed: %s", e)
                        task.context.llm_response = f"[Error: {e}]"
            return

        query = plan.get("query", "")
        topic = plan.get("topic", "gold")
        n_chunks = plan.get("n_chunks", 5)

        # Ensure we have data: run refresh to build evidence index (or use cache if fresh for gold-only)
        if topic in ("gold", "silver", "platinum", "all", "fred", ""):
            now = datetime.now(timezone.utc)
            cache_key = topic or "gold"
            cached = self._evidence_cache.get(cache_key) if topic == "gold" else None
            if cached:
                ts, evidence = cached
                age = (now - ts).total_seconds()
                if age < self._evidence_cache_ttl_seconds and evidence:
                    task.context.evidence_index = list(evidence)
                    logger.debug("Using cached gold evidence (age=%.0fs)", age)
                else:
                    cached = None
            if not cached:
                refresh_plan = self._plan_refresh(task)
                await self._execute_refresh(task, refresh_plan)
                self._build_evidence_index(task)
                # If refresh returned no gold data, fall back to stored market data so the LLM has evidence
                if (topic in ("gold", "all", "")) and not task.context.evidence_index:
                    try:
                        from domains.finance.gold_amalgamator import get_stored
                        start = task.parameters.get("start_date") or task.parameters.get("start")
                        end = task.parameters.get("end_date") or task.parameters.get("end")
                        stored = get_stored(start=start, end=end)
                        if stored:
                            # Normalize to same shape as refresh_results["gold"]["results"] for _build_evidence_index
                            normalized = {}
                            for sid, obs_list in stored.items():
                                if not obs_list:
                                    continue
                                normalized[sid] = [
                                    {
                                        "date": o.get("date", ""),
                                        "value": o.get("value"),
                                        "unit": (o.get("metadata") or {}).get("unit", "USD/oz"),
                                    }
                                    for o in obs_list[:100]
                                    if o.get("date") and o.get("value") is not None
                                ]
                            if normalized:
                                rr = task.context.fetched_data.setdefault("refresh_results", {})
                                if "gold" not in rr:
                                    rr["gold"] = {}
                                rr["gold"]["results"] = rr["gold"].get("results") or {}
                                for sid, obs in normalized.items():
                                    rr["gold"]["results"][sid] = obs
                                self._build_evidence_index(task)
                                logger.info("Gold evidence from store (refresh had no data): %d entries", len(task.context.evidence_index))
                    except Exception as e:
                        logger.warning("Fallback to stored gold failed: %s", e)
                if not task.context.evidence_index and topic in ("silver", "platinum"):
                    try:
                        from domains.finance.commodity_store import get_manual_history
                        obs_list = get_manual_history(topic, days=730)
                        if obs_list:
                            rr = task.context.fetched_data.setdefault("refresh_results", {})
                            rr[topic] = {
                                "results": {
                                    topic: [
                                        {"date": o.get("date"), "value": o.get("value"), "unit": o.get("unit", "USD/toz")}
                                        for o in obs_list[:100]
                                    ]
                                }
                            }
                            self._build_evidence_index(task)
                            logger.info("%s evidence from manual store: %d entries", topic.capitalize(), len(task.context.evidence_index))
                    except Exception as e:
                        logger.warning("Fallback to manual store for %s failed: %s", topic, e)
                if not task.context.evidence_index:
                    logger.warning("Analysis task %s has no evidence (refresh and store fallback yielded nothing)", task.task_id)
                if task.context.evidence_index and topic == "gold":
                    self._evidence_cache[cache_key] = (now, list(task.context.evidence_index))

        # Retrieve from vector store (semantic search)
        chunks_text: list[str] = []
        if self.embedding_module and self.vector_store:
            try:
                from domains.finance.embedding import embed_text
                from domains.finance.data.vector_store import query as vs_query
                vec = embed_text(query)
                if vec:
                    result = vs_query([vec], n_results=n_chunks)
                    docs = result.get("documents", [[]])[0] or []
                    chunks_text = [d for d in docs if d]
            except Exception as e:
                logger.debug("Vector retrieve failed: %s", e)

        task.context.evidence_chunks = chunks_text

        # RSS + historic context: always include all sources. Default date range = last 2 years when not provided.
        start = task.parameters.get("start_date") or task.parameters.get("start")
        end = task.parameters.get("end_date") or task.parameters.get("end")
        if not start or not end:
            from datetime import date, timedelta
            _end = date.today()
            _start = _end - timedelta(days=730)
            start = start or _start.isoformat()
            end = end or _end.isoformat()
            logger.info("Analysis task %s: using default date range %s to %s (all sources including historic context)", task.task_id, start, end)
        else:
            logger.info("Analysis task %s: date range %s to %s, including historic context", task.task_id, start, end)
        try:
            from domains.finance.evidence_collector import collect as evidence_collect
            bundle = evidence_collect(
                query=query,
                topic=topic,
                start_date=start,
                end_date=end,
                hours=168,
                max_rss=15,
                include_rss=True,
                include_api_summary=False,
                include_rag=False,
                include_historic_context=True,
            )
            task.context.rss_snippets = bundle.get("rss_snippets") or []
            if bundle.get("historic_context_summary"):
                task.context.historic_context_summary = bundle["historic_context_summary"]
                task.context.historic_context_events = bundle.get("historic_context_events") or []
                logger.info("Historic context summary length %d chars, events %d", len(bundle["historic_context_summary"]), len(bundle.get("historic_context_events") or []))
            else:
                logger.warning("Historic context returned empty summary (sources may have returned nothing)")
            self._append_rss_and_historic_evidence(task)
            self._run_causes_focused_historic_if_needed(task, query, topic, start, end)
        except Exception as e:
            logger.debug("Evidence collector (RSS) failed: %s", e)
            task.context.rss_snippets = []

        # Compute stats from evidence index
        stats_results: dict[str, Any] = {}
        if self.stats_module and task.context.evidence_index:
            try:
                from domains.finance.stats import latest_value, price_change_pct
                # Build obs list from gold entries
                gold_entries = [e for e in task.context.evidence_index if e.source == "gold"]
                if gold_entries:
                    obs = [{"date": str(e.date), "value": e.value} for e in gold_entries[:50]]
                    latest = latest_value(obs)
                    if latest is not None:
                        stats_results["latest_gold_usd"] = latest
                    vals = [(str(e.date), float(e.value)) for e in gold_entries[:30] if isinstance(e.value, (int, float))]
                    pct = price_change_pct(vals)
                    if pct is not None:
                        stats_results["gold_price_change_pct"] = round(pct, 2)
            except Exception as e:
                logger.debug("Stats compute failed: %s", e)
        task.context.stats_results = stats_results

        # Build prompt with evidence index and instructions
        prompt, system_prompt = self._build_analysis_prompt(task, query, stats_results)
        task.context.llm_prompt = prompt

        # GPU queue: serialize LLM calls
        async with self._gpu_lock:
            if self.llm_wrapper:
                try:
                    from domains.finance.llm import generate
                    ctx_docs = [{"ref_id": e.ref_id, "source": e.source, "char_count": len(str(e.context or ""))}
                                for e in (task.context.evidence_index or [])[:20]]
                    response = await generate(
                        prompt, system_prompt=system_prompt,
                        task_id=task.task_id, phase="synthesis", prompt_template_id="analysis",
                        context_documents=ctx_docs,
                    )
                    task.context.llm_response = response
                except Exception as e:
                    logger.warning("LLM generate failed: %s", e)
                    task.context.llm_response = f"[Error: {e}]"
            else:
                task.context.llm_response = "[LLM not configured]"

    def _build_analysis_prompt(
        self, task: Task, query: str, stats_results: dict[str, Any]
    ) -> tuple[str, str]:
        """Build prompt with evidence index (REF-ids), chunks, stats. System prompt instructs citation."""
        system_prompt = """You are a financial analyst. Use ONLY the provided evidence for concrete claims.
Cite every number, date, or percentage using its reference ID (e.g. REF-001).
Do not invent or guess values. Structure your response: (1) establish what happened from the Evidence REF-ids; (2) explain causes or drivers using the Historic context and News sections when they contain relevant information; (3) if they do not, say so briefly. Do not ask the user for more information."""

        parts = [f"## Query\n{query}\n"]
        if task.context.evidence_index:
            parts.append("## Evidence (cite by REF-ID)\n")
            for e in task.context.evidence_index[:100]:
                parts.append(f"- {e.ref_id}: {e.source} {e.identifier} | {e.date} | {e.value} {e.unit} | {e.context}")
        else:
            parts.append("## Evidence\nNo evidence was retrieved for this query (sources may be temporarily unavailable or no data in date range).")
        if stats_results:
            parts.append("\n## Computed stats\n")
            for k, v in stats_results.items():
                parts.append(f"- {k}: {v}")
        if task.context.evidence_chunks:
            parts.append("\n## Relevant excerpts\n")
            for i, txt in enumerate(task.context.evidence_chunks[:5]):
                parts.append(f"[Excerpt {i+1}]\n{txt[:500]}...\n")
        historic = getattr(task.context, "historic_context_summary", None)
        if historic:
            parts.append("\n## Historic context (multi-source)\n")
            parts.append(historic[:5000])
            parts.append("\nUse this historic context where it helps explain causes or prior events. Events mentioned by more sources are more reliable.")
        rss_snippets = getattr(task.context, "rss_snippets", None) or []
        if rss_snippets:
            parts.append("\n## News / reporting (use for causes, drivers, and context)\n")
            for s in rss_snippets[:15]:
                title = s.get("title") or ""
                snippet = (s.get("snippet") or "")[:350]
                pub = s.get("published_at") or ""
                parts.append(f"- {title} ({pub})\n  {snippet}\n")
            parts.append("Use the news/reporting above where relevant to explain causes, supply/demand, or market context. Cite price evidence (REF-ids) for levels and dates.")
        else:
            parts.append("\n## News / reporting\nNo news or reporting excerpts are available for this topic. Base your analysis on the price and other evidence above; note that causes or drivers are not evidenced.")
        parts.append(
            "\n## Response\n"
            "1) Establish the move: Using the Evidence (REF-ids), state clearly what happened to price/levels and over which dates. Cite REF-ids for every number and date.\n"
            "2) Explain causes: Use the Historic context and News / reporting sections above to explain why the move occurred (supply, demand, events, policy). If multiple sources agree on a cause, say so. If those sections do not contain specific causes, say so in one sentence (e.g. 'The provided news and historic context did not identify specific causes for this decline') and do not ask the user for more information.\n"
            "3) Be concise. Do not invent figures. When in doubt, describe what the evidence shows."
        )

        prompt = "\n".join(parts)
        return prompt, system_prompt

    def _extract_and_verify_claims(self, task: Task) -> VerificationResult:
        """Extract concrete claims from LLM output, verify against evidence index."""
        text = task.context.llm_response or ""
        index = task.context.evidence_index or []
        details: list[ClaimCheck] = []
        verified = unsupported = fabricated = 0

        # Extract REF-ids mentioned (e.g. REF-001, REF-042)
        ref_pattern = re.compile(r"REF-\d+", re.I)
        refs_mentioned = set(ref_pattern.findall(text.upper().replace("ref-", "REF-")))

        # Extract dollar amounts ($X, $X.XX)
        dollar_pattern = re.compile(r"\$\s*([\d,]+(?:\.\d{2})?)")
        # Extract percentages (X%, X.XX%)
        pct_pattern = re.compile(r"([\d.]+)\s*%")
        # Extract dates (YYYY-MM-DD, MM/DD/YYYY)
        date_pattern = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b")
        # Extract numeric values (standalone numbers that could be prices)
        num_pattern = re.compile(r"\b(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\b")

        def _find_match(value: str | float, tol_pct: float = 0.5) -> EvidenceIndexEntry | None:
            try:
                v = float(str(value).replace(",", ""))
            except (ValueError, TypeError):
                return None
            for e in index:
                ev = e.value
                if isinstance(ev, (int, float)):
                    if abs(ev - v) / max(abs(v), 1e-9) <= tol_pct / 100:
                        return e
            return None

        def _find_date(d: str) -> EvidenceIndexEntry | None:
            for e in index:
                if str(e.date) == d or (hasattr(e.date, "isoformat") and e.date.isoformat() == d):
                    return e
            return None

        # Check REF-ids: mentioned ref must exist in index
        index_refs = {e.ref_id.upper() for e in index}
        for ref in refs_mentioned:
            ref_upper = ref.upper()
            if ref_upper in index_refs:
                details.append(ClaimCheck(ref, ref, ClaimVerdict.verified))
                verified += 1
            else:
                details.append(ClaimCheck(ref, None, ClaimVerdict.unsupported))
                unsupported += 1

        # Check dollar amounts
        for m in dollar_pattern.finditer(text):
            val = m.group(1).replace(",", "")
            match = _find_match(val)
            if match:
                details.append(ClaimCheck(m.group(0), match.ref_id, ClaimVerdict.verified))
                verified += 1
            else:
                details.append(ClaimCheck(m.group(0), None, ClaimVerdict.unsupported))
                unsupported += 1

        # Check dates
        for m in date_pattern.finditer(text):
            d = m.group(1)
            match = _find_date(d)
            if match:
                details.append(ClaimCheck(d, match.ref_id, ClaimVerdict.verified))
                verified += 1
            else:
                details.append(ClaimCheck(d, None, ClaimVerdict.unsupported))
                unsupported += 1

        total = verified + unsupported + fabricated
        return VerificationResult(
            total_claims=total,
            verified=verified,
            unsupported=unsupported,
            fabricated=fabricated,
            details=details,
        )

    def _evaluate_analysis(self, task: Task) -> bool:
        """Return True if verification passes QualityCriteria."""
        vr = task.context.verification_result
        if not vr:
            return True
        qc = self.quality_criteria
        if vr.fabricated > qc.max_fabricated_claims:
            logger.info("Analysis rejected: %d fabricated claims", vr.fabricated)
            return False
        if vr.unsupported > qc.max_unsupported_claims:
            logger.info("Analysis rejected: %d unsupported claims (max %d)", vr.unsupported, qc.max_unsupported_claims)
            return False
        return True

    def _build_revision_prompt(self, task: Task) -> None:
        """Build revision prompt with failed claims and corrections. Sets task.context.llm_prompt."""
        vr = task.context.verification_result
        if not vr or not vr.details:
            return
        failed = [d for d in vr.details if d.verdict in (ClaimVerdict.unsupported, ClaimVerdict.fabricated)]
        if not failed:
            return
        index = {e.ref_id: e for e in (task.context.evidence_index or [])}
        parts = [
            "Your previous response had factual errors. Correct them using ONLY the evidence below.",
            "\n## Original response\n",
            task.context.llm_response or "",
            "\n## Errors to fix\n",
        ]
        for d in failed[:10]:
            parts.append(f"- \"{d.claim_text}\" (verdict: {d.verdict.value})")
        parts.append("\n## Evidence (use these REF-ids)\n")
        for e in list(index.values())[:30]:
            parts.append(f"- {e.ref_id}: {e.date} | {e.value} {e.unit}")
        parts.append("\n## Corrected response\n")
        task.context.llm_prompt = "\n".join(parts)
        task.context.revision_notes.append(f"Revision: {len(failed)} claims to fix")

    def _load_schedule_config(self) -> list[dict[str, Any]]:
        """Load scheduled tasks from finance_schedule.yaml."""
        try:
            from config.paths import FINANCE_SCHEDULE_YAML
            if not FINANCE_SCHEDULE_YAML.exists():
                return []
            import yaml
            with open(FINANCE_SCHEDULE_YAML) as f:
                cfg = yaml.safe_load(f) or {}
            sched = cfg.get("schedule") or {}
            out = []
            for name, spec in sched.items():
                if isinstance(spec, dict):
                    out.append({"name": name, **spec})
            return out
        except Exception as e:
            logger.warning("Schedule config load failed: %s", e)
            return []

    def start_scheduler(self) -> None:
        """Start background scheduler. Submits low-priority tasks on interval."""
        if self._schedule_task and not self._schedule_task.done():
            return
        self._schedule_stop.clear()
        self._schedule_task = asyncio.create_task(self._schedule_loop())
        logger.info("Finance scheduler started")

    def stop_scheduler(self) -> None:
        """Stop the scheduler and queue worker."""
        self._schedule_stop.set()
        if self._schedule_task:
            self._schedule_task.cancel()
            self._schedule_task = None
        self.stop_queue_worker()

    def start_queue_worker(self) -> None:
        """Start background worker that processes queued tasks (analysis, refresh, ingest)."""
        if self._queue_task and not self._queue_task.done():
            return
        self._queue_stop.clear()
        self._queue_task = asyncio.create_task(self._queue_loop())
        logger.info("Finance queue worker started")

    def stop_queue_worker(self) -> None:
        """Stop the queue worker."""
        self._queue_stop.set()
        if self._queue_task:
            self._queue_task.cancel()
            try:
                self._queue_task.result()
            except (asyncio.CancelledError, Exception):
                pass
            self._queue_task = None

    async def _queue_loop(self) -> None:
        """Process queued tasks: pick next by priority (high first), then run to completion."""
        while not self._queue_stop.is_set():
            try:
                queued_ids = [
                    tid for tid in self._task_order
                    if self._tasks.get(tid) and self._tasks[tid].status == TaskStatus.queued
                ]
                if not queued_ids:
                    try:
                        await asyncio.wait_for(self._queue_stop.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                    continue
                # Prefer high priority, then FIFO by _task_order
                next_id = min(
                    queued_ids,
                    key=lambda tid: (self._tasks[tid].priority.sort_value, self._task_order.index(tid)),
                )
                logger.info("Queue worker running task %s (type=%s)", next_id, self._tasks[next_id].task_type.value)
                try:
                    result = await self.run_task(next_id)
                    if result:
                        logger.info("Queue task %s finished: %s", next_id, result.status.value)
                    else:
                        logger.warning("Queue task %s returned None", next_id)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception("Queue task %s failed: %s", next_id, e)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Queue loop iteration failed: %s", e)
                try:
                    await asyncio.wait_for(self._queue_stop.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass

    async def _schedule_loop(self) -> None:
        """Background loop: every minute check if any task is due, submit and run if so."""
        while not self._schedule_stop.is_set():
            try:
                for spec in self._load_schedule_config():
                    name = spec.get("name", "")
                    interval_hours = spec.get("interval_hours", 24)
                    last = self._schedule_last_run.get(name)
                    now = datetime.now(timezone.utc)
                    if last is None:
                        due = True
                    else:
                        elapsed = (now - last).total_seconds()
                        due = elapsed >= interval_hours * 3600
                    if due:
                        task_type = spec.get("task_type", "refresh")
                        params = spec.get("parameters") or {}
                        try:
                            tt = TaskType(task_type)
                        except ValueError:
                            tt = TaskType.refresh
                        task_id = self.submit_task(
                            tt, params, priority=TaskPriority.low,
                            reason=f"Scheduled run: {name} (interval met)",
                        )
                        logger.info("Scheduled task %s submitted: %s", name, task_id)
                        self._schedule_last_run[name] = now
                        result = await self.run_task(task_id)
                        if result:
                            logger.info("Scheduled %s completed: %s", name, result.status)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Scheduler iteration failed: %s", e)
            try:
                await asyncio.wait_for(self._schedule_stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass

    def get_schedule_status(self) -> dict[str, Any]:
        """Return schedule status: next run times, last run results."""
        items = []
        for spec in self._load_schedule_config():
            name = spec.get("name", "")
            interval_hours = spec.get("interval_hours", 24)
            last = self._schedule_last_run.get(name)
            next_run = None
            if last:
                from datetime import timedelta
                next_run = last + timedelta(hours=interval_hours)
            items.append({
                "name": name,
                "task_type": spec.get("task_type", "refresh"),
                "interval_hours": interval_hours,
                "last_run": last.isoformat() if last else None,
                "next_run": next_run.isoformat() if next_run else None,
            })
        return {"tasks": items}

    def _ledger_record(self, task: Task, source_id: str, status: str, **kwargs: Any) -> None:
        """Record fetch attempt in evidence ledger."""
        if not self.evidence_ledger:
            return
        try:
            from domains.finance.data.evidence_ledger import record
            report_id = f"orchestrator_{task.task_id}"
            record(
                report_id=report_id,
                source_type="orchestrator_refresh",
                source_id=source_id,
                evidence_data={"status": status, "task_id": task.task_id, **kwargs},
            )
        except Exception as e:
            logger.debug("Ledger record failed: %s", e)

    def submit_task(
        self,
        task_type: TaskType,
        parameters: dict[str, Any],
        priority: TaskPriority = TaskPriority.high,
        iteration_budget: int = 3,
        reason: str | None = None,
    ) -> str:
        """
        Create a task, add to queue, return task_id.
        Does not execute yet — task remains queued until worker runs (Phase 2).
        reason: Optional short statement for logs (what activity, why).
        """
        task_id = f"fin-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        task = Task(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            parameters=parameters,
            iteration_budget=iteration_budget,
            current_iteration=0,
            context=TaskContext(),
            status=TaskStatus.queued,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task_id] = task
        self._task_order.append(task_id)

        activity = f"{task_type.value}"
        if not reason:
            if priority == TaskPriority.high:
                if task_type == TaskType.analysis:
                    reason = "User requested analysis"
                elif task_type == TaskType.refresh:
                    topic = parameters.get("topic", "?")
                    reason = f"Manual/API-triggered refresh (topic={topic})"
                elif task_type == TaskType.ingest:
                    reason = "Manual EDGAR ingest triggered"
                else:
                    reason = "User/API triggered"
            elif priority == TaskPriority.low:
                reason = "Scheduled background refresh"
            elif priority == TaskPriority.medium:
                reason = "Orchestrator revision (retry after failed evaluation)"
            else:
                reason = "Queued"

        log_queue_decision(activity=activity, reason=reason, task_id=task_id, priority=priority.value)
        log_event(TASK_ACCEPTED, task_id, {"type": task_type.value, "priority": priority.value})
        logger.info(
            "Task submitted: id=%s type=%s priority=%s — %s",
            task_id,
            task_type.value,
            priority.value,
            reason,
        )
        return task_id

    def list_tasks(
        self,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List tasks with optional filters. Returns paginated task summaries.
        Sorted by updated_at descending (most recent first).
        """
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        if task_type:
            tasks = [t for t in tasks if t.task_type.value == task_type]
        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        total = len(tasks)
        page = tasks[offset : offset + limit]
        items = [
            {
                "task_id": t.task_id,
                "task_type": t.task_type.value,
                "priority": t.priority.value,
                "status": t.status.value,
                "phase": _status_to_phase(t.status, t.task_type),
                "current_iteration": t.current_iteration,
                "iteration_budget": t.iteration_budget,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in page
        ]
        return {"tasks": items, "total": total, "limit": limit, "offset": offset}

    def list_evidence_index(
        self,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List evidence index entries (provenance) from completed tasks.
        Aggregates from all tasks with evidence_index. Sorted by most recent task first.
        """
        entries: list[dict[str, Any]] = []
        tasks = [
            t for t in self._tasks.values()
            if t.status in (TaskStatus.complete, TaskStatus.failed) and t.context.evidence_index
        ]
        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        for task in tasks:
            for e in task.context.evidence_index:
                if source and e.source != source:
                    continue
                entries.append({
                    "ref_id": e.ref_id,
                    "source": e.source,
                    "identifier": e.identifier,
                    "date": str(e.date) if e.date else None,
                    "value": e.value,
                    "unit": e.unit,
                    "context": e.context,
                    "task_id": task.task_id,
                })
        total = len(entries)
        page = entries[offset : offset + limit]
        return {"entries": page, "total": total, "limit": limit, "offset": offset}

    def list_verifications(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List verification results from completed analysis tasks.
        Sorted by task updated_at descending.
        """
        items: list[dict[str, Any]] = []
        tasks = [
            t for t in self._tasks.values()
            if t.task_type == TaskType.analysis
            and t.status in (TaskStatus.complete, TaskStatus.failed)
            and t.context.verification_result
        ]
        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        for task in tasks:
            vr = task.context.verification_result
            if not vr:
                continue
            items.append({
                "task_id": task.task_id,
                "query": task.parameters.get("query", ""),
                "total_claims": vr.total_claims,
                "verified": vr.verified,
                "unsupported": vr.unsupported,
                "fabricated": vr.fabricated,
                "details": [
                    {"claim_text": c.claim_text, "ref_id": c.ref_id, "verdict": c.verdict.value}
                    for c in vr.details[:20]
                ],
                "updated_at": task.updated_at.isoformat(),
            })
        total = len(items)
        page = items[offset : offset + limit]
        return {"verifications": page, "total": total, "limit": limit, "offset": offset}

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Return current state of a task. None if unknown."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        phase = _status_to_phase(task.status, task.task_type)
        return {
            "task_id": task_id,
            "task_type": task.task_type.value,
            "priority": task.priority.value,
            "status": task.status.value,
            "phase": phase,
            "current_iteration": task.current_iteration,
            "iteration_budget": task.iteration_budget,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }

    def get_task_result(self, task_id: str) -> TaskResult | None:
        """Return TaskResult if task is complete or failed. None otherwise."""
        task = self._tasks.get(task_id)
        if not task:
            return None
        if task.status not in (TaskStatus.complete, TaskStatus.failed):
            return None
        # Phase 1: we never complete tasks, so this returns None for now.
        # In later phases, we build TaskResult from task.context.
        return self._build_task_result(task)

    def _build_task_result(self, task: Task) -> TaskResult | None:
        """Build TaskResult from completed/failed task."""
        duration_ms = 0
        if task.created_at and task.updated_at:
            delta = task.updated_at - task.created_at
            duration_ms = int(delta.total_seconds() * 1000)

        output = None
        warnings: list[str] = []
        confidence = 1.0 if task.status == TaskStatus.complete else 0.0
        provenance = task.context.evidence_index or []
        verification_summary = task.context.verification_result

        sources_consulted: list[str] = []
        sources_succeeded: list[str] = []
        sources_failed: list[str] = []
        summary = task.context.fetched_data.get("refresh_summary")
        if summary:
            sources_consulted = list(summary.sources.keys())
            for sid, meta in summary.sources.items():
                if meta.get("success"):
                    sources_succeeded.append(sid)
                else:
                    sources_failed.append(sid)

        if task.status == TaskStatus.failed:
            warnings = task.context.revision_notes or ["Task failed"]
        elif task.task_type == TaskType.analysis:
            vr = task.context.verification_result
            if vr:
                confidence -= 0.02 * vr.unsupported
                confidence -= 0.1 * vr.fabricated
            confidence -= 0.1 * max(0, task.current_iteration)
            confidence = max(0.0, min(1.0, confidence))
            rss = getattr(task.context, "rss_snippets", None) or []
            output = {
                "response": task.context.llm_response,
                "query": task.parameters.get("query", ""),
                "verification": {
                    "verified": vr.verified if vr else 0,
                    "unsupported": vr.unsupported if vr else 0,
                    "fabricated": vr.fabricated if vr else 0,
                } if vr else None,
                "rss_snippets": [{"title": s.get("title"), "url": s.get("url"), "published_at": s.get("published_at")} for s in rss[:20]],
            }
        elif task.task_type in (TaskType.refresh, TaskType.ingest):
            if summary:
                output = {
                    "sources": summary.sources,
                    "total_observations": summary.total_observations,
                    "chunks_embedded": summary.chunks_embedded,
                    "chunk_ids": summary.chunk_ids[:50],
                }

        return TaskResult(
            task_id=task.task_id,
            status=ResultStatus.failed if task.status == TaskStatus.failed else ResultStatus.success,
            output=output,
            confidence=confidence,
            iterations_used=task.current_iteration,
            provenance=provenance,
            verification_summary=verification_summary,
            warnings=warnings,
            duration_ms=duration_ms,
            sources_consulted=sources_consulted,
            sources_succeeded=sources_succeeded,
            sources_failed=sources_failed,
            created_at=task.created_at,
        )
