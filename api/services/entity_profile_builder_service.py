"""
Entity profile builder service — Phase 1.3 context-centric.
Builds Wikipedia-style sections and relationships_summary for entity_profiles from context content.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, NamedTuple

from config.runtime import env_str
from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)


class ProfileBuildResult(NamedTuple):
    success: bool
    tier: str = "full"
    contexts_used: int = 0


@dataclass
class ProfileBuilderBatchResult:
    updated: int
    attempted: int
    fast_updated: int = 0
    full_updated: int = 0
    contexts_used: int = 0


def _env_int(name: str, default: int) -> int:
    try:
        return int(env_str(name, str(default)))
    except ValueError:
        return default


def entity_profile_build_fast_context_limit() -> int:
    return max(1, min(75, _env_int("ENTITY_PROFILE_BUILD_FAST_CONTEXT_LIMIT", 15)))


def entity_profile_build_full_context_limit() -> int:
    return max(1, min(150, _env_int("ENTITY_PROFILE_BUILD_FULL_CONTEXT_LIMIT", 75)))


def entity_profile_build_iterative_min_contexts() -> int:
    return max(2, _env_int("ENTITY_PROFILE_BUILD_ITERATIVE_MIN_CONTEXTS", 30))


def entity_profile_build_priority_first_pass() -> bool:
    return env_str("ENTITY_PROFILE_BUILD_PRIORITY_FIRST_PASS", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def entity_profile_build_batch_limit() -> int:
    default = max(1, min(150, _env_int("ENTITY_PROFILE_BUILD_LIMIT", 25)))
    try:
        from shared.adaptive_batch_policy import resolve_adaptive_batch

        tuned, _meta = resolve_adaptive_batch("entity_profile_build", default)
        return tuned
    except Exception:
        return default


def get_entity_profile_build_parallel() -> int:
    try:
        n = int(env_str("ENTITY_PROFILE_BUILD_PARALLEL", "3"))
    except ValueError:
        n = 3
    return max(1, min(12, n))


def entity_profile_build_drain_enabled() -> bool:
    """Single automation task loops batches until idle (default). Set ENTITY_PROFILE_BUILD_DRAIN=false for one batch only."""
    return env_str("ENTITY_PROFILE_BUILD_DRAIN", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _sections_empty(sections: Any) -> bool:
    if sections is None:
        return True
    if isinstance(sections, list):
        return len(sections) == 0
    if isinstance(sections, str):
        return sections.strip() in ("", "[]")
    return False


def get_contexts_for_entity_profile(entity_profile_id: int, limit: int = 75) -> list[tuple]:
    """Return (context_id, title, content) for contexts that mention this entity (via context_entity_mentions)."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.title, c.content
                FROM intelligence.contexts c
                JOIN intelligence.context_entity_mentions cem ON cem.context_id = c.id
                WHERE cem.entity_profile_id = %s
                ORDER BY c.created_at DESC
                LIMIT %s
                """,
                (entity_profile_id, limit),
            )
            return cur.fetchall()
    finally:
        conn.close()


def _parse_sections_response(raw: str) -> tuple:
    """Parse LLM response into (sections list, relationships list)."""
    sections = []
    relationships = []
    try:
        start = raw.find("{")
        if start < 0:
            return sections, relationships
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        if isinstance(data.get("sections"), list):
            sections = data["sections"]
        if isinstance(data.get("relationships"), list):
            relationships = data["relationships"]
    except (json.JSONDecodeError, ValueError):
        pass
    return sections, relationships


def _combined_from_contexts(
    contexts: list[tuple],
    *,
    preview_len: int,
    max_chars: int,
    include_source_id: bool = True,
) -> str:
    parts = []
    for ctx_id, title, content in contexts:
        content_preview = (content or "")[:preview_len].replace("\n", " ")
        if include_source_id:
            parts.append(f"[Source {ctx_id}] {title or 'Untitled'}\n{content_preview}")
        else:
            parts.append(f"[{title or 'Untitled'}] {content_preview}")
    return "\n\n".join(parts)[:max_chars]


def _profile_sections_prompt(name: str, etype: str, combined: str) -> str:
    return f"""Given the following entity and excerpts from news contexts where they are mentioned, produce a short profile.

