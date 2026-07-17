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
    # Keep below iterative_min by default so refreshes stay single-LLM (cheaper share).
    return max(1, min(150, _env_int("ENTITY_PROFILE_BUILD_FULL_CONTEXT_LIMIT", 40)))


def entity_profile_build_iterative_min_contexts() -> int:
    # Raised so multi-LLM chunk summarization only runs on very large refresh sets.
    return max(2, _env_int("ENTITY_PROFILE_BUILD_ITERATIVE_MIN_CONTEXTS", 50))


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


def entity_profile_build_llm_batch_size() -> int:
    """Profiles per LLM call in batched mode (default 30, range 5–50)."""
    return max(5, min(50, _env_int("ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE", 30)))


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


def _build_batched_profile_prompt(profile_data: list[dict]) -> str:
    """Build a prompt for processing multiple profiles in a single LLM call."""
    prompt_parts = [
        """You are an expert entity-profile writer. For each of the following entities, output a JSON object with keys "sections" (list of objects with "title" and "content") and "relationships" (list of objects with "target" and "relation").
Return a JSON array in the same order as the input, where each element corresponds to one entity.

Each section object should have:
- "title": string (section heading)
- "content": string (1-3 sentences)

Each relationship object should have:
- "target": string (the other entity or topic)
- "relation": string (describing the relationship)

If relationships are not clear from context, return an empty array for "relationships".

"""
    ]
    for i, data in enumerate(profile_data, 1):
        prompt_parts.append(
            f"""Entity {i}:
Name: {data['name']}
Type: {data['etype']}
Context excerpts:
{data['combined']}

"""
        )
    prompt_parts.append(
        "Return ONLY a valid JSON array with one element per entity in the same order as above."
    )
    return "\n".join(prompt_parts)


def _normalize_batched_profile_item(item: Any) -> tuple[list, list] | None:
    if not isinstance(item, dict):
        return None
    sections = item.get("sections", [])
    relationships = item.get("relationships", [])
    if not isinstance(sections, list):
        sections = []
    valid_sections = []
    for section in sections:
        if isinstance(section, dict) and "title" in section and "content" in section:
            valid_sections.append(
                {
                    "title": str(section["title"])[:200],
                    "content": str(section["content"])[:1000],
                }
            )
    if not valid_sections:
        return None
    if not isinstance(relationships, list):
        relationships = []
    valid_relationships = []
    for rel in relationships:
        if isinstance(rel, dict) and "target" in rel and "relation" in rel:
            valid_relationships.append(
                {
                    "target": str(rel["target"])[:200],
                    "relation": str(rel["relation"])[:100],
                }
            )
    return valid_sections, valid_relationships


def _parse_batched_response(raw_response: str, expected_count: int) -> list[tuple[list, list] | None]:
    """
    Parse the LLM's response expecting a JSON array of profile results.

    Returns a list of (sections, relationships) tuples, or None for failed parses.
    """
    try:
        parsed: Any = json.loads(raw_response.strip())
        if not isinstance(parsed, list):
            start = raw_response.find("[")
            end = raw_response.rfind("]") + 1
            if start < 0 or end <= start:
                parsed = None
            else:
                parsed = json.loads(raw_response[start:end])
        if isinstance(parsed, list):
            results: list[tuple[list, list] | None] = []
            for item in parsed[:expected_count]:
                results.append(_normalize_batched_profile_item(item))
            while len(results) < expected_count:
                results.append(None)
            return results[:expected_count]

        results = []
        pos = 0
        while pos < len(raw_response) and len(results) < expected_count:
            obj_start = raw_response.find("{", pos)
            if obj_start == -1:
                break
            obj_end = _find_matching_brace(raw_response, obj_start)
            if obj_end == -1:
                break
            try:
                obj_text = raw_response[obj_start : obj_end + 1]
                data = json.loads(obj_text)
                results.append(_normalize_batched_profile_item(data))
                pos = obj_end + 1
            except json.JSONDecodeError:
                pos = obj_start + 1
        while len(results) < expected_count:
            results.append(None)
        return results[:expected_count]
    except (json.JSONDecodeError, ValueError, IndexError) as e:
        logger.debug("Failed to parse batched response: %s", e)
        return [None] * expected_count


def _find_matching_brace(text: str, start_pos: int) -> int:
    """Find the matching closing brace for an opening brace at start_pos."""
    if start_pos >= len(text) or text[start_pos] != "{":
        return -1
    
    depth = 0
    in_string = False
    escape_next = False
    
    for i in range(start_pos, len(text)):
        char = text[i]
        
        if escape_next:
            escape_next = False
            continue
            
        if char == "\\":
            escape_next = True
            continue
            
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
            
        if in_string:
            continue
            
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
                
    return -1


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


def _get_profiles_metadata_batch(profile_ids: list[int]) -> dict[int, tuple[Any, Any, Any]]:
    """Return {id: (canonical_name, entity_type, sections_raw)} in one query."""
    if not profile_ids:
        return {}
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            _set_profile_build_statement_timeout(cur)
            cur.execute(
                """
                SELECT ep.id, ep.metadata->>'canonical_name',
                       ep.metadata->>'entity_type', ep.sections
                FROM intelligence.entity_profiles ep
                WHERE ep.id = ANY(%s)
                """,
                (profile_ids,),
            )
            return {row[0]: (row[1], row[2], row[3]) for row in cur.fetchall()}
    finally:
        conn.close()


