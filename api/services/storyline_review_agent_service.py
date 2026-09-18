"""
LLM agent for the storyline review queue (public.storyline_article_suggestions).

Drains pending approve/reject decisions using:
  1. Score fast-path (high combined_score → approve, very low → reject)
  2. Batched LLM review grouped by storyline (8B)

Reuses bulk approve/reject DB logic from storyline_automation_bulk.

Parse / miss failures persist attempt counts on review_notes (`agent_attempts:N`).
After max attempts the row is rejected (agent_parse_exhausted) so the queue cannot
spin forever on skip-only LLM responses.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_int, env_str
from shared.database.connection import get_db_connection
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.services.llm_service import LLMService, ModelType
from shared.services.ollama_model_policy import InvocationKind

logger = logging.getLogger(__name__)

_AGENT_ATTEMPTS_RE = re.compile(r"^agent_attempts:(\d+)")

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


def _auto_approve_score_for_domain(domain_key: str) -> float:
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        return float(
            get_domain_synthesis_config(domain_key).link_score_profile.auto_approve_combined
        )
    except Exception:
        return _auto_approve_score()


def _auto_approve_score() -> float:
    # Corpus p50 ~0.73; 0.80 clears the high tail without LLM.
    try:
        return float(env_str("STORYLINE_REVIEW_AUTO_APPROVE_SCORE", "0.80"))
    except ValueError:
        return 0.80


def _auto_reject_score() -> float:
    # Raise floor so low-mid scores drain via fast-path reject.
    try:
        return float(env_str("STORYLINE_REVIEW_AUTO_REJECT_SCORE", "0.65"))
    except ValueError:
        return 0.65


def _auto_reject_score_for_domain(domain_key: str) -> float:
    """Chemistry kinds use a lower reject floor (more mid-band / stimulus)."""
    base = _auto_reject_score()
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(domain_key)
        if cfg.story_kind == "research_topic":
            return max(0.40, base - 0.15)
        if cfg.is_chemistry_kind():
            return max(0.45, base - 0.10)
    except Exception:
        pass
    return base


def _llm_approve_confidence() -> float:
    try:
        return float(env_str("STORYLINE_REVIEW_LLM_APPROVE_CONFIDENCE", "0.65"))
    except ValueError:
        return 0.65


def _llm_batch_size(outer_batch: int | None = None) -> int:
    """
    LLM suggestions per storyline-group call.

    Scales with the adaptive outer domain batch so larger autotuned runs
    are not stuck on a tiny fixed chunk (default 8, hard cap 20).
    """
    base = max(1, env_int("STORYLINE_REVIEW_LLM_ITEMS", 8))
    cap = max(base, env_int("STORYLINE_REVIEW_LLM_ITEMS_MAX", 20))
    if outer_batch is None:
        return min(cap, base)
    # ~1/5 of domain batch, never below base or above cap
    scaled = max(base, min(cap, max(1, int(outer_batch) // 5)))
    return scaled


def _max_parse_attempts() -> int:
    return max(1, env_int("STORYLINE_REVIEW_MAX_PARSE_ATTEMPTS", 3))


def _parse_agent_attempts(notes: str | None) -> int:
    m = _AGENT_ATTEMPTS_RE.match((notes or "").strip())
    return int(m.group(1)) if m else 0


def _format_agent_attempts(n: int) -> str:
    return f"agent_attempts:{max(0, int(n))}"


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
                       a.title, LEFT(COALESCE(a.summary, a.content, ''), 400),
                       s.review_notes
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
                "review_notes": r[9] or "",
                "agent_attempts": _parse_agent_attempts(r[9] if len(r) > 9 else None),
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
        (datetime.now(timezone.utc), notes, suggestion_id, domain_key),
    )
    return cur.rowcount > 0


def _bump_or_exhaust_attempt(
    cur,
    *,
    domain_key: str,
    suggestion_id: int,
    current_attempts: int,
) -> str:
    """
    Persist a parse/miss attempt on the pending row.

    Returns: "rejected" (exhausted), "skipped" (bumped, still pending), or "error".
    """
    n = int(current_attempts or 0) + 1
    max_n = _max_parse_attempts()
    if n >= max_n:
        if _apply_reject(
            cur,
            domain_key=domain_key,
            suggestion_id=suggestion_id,
            reason_code="other",
            reason="agent_parse_exhausted",
        ):
            return "rejected"
        return "error"
    cur.execute(
        """
        UPDATE public.storyline_article_suggestions
        SET review_notes = %s
        WHERE id = %s AND domain_key = %s AND status = 'pending'
        """,
        (_format_agent_attempts(n), suggestion_id, domain_key),
    )
    return "skipped" if cur.rowcount > 0 else "error"


def _apply_attempt_outcomes(
    stats: dict[str, int],
    items: list[dict[str, Any]],
    *,
    domain_key: str,
    dry_run: bool,
) -> None:
    """Bump durable attempts for every item; reject when exhausted."""
    if dry_run:
        max_n = _max_parse_attempts()
        for it in items:
            n = int(it.get("agent_attempts") or 0) + 1
            if n >= max_n:
                stats["rejected"] += 1
                stats["parse_exhausted"] = stats.get("parse_exhausted", 0) + 1
            else:
                stats["skipped"] += 1
        return

    conn = get_db_connection()
    if not conn:
        stats["errors"] += len(items)
        return
    try:
        with conn.cursor() as cur:
            for it in items:
                outcome = _bump_or_exhaust_attempt(
                    cur,
                    domain_key=domain_key,
                    suggestion_id=int(it["suggestion_id"]),
                    current_attempts=int(it.get("agent_attempts") or 0),
                )
                if outcome == "rejected":
                    stats["rejected"] += 1
                    stats["parse_exhausted"] = stats.get("parse_exhausted", 0) + 1
                    it["agent_attempts"] = _max_parse_attempts()
                elif outcome == "skipped":
                    stats["skipped"] += 1
                    it["agent_attempts"] = int(it.get("agent_attempts") or 0) + 1
                else:
                    stats["errors"] += 1
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.warning("storyline_review_agent attempt bump: %s", e)
        stats["errors"] += len(items)
    finally:
        try:
            conn.close()
        except Exception:
            pass


async def _llm_review_storyline_group(
    items: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> dict[str, int]:
    """Review one storyline's suggestion batch via LLM."""
    stats = {
        "approved": 0,
        "rejected": 0,
        "skipped": 0,
        "errors": 0,
        "parse_exhausted": 0,
    }
    if not items:
        return stats

    storyline_title = items[0]["storyline_title"]
    storyline_summary = items[0]["storyline_summary"]
    domain_key = items[0].get("_domain_key", "")
    schema = items[0].get("_schema", "")
    storyline_id = items[0]["storyline_id"]
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
        _apply_attempt_outcomes(stats, items, domain_key=domain_key, dry_run=dry_run)
        return stats

    reviews = _parse_agent_reviews(raw)
    if not reviews:
        _apply_attempt_outcomes(stats, items, domain_key=domain_key, dry_run=dry_run)
        return stats

    approve_threshold = _llm_approve_confidence()
    decided_ids: set[int] = set()

    if dry_run:
        for rev in reviews:
            sid = rev.get("suggestion_id")
            if sid is None:
                continue
            try:
                sid = int(sid)
            except (TypeError, ValueError):
                continue
            if sid not in id_set:
                continue
            decided_ids.add(sid)
            decision = str(rev.get("decision", "")).lower()
            confidence = float(rev.get("confidence", 0) or 0)
            if decision == "approve" and confidence >= approve_threshold:
                stats["approved"] += 1
            else:
                stats["rejected"] += 1
        missing = [it for it in items if int(it["suggestion_id"]) not in decided_ids]
        if missing:
            _apply_attempt_outcomes(stats, missing, domain_key=domain_key, dry_run=True)
        return stats

    conn = get_db_connection()
    if not conn:
        stats["errors"] += len(items)
        return stats

    try:
        with conn.cursor() as cur:
            for rev in reviews:
                sid = rev.get("suggestion_id")
                if sid is None:
                    continue
                try:
                    sid = int(sid)
                except (TypeError, ValueError):
                    continue
                if sid not in id_set:
                    continue
                decision = str(rev.get("decision", "")).lower()
                confidence = float(rev.get("confidence", 0) or 0)
                reason_code = str(rev.get("reason_code") or "other")[:40]
                reason = str(rev.get("reason") or "")[:200]

                if decision == "approve" and confidence >= approve_threshold:
                    if _apply_approve(
                        cur,
                        domain_key=domain_key,
                        schema=schema,
                        storyline_id=storyline_id,
                        suggestion_id=sid,
                    ):
                        stats["approved"] += 1
                        decided_ids.add(sid)
                else:
                    if _apply_reject(
                        cur,
                        domain_key=domain_key,
                        suggestion_id=sid,
                        reason_code=reason_code,
                        reason=reason,
                    ):
                        stats["rejected"] += 1
                        decided_ids.add(sid)

            # Omitted from JSON or apply failed — durable attempt / exhaust
            for it in items:
                sid = int(it["suggestion_id"])
                if sid in decided_ids:
                    continue
                outcome = _bump_or_exhaust_attempt(
                    cur,
                    domain_key=domain_key,
                    suggestion_id=sid,
                    current_attempts=int(it.get("agent_attempts") or 0),
                )
                if outcome == "rejected":
                    stats["rejected"] += 1
                    stats["parse_exhausted"] = stats.get("parse_exhausted", 0) + 1
                elif outcome == "skipped":
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1
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
    approve_at = _auto_approve_score_for_domain(domain_key)
    reject_below = _auto_reject_score_for_domain(domain_key)

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
    if batch_limit is None:
        limit = max(10, env_int("STORYLINE_REVIEW_BATCH_SIZE", 60))
        try:
            from shared.adaptive_batch_policy import resolve_adaptive_batch

            limit, _meta = resolve_adaptive_batch("storyline_review_agent", limit)
            limit = max(10, int(limit))
        except Exception:
            pass
    else:
        limit = max(10, int(batch_limit))

    totals: dict[str, int] = {
        "approved": 0,
        "rejected": 0,
        "skipped": 0,
        "errors": 0,
        "llm_calls": 0,
        "parse_exhausted": 0,
    }

    if not llm_only:
        score_stats = _score_fast_path(
            domain_key=domain_key, schema=schema, limit=limit, dry_run=dry_run
        )
        for k, v in score_stats.items():
            totals[k] = totals.get(k, 0) + int(v or 0)

    approve_at = _auto_approve_score_for_domain(domain_key)
    reject_below = _auto_reject_score_for_domain(domain_key)
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

    chunk = _llm_batch_size(limit)
    totals["batch_limit"] = limit
    totals["llm_chunk"] = chunk
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
    agg = {
        "approved": 0,
        "rejected": 0,
        "skipped": 0,
        "errors": 0,
        "llm_calls": 0,
        "parse_exhausted": 0,
    }
    for dk in get_pipeline_active_domain_keys():
        r = await run_storyline_review_agent_for_domain(
            dk, batch_limit=batch_limit, dry_run=dry_run, llm_only=llm_only
        )
        by_domain[dk] = r
        for k in agg:
            agg[k] += int(r.get(k, 0) or 0)
    return {"by_domain": by_domain, **agg}