Entity name: {name}
Entity type: {etype}

Context excerpts:
{combined}

Return ONLY a JSON object (no markdown):
{{
  "sections": [
    {{ "title": "Summary", "content": "2-4 sentences summarizing who/what this entity is and recent relevance." }},
    {{ "title": "Key positions or role", "content": "1-3 sentences on positions, role, or stance if evident." }},
    {{ "title": "Recent context", "content": "1-2 sentences on recent developments from the excerpts." }}
  ],
  "relationships": [
    {{ "target": "Other entity or topic", "relation": "e.g. works with, opposes, member of" }}
  ]
}}
Keep each section content concise. If relationships are not clear, return empty array for "relationships"."""


async def build_profile_sections(entity_profile_id: int) -> ProfileBuildResult:
    """
    Gather contexts mentioning this entity, call LLM to generate Wikipedia-style sections
    and relationship summary, update entity_profiles.sections and relationships_summary.

    First pass (empty sections): capped contexts, single LLM call.
    Refresh (sections populated): full context limit with optional iterative chunking.
    """
    conn = get_db_connection()
    if not conn:
        return ProfileBuildResult(False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ep.id, ep.domain_key, ep.metadata->>'canonical_name',
                       ep.metadata->>'entity_type', ep.sections
                FROM intelligence.entity_profiles ep WHERE ep.id = %s
                """,
                (entity_profile_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return ProfileBuildResult(False)
        _, _domain_key, canonical_name, entity_type, sections_raw = row
        name = canonical_name or f"Entity {entity_profile_id}"
        etype = entity_type or "entity"
        is_first_pass = _sections_empty(sections_raw)
        tier = "fast" if is_first_pass else "full"

        if is_first_pass:
            ctx_limit = entity_profile_build_fast_context_limit()
            contexts = get_contexts_for_entity_profile(entity_profile_id, limit=ctx_limit)
            if not contexts:
                logger.debug(f"Entity profile {entity_profile_id}: no contexts to build from")
                return ProfileBuildResult(False, tier=tier)
            combined = _combined_from_contexts(
                contexts, preview_len=800, max_chars=8000, include_source_id=True
            )
        else:
            ctx_limit = entity_profile_build_full_context_limit()
            contexts = get_contexts_for_entity_profile(entity_profile_id, limit=ctx_limit)
            if not contexts:
                logger.debug(f"Entity profile {entity_profile_id}: no contexts to build from")
                return ProfileBuildResult(False, tier=tier)

            llm = LLMService()
            iterative_threshold = entity_profile_build_iterative_min_contexts()
            chunk_size = 15
            combined: str
            if len(contexts) > iterative_threshold:
                chunk_summaries: list[str] = []
                for i in range(0, min(len(contexts), 60), chunk_size):
                    chunk = contexts[i : i + chunk_size]
                    chunk_text = _combined_from_contexts(
                        chunk, preview_len=800, max_chars=6000, include_source_id=False
                    )
                    chunk_prompt = f"""Summarize in 2-4 sentences what the following excerpts say about "{name}" (entity type: {etype}). Focus on role, positions, and recent relevance. Be concise.\n\nExcerpts:\n{chunk_text}"""
                    raw_chunk = (
                        await llm._call_ollama(ModelType.LLAMA_8B, chunk_prompt) if chunk_text else ""
                    )
                    if raw_chunk and len(raw_chunk.strip()) > 20:
                        chunk_summaries.append(raw_chunk.strip()[:800])
                combined = "\n\n".join(chunk_summaries)[:5000] if chunk_summaries else ""
                if not combined:
                    combined = _combined_from_contexts(
                        contexts[:25], preview_len=800, max_chars=8000, include_source_id=True
                    )
            else:
                combined = _combined_from_contexts(
                    contexts[:40], preview_len=1200, max_chars=10000, include_source_id=True
                )

        llm = LLMService()
        prompt = _profile_sections_prompt(name, etype, combined)
        raw = await llm._call_ollama(ModelType.LLAMA_8B, prompt)
        sections, relationships = _parse_sections_response(raw)
        if not sections and not relationships:
            return ProfileBuildResult(False, tier=tier, contexts_used=len(contexts))

        conn = get_db_connection()
        if not conn:
            return ProfileBuildResult(False, tier=tier, contexts_used=len(contexts))
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.entity_profiles
                    SET sections = %s, relationships_summary = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(sections), json.dumps(relationships), entity_profile_id),
                )
            conn.commit()
            conn.close()
            logger.debug(
                f"Entity profile {entity_profile_id}: sections updated ({len(sections)} sections, tier={tier})"
            )
            return ProfileBuildResult(True, tier=tier, contexts_used=len(contexts))
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"build_profile_sections {entity_profile_id} failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return ProfileBuildResult(False)


