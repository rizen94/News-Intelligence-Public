"""
Claim extraction service — Phase 2.1 context-centric.
Extracts factual claims (subject/predicate/object) from contexts and stores in intelligence.extracted_claims.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
import re
from typing import List, Optional, Tuple

from shared.database.connection import get_db_connection
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

# domain_key on contexts / entity_profiles may be "science-tech" or "science_tech"
_DOMAIN_KEY_TO_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
    "science_tech": "science_tech",
}

_SCHEMAS = ("politics", "finance", "science_tech")


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
                SELECT title, content, metadata FROM intelligence.contexts WHERE id = %s
                """,
                (context_id,),
            )
            row = cur.fetchone()
        conn.close()
        if not row:
            return 0
        title, content, ctx_meta = row
        cred_mult = 1.0
        if ctx_meta:
            try:
                md = ctx_meta if isinstance(ctx_meta, dict) else json.loads(ctx_meta)
                if isinstance(md, dict):
                    sc = md.get("source_credibility") or {}
                    cred_mult = float(sc.get("multiplier", 1.0))
                    cred_mult = max(0.0, min(1.0, cred_mult))
            except (TypeError, ValueError, json.JSONDecodeError):
                cred_mult = 1.0
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
                        adj_conf = max(0.0, min(1.0, float(confidence) * cred_mult))
                        cur.execute(
                            """
                            INSERT INTO intelligence.extracted_claims
                            (context_id, subject_text, predicate_text, object_text, confidence)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (context_id, subject_text, predicate_text, object_text, adj_conf),
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


async def run_claim_extraction_batch(limit: int = 50) -> int:
    """
    Process up to `limit` contexts that have no claims yet. Returns total claims inserted.
    Production: max 50 contexts (LLM rate limits), 2-5s per context, ~20-50s total; parallel_requests=5.
    """
    ids = get_context_ids_without_claims(limit=limit)
    total = 0
    for context_id in ids:
        n = await extract_claims_for_context(context_id)
        total += n
    if total > 0:
        logger.info(f"Claim extraction batch: {len(ids)} contexts processed, {total} claims inserted")
    return total


# ---------------------------------------------------------------------------
# Claims → versioned_facts bridge
# ---------------------------------------------------------------------------

_PREDICATE_TO_FACT_TYPE = {
    "stated": "STATEMENT", "said": "STATEMENT", "announced": "STATEMENT",
    "declared": "STATEMENT", "claimed": "STATEMENT", "argued": "STATEMENT",
    "voted": "ACTION", "signed": "ACTION", "launched": "ACTION",
    "approved": "ACTION", "rejected": "ACTION", "imposed": "ACTION",
    "appointed": "ACTION", "resigned": "ACTION", "arrested": "ACTION",
    "holds": "POSITION", "supports": "POSITION", "opposes": "POSITION",
    "leads": "RELATIONSHIP", "allied with": "RELATIONSHIP",
    "is": "ATTRIBUTE", "was": "ATTRIBUTE", "has": "ATTRIBUTE",
}


def _map_predicate_to_fact_type(predicate: str) -> str:
    lower = predicate.lower().strip()
    for keyword, ftype in _PREDICATE_TO_FACT_TYPE.items():
        if keyword in lower:
            return ftype
    return "STATEMENT"


def promote_claims_to_versioned_facts(
    min_confidence: float = 0.7,
    limit: int = 100,
) -> int:
    """
    Promote high-confidence extracted_claims to intelligence.versioned_facts.

    Resolution chain: extracted_claims.context_id → contexts.article_id
    → article_entities → entity_canonical → entity_profiles.

    Only promotes claims whose subject can be resolved to an entity_profile_id.
    Inserting into versioned_facts fires the DB trigger that populates
    fact_change_log, which story_state_trigger_service reads to update
    storyline_states.
    """
    conn = get_db_connection()
    if not conn:
        return 0
    promoted = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ec.id, ec.context_id, ec.subject_text, ec.predicate_text, ec.object_text,
                       ec.confidence, ec.valid_from, ec.valid_to
                FROM intelligence.extracted_claims ec
                WHERE ec.confidence >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM intelligence.versioned_facts vf
                      WHERE vf.metadata->>'source_claim_id' = ec.id::text
                  )
                ORDER BY ec.confidence DESC
                LIMIT %s
                """,
                (min_confidence, limit),
            )
            claims = cur.fetchall()
            if not claims:
                return 0

            for claim_id, context_id, subject, predicate, obj, confidence, valid_from, valid_to in claims:
                entity_profile_id = _resolve_claim_to_entity_profile(cur, subject, context_id)
                if not entity_profile_id:
                    continue

                fact_type = _map_predicate_to_fact_type(predicate or "")
                fact_text = f"{subject} {predicate}"
                if obj:
                    fact_text += f" {obj}"

                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.versioned_facts
                            (entity_profile_id, fact_type, fact_text, confidence,
                             valid_from, valid_to, extraction_method, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, 'claim_extraction', %s)
                        """,
                        (
                            entity_profile_id,
                            fact_type,
                            fact_text[:2000],
                            confidence,
                            valid_from,
                            valid_to,
                            json.dumps({"source_claim_id": str(claim_id)}),
                        ),
                    )
                    promoted += 1
                except Exception as e:
                    logger.debug("promote claim %s to versioned_facts: %s", claim_id, e)

        conn.commit()
    except Exception as e:
        logger.warning("promote_claims_to_versioned_facts failed: %s", e)
        conn.rollback()
    finally:
        conn.close()
    if promoted:
        logger.info("Promoted %d claims to versioned_facts", promoted)
    return promoted


def _normalize_claim_subject(subject_text: str) -> str:
    """Strip noise so 'Japan' / 'Japan' / trailing quotes match canonical names."""
    s = (subject_text or "").strip()
    s = s.strip("'\"")  # outer quotes from LLM
    s = re.sub(r"^(dr\.?|mr\.?|mrs\.?|ms\.?|prof\.?)\s+", "", s, flags=re.I)
    return s.strip()


def _resolve_claim_to_entity_profile(
    cur,
    subject_text: str,
    context_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resolve claim subject_text to intelligence.entity_profiles.id.

    Order (first hit wins):
    1) Same-context context_entity_mentions (exact, then bidirectional ILIKE for longer strings)
    2) Article entities for the context's article (domain schema) — name / canonical_name / aliases
    3) entity_profiles.metadata canonical_name / display_name
    4) entity_profiles joined to domain entity_canonical (canonical_name + aliases) for all domains

    Note: An earlier implementation referenced ep.display_name and a broken old_entity_to_new join;
    that raised on every call (column does not exist), blocking all promotions.
    """
    subject_raw = (subject_text or "").strip()
    subject = _normalize_claim_subject(subject_raw)
    if not subject:
        return None

    norm_lower = subject.lower()

    def _one_int(sql: str, params: tuple) -> Optional[int]:
        try:
            cur.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None
        except Exception as e:
            logger.debug("claim entity resolve SQL: %s", e)
            return None

    # --- 1) Context-scoped mentions (strongest signal) ---
    if context_id is not None:
        pid = _one_int(
            """
            SELECT cem.entity_profile_id
            FROM intelligence.context_entity_mentions cem
            WHERE cem.context_id = %s
              AND lower(trim(cem.mention_text)) = %s
            LIMIT 1
            """,
            (context_id, norm_lower),
        )
        if pid:
            return pid

        if len(subject) >= 4:
            pid = _one_int(
                """
                SELECT cem.entity_profile_id
                FROM intelligence.context_entity_mentions cem
                WHERE cem.context_id = %s
                  AND (
                    lower(trim(%s)) LIKE '%%' || lower(trim(cem.mention_text)) || '%%'
                    OR lower(trim(cem.mention_text)) LIKE '%%' || lower(trim(%s)) || '%%'
                  )
                  AND length(trim(cem.mention_text)) >= 3
                ORDER BY length(cem.mention_text) DESC
                LIMIT 1
                """,
                (context_id, subject, subject),
            )
            if pid:
                return pid

    # --- 2) Article entities for this context's article ---
    if context_id is not None:
        cur.execute(
            """
            SELECT domain_key, article_id
            FROM intelligence.article_to_context
            WHERE context_id = %s
            LIMIT 1
            """,
            (context_id,),
        )
        row = cur.fetchone()
        if row and row[0] and row[1]:
            dk, article_id = row[0], row[1]
            schema = _DOMAIN_KEY_TO_SCHEMA.get(dk) or _DOMAIN_KEY_TO_SCHEMA.get(
                str(dk).replace("-", "_")
            )
            if schema and schema in _SCHEMAS:
                pid = _one_int(
                    f"""
                    SELECT ep.id
                    FROM {schema}.article_entities ae
                    JOIN intelligence.entity_profiles ep
                      ON ep.canonical_entity_id = ae.canonical_entity_id
                     AND ep.domain_key IN (%s, %s, %s)
                    WHERE ae.article_id = %s
                      AND ae.canonical_entity_id IS NOT NULL
                      AND lower(trim(ae.entity_name)) = %s
                    LIMIT 1
                    """,
                    (dk, dk.replace("_", "-"), dk.replace("-", "_"), article_id, norm_lower),
                )
                if pid:
                    return pid
                # canonical_name match on linked entity_canonical
                pid = _one_int(
                    f"""
                    SELECT ep.id
                    FROM {schema}.article_entities ae
                    JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                    JOIN intelligence.entity_profiles ep
                      ON ep.canonical_entity_id = ec.id
                     AND ep.domain_key IN (%s, %s, %s)
                    WHERE ae.article_id = %s
                      AND ae.canonical_entity_id IS NOT NULL
                      AND (
                        lower(trim(ec.canonical_name)) = %s
                        OR EXISTS (
                          SELECT 1
                          FROM unnest(COALESCE(ec.aliases, ARRAY[]::text[])) AS al
                          WHERE lower(trim(al)) = %s
                        )
                      )
                    LIMIT 1
                    """,
                    (dk, dk.replace("_", "-"), dk.replace("-", "_"), article_id, norm_lower, norm_lower),
                )
                if pid:
                    return pid

    # --- 3) entity_profiles.metadata ---
    pid = _one_int(
        """
        SELECT id FROM intelligence.entity_profiles
        WHERE lower(trim(COALESCE(metadata->>'canonical_name', ''))) = %s
           OR lower(trim(COALESCE(metadata->>'display_name', ''))) = %s
        LIMIT 1
        """,
        (norm_lower, norm_lower),
    )
    if pid:
        return pid

    # --- 4) Any domain entity_canonical ↔ profile ---
    for schema in _SCHEMAS:
        pid = _one_int(
            f"""
            SELECT ep.id
            FROM intelligence.entity_profiles ep
            JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
            WHERE ep.domain_key IN ('{schema}', '{schema.replace("_", "-")}')
              AND (
                lower(trim(ec.canonical_name)) = %s
                OR EXISTS (
                  SELECT 1 FROM unnest(COALESCE(ec.aliases, ARRAY[]::text[])) AS al
                  WHERE lower(trim(al)) = %s
                )
              )
            LIMIT 1
            """,
            (norm_lower, norm_lower),
        )
        if pid:
            return pid

    # --- 5) Legacy: global mention text (weaker; last resort) ---
    return _one_int(
        """
        SELECT DISTINCT cem.entity_profile_id
        FROM intelligence.context_entity_mentions cem
        WHERE lower(trim(cem.mention_text)) = %s
        LIMIT 1
        """,
        (norm_lower,),
    )
