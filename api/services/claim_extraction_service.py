"""
Claim extraction service — Phase 2.1 context-centric.
Extracts factual claims (subject/predicate/object) from contexts and stores in intelligence.extracted_claims.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import NamedTuple

from shared.database.connection import get_db_connection
from shared.domain_registry import (
    get_pipeline_schema_names_active,
    pipeline_url_schema_pairs,
    resolve_domain_schema,
)
from shared.services.ollama_model_caller import get_ollama_model_caller
from shared.services.ollama_model_policy import InvocationKind

logger = logging.getLogger(__name__)

_GENERIC_SUBJECTS = frozenset(
    {
        "company",
        "companies",
        "administration",
        "government",
        "public",
        "people",
        "person",
        "official",
        "officials",
        "officer",
        "officers",
        "investigator",
        "investigators",
        "source",
        "sources",
        "analyst",
        "analysts",
        "method",
        "methods",
        "approach",
        "approaches",
        "model",
        "models",
        "system",
        "systems",
        "report",
        "reports",
        "study",
        "studies",
        "paper",
        "papers",
        "price target",
        "target price",
        "consumer",
        "consumers",
        "customer",
        "customers",
        "parent",
        "parents",
        "women",
        "men",
        "i",
        "we",
        "they",
        "it",
        "this",
        "that",
    }
)


def _subject_norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _claim_text_norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _claims_to_facts_check_merged_source_ids() -> bool:
    """
    Optional extra dedupe gate for merged source_claim_ids in versioned_facts metadata.
    Disabled by default for throughput; this JSONB membership check can be expensive at scale.
    """
    return os.environ.get("CLAIMS_TO_FACTS_CHECK_MERGED_SOURCE_IDS", "").lower() in (
        "1",
        "true",
        "yes",
    )


def _is_overly_generic_subject(subject_text: str | None) -> bool:
    s = _subject_norm(subject_text)
    if not s:
        return True
    if s in _GENERIC_SUBJECTS:
        return True
    if len(s) <= 1:
        return True
    if re.fullmatch(r"[a-z]", s):
        return True
    if re.fullmatch(r"(the\s+)?(company|government|administration|public|people|officials?)", s):
        return True
    return False


def _claim_extraction_strict_seeded_domain_keys() -> frozenset[str]:
    """
    Optional allowlist of domains where claim subjects must match existing canonical/profile names
    before insertion into extracted_claims.
    """
    raw = os.environ.get("CLAIM_EXTRACTION_REQUIRE_SEEDED_DOMAIN_KEYS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())


def _subject_matches_seeded_pool(cur, domain_key: str, subject_text: str) -> bool:
    """Fast exact normalized match against entity_profiles canonical_name or domain entity_canonical."""
    norm = _subject_norm(subject_text)
    if not norm:
        return False
    schema = _claim_domain_key_to_schema(domain_key)
    cur.execute(
        """
        SELECT 1
        FROM intelligence.entity_profiles ep
        WHERE lower(trim(COALESCE(ep.metadata->>'canonical_name', ''))) = %s
        LIMIT 1
        """,
        (norm,),
    )
    if cur.fetchone():
        return True
    cur.execute(
        f"""
        SELECT 1
        FROM {schema}.entity_canonical ec
        WHERE lower(trim(ec.canonical_name)) = %s
        LIMIT 1
        """,
        (norm,),
    )
    return bool(cur.fetchone())


def claim_pipeline_max_fetch() -> int:
    """
    When CLAIM_EXTRACTION_BATCH_LIMIT or CLAIMS_TO_FACTS_BATCH_LIMIT is <= 0 (meaning "no explicit cap"),
    use this as the single SELECT LIMIT. Raise CLAIM_PIPELINE_MAX_FETCH if you need larger slices
    (memory and lock duration grow with batch size).
    """
    try:
        n = int(os.environ.get("CLAIM_PIPELINE_MAX_FETCH", "500000"))
    except ValueError:
        n = 500_000
    return max(1, n)


def get_claim_extraction_batch_limit() -> int:
    """Contexts per claim_extraction invocation. <=0 means use claim_pipeline_max_fetch()."""
    try:
        n = int(os.environ.get("CLAIM_EXTRACTION_BATCH_LIMIT", "4000"))
    except ValueError:
        n = 4000
    if n <= 0:
        return claim_pipeline_max_fetch()
    return n


def get_claim_extraction_parallel() -> int:
    """
    Concurrent LLM extractions per batch. No hard upper bound (tune to GPU / Ollama capacity).
    If CLAIM_EXTRACTION_PARALLEL <= 0, concurrency equals min(batch, claim_pipeline_max_fetch())
    so fanout tracks batch without spawning more coroutines than contexts selected.

    Optional CLAIM_EXTRACTION_PARALLEL_DAYTIME_MAX: when >0 and outside the unified nightly
    pipeline window, parallel is min(env_parallel, daytime_max) so one batch does not saturate
    the GPU while other phases could use the cluster.
    """
    batch = get_claim_extraction_batch_limit()
    try:
        n = int(os.environ.get("CLAIM_EXTRACTION_PARALLEL", "48"))
    except ValueError:
        n = 48
    if n <= 0:
        n = max(1, min(batch, claim_pipeline_max_fetch()))
    else:
        n = max(1, n)
    try:
        daytime_max = int(os.environ.get("CLAIM_EXTRACTION_PARALLEL_DAYTIME_MAX", "0") or 0)
        if daytime_max > 0:
            from services.nightly_ingest_window_service import in_nightly_pipeline_window_est

            if not in_nightly_pipeline_window_est():
                n = min(n, daytime_max)
    except Exception:
        pass
    return n


def get_claims_to_facts_batch_limit() -> int:
    """Max extracted_claims rows attempted per promote_claims_to_versioned_facts call. <=0 → claim_pipeline_max_fetch()."""
    try:
        n = int(os.environ.get("CLAIMS_TO_FACTS_BATCH_LIMIT", "10000"))
    except ValueError:
        n = 10_000
    if n <= 0:
        return claim_pipeline_max_fetch()
    return n


def get_claims_to_facts_min_confidence() -> float:
    try:
        return float(os.environ.get("CLAIMS_TO_FACTS_MIN_CONFIDENCE", "0.75"))
    except ValueError:
        return 0.75


def get_nightly_claims_to_facts_batch_limit() -> int:
    """
    Slice size for each ``promote_claims_to_versioned_facts`` call during **nightly sequential** drain.

    When ``NIGHTLY_CLAIMS_TO_FACTS_BATCH_LIMIT`` is unset, use the same value as
    ``CLAIMS_TO_FACTS_BATCH_LIMIT`` (via ``get_claims_to_facts_batch_limit()``) so night matches day.
    Set explicitly to cap a single nightly batch smaller than daytime if needed.
    """
    raw = os.environ.get("NIGHTLY_CLAIMS_TO_FACTS_BATCH_LIMIT", "").strip()
    if not raw:
        return get_claims_to_facts_batch_limit()
    try:
        n = int(raw)
    except ValueError:
        return get_claims_to_facts_batch_limit()
    return max(1, n)


def claims_to_facts_drain_enabled() -> bool:
    """Daytime automation: loop promote batches until idle or a guard trips (default on). Nightly sequential uses one batch per outer loop."""
    return os.environ.get("CLAIMS_TO_FACTS_DRAIN", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _claims_to_facts_drain_max_batches() -> int:
    try:
        n = int(os.environ.get("CLAIMS_TO_FACTS_DRAIN_MAX_BATCHES", "0"))
    except ValueError:
        n = 0
    return max(0, n)


def _claims_to_facts_drain_max_seconds() -> float:
    try:
        x = float(os.environ.get("CLAIMS_TO_FACTS_DRAIN_MAX_SECONDS", "0") or 0)
    except ValueError:
        x = 0.0
    return max(0.0, x)


def _claims_to_facts_drain_max_zero_promote_batches() -> int:
    """Stop after N consecutive batches with candidates but zero promotions (unresolved / stuck)."""
    try:
        n = int(os.environ.get("CLAIMS_TO_FACTS_DRAIN_MAX_ZERO_PROMOTE_BATCHES", "5"))
    except ValueError:
        n = 5
    return max(1, n)


def _persist_claims_to_facts_batch_run(started: datetime, finished: datetime) -> None:
    try:
        from shared.services.automation_run_history_writer import persist_automation_run_history

        persist_automation_run_history("claims_to_facts", started, finished, True, None)
    except Exception as e:
        logger.debug("claims_to_facts batch history persist failed: %s", e)


async def drain_claims_to_facts_for_automation_task(
    *,
    per_batch_limit: int | None = None,
) -> tuple[int, int]:
    """
    Run claim promotion in a loop until no candidates remain or a guard trips.

    Used for **scheduled** (non-nightly-sequential) automation so one worker can burn backlog
    without waiting for the next scheduler tick. Nightly unified drain keeps one promote per
    ``run_nightly_sequential_phase`` call; outer ``NIGHTLY_SEQUENTIAL_PHASE_LOOP_CAPS`` repeats that.

    Returns (total_promoted, batch_count).
    """
    max_batches = _claims_to_facts_drain_max_batches()
    max_sec = _claims_to_facts_drain_max_seconds()
    max_zero = _claims_to_facts_drain_max_zero_promote_batches()
    t0 = time.monotonic()
    total_promoted = 0
    batches = 0
    zero_streak = 0

    while True:
        if max_batches > 0 and batches >= max_batches:
            logger.info(
                "claims_to_facts drain stopping: CLAIMS_TO_FACTS_DRAIN_MAX_BATCHES=%s",
                max_batches,
            )
            break
        if max_sec > 0 and (time.monotonic() - t0) >= max_sec:
            logger.info(
                "claims_to_facts drain stopping: CLAIMS_TO_FACTS_DRAIN_MAX_SECONDS=%s",
                max_sec,
            )
            break

        batch_started = datetime.now(timezone.utc)
        if per_batch_limit is not None:
            stats = await asyncio.to_thread(
                promote_claims_to_versioned_facts,
                None,
                int(per_batch_limit),
            )
        else:
            stats = await asyncio.to_thread(promote_claims_to_versioned_facts)
        batch_finished = datetime.now(timezone.utc)
        await asyncio.to_thread(_persist_claims_to_facts_batch_run, batch_started, batch_finished)
        batches += 1

        if not isinstance(stats, dict):
            break
        promoted = int(stats.get("promoted") or 0)
        candidates = int(stats.get("candidates") or 0)
        total_promoted += promoted

        if candidates == 0:
            break

        if promoted == 0:
            zero_streak += 1
            if zero_streak >= max_zero:
                logger.warning(
                    "claims_to_facts drain stopping: %s consecutive batches with 0 promotions "
                    "(candidates=%s — check entity resolution / gap ignore / seeding)",
                    max_zero,
                    candidates,
                )
                break
        else:
            zero_streak = 0

        await asyncio.sleep(0)

    if batches > 1 or total_promoted > 0:
        logger.info(
            "claims_to_facts drain finished: %s batches, %s rows promoted",
            batches,
            total_promoted,
        )
    return total_promoted, batches


# Exclude from promotion/backlog counts when operators mark a (domain, subject_norm) as ignored
# in intelligence.claim_subject_gap_catalog (vague subjects not worth a synthetic entity).
CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL = """
  AND NOT EXISTS (
    SELECT 1
    FROM intelligence.article_to_context atc
    INNER JOIN intelligence.claim_subject_gap_catalog g
      ON g.domain_key = atc.domain_key
     AND g.subject_norm = lower(trim(COALESCE(ec.subject_text, '')))
     AND g.status = 'ignored'
    WHERE atc.context_id = ec.context_id
  )"""


def claim_promotion_generic_subject_exclude_sql() -> str:
    """SQL AND-clauses for subjects ``promote_claims_to_versioned_facts`` skips via ``_is_overly_generic_subject`` (exact-set + length)."""
    parts = sorted(_GENERIC_SUBJECTS)
    inner = ", ".join("'" + p.replace("'", "''") + "'" for p in parts)
    return f"""
  AND char_length(trim(COALESCE(ec.subject_text, ''))) > 1
  AND lower(trim(COALESCE(ec.subject_text, ''))) NOT IN ({inner})
  AND NOT (lower(trim(COALESCE(ec.subject_text, ''))) ~ '^[a-z]$')
