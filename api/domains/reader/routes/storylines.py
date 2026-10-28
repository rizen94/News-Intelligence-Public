"""GET/POST /api/reader/storylines/{id} — longform pack + pull-context."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, Query

from shared.domain_registry import DOMAIN_PATH_PATTERN

from ..services.storyline_pack import build_storyline_reader_pack

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_pull(pull_id: int) -> None:
    from services.article_context_pull_service import run_context_pull_job

    try:
        await run_context_pull_job(pull_id)
    except Exception:
        logger.exception("background storyline context pull %s crashed", pull_id)


def _should_schedule_llm_job(out: dict) -> bool:
    """Only legacy pending rows run Ollama; cache-first ready/cached never do."""
    if out.get("cached") is True:
        return False
    status = str(out.get("status") or "").lower()
    return status == "pending"


@router.get("/storylines/{storyline_id}")
async def reader_storyline_pack(
    storyline_id: int = Path(..., ge=1),
    domain: str = Query(..., pattern=DOMAIN_PATH_PATTERN, description="Domain key"),
):
    try:
        return build_storyline_reader_pack(domain=domain, storyline_id=storyline_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("reader pack failed for %s/%s", domain, storyline_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/storylines/{storyline_id}/pull-context")
async def start_storyline_pull_context(
    background_tasks: BackgroundTasks,
    storyline_id: int = Path(..., ge=1),
    domain: str = Query(..., pattern=DOMAIN_PATH_PATTERN),
):
    """Executive brief for the storyline (cache-first; no on-demand Ollama)."""
    from services.article_context_pull_service import enqueue_storyline_context_pull

    try:
        out = enqueue_storyline_context_pull(domain, storyline_id)
    except Exception as exc:
        logger.exception("enqueue storyline pull-context failed")
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
        "article_id": out.get("article_id"),
        "storyline_id": storyline_id,
        "domain": domain,
        "pull_scope": "storyline",
        "poll_url": f"/api/reader/articles/context-pulls/{pull_id}",
    }
