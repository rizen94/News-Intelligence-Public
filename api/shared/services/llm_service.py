"""
Shared LLM service for the News Intelligence system.
Uses Ollama-hosted primary (default Llama 3.1 8B), secondary slot (default Mistral-Nemo 12B), optional Qwen/Phi via policy.
Global concurrency limit so async Ollama callers share one cap.
"""

import asyncio
import os
import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from typing import Any

import httpx
from config.settings import (
    MODELS,
    NARRATIVE_FINISHER_MODEL,
    OLLAMA_HOST,
    OLLAMA_MODEL_EXTRACTION,
    OLLAMA_MODEL_PHI,
    OLLAMA_POP_OS_HOST,
    OLLAMA_TIMEOUT,
)
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str


def _httpx_ollama_timeout(lane: str | None = None) -> float:
    try:
        default = float(env_str("OLLAMA_TIMEOUT", str(OLLAMA_TIMEOUT)))
    except ValueError:
        default = float(OLLAMA_TIMEOUT)
    lane_key = (lane or "").strip().lower()
    if lane_key == "gpu":
        try:
            return float(env_str("OLLAMA_GPU_TIMEOUT", env_str("BULK_OLLAMA_TIMEOUT", str(default))))
        except ValueError:
            return default
    if lane_key == "cpu":
        try:
            return float(env_str("OLLAMA_CPU_TIMEOUT", str(default)))
        except ValueError:
            return default
    return default

logger = logging.getLogger(__name__)

# Global cap. Burst (48h catch-up): 6; revert to 5 after
OLLAMA_CONCURRENCY = 6
_ollama_semaphore: asyncio.Semaphore | None = None
_ollama_semaphore_loop: asyncio.AbstractEventLoop | None = None
_ollama_cpu_semaphore: asyncio.Semaphore | None = None
_ollama_cpu_semaphore_loop: asyncio.AbstractEventLoop | None = None
_ollama_gpu_semaphore: asyncio.Semaphore | None = None
_ollama_gpu_semaphore_loop: asyncio.AbstractEventLoop | None = None
_llm_execution_lane: ContextVar[str | None] = ContextVar("llm_execution_lane", default=None)


def _loop_bound_semaphore(
    sem: asyncio.Semaphore | None,
    sem_loop: asyncio.AbstractEventLoop | None,
    capacity: int,
) -> tuple[asyncio.Semaphore, asyncio.AbstractEventLoop]:
    """Recreate semaphore when the running event loop changes (uvicorn reload / worker restart)."""
    loop = asyncio.get_running_loop()
    if sem is None or sem_loop is not loop:
        return asyncio.Semaphore(capacity), loop
    return sem, sem_loop


def _get_ollama_semaphore() -> asyncio.Semaphore:
    global _ollama_semaphore, _ollama_semaphore_loop
    _ollama_semaphore, _ollama_semaphore_loop = _loop_bound_semaphore(
        _ollama_semaphore, _ollama_semaphore_loop, OLLAMA_CONCURRENCY
    )
    return _ollama_semaphore


def _get_lane_semaphore(execution_lane: str | None, dual_enabled: bool) -> asyncio.Semaphore:
    if not dual_enabled:
        return _get_ollama_semaphore()

    lane = (execution_lane or "gpu").strip().lower()
    if lane == "cpu":
        global _ollama_cpu_semaphore, _ollama_cpu_semaphore_loop
        cpu_cap = max(1, int(env_str("OLLAMA_CPU_CONCURRENCY", "6")))
        _ollama_cpu_semaphore, _ollama_cpu_semaphore_loop = _loop_bound_semaphore(
            _ollama_cpu_semaphore, _ollama_cpu_semaphore_loop, cpu_cap
        )
        return _ollama_cpu_semaphore

    global _ollama_gpu_semaphore, _ollama_gpu_semaphore_loop
    gpu_cap = max(1, int(env_str("OLLAMA_GPU_CONCURRENCY", "6")))
    _ollama_gpu_semaphore, _ollama_gpu_semaphore_loop = _loop_bound_semaphore(
        _ollama_gpu_semaphore, _ollama_gpu_semaphore_loop, gpu_cap
    )
    return _ollama_gpu_semaphore


@contextmanager
def set_llm_execution_lane(execution_lane: str | None):
    """Context helper so automation can steer LLM calls to cpu/gpu lanes."""
    normalized = None
    if execution_lane:
        lane = execution_lane.strip().lower()
        if lane in ("cpu", "gpu"):
            normalized = lane
    token = _llm_execution_lane.set(normalized)
    try:
        yield
    finally:
        _llm_execution_lane.reset(token)


