"""
LLM mid-band confirm for pending storyline_membership_actions.

Mirrors storyline_review_agent_service banding: high LLM confidence applies,
low rejects, ambiguous leaves pending for the Membership UI tab.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

from config.runtime import env_str
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

_MEMBERSHIP_LLM_PROMPT = """You review proposed storyline membership decoupling actions.
Storyline: {storyline_title}
Summary: {storyline_summary}

Pending actions (id | action | article_id | fit | rationale):
{actions_block}

For each action_id reply JSON array only:
[{{"action_id": 1, "decision": "approve"|"reject"|"skip", "confidence": 0.0-1.0, "reason": "short"}}]
Approve means apply the proposed unlink/demote. Reject means leave membership unchanged.
Use skip when uncertain.
"""


def membership_llm_enabled() -> bool:
    return env_str("STORYLINE_MEMBERSHIP_LLM_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def _approve_confidence() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_LLM_APPROVE_CONFIDENCE", "0.65"))
    except ValueError:
        return 0.65


def _reject_confidence() -> float:
    try:
        return float(env_str("STORYLINE_MEMBERSHIP_LLM_REJECT_CONFIDENCE", "0.55"))
    except ValueError:
        return 0.55


def _parse_reviews(raw: str) -> list[dict[str, Any]]:
    if not raw:
        return []
    text = raw.strip()
    # Strip markdown fences
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get("reviews"), list):
            return [x for x in data["reviews"] if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    # Find first array
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except json.JSONDecodeError:
            return []
    return []


def _fetch_pending_article_actions(
    *, limit: int = 40
) -> list[dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, storyline_id, article_id, action,
                       fit_score, rationale
                FROM intelligence.storyline_membership_actions
                WHERE status = 'pending'
                  AND action IN ('unlink', 'demote_relevance')
                  AND article_id IS NOT NULL
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = []
            for r in cur.fetchall():
                rows.append(
                    {
                        "id": int(r[0]),
                        "domain_key": r[1],
                        "storyline_id": int(r[2]),
                        "article_id": int(r[3]) if r[3] is not None else None,
                        "action": r[4],
                        "fit_score": float(r[5]) if r[5] is not None else None,
                        "rationale": r[6] or "",
                    }
                )
            return rows
    except Exception as e:
        logger.debug("_fetch_pending_article_actions: %s", e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _storyline_context(domain_key: str, storyline_id: int) -> tuple[str, str]:
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return f"Storyline {storyline_id}", ""
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title,
                       COALESCE(canonical_narrative, master_summary, summary, '')
                FROM {schema}.storylines WHERE id = %s
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                return f"Storyline {storyline_id}", ""
            return str(row[0] or f"Storyline {storyline_id}"), str(row[1] or "")[:600]
    except Exception:
        return f"Storyline {storyline_id}", ""
    finally:
        try:
            conn.close()
        except Exception:
            pass


async def _llm_review_group(
    items: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    from shared.services.llm_service import LLMService, ModelType
    from shared.services.ollama_model_policy import InvocationKind
    from services.storyline_membership_review_service import apply_membership_action

    stats = {"approved": 0, "rejected": 0, "skipped": 0, "errors": 0}
    if not items:
        return stats
    dk = items[0]["domain_key"]
    sid = items[0]["storyline_id"]
    title, summary = _storyline_context(dk, sid)
    block = []
    id_set = set()
    for it in items:
        id_set.add(it["id"])
        fit = it.get("fit_score")
        fit_s = f"{fit:.3f}" if fit is not None else "n/a"
        block.append(
            f"{it['id']} | {it['action']} | article={it.get('article_id')} | "
            f"fit={fit_s} | {(it.get('rationale') or '')[:120]}"
        )
    prompt = _MEMBERSHIP_LLM_PROMPT.format(
        storyline_title=title[:200],
        storyline_summary=summary[:600],
        actions_block="\n".join(block),
    )
    llm = LLMService()
    try:
        raw = await llm._call_ollama(
            ModelType.LLAMA_8B,
            prompt,
            invocation_kind=InvocationKind.STRUCTURED_EXTRACTION,
            batch_size=len(items),
        )
    except Exception as e:
        logger.warning("membership LLM failed storyline=%s: %s", sid, e)
        stats["errors"] += len(items)
        return stats

    reviews = _parse_reviews(raw or "")
    if not reviews:
        stats["skipped"] += len(items)
        return stats

    approve_at = _approve_confidence()
    reject_at = _reject_confidence()
    for rev in reviews:
        aid = rev.get("action_id")
        if aid is None or int(aid) not in id_set:
            continue
        aid = int(aid)
        decision = str(rev.get("decision") or "skip").lower()
        conf = float(rev.get("confidence") or 0.0)
        if dry_run:
            if decision == "approve" and conf >= approve_at:
                stats["approved"] += 1
            elif decision == "reject" and conf >= reject_at:
                stats["rejected"] += 1
            else:
                stats["skipped"] += 1
            continue
        if decision == "approve" and conf >= approve_at:
            out = apply_membership_action(aid, approve=True)
            if out.get("success"):
                stats["approved"] += 1
            else:
                stats["skipped"] += 1
        elif decision == "reject" and conf >= reject_at:
            out = apply_membership_action(aid, approve=False)
            if out.get("success"):
                stats["rejected"] += 1
            else:
                stats["skipped"] += 1
        else:
            stats["skipped"] += 1
    return stats


async def run_membership_llm_midband(
    *,
    batch_limit: int = 40,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Process pending mid-band membership actions with 8B confirm."""
    if not membership_llm_enabled() and not dry_run:
        # Allow dry_run path when explicitly testing even if flag off? Plan says flag gates.
        return {"enabled": False, "approved": 0, "rejected": 0, "skipped": 0}
    rows = _fetch_pending_article_actions(limit=batch_limit)
    by_sl: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_sl[(r["domain_key"], r["storyline_id"])].append(r)
    totals = {"approved": 0, "rejected": 0, "skipped": 0, "errors": 0, "groups": 0}
    for (_dk, _sid), items in by_sl.items():
        totals["groups"] += 1
        st = await _llm_review_group(items, dry_run=dry_run)
        for k in ("approved", "rejected", "skipped", "errors"):
            totals[k] += int(st.get(k, 0) or 0)
    totals["enabled"] = True
    totals["fetched"] = len(rows)
    return totals