def sql_entity_profile_upstream_cleared_exists() -> str:
    """SQL EXISTS fragment: profile has a mention tied to upstream-cleared article + context."""
    from shared.domain_registry import pipeline_url_schema_pairs
    from shared.pipeline_pass_marker import sql_article_pass_cleared, sql_context_pass_cleared

    ctx_cleared = sql_context_pass_cleared("claim_extraction", "c")
    branches: list[str] = []
    try:
        from shared.pipeline_resource_policy import intake_extraction_suppressed

        entity_phase = (
            "unified_intake_extraction"
            if intake_extraction_suppressed()
            else "entity_extraction"
        )
    except Exception:
        entity_phase = "entity_extraction"
    for domain_key, schema_name in pipeline_url_schema_pairs():
        art_cleared = sql_article_pass_cleared(entity_phase, "a")
        dk = domain_key.replace("'", "''")
        branches.append(
            f"""(
                ep.domain_key = '{dk}'
                AND EXISTS (
                    SELECT 1 FROM {schema_name}.articles a
                    WHERE a.id = atc.article_id
                      AND ({art_cleared})
                )
            )"""
        )
    if not branches:
        return "FALSE"
    domain_branch_sql = " OR ".join(branches)
    return f"""EXISTS (
        SELECT 1 FROM intelligence.context_entity_mentions cem
        JOIN intelligence.article_to_context atc
          ON atc.context_id = cem.context_id AND atc.domain_key = ep.domain_key
        JOIN intelligence.contexts c ON c.id = atc.context_id
        WHERE cem.entity_profile_id = ep.id
          AND ({ctx_cleared})
          AND ({domain_branch_sql})
    )"""


def _entity_profile_upstream_gate_enabled() -> bool:
    return env_str("ENTITY_PROFILE_BUILD_UPSTREAM_GATE", "true").lower() in ("1", "true", "yes")


