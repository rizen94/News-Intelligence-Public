"""
Promotion bridge — apply high-score tracking discovery candidates to NI automation.

Respects Phase 2 demotion: calls storyline_assembly (not standalone discovery phases).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from config.runtime import env_int

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLDS: dict[str, int] = {
    "storyline": 20,
    "context_thread": 18,
    "entity_hub": 15,
    "cross_domain_bridge": 18,
    "investigation_lead": 99,  # manual / work-queue only
}


def _threshold(candidate_type: str) -> int:
    env_key = f"TRACKING_PROMOTE_{candidate_type.upper()}_MIN_SCORE"
    from config.runtime import env_int as _ei

    return _ei(env_key, _DEFAULT_THRESHOLDS.get(candidate_type, 99))


async def apply_promotions(
    candidates: list[dict[str, Any]],
    *,
    top_n: int | None = None,
) -> dict[str, Any]:
    """Apply promotions for top-ranked candidates above type thresholds."""
    top_n = top_n or env_int("TRACKING_PROMOTION_TOP_N", 5)
    actions: list[dict[str, Any]] = []
    promoted = 0

    eligible = [
        c
        for c in candidates
        if c.get("status") == "candidate" and c.get("score", 0) >= _threshold(str(c.get("type", "")))
    ]
    eligible.sort(key=lambda x: x.get("score", 0), reverse=True)

    for c in eligible[:top_n]:
        ctype = str(c.get("type", ""))
        dk = c.get("domain_key") or (c.get("domain_keys") or [None])[0]
        try:
            if ctype == "storyline" and dk:
                from services.storyline_assembly_service import run_storyline_assembly_for_domain

                result = await run_storyline_assembly_for_domain(
                    str(dk),
                    run_proactive=False,
                    run_discovery=True,
                    run_automation=True,
                )
                actions.append(
                    {
                        "type": ctype,
                        "domain_key": dk,
                        "title": c.get("title"),
                        "action": "storyline_assembly",
                        "result": {
                            "unlinked_before": result.get("unlinked_before"),
                            "unlinked_after": result.get("unlinked_after"),
                        },
                    }
                )
                promoted += 1
                # Vault stub when we have a concrete storyline id
                sid = c.get("storyline_id")
                if sid:
                    from services import vault_bridge_service as vb

                    vb.write_story_stub(
                        domain_key=str(dk),
                        storyline_id=int(sid),
                        title=str(c.get("title") or f"Storyline {sid}"),
                    )
            elif ctype == "context_thread":
                actions.append(
                    {
                        "type": ctype,
                        "domain_key": dk,
                        "context_id": c.get("context_id"),
                        "title": c.get("title"),
                        "action": "work_queue_only",
                        "note": "Create tracked_event draft via Investigate UI",
                    }
                )
            elif ctype == "entity_hub":
                actions.append(
                    {
                        "type": ctype,
                        "entity_profile_id": c.get("entity_profile_id"),
                        "action": "vault_entity_hub",
                        "note": "Queue dossier / 40_Reference/entities/",
                    }
                )
            elif ctype == "cross_domain_bridge":
                actions.append(
                    {
                        "type": ctype,
                        "title": c.get("title"),
                        "action": "cross_domain_synthesis",
                        "domain_keys": c.get("domain_keys"),
                    }
                )
            else:
                actions.append(
                    {
                        "type": ctype,
                        "title": c.get("title"),
                        "action": "append_work_queue",
                    }
                )
        except Exception as e:
            logger.warning("promotion %s: %s", ctype, e)
            actions.append({"type": ctype, "error": str(e)})

    return {"success": True, "promoted_count": promoted, "actions": actions}


def apply_promotions_sync(candidates: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    return asyncio.get_event_loop().run_until_complete(apply_promotions(candidates, **kwargs))