""".rstrip()


def claims_to_facts_versioned_fact_absent_sql() -> str:
    """Same NOT EXISTS as ``promote_claims_to_versioned_facts`` (optional merged source_claim_ids guard)."""
    merged = ""
    if _claims_to_facts_check_merged_source_ids():
        merged = " OR COALESCE(vf.metadata->'source_claim_ids', '[]'::jsonb) ? ec.id::text"
    return f"""
  AND NOT EXISTS (
    SELECT 1 FROM intelligence.versioned_facts vf
    WHERE vf.metadata->>'source_claim_id' = ec.id::text{merged}
  )"""


def _claims_to_facts_article_entity_exact_subject_sql() -> str:
    """EXISTS clauses: article_entities.entity_name equals claim subject (per pipeline domain)."""
    clauses: list[str] = []
    for dk, schema in pipeline_url_schema_pairs():
        if not re.fullmatch(r"[a-z0-9-]+", dk or ""):
            continue
        if not re.fullmatch(r"[a-z0-9_]+", schema or ""):
            continue
        clauses.append(
            f"""EXISTS (
    SELECT 1 FROM intelligence.article_to_context atc
    INNER JOIN {schema}.article_entities ae ON ae.article_id = atc.article_id
    WHERE atc.context_id = ec.context_id AND atc.domain_key = '{dk}'
      AND ae.canonical_entity_id IS NOT NULL
      AND lower(trim(ae.entity_name)) = lower(trim(COALESCE(ec.subject_text, '')))
  )"""
        )
    if not clauses:
        return "FALSE"
    if len(clauses) == 1:
        return clauses[0]
    return "(" + " OR ".join(clauses) + ")"


def claims_to_facts_resolvable_hint_predicate_sql() -> str:
    """
    Approximation of claims likely to resolve without fuzzy/trgm passes (context mention exact,
    global profile canonical/display exact, or article_entities exact name on linked article).
    Used for Monitor ``pending_records`` so the number is closer to promotable work than raw SQL candidates.
    """
    ae = _claims_to_facts_article_entity_exact_subject_sql()
    return f"""(
  EXISTS (
    SELECT 1 FROM intelligence.context_entity_mentions cem
    WHERE cem.context_id = ec.context_id
      AND lower(trim(cem.mention_text)) = lower(trim(COALESCE(ec.subject_text, '')))
  )
  OR EXISTS (
    SELECT 1 FROM intelligence.entity_profiles ep
    WHERE lower(trim(COALESCE(ep.metadata->>'canonical_name', ''))) = lower(trim(COALESCE(ec.subject_text, '')))
       OR lower(trim(COALESCE(ep.metadata->>'display_name', ''))) = lower(trim(COALESCE(ec.subject_text, '')))
  )
  OR {ae}
)"""


def get_claims_to_facts_backlog_count_mode() -> str:
    """
    ``promotable_hint`` (default): backlog count uses generic-subject exclusion + resolvable-hint predicate.
    ``batch_candidate``: count all SQL batch candidates (confidence + not in versioned_facts + gap ignore + generic),
    matching promote's row set before per-row resolution (can be very large).
    """
    raw = os.environ.get("CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE", "promotable_hint").strip().lower()
    if raw in ("batch_candidate", "candidate", "candidates", "all", "all_candidates"):
        return "batch_candidate"
    return "promotable_hint"


def build_claims_to_facts_backlog_where_suffix() -> str:
    """Fragment appended after ``WHERE ec.confidence >= %s`` for ``_count_claims_to_facts_pending``."""
    base = (
        claims_to_facts_versioned_fact_absent_sql()
        + CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL
        + claim_promotion_generic_subject_exclude_sql()
    )
    if get_claims_to_facts_backlog_count_mode() == "batch_candidate":
        return base
    return base + " AND " + claims_to_facts_resolvable_hint_predicate_sql()


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
                SELECT title, content, metadata, domain_key FROM intelligence.contexts WHERE id = %s
                """,
                (context_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return 0
    title, content, ctx_meta, context_domain_key = row
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

    try:
        caller = get_ollama_model_caller()
        gen = await caller.generate(
            prompt,
            kind=InvocationKind.STRUCTURED_EXTRACTION,
            approx_prompt_chars=len(prompt),
        )
        raw = gen.text
    except Exception as e:
        logger.warning("Claim extraction LLM failed for context %s: %s", context_id, e)
        return 0

    claims = _parse_claims_response(raw)
    parse_ok = len(claims) > 0
    logger.info(
        "claim_extraction_parsed context_id=%s model=%s parse_nonempty=%s",
        context_id,
        gen.model,
        parse_ok,
    )
    if not claims:
        return 0

    conn = get_db_connection()
    if not conn:
        return 0
    inserted = 0
    skipped_generic = 0
    skipped_unseeded = 0
    strict_domains = _claim_extraction_strict_seeded_domain_keys()
    strict_seeded = bool(context_domain_key and context_domain_key in strict_domains)
    try:
        with conn.cursor() as cur:
            for subject_text, predicate_text, object_text, confidence in claims:
                try:
                    if _is_overly_generic_subject(subject_text):
                        skipped_generic += 1
                        continue
                    if strict_seeded and not _subject_matches_seeded_pool(
                        cur, str(context_domain_key), subject_text
                    ):
                        skipped_unseeded += 1
                        continue
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
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning("Claim extraction insert failed for context %s: %s", context_id, e)
        return 0
    finally:
        conn.close()

    if inserted > 0:
        logger.debug(f"Claims extracted for context {context_id}: {inserted}")
    if skipped_generic > 0 or skipped_unseeded > 0:
        logger.info(
            "claim_extraction_filters context_id=%s domain=%s skipped_generic=%s skipped_unseeded=%s strict_seeded=%s",
            context_id,
            context_domain_key,
            skipped_generic,
            skipped_unseeded,
            strict_seeded,
        )
    return inserted


class ClaimExtractionBatchResult(NamedTuple):
    """One claim_extraction batch: claims inserted and contexts attempted (including 0-claim outcomes)."""

    claims_inserted: int
    contexts_processed: int


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


async def run_claim_extraction_batch(limit: int | None = None) -> ClaimExtractionBatchResult:
    """
    Process up to `limit` contexts that have no claims yet.
    If ``limit`` is None, uses get_claim_extraction_batch_limit().
    Concurrency: get_claim_extraction_parallel() (env CLAIM_EXTRACTION_PARALLEL; no fixed code cap).
    """
    if limit is None:
        limit = get_claim_extraction_batch_limit()
    ids = get_context_ids_without_claims(limit=limit)
    if not ids:
        return ClaimExtractionBatchResult(0, 0)
    parallel = get_claim_extraction_parallel()
    try:
        chunk_sz = int(os.environ.get("CLAIM_EXTRACTION_INTERNAL_CHUNK", "0"))
    except ValueError:
        chunk_sz = 0
    if chunk_sz <= 0:
        chunk_sz = max(parallel * 10, 96)
    chunk_sz = max(chunk_sz, parallel)

    total = 0
    for off in range(0, len(ids), chunk_sz):
        chunk = ids[off : off + chunk_sz]
        sem = asyncio.Semaphore(parallel)

        async def _one(cid: int) -> int:
            async with sem:
                return await extract_claims_for_context(cid)

        results = await asyncio.gather(*[_one(cid) for cid in chunk], return_exceptions=True)
        for r in results:
            if isinstance(r, int):
                total += r
            elif isinstance(r, Exception):
                logger.debug("claim extraction batch item failed: %s", r)
        if len(ids) > chunk_sz:
            logger.info(
                "claim_extraction progress %s/%s contexts (chunk size %s)",
                min(off + len(chunk), len(ids)),
                len(ids),
                len(chunk),
            )
        await asyncio.sleep(0)

    if total > 0:
        logger.info(
            "Claim extraction batch: %s contexts processed, %s claims inserted",
            len(ids),
            total,
        )
    return ClaimExtractionBatchResult(total, len(ids))


def _claim_extraction_drain_max_batches() -> int:
    try:
        n = int(os.environ.get("CLAIM_EXTRACTION_DRAIN_MAX_BATCHES", "0"))
    except ValueError:
        n = 0
    return max(0, n)


def _claim_extraction_drain_max_seconds() -> float:
    try:
        x = float(os.environ.get("CLAIM_EXTRACTION_DRAIN_MAX_SECONDS", "0") or 0)
    except ValueError:
        x = 0.0
    return max(0.0, x)


def _claim_extraction_drain_max_zero_claim_batches() -> int:
    """Stop drain after this many consecutive batches with contexts but 0 claims inserted (stuck / all filtered)."""
    try:
        n = int(os.environ.get("CLAIM_EXTRACTION_DRAIN_MAX_ZERO_CLAIM_BATCHES", "3"))
    except ValueError:
        n = 3
    return max(1, n)


def claim_extraction_drain_enabled() -> bool:
    """Single automation task loops batches until idle (default). Set CLAIM_EXTRACTION_DRAIN=false for one batch only."""
    return os.environ.get("CLAIM_EXTRACTION_DRAIN", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _persist_claim_extraction_batch_run(started: datetime, finished: datetime) -> None:
    """One automation_run_history row per completed batch (drain keeps work in one scheduler task)."""
    try:
        from shared.services.automation_run_history_writer import persist_automation_run_history

        persist_automation_run_history("claim_extraction", started, finished, True, None)
    except Exception as e:
        logger.debug("claim_extraction batch history persist failed: %s", e)


async def drain_claim_extraction_for_automation_task(
    *,
    nightly_limit: int | None = None,
) -> tuple[int, int]:
    """
    Run claim extraction until no contexts remain without extracted_claims rows, or a guard trips.

    Uses one automation worker for the whole drain (pair with AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES=claim_extraction:1).
    Other automation workers stay free for other phases; GPU/CPU sharing with those phases is handled by LLM lane
    semaphores and the resource router — not by slicing claim work into many queued tasks.

    Returns (total_claims_inserted, batch_count).
    """
    lim = int(nightly_limit) if nightly_limit is not None else None
    max_batches = _claim_extraction_drain_max_batches()
    max_sec = _claim_extraction_drain_max_seconds()
    max_zero = _claim_extraction_drain_max_zero_claim_batches()
    t0 = time.monotonic()
    total_claims = 0
    batches = 0
    zero_streak = 0

    while True:
        if max_batches > 0 and batches >= max_batches:
            logger.info(
                "claim_extraction drain stopping: CLAIM_EXTRACTION_DRAIN_MAX_BATCHES=%s",
                max_batches,
            )
            break
        if max_sec > 0 and (time.monotonic() - t0) >= max_sec:
            logger.info(
                "claim_extraction drain stopping: CLAIM_EXTRACTION_DRAIN_MAX_SECONDS=%s",
                max_sec,
            )
            break

        batch_started = datetime.now(timezone.utc)
        res = await run_claim_extraction_batch(limit=lim)
        batch_finished = datetime.now(timezone.utc)
        await asyncio.to_thread(_persist_claim_extraction_batch_run, batch_started, batch_finished)
        batches += 1
        total_claims += res.claims_inserted

        if res.contexts_processed == 0:
            break

        if res.claims_inserted == 0:
            zero_streak += 1
            if zero_streak >= max_zero:
                logger.warning(
                    "claim_extraction drain stopping: %s consecutive batches with 0 claims "
                    "(contexts still lack rows — check strict_seeded filters / LLM parse)",
                    max_zero,
                )
                break
        else:
            zero_streak = 0

        await asyncio.sleep(0)

    if batches > 1 or total_claims > 0:
        logger.info(
            "claim_extraction drain finished: %s batches, %s claims inserted",
            batches,
            total_claims,
        )
    return total_claims, batches


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
    min_confidence: float | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """
    Promote high-confidence extracted_claims to intelligence.versioned_facts.

    Resolution chain: extracted_claims.context_id → contexts.article_id
    → article_entities → entity_canonical → entity_profiles.

    Only promotes claims whose subject can be resolved to an entity_profile_id.
    Inserting into versioned_facts fires the DB trigger that populates
    fact_change_log, which story_state_trigger_service reads to update
    storyline_states.

    Uses ``FOR UPDATE OF ec SKIP LOCKED`` so multiple processes can promote in parallel without
    duplicating work on the same claim rows (each worker takes disjoint locks).

    ``min_confidence`` / ``limit`` default from ``CLAIMS_TO_FACTS_MIN_CONFIDENCE`` /
    ``CLAIMS_TO_FACTS_BATCH_LIMIT`` (and claim_pipeline_max_fetch when limit <= 0).

    Returns counts: ``promoted``, ``candidates``, ``unresolved_subject``, ``insert_failed``,
    plus batch-local merge telemetry.
    """
    if min_confidence is None:
        min_confidence = get_claims_to_facts_min_confidence()
    if limit is None:
        limit = get_claims_to_facts_batch_limit()
    empty = {
        "promoted": 0,
        "candidates": 0,
        "unresolved_subject": 0,
        "insert_failed": 0,
        "generic_subject_skipped": 0,
        "merged_groups": 0,
        "merged_claims_collapsed": 0,
    }
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
                """
                + claims_to_facts_versioned_fact_absent_sql()
                + CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL
                + claim_promotion_generic_subject_exclude_sql()
                + """
                ORDER BY ec.confidence DESC
                LIMIT %s
                FOR UPDATE OF ec SKIP LOCKED
                """,
                (min_confidence, limit),
            )
            claims = cur.fetchall()
            stats["candidates"] = len(claims)
            if not claims:
                conn.commit()
                return stats

            active_schemas = frozenset(get_pipeline_schema_names_active())
            grouped: dict[tuple, dict[str, object]] = {}
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
                if _is_overly_generic_subject(subject):
                    stats["generic_subject_skipped"] += 1
                    continue
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
                key = (
                    int(entity_profile_id),
                    fact_type,
                    _claim_text_norm(subject),
                    _claim_text_norm(predicate),
                    _claim_text_norm(obj),
                    valid_from.isoformat() if hasattr(valid_from, "isoformat") else str(valid_from),
                    valid_to.isoformat() if hasattr(valid_to, "isoformat") else str(valid_to),
                )
                group = grouped.get(key)
                if not group:
                    grouped[key] = {
                        "claim_ids": [int(claim_id)],
                        "entity_profile_id": int(entity_profile_id),
                        "fact_type": fact_type,
                        "subject": subject or "",
                        "predicate": predicate or "",
                        "obj": obj or "",
                        "confidence": float(confidence or 0.0),
                        "valid_from": valid_from,
                        "valid_to": valid_to,
                    }
                else:
                    group["claim_ids"].append(int(claim_id))
                    group["confidence"] = max(
                        float(group.get("confidence") or 0.0),
                        float(confidence or 0.0),
                    )

            stats["merged_groups"] = len(grouped)
            for group in grouped.values():
                claim_ids = list(group.get("claim_ids") or [])
                if len(claim_ids) > 1:
                    stats["merged_claims_collapsed"] += len(claim_ids) - 1
                subject_text = str(group.get("subject") or "")
                predicate_text = str(group.get("predicate") or "")
                object_text = str(group.get("obj") or "")
                fact_text = f"{subject_text} {predicate_text}"
                if object_text:
                    fact_text += f" {object_text}"
                rep_claim_id = claim_ids[0] if claim_ids else None
                metadata = {
                    "source_claim_id": str(rep_claim_id) if rep_claim_id is not None else "",
                    "source_claim_ids": [str(cid) for cid in claim_ids],
                    "merged_count": len(claim_ids),
                }
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.versioned_facts
                            (entity_profile_id, fact_type, fact_text, confidence,
                             valid_from, valid_to, extraction_method, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, 'claim_extraction', %s)
                        """,
                        (
                            int(group["entity_profile_id"]),
                            str(group["fact_type"]),
                            fact_text[:2000],
                            float(group.get("confidence") or 0.0),
                            group.get("valid_from"),
                            group.get("valid_to"),
                            json.dumps(metadata),
                        ),
                    )
                    stats["promoted"] += 1
                except Exception as e:
                    stats["insert_failed"] += 1
                    logger.debug(
                        "promote merged claim group rep=%s size=%s: %s",
                        rep_claim_id,
                        len(claim_ids),
                        e,
                    )

        conn.commit()
    except Exception as e:
        logger.warning("promote_claims_to_versioned_facts failed: %s", e)
        conn.rollback()
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if stats["candidates"] > 0:
        logger.info(
            "claims_to_facts batch: promoted=%s candidates=%s unresolved_subject=%s insert_failed=%s merged_groups=%s collapsed=%s merged_id_check=%s",
            stats["promoted"],
            stats["candidates"],
            stats["unresolved_subject"],
            stats["insert_failed"],
            stats["merged_groups"],
            stats["merged_claims_collapsed"],
            _claims_to_facts_check_merged_source_ids(),
        )
    return stats


def sample_unpromoted_claim_resolution_stats(
    *,
    limit: int = 500,
    min_confidence: float | None = None,
) -> dict[str, int | float]:
    """
    Dry-run the same subject resolution as ``promote_claims_to_versioned_facts`` on up to ``limit``
    highest-confidence unpromoted rows. Does **not** insert into ``versioned_facts``.

    Use this to compare **resolved** vs **unresolved** before tuning confidence or seeding entities.
    """
    if min_confidence is None:
        min_confidence = get_claims_to_facts_min_confidence()
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 500
    lim = max(0, min(5000, lim))
    out: dict[str, int | float] = {
        "candidates": 0,
        "resolved": 0,
        "unresolved": 0,
        "min_confidence": float(min_confidence),
        "sample_limit": lim,
    }
    if lim <= 0:
        return out

    conn = get_db_connection()
    if not conn:
        return out
    active_schemas = frozenset(get_pipeline_schema_names_active())
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ec.id, ec.context_id, ec.subject_text
                FROM intelligence.extracted_claims ec
                WHERE ec.confidence >= %s
                """
                + claims_to_facts_versioned_fact_absent_sql()
                + CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL
                + claim_promotion_generic_subject_exclude_sql()
                + """
                ORDER BY ec.confidence DESC
                LIMIT %s
                """,
                (min_confidence, lim),
            )
            rows = cur.fetchall()
        out["candidates"] = len(rows)
        resolved = 0
        for claim_id, context_id, subject in rows:
            with conn.cursor() as cur2:
                pid = _resolve_claim_to_entity_profile(
                    cur2,
                    subject or "",
                    context_id,
                    active_schema_set=active_schemas,
                )
                if pid:
                    resolved += 1
        out["resolved"] = resolved
        out["unresolved"] = out["candidates"] - resolved
        if out["candidates"]:
            out["resolve_rate"] = round(float(resolved) / float(out["candidates"]), 4)
        else:
            out["resolve_rate"] = 0.0
    except Exception as e:
        logger.warning("sample_unpromoted_claim_resolution_stats: %s", e)
        out["error"] = str(e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return out


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
    r"secretary\s+of\s+defense|secretary\s+of\s+the\s+treasury|"
    r"white\s+house\s+press\s+secretary|press\s+secretary|"
    r"president|vice\s+president|u\.s\.\s+senator|u\.s\.\s+representative|"
    r"senator|representative|congressman|congresswoman|governor|mayor|"
    r"ceo|chief\s+executive"
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
    "pakistani": "pakistan",
    "bangladeshi": "bangladesh",
    "egyptian": "egypt",
    "vietnamese": "vietnam",
    "thai": "thailand",
    "indonesian": "indonesia",
    "malaysian": "malaysia",
    "singaporean": "singapore",
    "filipino": "philippines",
    "taiwanese": "taiwan",
    "swedish": "sweden",
    "norwegian": "norway",
    "finnish": "finland",
    "danish": "denmark",
    "dutch": "netherlands",
    "spanish": "spain",
    "italian": "italy",
    "portuguese": "portugal",
    "greek": "greece",
    "belgian": "belgium",
    "swiss": "switzerland",
    "austrian": "austria",
    "irish": "ireland",
    "hungarian": "hungary",
    "czech": "czech republic",
    "romanian": "romania",
    "colombian": "colombia",
    "argentinian": "argentina",
    "argentine": "argentina",
    "chilean": "chile",
    "peruvian": "peru",
    "venezuelan": "venezuela",
    "cuban": "cuba",
    "nigerian": "nigeria",
    "kenyan": "kenya",
    "south african": "south africa",
    "ethiopian": "ethiopia",
    "new zealander": "new zealand",
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
    "dutch": frozenset({"oven"}),
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
    short = float(os.environ.get("CLAIM_RESOLVE_TRGM_THRESHOLD_SHORT", "0.52"))
    long_t = float(os.environ.get("CLAIM_RESOLVE_TRGM_THRESHOLD_LONG", "0.40"))
    return short if len(norm_lower) <= 6 else long_t


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
        else frozenset(get_pipeline_schema_names_active())
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

            if slen >= 4:
                max_meta = min(160, slen + 48)
                if triple:
                    d1, d2, d3 = triple
                    pid = _one_int(
                        """
                        SELECT ep.id FROM intelligence.entity_profiles ep
                        WHERE (
                          (COALESCE(metadata->>'canonical_name', '') <> ''
                            AND char_length(trim(metadata->>'canonical_name')) BETWEEN 2 AND %s
                            AND (
                              lower(trim(metadata->>'canonical_name')) LIKE '%%' || %s || '%%'
                              OR %s LIKE '%%' || lower(trim(metadata->>'canonical_name')) || '%%'
                            ))
                          OR
                          (COALESCE(metadata->>'display_name', '') <> ''
                            AND char_length(trim(metadata->>'display_name')) BETWEEN 2 AND %s
                            AND (
                              lower(trim(metadata->>'display_name')) LIKE '%%' || %s || '%%'
                              OR %s LIKE '%%' || lower(trim(metadata->>'display_name')) || '%%'
                            ))
                        )
                        ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END
                        LIMIT 1
                        """,
                        (
                            max_meta,
                            norm_lower,
                            norm_lower,
                            max_meta,
                            norm_lower,
                            norm_lower,
                            d1,
                            d2,
                            d3,
                        ),
                    )
                else:
                    pid = _one_int(
                        """
                        SELECT ep.id FROM intelligence.entity_profiles ep
                        WHERE (
                          (COALESCE(metadata->>'canonical_name', '') <> ''
                            AND char_length(trim(metadata->>'canonical_name')) BETWEEN 2 AND %s
                            AND (
                              lower(trim(metadata->>'canonical_name')) LIKE '%%' || %s || '%%'
                              OR %s LIKE '%%' || lower(trim(metadata->>'canonical_name')) || '%%'
                            ))
                          OR
                          (COALESCE(metadata->>'display_name', '') <> ''
                            AND char_length(trim(metadata->>'display_name')) BETWEEN 2 AND %s
                            AND (
                              lower(trim(metadata->>'display_name')) LIKE '%%' || %s || '%%'
                              OR %s LIKE '%%' || lower(trim(metadata->>'display_name')) || '%%'
                            ))
                        )
                        LIMIT 1
                        """,
                        (
                            max_meta,
                            norm_lower,
                            norm_lower,
                            max_meta,
                            norm_lower,
                            norm_lower,
                        ),
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

            if slen >= 3:
                try:
                    cap = int(os.environ.get("CLAIM_RESOLVE_SUBSTRING_MAX_CANON_LEN", "120"))
                except ValueError:
                    cap = 120
                max_canon = min(cap, max(48, slen + 36))
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
                              AND char_length(trim(ec.canonical_name)) >= 3
                              AND char_length(trim(ec.canonical_name)) <= %s
                              AND (
                                lower(trim(ec.canonical_name)) LIKE '%%' || %s || '%%'
                                OR %s LIKE '%%' || lower(trim(ec.canonical_name)) || '%%'
                              )
                            ORDER BY CASE WHEN ep.domain_key IN (%s, %s, %s) THEN 0 ELSE 1 END,
                              char_length(trim(ec.canonical_name)) ASC
                            LIMIT 1
                            """,
                            (max_canon, norm_lower, norm_lower, d1, d2, d3),
                        )
                    else:
                        pid = _one_int(
                            f"""
                            SELECT ep.id
                            FROM intelligence.entity_profiles ep
                            JOIN {schema}.entity_canonical ec ON ec.id = ep.canonical_entity_id
                            WHERE ep.domain_key IN ('{schema}', '{dk_guess}')
                              AND char_length(trim(ec.canonical_name)) >= 3
                              AND char_length(trim(ec.canonical_name)) <= %s
                              AND (
                                lower(trim(ec.canonical_name)) LIKE '%%' || %s || '%%'
                                OR %s LIKE '%%' || lower(trim(ec.canonical_name)) || '%%'
                              )
                            ORDER BY char_length(trim(ec.canonical_name)) ASC
                            LIMIT 1
                            """,
                            (max_canon, norm_lower, norm_lower),
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

