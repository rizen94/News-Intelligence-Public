"""
Entity profile builder service — Phase 1.3 context-centric.
Builds Wikipedia-style sections and relationships_summary for entity_profiles from context content.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)


def get_contexts_for_entity_profile(entity_profile_id: int, limit: int = 75) -> List[tuple]:  # v8
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


async def build_profile_sections(entity_profile_id: int) -> bool:
    """
    Gather contexts mentioning this entity, call LLM to generate Wikipedia-style sections
    and relationship summary, update entity_profiles.sections and relationships_summary.
    Returns True if updated.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ep.id, ep.domain_key, ep.metadata->>'canonical_name', ep.metadata->>'entity_type'
                FROM intelligence.entity_profiles ep WHERE ep.id = %s
                """,
                (entity_profile_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return False
        _, domain_key, canonical_name, entity_type = row
        name = canonical_name or f"Entity {entity_profile_id}"
        etype = entity_type or "entity"

        contexts = get_contexts_for_entity_profile(entity_profile_id, limit=75)
        if not contexts:
            logger.debug(f"Entity profile {entity_profile_id}: no contexts to build from")
            return False

        llm = LLMService()
        # v8: Iterative summarization for large sets — summarize in chunks then synthesize
        ITERATIVE_THRESHOLD = 30
        CHUNK_SIZE = 15
        combined: str
        if len(contexts) > ITERATIVE_THRESHOLD:
            chunk_summaries: List[str] = []
            for i in range(0, min(len(contexts), 60), CHUNK_SIZE):
                chunk = contexts[i : i + CHUNK_SIZE]
                parts_chunk = []
                for ctx_id, title, content in chunk:
                    content_preview = (content or "")[:800].replace("\n", " ")
                    parts_chunk.append(f"[{title or 'Untitled'}] {content_preview}")
                chunk_text = "\n".join(parts_chunk)[:6000]
                chunk_prompt = f"""Summarize in 2-4 sentences what the following excerpts say about "{name}" (entity type: {etype}). Focus on role, positions, and recent relevance. Be concise.\n\nExcerpts:\n{chunk_text}"""
                raw_chunk = await llm._call_ollama(ModelType.LLAMA_8B, chunk_prompt) if chunk_text else ""
                if raw_chunk and len(raw_chunk.strip()) > 20:
                    chunk_summaries.append(raw_chunk.strip()[:800])
            combined = "\n\n".join(chunk_summaries)[:5000] if chunk_summaries else ""
            if not combined:
                # Fallback: use first 25 contexts as single block
                parts = []
                for ctx_id, title, content in contexts[:25]:
                    content_preview = (content or "")[:800].replace("\n", " ")
                    parts.append(f"[Source {ctx_id}] {title or 'Untitled'}\n{content_preview}")
                combined = "\n\n".join(parts)[:8000]
        else:
            parts = []
            for ctx_id, title, content in contexts[:40]:
                content_preview = (content or "")[:1200].replace("\n", " ")
                parts.append(f"[Source {ctx_id}] {title or 'Untitled'}\n{content_preview}")
            combined = "\n\n".join(parts)[:10000]

        prompt = f"""Given the following entity and excerpts from news contexts where they are mentioned, produce a short profile.

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

        raw = await llm._call_ollama(ModelType.LLAMA_8B, prompt)
        sections, relationships = _parse_sections_response(raw)
        if not sections and not relationships:
            return False

        conn = get_db_connection()
        if not conn:
            return False
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
            logger.debug(f"Entity profile {entity_profile_id}: sections updated ({len(sections)} sections)")
            return True
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
        return False


def get_entity_profile_ids_to_build(limit: int = 20) -> List[int]:
    """Return entity_profile IDs that should be (re)built: either sections empty or not updated recently."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ep.id FROM intelligence.entity_profiles ep
                WHERE ep.sections = '[]'::jsonb OR ep.sections IS NULL
                   OR ep.updated_at < NOW() - INTERVAL '7 days'
                ORDER BY ep.updated_at ASC NULLS FIRST
                LIMIT %s
                """,
                (limit,),
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


async def run_profile_builder_batch(limit: int = 15) -> int:
    """Build or refresh up to `limit` entity profiles. Returns number updated."""
    ids = get_entity_profile_ids_to_build(limit=limit)
    updated = 0
    for entity_profile_id in ids:
        if await build_profile_sections(entity_profile_id):
            updated += 1
    if updated > 0:
        logger.info(f"Entity profile builder: {len(ids)} processed, {updated} updated")
    return updated
