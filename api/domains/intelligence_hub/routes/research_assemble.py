"""Research assembly API — idea → (LLM interpret) → package + spine + draft sections."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/api/research", tags=["Research assemble"])


def _ok(data: Any, message: str | None = None) -> dict[str, Any]:
    return {"success": True, "data": data, "message": message}


@router.post("/assemble")
async def api_research_assemble(
    idea: str = Body(..., embed=True),
    domain_key: str | None = Body(None, embed=True),
    dry_run: bool = Body(False, embed=True),
    interpret: bool = Body(True, embed=True),
    run_spine: bool = Body(True, embed=True),
    attach_limit: int = Body(30, embed=True),
    actor: str = Body("research_assemble", embed=True),
) -> dict[str, Any]:
    """
    Take a natural-language idea, optionally expand it with an LLM, then assemble.

    Flow when interpret=true (default):
      1) LLM turns the idea into entities / assumptions / search queries
      2) Retrieve + attach corpus spine
      3) Optional research spine pass

    Example:
      {"idea": "China dropping US bonds and moving to gold", "domain_key": "finance"}
    """
    from services.research_assemble_service import assemble_from_idea_async

    text = (idea or "").strip()
    if len(text) < 8:
        raise HTTPException(status_code=400, detail="idea must be at least 8 characters")
    result = await assemble_from_idea_async(
        text,
        domain_key=domain_key,
        actor=actor,
        attach_limit=max(5, min(80, int(attach_limit))),
        run_spine=bool(run_spine),
        dry_run=bool(dry_run),
        interpret=bool(interpret),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "assemble failed")
    return _ok(result)


@router.post("/interpret")
async def api_research_interpret(
    idea: str = Body(..., embed=True),
    domain_key: str | None = Body(None, embed=True),
) -> dict[str, Any]:
    """LLM-only: expand an idea into a retrieval brief (no package create)."""
    from services.research_assemble_service import interpret_research_idea

    text = (idea or "").strip()
    if len(text) < 8:
        raise HTTPException(status_code=400, detail="idea must be at least 8 characters")
    result = await interpret_research_idea(text, domain_key=domain_key)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "interpret failed")
    return _ok(result)
