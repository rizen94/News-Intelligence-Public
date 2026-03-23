"""
Claim extraction service — Phase 2.1 context-centric.
Extracts factual claims (subject/predicate/object) from contexts and stores in intelligence.extracted_claims.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
import re

from shared.database.connection import get_db_connection
from shared.domain_registry import get_schema_names_active, resolve_domain_schema
from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

def _claim_domain_key_to_schema(dk: str) -> str:
    from shared.domain_registry import domain_key_to_schema

    try:
        return domain_key_to_schema(dk)
    except KeyError:
        return (dk or "").replace("-", "_")


def _parse_claims_response(raw: str) -> list[tuple[str, str, str, float]]:
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
Rules: subject and predicate required; object optional. confidence 0.0-1.0. Keep phrases short and factual.
For subject, prefer a short proper noun that could match a Wikipedia-style entity name (e.g. "Japan" or "Minoru Kihara") rather than a long descriptive phrase, when the text supports it.
Keep each subject under ~80 characters when possible."""

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


def get_context_ids_without_claims(limit: int = 50) -> list[int]:
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
        logger.info(
            f"Claim extraction batch: {len(ids)} contexts processed, {total} claims inserted"
        )
    return total


# ---------------------------------------------------------------------------
# Claims → versioned_facts bridge
# ---------------------------------------------------------------------------

_PREDICATE_TO_FACT_TYPE = {
    "stated": "STATEMENT",
    "said": "STATEMENT",
    "announced": "STATEMENT",
    "declared": "STATEMENT",
    "claimed": "STATEMENT",
    "argued": "STATEMENT",
    "voted": "ACTION",
    "signed": "ACTION",
    "launched": "ACTION",
    "approved": "ACTION",
    "rejected": "ACTION",
    "imposed": "ACTION",
    "appointed": "ACTION",
    "resigned": "ACTION",
    "arrested": "ACTION",
    "holds": "POSITION",
    "supports": "POSITION",
    "opposes": "POSITION",
    "leads": "RELATIONSHIP",
    "allied with": "RELATIONSHIP",
    "is": "ATTRIBUTE",
    "was": "ATTRIBUTE",
    "has": "ATTRIBUTE",
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
) -> dict[str, int]:
    """
    Promote high-confidence extracted_claims to intelligence.versioned_facts.

    Resolution chain: extracted_claims.context_id → contexts.article_id
    → article_entities → entity_canonical → entity_profiles.

    Only promotes claims whose subject can be resolved to an entity_profile_id.
    Inserting into versioned_facts fires the DB trigger that populates
    fact_change_log, which story_state_trigger_service reads to update
    storyline_states.

    Returns counts: ``promoted``, ``candidates``, ``unresolved_subject``, ``insert_failed``.
    """
    empty = {"promoted": 0, "candidates": 0, "unresolved_subject": 0, "insert_failed": 0}
    conn = get_db_connection()
    if not conn:
        return dict(empty)
    stats = dict(empty)
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
            stats["candidates"] = len(claims)
            if not claims:
                return stats

            active_schemas = frozenset(get_schema_names_active())
            for (
                claim_id,
                context_id,
                subject,
                predicate,
                obj,
                confidence,
                valid_from,
                valid_to,
            ) in claims:
                entity_profile_id = _resolve_claim_to_entity_profile(
                    cur,
                    subject,
                    context_id,
                    active_schema_set=active_schemas,
                )
                if not entity_profile_id:
                    stats["unresolved_subject"] += 1
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
                    stats["promoted"] += 1
                except Exception as e:
                    stats["insert_failed"] += 1
                    logger.debug("promote claim %s to versioned_facts: %s", claim_id, e)

        conn.commit()
    except Exception as e:
        logger.warning("promote_claims_to_versioned_facts failed: %s", e)
        conn.rollback()
    finally:
        conn.close()
    if stats["candidates"] > 0:
        logger.info(
            "claims_to_facts batch: promoted=%s candidates=%s unresolved_subject=%s insert_failed=%s",
            stats["promoted"],
            stats["candidates"],
            stats["unresolved_subject"],
            stats["insert_failed"],
        )
    return stats


