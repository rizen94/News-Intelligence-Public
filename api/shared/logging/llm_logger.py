"""
LLM Interaction Ledger — structured logging for every LLM call.
Captures model, tokens, context documents, eval scores, latency, cost.
Writes to logs/llm_interactions.jsonl and activity.jsonl (event_type=llm_interaction).
When file write or activity_logger forward fails, the write is no-op (failure swallowed).
"""

import hashlib
import json
import threading
import time
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

# Lazy init
_LOG_DIR: Path | None = None
_INITIALIZED = False
_LOCK = threading.Lock()


def _ensure_init() -> Path:
    global _LOG_DIR, _INITIALIZED
    if _INITIALIZED and _LOG_DIR:
        return _LOG_DIR
    with _LOCK:
        if _INITIALIZED and _LOG_DIR:
            return _LOG_DIR
        try:
            from config.paths import LOG_DIR

            _LOG_DIR = Path(LOG_DIR)
        except Exception:
            _LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _INITIALIZED = True
    return _LOG_DIR


def _hash_text(text: str) -> str:
    """Short hash of text for dedup without storing full content."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16] if text else ""


def _log_full_text() -> bool:
    """Whether to log full prompt/response (dev: true, prod: false)."""
    try:
        from config.settings import LOG_LLM_FULL_TEXT

        return bool(LOG_LLM_FULL_TEXT)
    except Exception:
        return False


@dataclass
class LLMInteractionRecord:
    interaction_id: str
    task_id: str | None
    request_id: str | None
    phase: str
    worker: str
    model: str
    prompt_template_id: str | None
    prompt_hash: str
    system_prompt_hash: str
    input_token_count: int | None
    context_documents: list[dict]
    output_token_count: int | None
    response_hash: str
    latency_ms: float
    finish_reason: str | None
    self_eval_score: float | None
    downstream_eval_score: float | None
    eval_criteria: str | None
    estimated_cost_usd: float | None
    timestamp: str
    prompt_text: str | None
    response_text: str | None


def log_llm_interaction(
    *,
    task_id: str | None = None,
    request_id: str | None = None,
    phase: str = "unknown",
    worker: str = "unknown",
    model: str,
    prompt_template_id: str | None = None,
    prompt: str = "",
    system_prompt: str | None = "",
    input_token_count: int | None = None,
    context_documents: list[dict] | None = None,
    response: str = "",
    output_token_count: int | None = None,
    latency_ms: float = 0,
    finish_reason: str | None = None,
    self_eval_score: float | None = None,
    downstream_eval_score: float | None = None,
    eval_criteria: str | None = None,
    estimated_cost_usd: float | None = None,
    log_full_text: bool | None = None,
    **extra: Any,
) -> str:
    """
    Log a single LLM interaction. Returns interaction_id.
    """
    interaction_id = f"llm-{uuid.uuid4().hex[:12]}"
    ts = datetime.now(timezone.utc).isoformat()
    full_text = log_full_text if log_full_text is not None else _log_full_text()

    record = LLMInteractionRecord(
        interaction_id=interaction_id,
        task_id=task_id,
        request_id=request_id,
        phase=phase,
        worker=worker,
        model=model,
        prompt_template_id=prompt_template_id,
        prompt_hash=_hash_text(prompt),
        system_prompt_hash=_hash_text(system_prompt or ""),
        input_token_count=input_token_count,
        context_documents=context_documents or [],
        output_token_count=output_token_count,
        response_hash=_hash_text(response),
        latency_ms=round(latency_ms, 2),
        finish_reason=finish_reason,
        self_eval_score=self_eval_score,
        downstream_eval_score=downstream_eval_score,
        eval_criteria=eval_criteria,
        estimated_cost_usd=estimated_cost_usd,
        timestamp=ts,
        prompt_text=prompt[:5000] if full_text and prompt else None,
        response_text=response[:5000] if full_text and response else None,
    )

    entry = {k: v for k, v in asdict(record).items() if v is not None}
    entry.update(extra)

    log_dir = _ensure_init()
    try:
        with open(log_dir / "llm_interactions.jsonl", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        pass

    try:
        from shared.logging.activity_logger import log_activity

        simple = {
            k: v
            for k, v in entry.items()
            if k not in ("prompt_text", "response_text", "context_documents")
        }
        if context_documents:
            simple["context_doc_count"] = len(context_documents)
        log_activity(
            component="llm",
            event_type="llm_interaction",
            status="success",
            message=f"LLM {phase} {model} {latency_ms:.0f}ms",
            **simple,
        )
    except Exception:
        pass

    return interaction_id


def track_llm_call(
    phase: str = "unknown",
    worker: str = "unknown",
    prompt_template_id: str | None = None,
):
    """
    Decorator for LLM call functions. Captures timing and logs to ledger.
    Use on async functions that return (response: str) or raise.
    """

    def decorator(f: Callable[..., Coroutine[Any, Any, str]]):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            task_id = kwargs.get("task_id")
            request_id = kwargs.get("request_id")
            try:
                result = await f(*args, **kwargs)
                latency_ms = (time.perf_counter() - t0) * 1000
                log_llm_interaction(
                    task_id=task_id,
                    request_id=request_id,
                    phase=phase,
                    worker=worker,
                    model=kwargs.get("model", "unknown"),
                    prompt_template_id=prompt_template_id,
                    prompt=kwargs.get("prompt", ""),
                    system_prompt=kwargs.get("system_prompt"),
                    response=result if isinstance(result, str) else str(result),
                    latency_ms=latency_ms,
                    context_documents=kwargs.get("context_documents"),
                )
                return result
            except Exception as e:
                latency_ms = (time.perf_counter() - t0) * 1000
                log_llm_interaction(
                    task_id=task_id,
                    request_id=request_id,
                    phase=phase,
                    worker=worker,
                    model=kwargs.get("model", "unknown"),
                    prompt_template_id=prompt_template_id,
                    prompt=kwargs.get("prompt", ""),
                    system_prompt=kwargs.get("system_prompt"),
                    response="",
                    latency_ms=latency_ms,
                    error=str(e),
                    status="error",
                )
                raise

        return wrapper

    return decorator
