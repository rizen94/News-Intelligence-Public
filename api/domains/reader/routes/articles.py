"""GET/POST /api/reader/articles/... — Pull context executive summaries."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_pull(pull_id: int) -> None:
    from services.article_context_pull_service import run_context_pull_job

    try:
        await run_context_pull_job(pull_id)
    except Exception:
        logger.exception("background context pull %s crashed", pull_id)


def _should_schedule_llm_job(out: dict) -> bool:
    """Only legacy pending rows run Ollama; cache-first ready/cached never do."""
    if out.get("cached") is True:
        return False
    status = str(out.get("status") or "").lower()
    return status == "pending"


@router.post("/articles/{article_id}/pull-context")
async def start_pull_context(
    article_id: int,
    background_tasks: BackgroundTasks,
    domain: str = Query("politics"),
    storyline_id: int | None = Query(None),
):
    """Enqueue living-context executive summary (vault + RAG + article).

    Cache-first: morning expansion / prior pull / deferred message return as
    status=ready without scheduling Ollama.
    """
    from services.article_context_pull_service import enqueue_context_pull

    try:
        out = enqueue_context_pull(domain, article_id, storyline_id=storyline_id)
    except Exception as exc:
        logger.exception("enqueue pull-context failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not out.get("ok"):
        raise HTTPException(status_code=404, detail=out.get("error") or "failed")
    pull_id = int(out["id"])
    status = str(out.get("status") or "pending")
    if _should_schedule_llm_job(out):
        background_tasks.add_task(_run_pull, pull_id)
        status = "pending"
    return {
        "ok": True,
        "pull_id": pull_id,
        "id": pull_id,
        "status": status,
        "cached": bool(out.get("cached")),
        "cache_source": out.get("cache_source"),
        "summary_markdown": out.get("summary_markdown"),
        "article_id": out.get("article_id", article_id),
        "domain": domain,
        "poll_url": f"/api/reader/articles/context-pulls/{pull_id}",
    }


@router.get("/articles/context-pulls/{pull_id}")
async def get_pull_context(pull_id: int):
    from services.article_context_pull_service import get_context_pull

    try:
        out = get_context_pull(pull_id)
    except Exception as exc:
        logger.exception("get pull-context failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not out:
        raise HTTPException(status_code=404, detail="not_found")
    return out


@router.get("/articles/{article_id}/pull-context")
async def latest_pull_context(
    article_id: int,
    domain: str = Query("politics"),
):
    """Latest pull for this article (if any)."""
    from services.article_context_pull_service import latest_context_pull

    try:
        out = latest_context_pull(domain, article_id)
    except Exception as exc:
        logger.exception("latest pull-context failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not out:
        return {
            "ok": True,
            "article_id": article_id,
            "domain_key": domain,
            "status": "absent",
            "summary_markdown": None,
        }
    return out