def _normalize_claim_subject(subject_text: str) -> str:
    """Strip noise so quoted names and honorifics match catalogued entities."""
    s = (subject_text or "").strip()
    s = s.strip("'\"")
    s = re.sub(r"^(dr\.?|mr\.?|mrs\.?|ms\.?|prof\.?)\s+", "", s, flags=re.I)
    return s.strip()


_LEADING_ROLE_PREFIXES = re.compile(
    r"^(?:(?:the|a)\s+)?(?:acting\s+)?(?:"
    r"chief\s+cabinet\s+secretary|"
    r"prime\s+minister|foreign\s+minister|defense\s+minister|defence\s+minister|"
    r"attorney\s+general|secretary\s+of\s+state|"
    r"white\s+house\s+press\s+secretary|press\s+secretary"
    r")\s+",
    re.I | re.X,
)

_CLAIM_SUBJECT_DEMONYMS: dict[str, str] = {
    "japanese": "japan",
    "chinese": "china",
    "russian": "russia",
    "indian": "india",
    "german": "germany",
    "french": "france",
    "british": "united kingdom",
    "american": "united states",
    "canadian": "canada",
    "australian": "australia",
    "mexican": "mexico",
    "brazilian": "brazil",
    "south korean": "south korea",
    "north korean": "north korea",
    "israeli": "israel",
    "palestinian": "palestine",
    "ukrainian": "ukraine",
    "iranian": "iran",
    "iraqi": "iraq",
    "turkish": "turkey",
    "polish": "poland",
}

# Longest phrase first so "south korean" wins over a hypothetical single-token prefix.
_LEADING_DEMONYM_ITEMS: tuple[tuple[str, str], ...] = tuple(
    sorted(_CLAIM_SUBJECT_DEMONYMS.items(), key=lambda kv: len(kv[0]), reverse=True)
)

# First word of remainder after demonym — skip geo mapping (e.g. Indian Ocean, British Columbia).
_LEADING_DEMONYM_SKIP_FIRST_TOKEN: dict[str, frozenset[str]] = {
    "indian": frozenset({"ocean"}),
    "british": frozenset({"columbia", "virgin"}),
    "french": frozenset({"guiana", "polynesia", "polynesian"}),
    "american": frozenset({"samoa", "football"}),
}


def _strip_leading_role_prefixes(s: str) -> str:
    t = (s or "").strip()
    prev = None
    while prev != t:
        prev = t
        t = _LEADING_ROLE_PREFIXES.sub("", t).strip()
    return t


def _add_remainder_entity_variants(remainder: str, add) -> None:
    """Role-strip and tail-token variants for text after a leading demonym."""
    rem = _normalize_claim_subject(remainder)
    if not rem:
        return
    add(rem)
    rlow = rem.lower()
    stripped = _strip_leading_role_prefixes(rem)
    if stripped.lower() != rlow:
        add(stripped)
    role_twice = _strip_leading_role_prefixes(stripped)
    if role_twice.lower() != stripped.lower():
        add(role_twice)
    words = [w for w in re.split(r"\s+", rem) if w]
    if len(words) >= 3:
        add(" ".join(words[-2:]))
    if len(words) >= 2:
        add(words[-1])


def _claim_subject_variant_norms(raw: str) -> list[str]:
    """Ordered unique lowercase variants for entity matching."""
    seen: set[str] = set()
    out: list[str] = []

    def add(norm: str) -> None:
        n = (norm or "").strip().lower()
        if len(n) < 2 or n in seen:
            return
        seen.add(n)
        out.append(n)

    base = _normalize_claim_subject(raw)
    if not base:
        return out
    add(base)
    low = base.lower()
    if low in _CLAIM_SUBJECT_DEMONYMS:
        add(_CLAIM_SUBJECT_DEMONYMS[low])
    else:
        for demo_word, geo in _LEADING_DEMONYM_ITEMS:
            dlen = len(demo_word)
            if not low.startswith(demo_word):
                continue
            if len(low) == dlen:
                break
            next_ch = low[dlen]
            if next_ch not in " \t,;":
                continue
            tail = base[dlen:].lstrip(" \t,;").strip()
            skip_tokens = _LEADING_DEMONYM_SKIP_FIRST_TOKEN.get(demo_word)
            if skip_tokens and tail:
                first_tok = tail.lower().split(None, 1)[0]
                if first_tok in skip_tokens:
                    continue
            add(geo)
            if tail:
                _add_remainder_entity_variants(tail, add)
            break

    stripped = _strip_leading_role_prefixes(base)
    if stripped.lower() != low:
        add(stripped)
    role_twice = _strip_leading_role_prefixes(stripped)
    if role_twice.lower() != stripped.lower():
        add(role_twice)
    words = [w for w in re.split(r"\s+", base) if w]
    if len(words) >= 3:
        add(" ".join(words[-2:]))
    if len(words) >= 2:
        add(words[-1])
    return out


