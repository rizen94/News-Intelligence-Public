"""
Central rules for which Ollama text model to use (primary, secondary slot, Qwen/Phi, or narrative finisher ~70B).

Used by ollama_model_caller (preferred entry) and LLMService.select_model (TaskType bridge).
Adjust thresholds via config.settings env vars.
"""

from __future__ import annotations

from enum import Enum

from config.settings import (
    OLLAMA_BATCH_PROMPT_CHARS_FOR_SECONDARY,
    OLLAMA_USE_PHI_FOR_FAST_SIMPLE,
    OLLAMA_USE_QWEN_FOR_EXTRACTION,
    OLLAMA_USE_SECONDARY_FOR_EXTRACTION,
)

# Import after settings to avoid cycles at collection time
from shared.services.llm_service import ModelType, TaskType
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str


class InvocationKind(str, Enum):
    """Why we are calling the LLM — drives model selection."""

    REAL_TIME_UI = "real_time_ui"  # user-visible, latency-sensitive
    INTERACTIVE_SUMMARY = "interactive_summary"  # summaries, hub insights
    BACKGROUND_BATCH = "background_batch"  # queue workers, bulk
    STRUCTURED_EXTRACTION = "structured_extraction"  # JSON-ish: entities, claims, events
    LONG_SYNTHESIS = "long_synthesis"  # draft narrative (8B) — not the finisher pass
    STORYLINE_NARRATIVE_FINISH = "storyline_narrative_finish"  # ~70B: permanent storyline editor
    BRIEFING_LEAD = "briefing_lead"  # short editorial lead
    FINANCE_GENERATION_HIGH = "finance_generation_high"  # finance domain high-quality pass
    FAST_SIMPLE = "fast_simple"  # low-latency simple JSON-ish or quality passes (optional Phi)
    DEFAULT = "default"


def resolve_model_for_invocation(
    kind: InvocationKind,
    urgency: str = "standard",
    approx_prompt_chars: int = 0,
) -> ModelType:
    """
    Pick primary, secondary (MODELS[\"secondary\"]), Qwen, Phi, or narrative finisher (settings.NARRATIVE_FINISHER_MODEL).

    Policy:
    - Storyline narrative finish → LLAMA_70B only (final editor; low frequency).
    - Finance high-quality → secondary slot (matches FINANCE_MODELS.generation_high).
    - real_time urgency or REAL_TIME_UI → primary (best latency profile on this stack).
    - Large background batches → secondary when prompt size exceeds
      OLLAMA_BATCH_PROMPT_CHARS_FOR_SECONDARY (VRAM / throughput).
    - Structured extraction → Qwen if OLLAMA_USE_QWEN_FOR_EXTRACTION; else secondary if
      OLLAMA_USE_SECONDARY_FOR_EXTRACTION; else primary.
    - Fast simple → Phi if OLLAMA_USE_PHI_FOR_FAST_SIMPLE; else primary.
    - Long synthesis (draft) → primary — finisher is STORYLINE_NARRATIVE_FINISH, not this kind.
    """
    if kind == InvocationKind.STORYLINE_NARRATIVE_FINISH:
        return ModelType.LLAMA_70B

    if kind == InvocationKind.FINANCE_GENERATION_HIGH:
        return ModelType.MISTRAL_7B

    if kind == InvocationKind.FAST_SIMPLE:
        if OLLAMA_USE_PHI_FOR_FAST_SIMPLE:
            return ModelType.PHI_35
        return ModelType.LLAMA_8B

    if urgency == "real_time" or kind == InvocationKind.REAL_TIME_UI:
        return ModelType.LLAMA_8B

    if kind == InvocationKind.BACKGROUND_BATCH:
        if approx_prompt_chars >= OLLAMA_BATCH_PROMPT_CHARS_FOR_SECONDARY:
            return ModelType.MISTRAL_7B
        return ModelType.LLAMA_8B

    if kind == InvocationKind.STRUCTURED_EXTRACTION:
        if env_bool("OLLAMA_USE_QWEN_FOR_EXTRACTION", OLLAMA_USE_QWEN_FOR_EXTRACTION):
            return ModelType.QWEN_25_7B
        if env_bool("OLLAMA_USE_SECONDARY_FOR_EXTRACTION", OLLAMA_USE_SECONDARY_FOR_EXTRACTION):
            return ModelType.MISTRAL_7B
        return ModelType.LLAMA_8B

    if kind in (
        InvocationKind.LONG_SYNTHESIS,
        InvocationKind.BRIEFING_LEAD,
        InvocationKind.INTERACTIVE_SUMMARY,
    ):
        return ModelType.LLAMA_8B

    return ModelType.LLAMA_8B


