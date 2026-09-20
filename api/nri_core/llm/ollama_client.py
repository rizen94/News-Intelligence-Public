"""NRI-owned Ollama client — routes to PopOS 5090, no NI imports."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from nri_core.config import get_config

JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


def _role_model(role: str) -> str:
    """
    Resolve NRI role → Ollama tag via shared SoT when available.

    NRI roles: reasoner/skeptic → extract, deep → finish, else extract.
    Falls back to env defaults when shared.llm_service is not importable.
    """
    role_l = (role or "").strip().lower()
    try:
        from shared.services.llm_service import ModelType, resolve_model_tag

        if role_l == "deep":
            return resolve_model_tag(ModelType.FINISH)
        if role_l in ("reasoner", "skeptic", "extract", "extraction"):
            return resolve_model_tag(ModelType.EXTRACT)
        if role_l in ("low", "phi", "fast"):
            return resolve_model_tag(ModelType.LOW)
        if role_l in ("high", "secondary"):
            return resolve_model_tag(ModelType.HIGH)
        return resolve_model_tag(ModelType.DEFAULT)
    except Exception:
        extraction = (os.environ.get("OLLAMA_MODEL_EXTRACTION") or "qwen3.6:latest").strip()
        primary = (os.environ.get("OLLAMA_MODEL_PRIMARY") or "llama3.1:8b").strip()
        if role_l in ("reasoner", "skeptic"):
            return extraction or "qwen3.6:latest"
        if role_l == "deep":
            return (
                (os.environ.get("OLLAMA_NARRATIVE_FINISHER_MODEL") or "").strip()
                or extraction
                or primary
                or "qwen3.6:latest"
            )
        return extraction or primary or "llama3.1:8b"


def _priority_headers() -> dict[str, str]:
    """LOW by default so NI/NRI never looks like interactive HIGH on the proxy."""
    raw = (os.environ.get("OLLAMA_PRIORITY") or "low").strip().lower()
    if raw in ("high", "interactive"):
        return {"X-Ollama-Priority": "high"}
    return {"X-Ollama-Priority": "low"}


def chat_json(prompt: str, role: str = "reasoner", timeout: float = 120.0) -> dict[str, Any]:
    cfg = get_config()
    model = _role_model(role)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    url = f"{cfg.ollama_url.rstrip('/')}/api/generate"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=_priority_headers())
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return _fallback_response(role)

    response_text = data.get("response", "{}")
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        match = JSON_BLOCK_RE.search(response_text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return _fallback_response(role)


def _fallback_response(role: str) -> dict[str, Any]:
    """Offline/test fallback when Ollama unreachable."""
    return {
        "mundane_explanation": "Routine co-occurrence may reflect shared news cycle coverage.",
        "competing_hypotheses": ["Coincidental coverage", "Shared sector reporting"],
        "cheapest_test": "Check whether entities share a parent company or event filing.",
        "confidence": 0.25,
        "causal_claims": [],
        "findings": ["Insufficient evidence for causal claim"],
        "confidence_downgrade": 0.2,
        "refutation_recommended": False,
        "causal_language_flags": [],
        "_fallback": True,
        "_role": role,
    }


def health_check() -> bool:
    cfg = get_config()
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{cfg.ollama_url.rstrip('/')}/api/tags")
            return r.status_code == 200
    except httpx.HTTPError:
        return False