def get_entity_profile_ids_to_build(limit: int = 20) -> list[int]:
    """Return buildable profile IDs: pipeline-active domains with context mentions."""
    from shared.entity_profile_eligibility import sql_entity_profile_needs_build
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    conn = get_db_connection()
    if not conn:
        return []
    domain_sql, domain_keys = pipeline_domain_any_sql("ep.domain_key")
    if not domain_keys:
        return []
    upstream_sql = ""
    if _entity_profile_upstream_gate_enabled():
        upstream_sql = f" AND {sql_entity_profile_upstream_cleared_exists()} "
    needs_build = sql_entity_profile_needs_build("ep")
    if entity_profile_build_priority_first_pass():
        order_sql = (
            "(ep.sections IS NULL OR ep.sections = '[]'::jsonb) DESC, ep.updated_at ASC NULLS FIRST"
        )
    else:
        order_sql = "ep.updated_at ASC NULLS FIRST"
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ep.id FROM intelligence.entity_profiles ep
                WHERE {domain_sql}
                  AND {needs_build}
                  AND EXISTS (
                      SELECT 1 FROM intelligence.context_entity_mentions cem
                      WHERE cem.entity_profile_id = ep.id
                  )
                  {upstream_sql}
                ORDER BY {order_sql}
                LIMIT %s
                """,
                (domain_keys, limit),
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


async def run_profile_builder_batch(
    limit: int = 15,
    *,
    on_profile_built: Callable[[int, int], Awaitable[None]] | None = None,
) -> ProfileBuilderBatchResult:
    """Build or refresh up to `limit` entity profiles."""
    ids = get_entity_profile_ids_to_build(limit=limit)
    if not ids:
        return ProfileBuilderBatchResult(updated=0, attempted=0)

    parallel = get_entity_profile_build_parallel()
    sem = asyncio.Semaphore(parallel)
    lock = asyncio.Lock()
    updated = 0
    fast_updated = 0
    full_updated = 0
    contexts_used = 0
    processed_idx = 0

    async def _one(entity_profile_id: int) -> None:
        nonlocal updated, fast_updated, full_updated, contexts_used, processed_idx
        async with sem:
            result = await build_profile_sections(entity_profile_id)
            if not result.success:
                return
            async with lock:
                updated += 1
                processed_idx += 1
                if result.tier == "fast":
                    fast_updated += 1
                else:
                    full_updated += 1
                contexts_used += result.contexts_used
                idx = updated
                current_idx = processed_idx
            if on_profile_built is not None:
                await on_profile_built(idx, current_idx)

    await asyncio.gather(*[_one(eid) for eid in ids], return_exceptions=True)

    if updated > 0:
        logger.info(
            "Entity profile builder: %s processed, %s updated (%s fast, %s full)",
            len(ids),
            updated,
            fast_updated,
            full_updated,
        )
    return ProfileBuilderBatchResult(
        updated=updated,
        attempted=len(ids),
        fast_updated=fast_updated,
        full_updated=full_updated,
        contexts_used=contexts_used,
    )


def _entity_profile_build_budget_seconds(budget_seconds: int | None) -> int:
    if budget_seconds is not None:
        return max(0, int(budget_seconds))
    from shared.pipeline_batch_drain import phase_run_budget_seconds

    sec = phase_run_budget_seconds("entity_profile_build", default=600)
    if sec > 0:
        return sec
    try:
        raw = env_str("ASSEMBLY_ENTITY_PROFILE_BUILD_CYCLE_BUDGET_SECONDS", "600")
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 600


async def drain_entity_profile_build(
    *,
    budget_seconds: int | None = None,
    batch_limit: int | None = None,
    on_batch_complete: Callable[[int, ProfileBuilderBatchResult], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """
    Drain entity profile builds until idle, budget expires, or stall detected.
    Shared by assembly conductor and automation_manager.
    """
    from shared.pipeline_batch_drain import DrainStallTracker, RunBudget

    budget_sec = _entity_profile_build_budget_seconds(budget_seconds)
    budget = RunBudget(budget_sec)
    stall = DrainStallTracker()
    limit = batch_limit if batch_limit is not None else entity_profile_build_batch_limit()
    total_updated = 0
    total_fast = 0
    total_full = 0
    total_contexts = 0
    rounds = 0

    while not budget.expired():
        rounds += 1
        batch_result = await run_profile_builder_batch(limit=limit)
        total_updated += batch_result.updated
        total_fast += batch_result.fast_updated
        total_full += batch_result.full_updated
        total_contexts += batch_result.contexts_used
        had_pending = batch_result.attempted > 0

        if on_batch_complete is not None:
            await on_batch_complete(rounds, batch_result)

        if stall.record_round(processed=batch_result.updated, had_pending=had_pending):
            break
        if batch_result.updated == 0:
            break

    return {
        "profiles_updated": total_updated,
        "round_processed": total_updated,
        "processed": total_updated,
        "fast_updated": total_fast,
        "full_updated": total_full,
        "contexts_used": total_contexts,
        "rounds": rounds,
        "batch_limit": limit,
        "budget_seconds": budget_sec,
    }