def resolve_model_for_llm_task(
    task_type: TaskType,
    urgency: str = "standard",
    approx_prompt_chars: int = 0,
) -> ModelType:
    """Map legacy TaskType + urgency to the same policy as InvocationKind."""
    if urgency == "real_time" or task_type == TaskType.REAL_TIME:
        return resolve_model_for_invocation(InvocationKind.REAL_TIME_UI, urgency, approx_prompt_chars)
    if task_type == TaskType.BATCH_PROCESSING:
        return resolve_model_for_invocation(
            InvocationKind.BACKGROUND_BATCH, urgency, approx_prompt_chars
        )
    if task_type == TaskType.COMPREHENSIVE_ANALYSIS:
        return resolve_model_for_invocation(
            InvocationKind.LONG_SYNTHESIS, urgency, approx_prompt_chars
        )
    if task_type == TaskType.QUICK_SUMMARY:
        return resolve_model_for_invocation(
            InvocationKind.INTERACTIVE_SUMMARY, urgency, approx_prompt_chars
        )
    return resolve_model_for_invocation(InvocationKind.DEFAULT, urgency, approx_prompt_chars)


def extraction_temperature_for_invocation(kind: InvocationKind | None) -> float:
    """Lower temperature for structured JSON extraction."""
    if kind == InvocationKind.STRUCTURED_EXTRACTION:
        try:
            return float(env_str("OLLAMA_EXTRACTION_TEMPERATURE", "0.15"))
        except ValueError:
            return 0.15
    return 0.7


def num_predict_for_invocation(kind: InvocationKind | None) -> int:
    """Token cap by invocation kind — avoids 2000-token budget on short extraction passes."""
    if kind is None:
        return 800
    if kind in (
        InvocationKind.STRUCTURED_EXTRACTION,
        InvocationKind.FAST_SIMPLE,
        InvocationKind.REAL_TIME_UI,
    ):
        try:
            return int(env_str("OLLAMA_EXTRACTION_NUM_PREDICT", "2048"))
        except ValueError:
            return 2048
    if kind in (
        InvocationKind.INTERACTIVE_SUMMARY,
        InvocationKind.BRIEFING_LEAD,
        InvocationKind.BACKGROUND_BATCH,
        InvocationKind.DEFAULT,
    ):
        return 800
    if kind in (InvocationKind.LONG_SYNTHESIS, InvocationKind.STORYLINE_NARRATIVE_FINISH):
        return 2000
    if kind == InvocationKind.FINANCE_GENERATION_HIGH:
        return 1200
    return 800


def num_ctx_for_invocation(kind: InvocationKind | None) -> int | None:
    """Cap context window for extraction — PopOS defaults to 32k which slows inference."""
    import os

    if kind == InvocationKind.STRUCTURED_EXTRACTION:
        try:
            return int(env_str("OLLAMA_EXTRACTION_NUM_CTX", "8192"))
        except ValueError:
            return 8192
    return None


def keep_alive_for_invocation(kind: InvocationKind | None) -> str:
    """Ollama model residency — longer for automation, shorter for UI."""
    if kind in (
        InvocationKind.REAL_TIME_UI,
        InvocationKind.INTERACTIVE_SUMMARY,
    ):
        return "5m"
    return "30m"
