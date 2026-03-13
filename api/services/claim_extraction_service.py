"""
Claim extraction service — Phase 2.1 context-centric.
Extracts factual claims (subject/predicate/object) from contexts and stores in intelligence.extracted_claims.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
from typing import List, Optional, Tuple

from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)


def _parse_claims_response(raw: str) -> List[Tuple[str, str, str, float]]:
    """Parse LLM response into (subject, predicate, object, confidence) list."""
    out = []
    try:
        start = raw.find("[")
        if start < 0:
            start = raw.find("{")
            if start >= 0 and '"claims"' in raw:
                end = raw.rfind("}") + 1
                data = json.loads(raw[start:end])
                arr = data.get("claims", [])
            else:
                return out
        else:
            end = raw.rfind("]") + 1
            arr = json.loads(raw[start:end])
        for item in arr:
            if isinstance(item, dict):
                s = (item.get("subject") or item.get("subject_text") or "").strip()
                p = (item.get("predicate") or item.get("predicate_text") or "").strip()
                o = (item.get("object") or item.get("object_text") or "").strip()
                c = float(item.get("confidence", 0.8))
                if s and p:
                    out.append((s[:2000], p[:500], o[:2000] if o else None, max(0, min(1, c))))
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Claim parse failed: {e}")
    return out


async def extract_claims_for_context(context_id: int) -> int:
    """
    Fetch context content, call LLM to extract claims (subject/predicate/object), insert into extracted_claims.
    Returns number of claims inserted. No-op if context has no content or LLM unavailable.
    """
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, content FROM intelligence.contexts WHERE id = %s
                """,
                (context_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return 0
        title, content = row
        text = f"{title or ''}\n\n{content or ''}"[:6000].strip()
        if len(text) < 80:
            return 0

        prompt = f"""Extract factual claims from this text as subject-predicate-object triples. One claim per line of reasoning.

Text:
{text[:5000]}

Return ONLY a JSON array (no markdown, no explanation):
[
  {{"subject": "entity or concept", "predicate": "what they did or state", "object": "target or value", "confidence": 0.9}},
  ...
]
Rules: subject and predicate required; object optional. confidence 0.0-1.0. Keep phrases short and factual."""

        llm = LLMService()
        raw = await llm._call_ollama(ModelType.LLAMA_8B, prompt)
        claims = _parse_claims_response(raw)
        if not claims:
            return 0

        conn = get_db_connection()
        if not conn:
            return 0
        inserted = 0
        try:
            with conn.cursor() as cur:
                for subject_text, predicate_text, object_text, confidence in claims:
                    try:
                        cur.execute(
                            """
                            INSERT INTO intelligence.extracted_claims
                            (context_id, subject_text, predicate_text, object_text, confidence)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (context_id, subject_text, predicate_text, object_text, confidence),
                        )
                        inserted += 1
                    except Exception as e:
                        logger.debug(f"Claim insert skip: {e}")
            conn.commit()
        finally:
            conn.close()
        if inserted > 0:
            logger.debug(f"Claims extracted for context {context_id}: {inserted}")
        return inserted
    except Exception as e:
        logger.warning(f"Claim extraction for context {context_id} failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return 0


def get_context_ids_without_claims(limit: int = 50) -> List[int]:
    """Return context IDs that have no rows in extracted_claims, for batch processing."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                ORDER BY c.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


async def run_claim_extraction_batch(limit: int = 30) -> int:
    """
    Process up to `limit` contexts that have no claims yet. Returns total claims inserted.
    """
    ids = get_context_ids_without_claims(limit=limit)
    total = 0
    for context_id in ids:
        n = await extract_claims_for_context(context_id)
        total += n
    if total > 0:
        logger.info(f"Claim extraction batch: {len(ids)} contexts processed, {total} claims inserted")
    return total
