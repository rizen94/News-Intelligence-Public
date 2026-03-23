"""
Finance domain — LLM inference abstraction.
Delegates to shared LLMService with finance model names from settings.
"""

import logging

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import FINANCE_MODELS, MODELS, OLLAMA_HOST
from shared.services.llm_service import LLMService, ModelType
from shared.services.ollama_model_policy import InvocationKind, resolve_model_for_invocation

_llm_service: LLMService | None = None


def get_llm() -> LLMService:
    """Singleton LLM service for finance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(ollama_base_url=OLLAMA_HOST)
    return _llm_service


def _model_key_to_type(key: str) -> ModelType:
    """Map finance model key to shared ModelType (central policy + FINANCE_MODELS names)."""
    if key == "generation_high":
        return resolve_model_for_invocation(InvocationKind.FINANCE_GENERATION_HIGH)
    name = FINANCE_MODELS.get(key, MODELS["primary"])
    if name == MODELS.get("secondary"):
        return ModelType.MISTRAL_7B
    return ModelType.LLAMA_8B


async def generate(
    prompt: str,
    system_prompt: str | None = None,
    model_key: str = "generation_fast",
    *,
    task_id: str | None = None,
    request_id: str | None = None,
    phase: str = "analysis",
    prompt_template_id: str | None = None,
    context_documents: list | None = None,
) -> str:
    """
    Generate text using finance-configured model.
    model_key: classification | generation_fast | generation_high
    """
    import time

    llm = get_llm()
    model = _model_key_to_type(model_key)
    model_name = model.value if hasattr(model, "value") else str(model)
    full_prompt = prompt
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"
    t0 = time.perf_counter()
    try:
        response = await llm._call_ollama(model, full_prompt)
        latency_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.llm_logger import log_llm_interaction

            log_llm_interaction(
                task_id=task_id,
                request_id=request_id,
                phase=phase,
                worker="finance.llm",
                model=model_name,
                prompt_template_id=prompt_template_id,
                prompt=prompt,
                system_prompt=system_prompt or "",
                response=response,
                latency_ms=latency_ms,
                context_documents=context_documents,
                finish_reason="stop",
            )
        except Exception:
            pass
        return response
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        try:
            from shared.logging.llm_logger import log_llm_interaction

            log_llm_interaction(
                task_id=task_id,
                request_id=request_id,
                phase=phase,
                worker="finance.llm",
                model=model_name,
                prompt_template_id=prompt_template_id,
                prompt=prompt,
                system_prompt=system_prompt or "",
                response="",
                latency_ms=latency_ms,
                error=str(e),
            )
        except Exception:
            pass
        logger.warning("Finance LLM generate failed: %s", e)
        raise