def get_contexts_for_entity_profiles_batch(
    profile_ids: list[int],
    per_profile_limit: int,
) -> dict[int, list[tuple]]:
    """Single query: {entity_profile_id: [(context_id, title, content), ...]}."""
    if not profile_ids:
        return {}
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            _set_profile_build_statement_timeout(cur)
            cur.execute(
                """
                SELECT sub.entity_profile_id, sub.context_id, sub.title, sub.content
                FROM (
                    SELECT cem.entity_profile_id, c.id AS context_id, c.title, c.content,
                           ROW_NUMBER() OVER (
                               PARTITION BY cem.entity_profile_id
                               ORDER BY c.created_at DESC
                           ) AS rn
                    FROM intelligence.context_entity_mentions cem
                    JOIN intelligence.contexts c ON c.id = cem.context_id
                    WHERE cem.entity_profile_id = ANY(%s)
                ) sub
                WHERE sub.rn <= %s
                """,
                (profile_ids, per_profile_limit),
            )
            out: dict[int, list[tuple]] = {pid: [] for pid in profile_ids}
            for row in cur.fetchall():
                pid, ctx_id, title, content = row
                out.setdefault(pid, []).append((ctx_id, title, content))
            return out
    finally:
        conn.close()


def _persist_profile_sections_batch(
    updates: list[tuple[int, list, list]],
) -> None:
    """Write sections/relationships for many profiles in one DB connection."""
    if not updates:
        return
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            for profile_id, sections, relationships in updates:
                cur.execute(
                    """
                    UPDATE intelligence.entity_profiles
                    SET sections = %s, relationships_summary = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(sections), json.dumps(relationships), profile_id),
                )
        conn.commit()
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


def _entity_profile_upstream_gate_for_select() -> bool:
    """Upstream EXISTS is expensive; skip during bulk catchup unless explicitly enabled."""
    if not _entity_profile_upstream_gate_enabled():
        return False
    try:
        from config.runtime import env_bool

        if env_bool("BULK_CATCHUP_ACTIVE", False):
            return env_bool("ENTITY_PROFILE_BUILD_UPSTREAM_GATE_CATCHUP", False)
    except Exception:
        pass
    return True


def _profile_build_db_timeout_ms() -> int:
    return max(5000, _env_int("ENTITY_PROFILE_BUILD_DB_TIMEOUT_MS", 600000))


def _set_profile_build_statement_timeout(cur) -> None:
    cur.execute("SET LOCAL statement_timeout = %s", (str(_profile_build_db_timeout_ms()),))


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
    if _entity_profile_upstream_gate_for_select():
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
            _set_profile_build_statement_timeout(cur)
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
    """Build or refresh up to `limit` entity profiles (batched LLM + batched DB by default)."""
    return await run_profile_builder_batch_batched(limit=limit, on_profile_built=on_profile_built)


async def _run_profile_builder_batch_parallel(
    limit: int = 15,
    *,
    on_profile_built: Callable[[int, int], Awaitable[None]] | None = None,
) -> ProfileBuilderBatchResult:
    """Per-profile parallel path (used by unit tests and per-profile fallback)."""
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
            "Entity profile builder (parallel): %s processed, %s updated (%s fast, %s full)",
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


def _prepare_profile_data_for_batch(ids: list[int]) -> list[dict]:
    """Load metadata + contexts for many profiles using two batched DB queries."""
    fast_limit = entity_profile_build_fast_context_limit()
    full_limit = entity_profile_build_full_context_limit()
    fetch_limit = max(fast_limit, full_limit)

    metadata = _get_profiles_metadata_batch(ids)
    contexts_by_id = get_contexts_for_entity_profiles_batch(ids, fetch_limit)

    profile_data: list[dict] = []
    for entity_profile_id in ids:
        meta = metadata.get(entity_profile_id)
        if not meta:
            continue
        canonical_name, entity_type, sections_raw = meta
        is_first_pass = _sections_empty(sections_raw)
        ctx_limit = fast_limit if is_first_pass else full_limit
        contexts = (contexts_by_id.get(entity_profile_id) or [])[:ctx_limit]
        if not contexts:
            continue
        combined = _combined_from_contexts(
            contexts,
            preview_len=600,
            max_chars=3000,
            include_source_id=True,
        )
        profile_data.append(
            {
                "id": entity_profile_id,
                "name": canonical_name or f"Entity {entity_profile_id}",
                "etype": entity_type or "entity",
                "combined": combined,
                "is_first_pass": is_first_pass,
                "contexts_used": len(contexts),
            }
        )
    return profile_data


async def _process_batched_profile_chunk(
    chunk: list[dict],
    llm: LLMService,
    *,
    on_profile_built: Callable[[int, int], Awaitable[None]] | None,
    updated_so_far: int,
) -> ProfileBuilderBatchResult:
    """One LLM call for up to N profiles; per-profile fallback on parse failure."""
    updated = 0
    fast_updated = 0
    full_updated = 0
    total_contexts = 0

    try:
        batched_prompt = _build_batched_profile_prompt(chunk)
        raw_response = await llm._call_ollama(ModelType.LLAMA_8B, batched_prompt)
        results = _parse_batched_response(raw_response, len(chunk))
    except Exception as e:
        logger.warning("Batched profile chunk LLM failed (%s), falling back per profile", e)
        results = [None] * len(chunk)

    db_updates: list[tuple[int, list, list]] = []
    fallback_ids: list[int] = []
    for data, result in zip(chunk, results):
        if result is not None:
            sections, relationships = result
            db_updates.append((data["id"], sections, relationships))
            updated += 1
            total_contexts += data["contexts_used"]
            if data["is_first_pass"]:
                fast_updated += 1
            else:
                full_updated += 1
        else:
            fallback_ids.append(data["id"])

    if db_updates:
        _persist_profile_sections_batch(db_updates)
        if on_profile_built is not None:
            for i in range(len(db_updates)):
                await on_profile_built(updated_so_far + i + 1, updated_so_far + i + 1)

    for entity_profile_id in fallback_ids:
        result = await build_profile_sections(entity_profile_id)
        if not result.success:
            continue
        updated += 1
        total_contexts += result.contexts_used
        if result.tier == "fast":
            fast_updated += 1
        else:
            full_updated += 1
        if on_profile_built is not None:
            await on_profile_built(updated_so_far + updated, updated_so_far + updated)

    return ProfileBuilderBatchResult(
        updated=updated,
        attempted=len(chunk),
        fast_updated=fast_updated,
        full_updated=full_updated,
        contexts_used=total_contexts,
    )


async def run_profile_builder_batch_batched(
    limit: int = 15,
    *,
    on_profile_built: Callable[[int, int], Awaitable[None]] | None = None,
) -> ProfileBuilderBatchResult:
    """
    Build profiles using chunked batched LLM calls (~30 profiles/call by default)
    and two batched DB queries for metadata + contexts.

    Honors ``ENTITY_PROFILE_BUILD_PARALLEL``: up to N LLM chunks run concurrently
    (semaphore + gather). Set PARALLEL=1 to restore serial chunk awaits.
    """
    ids = get_entity_profile_ids_to_build(limit=limit)
    if not ids:
        return ProfileBuilderBatchResult(updated=0, attempted=0)

    profile_data = _prepare_profile_data_for_batch(ids)
    if not profile_data:
        return ProfileBuilderBatchResult(updated=0, attempted=len(ids))

    chunk_size = entity_profile_build_llm_batch_size()
    parallel = get_entity_profile_build_parallel()
    llm = LLMService()
    chunks = [
        profile_data[start : start + chunk_size]
        for start in range(0, len(profile_data), chunk_size)
    ]

    updated = 0
    fast_updated = 0
    full_updated = 0
    total_contexts = 0
    progress_lock = asyncio.Lock()
    sem = asyncio.Semaphore(parallel)
    progress_count = 0

    async def _run_chunk(chunk: list[dict]) -> ProfileBuilderBatchResult:
        nonlocal progress_count

        async def _progress(_idx: int, _current_idx: int) -> None:
            nonlocal progress_count
            if on_profile_built is None:
                return
            async with progress_lock:
                progress_count += 1
                n = progress_count
            await on_profile_built(n, n)

        async with sem:
            return await _process_batched_profile_chunk(
                chunk,
                llm,
                on_profile_built=_progress if on_profile_built is not None else None,
                updated_so_far=0,
            )

    results = await asyncio.gather(
        *[_run_chunk(chunk) for chunk in chunks],
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("Batched profile chunk failed: %s", result)
            continue
        updated += result.updated
        fast_updated += result.fast_updated
        full_updated += result.full_updated
        total_contexts += result.contexts_used

    if updated > 0:
        logger.info(
            "Entity profile builder (batched): %s ids, %s LLM-ready, %s updated "
            "(%s fast, %s full, chunk_size=%s, parallel=%s)",
            len(ids),
            len(profile_data),
            updated,
            fast_updated,
            full_updated,
            chunk_size,
            parallel,
        )
    return ProfileBuilderBatchResult(
        updated=updated,
        attempted=len(ids),
        fast_updated=fast_updated,
        full_updated=full_updated,
        contexts_used=total_contexts,
    )


def _entity_profile_build_budget_seconds(budget_seconds: int | None) -> int:
    if budget_seconds is not None:
        return max(0, int(budget_seconds))
    from shared.pipeline_batch_drain import phase_run_budget_seconds

    # Align with PhasePolicy.run_budget_seconds (900) when env/governance unset.
    sec = phase_run_budget_seconds("entity_profile_build", default=900)
    if sec > 0:
        return sec
    try:
        raw = env_str("ASSEMBLY_ENTITY_PROFILE_BUILD_CYCLE_BUDGET_SECONDS", "900")
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 900


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