def _domain_key_sql_tuple(dk: str) -> tuple[str, str, str]:
    s = str(dk)
    return (s, s.replace("_", "-"), s.replace("-", "_"))


_trgm_ext_available: bool | None = None


def _pg_trgm_available(cur) -> bool:
    global _trgm_ext_available
    if _trgm_ext_available is not None:
        return _trgm_ext_available
    try:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm' LIMIT 1")
        _trgm_ext_available = cur.fetchone() is not None
    except Exception:
        _trgm_ext_available = False
    return _trgm_ext_available


def _trgm_subject_threshold(norm_lower: str) -> float:
    return 0.52 if len(norm_lower) <= 6 else 0.40


def _resolve_claim_to_entity_profile(
    cur,
    subject_text: str,
    context_id: int | None = None,
    *,
    active_schema_set: frozenset[str] | None = None,
) -> int | None:
    """
    Resolve claim subject to entity_profiles.id using variants, then exact → fuzzy (pg_trgm).

    Prefers profiles in the same domain as the context's article when multiple rows tie.
    """
    schemas = (
        active_schema_set
        if active_schema_set is not None
        else frozenset(get_schema_names_active())
    )
    variants = _claim_subject_variant_norms(subject_text)
    if not variants:
        return None

    # Failed SELECTs inside this resolver must not abort the outer promote transaction.
    _SP = "claim_resolve_sp"
    cur.execute(f"SAVEPOINT {_SP}")

    def _rollback_sp() -> None:
        try:
            cur.execute(f"ROLLBACK TO SAVEPOINT {_SP}")
        except Exception:
            pass

    try:
        ctx_dk: str | None = None
        ctx_article_id: int | None = None
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
            r = cur.fetchone()
            if r and r[0] and r[1]:
                ctx_dk = str(r[0])
                ctx_article_id = int(r[1])

        triple = _domain_key_sql_tuple(ctx_dk) if ctx_dk else None

        def _one_int(sql: str, params: tuple) -> int | None:
            try:
                cur.execute(sql, params)
                row = cur.fetchone()
                return int(row[0]) if row and row[0] is not None else None
            except Exception as e:
                logger.debug("claim entity resolve SQL: %s", e)
                _rollback_sp()
                return None

        for norm_lower in variants:
            slen = len(norm_lower)
    
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
    
                if slen >= 4:
                    if triple:
                        d1, d2, d3 = triple
                        pid = _one_int(
                            """
                            SELECT cem.entity_profile_id
                            FROM intelligence.context_entity_mentions cem
                            JOIN intelligence.entity_profiles ep ON ep.id = cem.entity_profile_id
                            WHERE cem.context_id = %s
                              AND (
                                lower(trim(cem.mention_text)) LIKE '%%' || %s || '%%'
                                OR %s LIKE '%%' || lower(trim(cem.mention_text)) || '%%'
                              )
                              AND length(trim(cem.mention_text)) >= 3
                            ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END,
                              length(cem.mention_text) DESC
                            LIMIT 1
                            """,
                            (context_id, norm_lower, norm_lower, d1, d2, d3),
                        )
                    else:
                        pid = _one_int(
                            """
                            SELECT cem.entity_profile_id
                            FROM intelligence.context_entity_mentions cem
                            WHERE cem.context_id = %s
                              AND (
                                lower(trim(cem.mention_text)) LIKE '%%' || %s || '%%'
                                OR %s LIKE '%%' || lower(trim(cem.mention_text)) || '%%'
                              )
                              AND length(trim(cem.mention_text)) >= 3
                            ORDER BY length(cem.mention_text) DESC
                            LIMIT 1
                            """,
                            (context_id, norm_lower, norm_lower),
                        )
                    if pid:
                        return pid
    
            if ctx_article_id is not None and ctx_dk is not None:
                schema = resolve_domain_schema(ctx_dk)
                if schema in schemas:
                    d1, d2, d3 = _domain_key_sql_tuple(ctx_dk)
                    aid = ctx_article_id
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
                        ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END
                        LIMIT 1
                        """,
                        (d1, d2, d3, aid, norm_lower, d1, d2, d3),
                    )
                    if pid:
                        return pid
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
                        ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END
                        LIMIT 1
                        """,
                        (d1, d2, d3, aid, norm_lower, norm_lower, d1, d2, d3),
                    )
                    if pid:
                        return pid
                    max_ent_len = max(48, slen + 32)
                    pid = _one_int(
                        f"""
                        SELECT ep.id
                        FROM {schema}.article_entities ae
                        JOIN intelligence.entity_profiles ep
                          ON ep.canonical_entity_id = ae.canonical_entity_id
                         AND ep.domain_key IN (%s, %s, %s)
                        WHERE ae.article_id = %s
                          AND ae.canonical_entity_id IS NOT NULL
                          AND length(trim(ae.entity_name)) >= 3
                          AND length(trim(ae.entity_name)) <= %s
                          AND (
                            lower(trim(ae.entity_name)) LIKE '%%' || %s || '%%'
                            OR %s LIKE '%%' || lower(trim(ae.entity_name)) || '%%'
                          )
                        ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END,
                          length(trim(ae.entity_name)) DESC
                        LIMIT 1
                        """,
                        (d1, d2, d3, aid, max_ent_len, norm_lower, norm_lower, d1, d2, d3),
                    )
                    if pid:
                        return pid
    
            if triple:
                d1, d2, d3 = triple
                pid = _one_int(
                    """
                    SELECT id FROM intelligence.entity_profiles ep
                    WHERE lower(trim(COALESCE(metadata->>'canonical_name', ''))) = %s
                       OR lower(trim(COALESCE(metadata->>'display_name', ''))) = %s
                    ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (norm_lower, norm_lower, d1, d2, d3),
                )
            else:
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
    
            for schema in schemas:
                dk_guess = schema.replace("_", "-")
                if triple:
                    d1, d2, d3 = triple
                    pid = _one_int(
                        f"""
                        SELECT ep.id
                        FROM intelligence.entity_profiles ep
                        JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
                        WHERE ep.domain_key IN ('{schema}', '{dk_guess}')
                          AND (
                            lower(trim(ec.canonical_name)) = %s
                            OR EXISTS (
                              SELECT 1 FROM unnest(COALESCE(ec.aliases, ARRAY[]::text[])) AS al
                              WHERE lower(trim(al)) = %s
                            )
                          )
                        ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END
                        LIMIT 1
                        """,
                        (norm_lower, norm_lower, d1, d2, d3),
                    )
                else:
                    pid = _one_int(
                        f"""
                        SELECT ep.id
                        FROM intelligence.entity_profiles ep
                        JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
                        WHERE ep.domain_key IN ('{schema}', '{dk_guess}')
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
    
            if triple:
                d1, d2, d3 = triple
                pid = _one_int(
                    """
                    SELECT cem.entity_profile_id
                    FROM intelligence.context_entity_mentions cem
                    JOIN intelligence.entity_profiles ep ON ep.id = cem.entity_profile_id
                    WHERE lower(trim(cem.mention_text)) = %s
                    ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (norm_lower, d1, d2, d3),
                )
            else:
                pid = _one_int(
                    """
                    SELECT DISTINCT cem.entity_profile_id
                    FROM intelligence.context_entity_mentions cem
                    WHERE lower(trim(cem.mention_text)) = %s
                    LIMIT 1
                    """,
                    (norm_lower,),
                )
            if pid:
                return pid
    
            if _pg_trgm_available(cur) and slen >= 3:
                thr = _trgm_subject_threshold(norm_lower)
                best_key: tuple[int, float] | None = None
                best_pid: int | None = None
                for schema in schemas:
                    try:
                        if triple:
                            d1, d2, d3 = triple
                            cur.execute(
                                f"""
                                SELECT ep.id,
                                  similarity(lower(trim(ec.canonical_name)), %s) AS sc
                                FROM intelligence.entity_profiles ep
                                JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
                                WHERE char_length(trim(ec.canonical_name)) >= 2
                                  AND similarity(lower(trim(ec.canonical_name)), %s) > %s
                                ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END,
                                  sc DESC
                                LIMIT 1
                                """,
                                (norm_lower, norm_lower, thr, d1, d2, d3),
                            )
                        else:
                            cur.execute(
                                f"""
                                SELECT ep.id,
                                  similarity(lower(trim(ec.canonical_name)), %s) AS sc
                                FROM intelligence.entity_profiles ep
                                JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
                                WHERE char_length(trim(ec.canonical_name)) >= 2
                                  AND similarity(lower(trim(ec.canonical_name)), %s) > %s
                                ORDER BY sc DESC
                                LIMIT 1
                                """,
                                (norm_lower, norm_lower, thr),
                            )
                        row = cur.fetchone()
                        if not row:
                            continue
                        pid_i, sc = int(row[0]), float(row[1])
                        pref = 0
                        if triple:
                            cur.execute(
                                """
                                SELECT 1 FROM intelligence.entity_profiles
                                WHERE id = %s AND domain_key IN (%s, %s, %s)
                                """,
                                (pid_i,) + triple,
                            )
                            pref = 0 if cur.fetchone() else 1
                        key = (pref, -sc)
                        if best_key is None or key < best_key:
                            best_key, best_pid = key, pid_i
                    except Exception as e:
                        logger.debug("claim trgm canonical %s: %s", schema, e)
                        _rollback_sp()
                if best_pid is not None:
                    return best_pid
    
                try:
                    if triple:
                        d1, d2, d3 = triple
                        cur.execute(
                            """
                            SELECT ep.id,
                              GREATEST(
                                similarity(lower(trim(COALESCE(metadata->>'canonical_name', ''))), %s),
                                similarity(lower(trim(COALESCE(metadata->>'display_name', ''))), %s)
                              ) AS sc
                            FROM intelligence.entity_profiles ep
                            WHERE (
                              (COALESCE(metadata->>'canonical_name', '') <> ''
                                AND char_length(trim(metadata->>'canonical_name')) >= 2
                                AND similarity(lower(trim(metadata->>'canonical_name')), %s) > %s)
                              OR
                              (COALESCE(metadata->>'display_name', '') <> ''
                                AND char_length(trim(metadata->>'display_name')) >= 2
                                AND similarity(lower(trim(metadata->>'display_name')), %s) > %s)
                            )
                            ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END,
                              sc DESC
                            LIMIT 1
                            """,
                            (
                                norm_lower,
                                norm_lower,
                                norm_lower,
                                thr,
                                norm_lower,
                                thr,
                                d1,
                                d2,
                                d3,
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT ep.id,
                              GREATEST(
                                similarity(lower(trim(COALESCE(metadata->>'canonical_name', ''))), %s),
                                similarity(lower(trim(COALESCE(metadata->>'display_name', ''))), %s)
                              ) AS sc
                            FROM intelligence.entity_profiles ep
                            WHERE (
                              (COALESCE(metadata->>'canonical_name', '') <> ''
                                AND char_length(trim(metadata->>'canonical_name')) >= 2
                                AND similarity(lower(trim(metadata->>'canonical_name')), %s) > %s)
                              OR
                              (COALESCE(metadata->>'display_name', '') <> ''
                                AND char_length(trim(metadata->>'display_name')) >= 2
                                AND similarity(lower(trim(metadata->>'display_name')), %s) > %s)
                            )
                            ORDER BY sc DESC
                            LIMIT 1
                            """,
                            (
                                norm_lower,
                                norm_lower,
                                norm_lower,
                                thr,
                                norm_lower,
                                thr,
                            ),
                        )
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        return int(row[0])
                except Exception as e:
                    logger.debug("claim trgm metadata: %s", e)
                    _rollback_sp()

        return None
    finally:
        try:
            cur.execute(f"RELEASE SAVEPOINT {_SP}")
        except Exception:
            try:
                cur.execute(f"ROLLBACK TO SAVEPOINT {_SP}")
            except Exception:
                pass