def push_llm_execution_lane(execution_lane: str | None):
    """Set lane in current context and return token for manual reset."""
    normalized = None
    if execution_lane:
        lane = execution_lane.strip().lower()
        if lane in ("cpu", "gpu"):
            normalized = lane
    return _llm_execution_lane.set(normalized)


def pop_llm_execution_lane(token) -> None:
    _llm_execution_lane.reset(token)


class ModelType(str, Enum):
    """Ollama text models. Values come from config.settings (env overrides). LLAMA_70B = NARRATIVE_FINISHER_MODEL."""

    LLAMA_8B = MODELS["primary"]
    MISTRAL_7B = MODELS["secondary"]  # secondary slot (default Mistral-Nemo 12B)
    QWEN_25_7B = OLLAMA_MODEL_EXTRACTION
    PHI_35 = OLLAMA_MODEL_PHI
    LLAMA_70B = NARRATIVE_FINISHER_MODEL


class TaskType(Enum):
    """Task types for model selection"""

    REAL_TIME = "real_time"
    BATCH_PROCESSING = "batch_processing"
    COMPREHENSIVE_ANALYSIS = "comprehensive_analysis"
    QUICK_SUMMARY = "quick_summary"


class LLMService:
    """
    Centralized LLM service using Ollama-hosted models
    Optimized for primary + secondary (see config.settings MODELS)
    """

    def __init__(self, ollama_base_url: str | None = None):
        self.ollama_base_url = (ollama_base_url or OLLAMA_HOST).rstrip("/")
        self.ollama_cpu_host = (
            env_str("OLLAMA_CPU_HOST", self.ollama_base_url).rstrip("/")
        )
        self.ollama_gpu_host = (
            env_str("OLLAMA_GPU_HOST", self.ollama_base_url).rstrip("/")
        )
        # popOS host for 70B model - heavy summarization work on RTX5090
        self.ollama_pop_os_host = OLLAMA_POP_OS_HOST.rstrip("/")
        self.dual_host_enabled = env_str(
            "OLLAMA_DUAL_HOST_ROUTING_ENABLED", "false"
        ).lower() in ("1", "true", "yes")
        base_timeout = _httpx_ollama_timeout()
        cpu_timeout = _httpx_ollama_timeout("cpu")
        gpu_timeout = _httpx_ollama_timeout("gpu")
        self.client = httpx.AsyncClient(timeout=base_timeout)
        self.cpu_client = (
            self.client
            if self.ollama_cpu_host == self.ollama_base_url
            else httpx.AsyncClient(timeout=cpu_timeout)
        )
        self.gpu_client = (
            self.client
            if self.ollama_gpu_host == self.ollama_base_url
            else httpx.AsyncClient(timeout=gpu_timeout)
        )
        # popOS client for 70B model on remote RTX5090
        self.pop_os_client = (
            self.client
            if self.ollama_pop_os_host == self.ollama_base_url
            else httpx.AsyncClient(timeout=gpu_timeout)
        )
        self._pop_os_available = True
        self._pop_os_last_check = None
        self.model_performance = {
            ModelType.LLAMA_8B: {
                "speed": 2.93,  # seconds for 200 words
                "quality": 73.0,  # MMLU score
                "memory": 5.0,  # GB VRAM
                "best_for": ["comprehensive_analysis", "real_time", "quick_summary"],
            },
            ModelType.MISTRAL_7B: {
                "speed": 4.17,  # seconds for 200 words (approximate)
                "quality": "very_good",
                "memory": 8.0,  # GB VRAM (12B-class secondary)
                "best_for": ["batch_processing", "alternative_analysis"],
            },
            ModelType.QWEN_25_7B: {
                "speed": 3.5,
                "quality": "structured_extraction",
                "memory": 4.5,
                "best_for": ["structured_extraction"],
            },
            ModelType.PHI_35: {
                "speed": 2.5,
                "quality": "fast_simple",
                "memory": 2.3,
                "best_for": ["fast_simple", "readability_quality"],
            },
        }

    def select_model(
        self,
        task_type: TaskType,
        urgency: str = "standard",
        approx_prompt_chars: int = 0,
    ) -> ModelType:
        """
        Model selection via shared policy (ollama_model_policy).
        approx_prompt_chars: large background prompts may route to secondary (see MODELS["secondary"]).
        """
        from shared.services.ollama_model_policy import resolve_model_for_llm_task

        return resolve_model_for_llm_task(task_type, urgency, approx_prompt_chars)

    def _coerce_task_type(self, task_type: TaskType | str | None) -> TaskType:
        """Normalize legacy string task types to TaskType enum."""
        if isinstance(task_type, TaskType):
            return task_type
        if isinstance(task_type, str):
            normalized = task_type.strip().lower()
            mapping = {
                "quick_summary": TaskType.QUICK_SUMMARY,
                "real_time": TaskType.REAL_TIME,
                "batch_processing": TaskType.BATCH_PROCESSING,
                "content_analysis": TaskType.COMPREHENSIVE_ANALYSIS,
                "comprehensive_analysis": TaskType.COMPREHENSIVE_ANALYSIS,
            }
            return mapping.get(normalized, TaskType.QUICK_SUMMARY)
        return TaskType.QUICK_SUMMARY

    async def generate_text(
        self,
        prompt: str,
        task_type: TaskType | str = TaskType.QUICK_SUMMARY,
        max_tokens: int = 2000,
        model: str | ModelType | None = None,
        execution_lane: str | None = None,
    ) -> dict[str, Any]:
        """
        Backward-compatible freeform text generation API.
        Returns {"success": bool, "text"|"error", "model_used"}.
        """
        chosen_model: ModelType
        if isinstance(model, ModelType):
            chosen_model = model
        elif isinstance(model, str) and model.strip():
            try:
                chosen_model = ModelType(model.strip())
            except ValueError:
                chosen_model = self.select_model(
                    self._coerce_task_type(task_type),
                    approx_prompt_chars=len(prompt or ""),
                )
        else:
            chosen_model = self.select_model(
                self._coerce_task_type(task_type),
                approx_prompt_chars=len(prompt or ""),
            )

        try:
            start_time = datetime.now()
            response = await self._call_ollama(chosen_model, prompt, execution_lane=execution_lane)
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            # Lightweight max_tokens trimming for callers that expect bounded output.
            text = (response or "").strip()
            if max_tokens and max_tokens > 0:
                approx_chars = max_tokens * 4
                if len(text) > approx_chars:
                    text = text[:approx_chars].rstrip()

            return {
                "success": True,
                "text": text,
                "model_used": chosen_model.value,
                "processing_time": processing_time,
                "task_type": self._coerce_task_type(task_type).value,
                "timestamp": end_time.isoformat(),
            }
        except Exception as e:
            logger.error("generate_text failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "model_used": chosen_model.value if "chosen_model" in locals() else None,
                "task_type": self._coerce_task_type(task_type).value,
            }

    def _resolve_sync_execution_target(
        self, model: ModelType | None = None, execution_lane: str | None = None
    ) -> tuple[str, str]:
        """
        Resolve execution target for sync LLM calls.
        Returns (base_url, cb_key).
        Routing logic:
        - 70B models (LLAMA_70B) -> popOS (RTX5090 for heavy summarization)
        - Smaller models -> local GPU/CPU based on lane
        """
        # Heavy models (70B) always route to popOS for intensive summarization work
        if model is not None:
            model_str = model.value.lower()
            if ":70b" in model_str or model == ModelType.LLAMA_70B:
                return self.ollama_pop_os_host, "ollama_pop_os"

        # Fallback to lane-based routing for smaller models
        lane = (execution_lane or _llm_execution_lane.get() or "gpu").strip().lower()
        if not self.dual_host_enabled:
            return self.ollama_base_url, "ollama"
        if lane == "cpu":
            return self.ollama_cpu_host, "ollama_cpu"
        return self.ollama_gpu_host, "ollama_gpu"

    def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        task_type: TaskType | str = TaskType.QUICK_SUMMARY,
        model: str | ModelType | None = None,
        execution_lane: str | None = None,
    ) -> str:
        """
        Legacy sync wrapper used by synchronous services.
        Returns raw text (empty string on failure).
        Routes 70B models to popOS (RTX5090), smaller models to local GPU/CPU.
        """
        chosen_model: str
        model_type: ModelType | None = None
        if isinstance(model, ModelType):
            chosen_model = model.value
            model_type = model
        elif isinstance(model, str) and model.strip():
            chosen_model = model.strip()
            try:
                model_type = ModelType(model.strip())
            except ValueError:
                pass  # Unknown model string, will use as-is
        else:
            selected = self.select_model(
                self._coerce_task_type(task_type),
                approx_prompt_chars=len(prompt or ""),
            )
            model_type = selected
            chosen_model = selected.value

        # Resolve execution target based on model (70B -> popOS, smaller -> local)
        base_url, cb_key = self._resolve_sync_execution_target(model=model_type, execution_lane=execution_lane)

        try:
            with httpx.Client(timeout=_httpx_ollama_timeout()) as sync_client:
                response = sync_client.post(
                    f"{base_url}/api/generate",
                    json={
                        "model": chosen_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "num_predict": max(1, int(max_tokens or 2000)),
                        },
                    },
                )
                if response.status_code != 200:
                    logger.error(
                        "generate sync call failed to %s: status=%s body=%s",
                        cb_key,
                        response.status_code,
                        response.text[:500],
                    )
                    return ""
                return (response.json().get("response", "") or "").strip()
        except Exception as e:
            logger.error("generate sync call failed to %s: %s", cb_key, e)
            return ""

    async def generate_summary(
        self, content: str, task_type: TaskType = TaskType.QUICK_SUMMARY
    ) -> dict[str, Any]:
        """
        Generate article summary using appropriate model
        """
        model = self.select_model(task_type, approx_prompt_chars=len(content or ""))

        prompt = f"""
        Write a professional, journalistic summary of the following news article.
        Focus on the key facts, main points, and important context.
        Keep it concise but comprehensive. Write in a clear, objective tone.
        Respond with only the summary text — no preamble, labels, or markdown headers.

        Article content:
        {content[:2000]}  # Limit content to avoid token limits
        """

        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()

            processing_time = (end_time - start_time).total_seconds()

            return {
                "success": True,
                "summary": response,
                "model_used": model.value,
                "processing_time": processing_time,
                "task_type": task_type.value,
                "timestamp": end_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {
                "success": False,
                "error": str(e),
                "model_used": model.value,
                "task_type": task_type.value,
            }

    async def analyze_sentiment(self, content: str) -> dict[str, Any]:
        """
        Analyze sentiment using Llama 3.1 8B
        """
        model = ModelType.LLAMA_8B

        prompt = f"""
        Analyze the sentiment of this news article. Provide:
        1. Overall sentiment (positive, negative, neutral)
        2. Confidence score (0-100)
        3. Key emotional indicators
        4. Political bias indicators (if any)

        Article:
        {content[:1500]}

        Respond in JSON format:
        {{
            "overall_sentiment": "positive/negative/neutral",
            "confidence": 85,
            "emotional_indicators": ["optimistic", "concerned"],
            "political_bias": "none/minimal/moderate/strong",
            "reasoning": "brief explanation"
        }}
        """

        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()

            # Try to parse JSON response
            try:
                sentiment_data = json.loads(response)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                sentiment_data = {
                    "overall_sentiment": "neutral",
                    "confidence": 50,
                    "emotional_indicators": ["unclear"],
                    "political_bias": "none",
                    "reasoning": "Could not parse structured response",
                    "raw_response": response,
                }

            return {
                "success": True,
                "sentiment": sentiment_data,
                "model_used": model.value,
                "processing_time": (end_time - start_time).total_seconds(),
                "timestamp": end_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {"success": False, "error": str(e), "model_used": model.value}

    async def extract_entities(self, content: str) -> dict[str, Any]:
        """
        Extract named entities using Llama 3.1 8B
        """
        model = ModelType.LLAMA_8B

        prompt = f"""
        Extract named entities from this news article. Identify:
        1. People (PERSON)
        2. Organizations (ORG)
        3. Locations (LOC)
        4. Events (EVENT)
        5. Dates (DATE)

        Article:
        {content[:1500]}

        Respond in JSON format:
        {{
            "people": ["Name1", "Name2"],
            "organizations": ["Org1", "Org2"],
            "locations": ["City1", "Country1"],
            "events": ["Event1", "Event2"],
            "dates": ["2024-01-01", "January 2024"],
            "relationships": [
                {{"entity1": "Name1", "entity2": "Org1", "relation": "works_for"}}
            ]
        }}
        """

        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()

            # Try to parse JSON response
            try:
                entities_data = json.loads(response)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                entities_data = {
                    "people": [],
                    "organizations": [],
                    "locations": [],
                    "events": [],
                    "dates": [],
                    "relationships": [],
                    "raw_response": response,
                }

            return {
                "success": True,
                "entities": entities_data,
                "model_used": model.value,
                "processing_time": (end_time - start_time).total_seconds(),
                "timestamp": end_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {"success": False, "error": str(e), "model_used": model.value}

    async def generate_storyline_analysis(self, storyline_context: str) -> dict[str, Any]:
        """
        Generate comprehensive storyline analysis using Llama 3.1 8B
        """
        model = ModelType.LLAMA_8B

        prompt = f"""
        Analyze this storyline and provide a comprehensive report:
        1. Main narrative thread
        2. Key developments
        3. Timeline of events
        4. Stakeholders involved
        5. Potential future developments
        6. Quality assessment

        Storyline context:
        {storyline_context}

        Write a professional, journalistic analysis that would be suitable for publication.
        """

        try:
            start_time = datetime.now()
            response = await self._call_ollama(model, prompt)
            end_time = datetime.now()

            return {
                "success": True,
                "analysis": response,
                "model_used": model.value,
                "processing_time": (end_time - start_time).total_seconds(),
                "timestamp": end_time.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating storyline analysis: {e}")
            return {"success": False, "error": str(e), "model_used": model.value}

    async def generate_briefing_lead(self, context: str, domain: str = "") -> dict[str, Any]:
        """
        Generate a short editorial lead paragraph for a daily briefing from headline/storyline context.
        Uses a direct prompt (no article-summary wrapper). Returns {"success", "summary" or "error"}.
        """
        if not (context or "").strip():
            return {"success": False, "error": "Empty context"}
        domain_instruction = ""
        if domain:
            try:
                from services.domain_synthesis_config import get_domain_synthesis_config

                cfg = get_domain_synthesis_config(domain)
                if cfg.llm_context:
                    domain_instruction = f" {cfg.llm_context}"
            except ImportError:
                domain_instruction = f" Domain: {domain}."
        prompt = (
            "You are writing the lead paragraph for a daily news briefing."
            + domain_instruction
            + " Focus on developments from the last 24 hours. Prefer items marked [recent] or [recent activity]; mention older storylines only briefly if they are still the main focus. Based only on the following headlines and storylines, write 2–3 short sentences that tell the reader what matters most today. Be factual and concise. No preamble.\n\n"
            + context[:2500]
        )
        try:
            model = self.select_model(
                TaskType.QUICK_SUMMARY, approx_prompt_chars=len(context or "")
            )
            response = await self._call_ollama(model, prompt)
            try:
                from shared.llm_text_sanitize import strip_llm_wrapping_artifacts

                cleaned = strip_llm_wrapping_artifacts(response or "")
            except Exception:
                cleaned = (response or "").strip()
            return {"success": True, "summary": cleaned}
        except Exception as e:
            logger.debug("generate_briefing_lead failed: %s", e)
            return {"success": False, "error": str(e)}

    def _resolve_execution_target(
        self, model: ModelType | None = None, execution_lane: str | None = None
    ) -> tuple[str, httpx.AsyncClient, str]:
        """
        Resolve execution target for LLM calls.
        Routing logic:
        - 70B models (LLAMA_70B) -> popOS (RTX5090 for heavy summarization)
        - Smaller models -> local GPU/CPU based on lane
        
        The `execution_lane` parameter is always provided by callers (via `_call_ollama`).
        If the caller explicitly passes a lane, it will be respected (used for explicit control or testing).
        If not provided, falls back to the context var or defaults to "gpu".
        """
        # Heavy models (70B) always route to popOS for intensive summarization work
        if model is not None:
            model_str = model.value.lower()
            if ":70b" in model_str or model == ModelType.LLAMA_70B:
                return self.ollama_pop_os_host, self.pop_os_client, "ollama_pop_os"

        # For smaller models: if execution_lane is explicitly provided, use it
        # Otherwise fall back to the context var, then default to "gpu"
        lane = None
        if execution_lane is not None:
            lane = execution_lane.strip().lower()
        elif _llm_execution_lane.get() is not None:
            lane = _llm_execution_lane.get()
        else:
            lane = "gpu"

        if not self.dual_host_enabled:
            return self.ollama_base_url, self.client, "ollama"
        if lane == "cpu":
            return self.ollama_cpu_host, self.cpu_client, "ollama_cpu"
        return self.ollama_gpu_host, self.gpu_client, "ollama_gpu"

    async def _call_ollama(
        self,
        model: ModelType,
        prompt: str,
        execution_lane: str | None = None,
        invocation_kind: Any | None = None,
    ) -> str:
        """Make API call to Ollama with circuit breaker protection and lane-aware semaphores."""
        sem = _get_lane_semaphore(execution_lane or _llm_execution_lane.get(), self.dual_host_enabled)
        async with sem:
            return await self._call_ollama_impl(
                model, prompt, execution_lane=execution_lane, invocation_kind=invocation_kind
            )

    async def _call_ollama_impl(
        self,
        model: ModelType,
        prompt: str,
        execution_lane: str | None = None,
        invocation_kind: Any | None = None,
    ) -> str:
        """Inner Ollama call (no semaphore). Routes 70B to popOS, smaller models to local GPU."""
        from services.circuit_breaker_service import get_circuit_breaker_service

        cb_service = get_circuit_breaker_service()
        # Pass model to enable 70B -> popOS routing
        base_url, client, cb_key = self._resolve_execution_target(model=model, execution_lane=execution_lane)
        cb = cb_service.get_circuit_breaker(cb_key)

        if cb.state.value == "open":
            raise Exception(
                f"{cb_key} circuit breaker is OPEN — skipping call to avoid cascading timeouts"
            )

        try:
            from shared.services.ollama_model_policy import (
                InvocationKind,
                keep_alive_for_invocation,
                num_ctx_for_invocation,
                num_predict_for_invocation,
            )

            kind = invocation_kind if isinstance(invocation_kind, InvocationKind) else None
            opts: dict = {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": num_predict_for_invocation(kind),
            }
            num_ctx = num_ctx_for_invocation(kind)
            if num_ctx is not None:
                opts["num_ctx"] = num_ctx
            model_name = model.value
            if kind == InvocationKind.STRUCTURED_EXTRACTION:
                override = (
                    env_str("BULK_EXTRACTION_MODEL", "").strip()
                    or env_str("OLLAMA_MODEL_EXTRACTION", "").strip()
                )
                if override:
                    model_name = override
            lane = (execution_lane or _llm_execution_lane.get() or "gpu").strip().lower()
            if lane == "cpu":
                cpu_extraction = env_str("BULK_CPU_EXTRACTION_MODEL", "").strip()
                if cpu_extraction:
                    model_name = cpu_extraction
            response = await client.post(
                f"{base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": keep_alive_for_invocation(kind),
                    "options": opts,
                },
            )

            if response.status_code == 200:
                result = response.json()
                await cb._record_success()
                return result.get("response", "")
            else:
                await cb._record_failure()
                raise Exception(f"{cb_key} API error: {response.status_code} - {response.text}")

        except httpx.TimeoutException:
            await cb._record_failure()
            raise Exception(f"{cb_key} request timed out")
        except httpx.ConnectError:
            await cb._record_failure()
            raise Exception(f"Cannot connect to {cb_key} service")
        except Exception as e:
            if "circuit breaker" not in str(e).lower():
                await cb._record_failure()
            raise Exception(f"{cb_key} API error: {str(e)}")

    async def get_model_status(self, timeout_seconds: float | None = None) -> dict[str, Any]:
        """
        Get status of available models.
        Use timeout_seconds (e.g. 1.0) for health checks to avoid blocking when Ollama is busy.
        """
        try:
            if timeout_seconds is not None:
                response = await asyncio.wait_for(
                    self.client.get(f"{self.ollama_base_url}/api/tags"), timeout=timeout_seconds
                )
            else:
                response = await self.client.get(f"{self.ollama_base_url}/api/tags")

            if response.status_code == 200:
                models = response.json().get("models", [])
                available_models = [model["name"] for model in models]

                finisher = ModelType.LLAMA_70B.value
                return {
                    "success": True,
                    "available_models": available_models,
                    "primary_model": ModelType.LLAMA_8B.value,
                    "secondary_model": ModelType.MISTRAL_7B.value,
                    "narrative_finisher_model": finisher,
                    "primary_available": ModelType.LLAMA_8B.value in available_models,
                    "secondary_available": ModelType.MISTRAL_7B.value in available_models,
                    "narrative_finisher_available": finisher in available_models,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {"success": False, "error": f"Ollama API error: {response.status_code}"}

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Ollama busy (timeout) — web requests take priority",
                "primary_available": None,
                "secondary_available": None,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"success": False, "error": f"Cannot connect to Ollama: {str(e)}"}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        if self.cpu_client is not self.client:
            await self.cpu_client.aclose()
        if self.gpu_client is not self.client and self.gpu_client is not self.cpu_client:
            await self.gpu_client.aclose()


# Global LLM service instance
llm_service = LLMService()


def reset_llm_service() -> LLMService:
    """Recreate global LLMService after env routing changes (bulk PopOS offload)."""
    global llm_service
    llm_service = LLMService()
    return llm_service
