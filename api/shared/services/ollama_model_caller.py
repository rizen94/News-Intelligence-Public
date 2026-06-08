"""
Central Ollama caller: chooses model from InvocationKind + policy, then invokes LLMService.

Prefer this for new code instead of hardcoding ModelType or REST URLs.
Embeddings use the same Ollama host as settings.MODELS["embedding"].
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Optional

import httpx

from config.settings import MODELS, OLLAMA_HOST, OLLAMA_TIMEOUT

from shared.services.llm_service import LLMService, ModelType, llm_service
from shared.services.optional_llm_redis_cache import cache_get, cache_set
from shared.services.ollama_model_policy import InvocationKind, resolve_model_for_invocation

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    text: str
    model: str
    kind: InvocationKind


class OllamaModelCaller:
    """
    Single entry for text generation and embedding calls with policy-based model selection.
    """

    def __init__(self, llm: Optional[LLMService] = None):
        self._llm = llm or llm_service
        base = (self._llm.ollama_base_url or OLLAMA_HOST).rstrip("/")
        self._ollama_base_url = base
        self._embedding_model = MODELS.get("embedding", "nomic-embed-text")

    def resolve_text_model(
        self,
        kind: InvocationKind,
        urgency: str = "standard",
        approx_prompt_chars: int = 0,
    ) -> ModelType:
        return resolve_model_for_invocation(kind, urgency, approx_prompt_chars)

    @staticmethod
    def _execution_lane_for_kind(kind: InvocationKind) -> str:
        """Default lane policy by invocation purpose."""
        gpu_kinds = {
            InvocationKind.LONG_SYNTHESIS,
            InvocationKind.STORYLINE_NARRATIVE_FINISH,
            InvocationKind.BRIEFING_LEAD,
            InvocationKind.FINANCE_GENERATION_HIGH,
            InvocationKind.INTERACTIVE_SUMMARY,
        }
        return "gpu" if kind in gpu_kinds else "cpu"

    async def generate(
        self,
        prompt: str,
        *,
        kind: InvocationKind,
        urgency: str = "standard",
        approx_prompt_chars: Optional[int] = None,
    ) -> GenerationResult:
        """
        Run /api/generate with the model chosen by policy.

        approx_prompt_chars: defaults to len(prompt) for batch thresholding.
        """
        chars = approx_prompt_chars if approx_prompt_chars is not None else len(prompt or "")
        model = self.resolve_text_model(kind, urgency, chars)
        logger.debug(
            "ollama_caller.generate kind=%s urgency=%s chars=%s model=%s",
            kind.value,
            urgency,
            chars,
            model.value,
        )
        cached = cache_get(prompt=prompt or "", model=model.value, kind=kind.value)
        if cached is not None:
            return GenerationResult(text=cached, model=model.value, kind=kind)
        text = await self._llm._call_ollama(
            model,
            prompt,
            execution_lane=self._execution_lane_for_kind(kind),
            invocation_kind=kind,
        )
        out = text or ""
        # Do not cache empty responses — allows retry after transient failures
        if out.strip():
            cache_set(prompt=prompt or "", model=model.value, kind=kind.value, text=out)
        return GenerationResult(text=out, model=model.value, kind=kind)

    def _embedding_base_url(self) -> str:
        """Match batch LLM routing: CPU host when dual-host is enabled."""
        if self._llm.dual_host_enabled:
            return self._llm.ollama_cpu_host.rstrip("/")
        return self._ollama_base_url

    async def embed_text(self, text: str) -> tuple[List[float], str]:
        """
        Single-document embedding via Ollama /api/embeddings.
        Returns (vector, model_name).
        """
        payload = {"model": self._embedding_model, "prompt": text}
        base = self._embedding_base_url()
        async with httpx.AsyncClient(timeout=float(OLLAMA_TIMEOUT)) as client:
            r = await client.post(f"{base}/api/embeddings", json=payload)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                raise ValueError("Ollama embeddings response is not a JSON object")
            emb = data.get("embedding")
            if not isinstance(emb, list):
                raise ValueError("Ollama embeddings response missing embedding array")
            return emb, self._embedding_model

    async def embed_batch(self, texts: List[str]) -> List[tuple[List[float], str]]:
        """Sequential embeddings (Ollama typically one request per doc)."""
        out: List[tuple[List[float], str]] = []
        for t in texts:
            out.append(await self.embed_text(t))
        return out


_caller: Optional[OllamaModelCaller] = None


def get_ollama_model_caller() -> OllamaModelCaller:
    global _caller
    if _caller is None:
        _caller = OllamaModelCaller()
    return _caller
