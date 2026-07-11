"""
LLM agent for the storyline review queue (public.storyline_article_suggestions).

Drains pending approve/reject decisions using:
  1. Score fast-path (high combined_score → approve, very low → reject)
  2. Batched LLM review grouped by storyline (8B)

Reuses bulk approve/reject DB logic from storyline_automation_bulk.
"""

from collections import defaultdict

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from config.runtime import env_int, env_str
from shared.database.connection import get_db_connection
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.services.llm_service import LLMService, ModelType
from shared.services.ollama_model_policy import InvocationKind

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """You are a news intelligence curator. For each article suggestion below, decide whether it belongs on the given storyline.

A suggestion should be APPROVED only if the article clearly continues or directly reports on the same specific story thread — not merely a loosely related topic or shared keyword.

STORYLINE: {storyline_title}
STORYLINE SUMMARY: {storyline_summary}

SUGGESTIONS (id | title | summary snippet | combined_score | prior_reasoning):
{suggestions_block}

Respond with ONLY a JSON array. Each entry:
- "suggestion_id": integer id from the list
- "decision": "approve" or "reject"
- "confidence": 0.0 to 1.0
- "reason_code": one of not_relevant, duplicate, low_quality, wrong_storyline, other
- "reason": brief explanation (max 25 words)

Example:
[{{"suggestion_id": 12, "decision": "approve", "confidence": 0.92, "reason_code": "other", "reason": "same policy vote coverage"}}]
"""


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_agent_reviews(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                text = part
                break
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _auto_approve_score() -> float:
    try:
        return float(env_str("STORYLINE_REVIEW_AUTO_APPROVE_SCORE", "0.85"))
    except ValueError:
        return 0.85


def _auto_reject_score() -> float:
    try:
        return float(env_str("STORYLINE_REVIEW_AUTO_REJECT_SCORE", "0.45"))
    except ValueError:
        return 0.45


def _llm_approve_confidence() -> float:
    try:
        return float(env_str("STORYLINE_REVIEW_LLM_APPROVE_CONFIDENCE", "0.65"))
    except ValueError:
        return 0.65


def _llm_batch_size() -> int:
    return max(1, min(20, env_int("STORYLINE_REVIEW_LLM_ITEMS", 8)))


def _fetch_pending_batch(
    *,
    domain_key: str,
    schema: str,
    limit: int,
    min_score: float | None = None,
    max_score: float | None = None,
) -> list[dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    where = "WHERE s.domain_key = %s AND s.status = 'pending'"
    params: list[Any] = [domain_key]
    if min_score is not None:
        where += " AND s.combined_score >= %s"
        params.append(min_score)
    if max_score is not None:
        where += " AND s.combined_score < %s"
        params.append(max_score)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id, s.storyline_id, sl.title,
                       COALESCE(NULLIF(TRIM(sl.master_summary), ''),
                                NULLIF(TRIM(sl.timeline_summary), ''),
                                NULLIF(TRIM(sl.description), ''),
                                sl.title) AS storyline_summary,
                       s.article_id, s.combined_score, s.reasoning,
                       a.title, LEFT(COALESCE(a.summary, a.content, ''), 400)
                FROM public.storyline_article_suggestions s
                JOIN {schema}.articles a ON s.article_id = a.id
                JOIN {schema}.storylines sl ON s.storyline_id = sl.id
                {where}
                ORDER BY s.storyline_id, s.combined_score DESC, s.suggested_at ASC
                LIMIT %s
                """,
                params + [limit],
            )
            rows = cur.fetchall()
        return [
            {
                "suggestion_id": int(r[0]),
                "storyline_id": int(r[1]),
                "storyline_title": r[2] or "",
                "storyline_summary": _strip_html(str(r[3] or ""))[:800],
                "article_id": int(r[4]),
                "combined_score": float(r[5] or 0),
                "prior_reasoning": r[6] or "",
                "article_title": r[7] or "",
                "article_snippet": _strip_html(str(r[8] or ""))[:400],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("storyline_review_agent fetch %s: %s", domain_key, e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _apply_approve(cur, *, domain_key: str, schema: str, storyline_id: int, suggestion_id: int) -> bool:
    from domains.storyline_management.routes.storyline_automation_bulk import (
        _approve_suggestion_row,
    )

    ok, _err = _approve_suggestion_row(
        cur,
        domain=domain_key,
        schema=schema,
        storyline_id=storyline_id,
        suggestion_id=suggestion_id,
    )
    return ok


def _apply_reject(
    cur,
    *,
    domain_key: str,
    suggestion_id: int,
    reason_code: str,
    reason: str,
) -> bool:
    notes = f"agent:{reason_code}: {reason}"[:500]
    cur.execute(
        """
        UPDATE public.storyline_article_suggestions
        SET status = 'rejected', reviewed_at = %s, review_notes = %s
        WHERE id = %s AND domain_key = %s AND status = 'pending'
        """,
        (datetime.now(), notes, suggestion_id, domain_key),
    )
    return cur.rowcount > 0


async def _llm_review_storyline_group(
    items: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> dict[str, int]:
    """Review one storyline's suggestion batch via LLM."""
    stats = {"approved": 0, "rejected": 0, "skipped": 0, "errors": 0}
    if not items:
        return stats

    # Track consecutive parse failures to eventually mark items as needs_manual_review
    # Threshold: after 3 consecutive failures, mark as needs_manual_review
    MAX_CONSECUTIVE_FAILURES = 3
    failure_counts: Dict[int, int] = defaultdict(int)
    items_to_process = items.copy()

    storyline_title = items[0]["storyline_title"]
    storyline_summary = items[0]["storyline_summary"]
    block_lines = []
    id_set: set[int] = set()
    for it in items:
        sid = it["suggestion_id"]
        id_set.add(sid)
        block_lines.append(
            f"{sid} | {it['article_title'][:120]} | {it['article_snippet'][:200]} | "
            f"score={it['combined_score']:.2f} | {it['prior_reasoning'][:80]}"
        )

    prompt = REVIEW_PROMPT.format(
        storyline_title=storyline_title[:200],
        storyline_summary=storyline_summary[:600],
        suggestions_block="\n".join(block_lines),
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
        logger.warning("storyline_review_agent LLM failed storyline=%s: %s", storyline_title[:40], e)
        stats["errors"] += len(items)
        # Increment failure count for all items since the entire batch failed
        for item in items:
            failure_counts[item["suggestion_id"]] += 1
        return stats

    reviews = _parse_agent_reviews(raw)
    if not reviews:
        stats["skipped"] += len(items)
        # Increment failure count for all items since parsing failed completely
        for item in items:
            failure_counts[item["suggestion_id"]] += 1
        return stats

    # Process successful reviews
    reviewed_suggestion_ids = {rev.get("suggestion_id") for rev in reviews if rev.get("suggestion_id") is not None}
    for item in items:
        sid = item["suggestion_id"]
        if sid in reviewed_suggestion_ids:
            # Reset failure count on successful parse
            failure_counts[sid] = 0

    domain_key = items[0].get("_domain_key", "")
    schema = items[0].get("_schema", "")
    storyline_id = items[0]["storyline_id"]
    approve_threshold = _llm_approve_confidence()

    conn = get_db_connection()
    if not conn:
        stats["errors"] += len(items)
        return stats

    try:
        with conn.cursor() as cur:
            for rev in reviews:
                sid = rev.get("suggestion_id")
                if sid is None or int(sid) not in id_set:
                    continue
                sid = int(sid)
                decision = str(rev.get("decision", "")).lower()
                confidence = float(rev.get("confidence", 0) or 0)
                reason_code = str(rev.get("reason_code") or "other")[:40]
                reason = str(rev.get("reason") or "")[:200]

                if dry_run:
                    if decision == "approve" and confidence >= approve_threshold:
                        stats["approved"] += 1
                    elif decision == "reject" or confidence < approve_threshold:
                        stats["rejected"] += 1
                    else:
                        stats["skipped"] += 1
                    continue

                if decision == "approve" and confidence >= approve_threshold:
                    if _apply_approve(
                        cur,
                        domain_key=domain_key,
                        schema=schema,
                        storyline_id=storyline_id,
                        suggestion_id=sid,
                    ):
                        stats["approved"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    if _apply_reject(
                        cur,
                        domain_key=domain_key,
                        suggestion_id=sid,
                        reason_code=reason_code,
                        reason=reason,
                    ):
                        stats["rejected"] += 1
                    else:
                        stats["skipped"] += 1
            if not dry_run:
                conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning("storyline_review_agent apply: %s", e)
        stats["errors"] += 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # After processing, check for items that have exceeded max consecutive failures
    # and mark them as needs_manual_review
    for item in items:
        sid = item["suggestion_id"]
        if failure_counts[sid] >= MAX_CONSECUTIVE_FAILURES:
            # Mark this item as needs_manual_review instead of leaving it pending
            if not dry_run:
                try:
                    conn = get_db_connection()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                UPDATE public.storyline_article_suggestions
                                SET status = 'needs_manual_review', reviewed_at = %s, review_notes = %s
                                WHERE id = %s AND domain_key = %s AND status = 'pending'
                                """,
                                (datetime.now(), f"auto:max_consecutive_failures({failure_counts[sid]})", sid, domain_key),
                            )
                            if cur.rowcount > 0:
                                logger.info(
                                    "Marked suggestion %s as needs_manual_review after %s consecutive failures",
                                    sid,
                                    failure_counts[sid],
                                )
                                # Don't count this as skipped/error since we're handling it specially
                            conn.commit()
                        except Exception as e:
                            logger.warning("Failed to mark suggestion %s as needs_manual_review: %s", sid, e)
                            if conn:
                                conn.rollback()
                        finally:
                            if conn:
                                conn.close()
                else:
                    # In dry run, just count it as skipped for stats purposes
                    stats["skipped"] += 1

    return stats


def _score_fast_path(
    *,
    domain_key: str,
    schema: str,
    limit: int,
    dry_run: bool,
) -> dict[str, int]:
    """Auto-approve/reject by combined_score without LLM."""
    stats = {"approved": 0, "rejected": 0, "skipped": 0, "errors": 0}
    approve_at = _auto_approve_score()
    reject_below = _auto_reject_score()

    high = _fetch_pending_batch(
        domain_key=domain_key,
        schema=schema,
        limit=limit,
        min_score=approve_at,
    )
    low = _fetch_pending_batch(
        domain_key=domain_key,
        schema=schema,
        limit=limit,
        max_score=reject_below,
    )

    conn = get_db_connection()
    if not conn:
        return stats

    try:
        with conn.cursor() as cur:
            for row in high:
                if dry_run:
                    stats["approved"] += 1
                    continue
                if _apply_approve(
                    cur,
                    domain_key=domain_key,
                    schema=schema,
                    storyline_id=row["storyline_id"],
                    suggestion_id=row["suggestion_id"],
                ):
                    stats["approved"] += 1
                else:
                    stats["skipped"] += 1
            for row in low:
                if dry_run:
                    stats["rejected"] += 1
                    continue
                if _apply_reject(
                    cur,
                    domain_key=domain_key,
                    suggestion_id=row["suggestion_id"],
                    reason_code="low_quality",
                    reason=f"auto-reject combined_score={row['combined_score']:.2f}",
                ):
                    stats["rejected"] += 1
                else:
                    stats["skipped"] += 1
        if not dry_run:
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning("storyline_review_agent score path: %s", e)
        stats["errors"] += 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return stats


async def run_storyline_review_agent_for_domain(
    domain_key: str,
    *,
    batch_limit: int | None = None,
    dry_run: bool = False,
    llm_only: bool = False,
) -> dict[str, Any]:
    """Process one batch for a domain. Returns aggregate stats."""
    schema = resolve_domain_schema(domain_key)
    limit = batch_limit or max(10, min(200, env_int("STORYLINE_REVIEW_BATCH_SIZE", 60)))

    totals: dict[str, int] = {"approved": 0, "rejected": 0, "skipped": 0, "errors": 0, "llm_calls": 0}

    if not llm_only:
        score_stats = _score_fast_path(
            domain_key=domain_key, schema=schema, limit=limit, dry_run=dry_run
        )
        for k in totals:
            if k in score_stats:
                totals[k] += score_stats[k]

    approve_at = _auto_approve_score()
    reject_below = _auto_reject_score()
    llm_candidates = _fetch_pending_batch(
        domain_key=domain_key,
        schema=schema,
        limit=limit,
        min_score=reject_below,
        max_score=approve_at,
    )

    # Group by storyline
    by_storyline: dict[int, list[dict[str, Any]]] = {}
    for row in llm_candidates:
        row["_domain_key"] = domain_key
        row["_schema"] = schema
        by_storyline.setdefault(row["storyline_id"], []).append(row)

    chunk = _llm_batch_size()
    for _sid, group in by_storyline.items():
        for i in range(0, len(group), chunk):
            batch = group[i : i + chunk]
            totals["llm_calls"] += 1
            batch_stats = await _llm_review_storyline_group(batch, dry_run=dry_run)
            for k, v in batch_stats.items():
                totals[k] = totals.get(k, 0) + v

    totals["domain"] = domain_key
    totals["dry_run"] = int(dry_run)
    return totals


async def run_storyline_review_agent_all_domains(
    *,
    batch_limit: int | None = None,
    dry_run: bool = False,
    llm_only: bool = False,
) -> dict[str, Any]:
    """Run one batch per active pipeline domain."""
    by_domain: dict[str, Any] = {}
    agg = {"approved": 0, "rejected": 0, "skipped": 0, "errors": 0, "llm_calls": 0}
    for dk in get_pipeline_active_domain_keys():
        r = await run_storyline_review_agent_for_domain(
            dk, batch_limit=batch_limit, dry_run=dry_run, llm_only=llm_only
        )
        by_domain[dk] = r
        for k in agg:
            agg[k] += int(r.get(k, 0) or 0)
    return {"by_domain": by_domain, **agg}
