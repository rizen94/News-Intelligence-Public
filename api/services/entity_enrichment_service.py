"""
Entity enrichment pipeline — Phase 1 RAG Enhancement.
Enriches entity_profiles using Wikipedia (and optionally GDELT): fetches external
context, updates profile sections, and writes versioned_facts.
See docs/RAG_ENHANCEMENT_ROADMAP.md.
"""

import json
import logging
import os
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def _get_wikipedia_service():
    """Lazy import to avoid circular deps."""
    from modules.ml.rag_external_services import WikipediaService

    return WikipediaService()


def _get_canonical_name_for_profile(entity_profile_id: int) -> tuple | None:
    """Return (canonical_name, domain_key) for entity_profile_id, or None."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ep.metadata->>'canonical_name', ep.domain_key
                FROM intelligence.entity_profiles ep
                WHERE ep.id = %s
                """,
                (entity_profile_id,),
            )
            row = cur.fetchone()
            return (row[0], row[1]) if row and row[0] else None
    finally:
        conn.close()


def _fetch_wikipedia_summary(canonical_name: str) -> dict[str, Any] | None:
    """Fetch entity knowledge via high-level connector (Wikipedia first, optional KG fallback)."""
    try:
        from services.entity_knowledge_connector import resolve_entity_knowledge

        result = resolve_entity_knowledge(
            canonical_name,
            sources=("wikipedia", "knowledge_graph"),
        )
        if not result:
            return None
        # Map connector shape to legacy summary shape for _merge_wikipedia_section and _facts_*
        return {
            "title": result.get("title", ""),
            "extract": result.get("description", ""),
            "url": result.get("url", ""),
            "page_id": result.get("wikipedia_page_id"),
        }
    except Exception as e:
        logger.debug("Entity knowledge fetch for %s: %s", canonical_name, e)
    return None


def _facts_from_wikipedia_summary(
    summary: dict[str, Any], canonical_name: str
) -> list[dict[str, Any]]:
    """Turn a Wikipedia summary into a small list of fact dicts (fact_type, fact_text, confidence)."""
    facts = []
    extract = (summary.get("extract") or "").strip()
    if not extract:
        return facts
    # One overarching "summary" fact; optionally split first 2 sentences as separate facts
    if len(extract) > 20:
        facts.append(
            {
                "fact_type": "ATTRIBUTE",
                "fact_text": extract[:2000],
                "confidence": 0.85,
            }
        )
    return facts


def _merge_wikipedia_section_into_sections(
    existing_sections: list[dict], wiki_summary: dict
) -> list[dict]:
    """Append or replace a 'Background (Wikipedia)' section."""
    wiki_summary.get("title", "")
    extract = (wiki_summary.get("extract") or "").strip()
    if not extract:
        return existing_sections
    new_section = {
        "title": "Background (Wikipedia)",
        "content": extract[:3000],
        "source": "wikipedia",
        "url": wiki_summary.get("url", ""),
    }
    out = [
        s for s in (existing_sections or []) if (s.get("title") or "") != "Background (Wikipedia)"
    ]
    out.append(new_section)
    return out


def enrich_entity_profile(entity_profile_id: int) -> bool:
    """
    Enrich one entity profile using Wikipedia (and optionally GDELT).
    - Fetches Wikipedia summary for the canonical name.
    - Merges a 'Background (Wikipedia)' section into entity_profiles.sections.
    - Inserts 1–3 versioned_facts from the summary (sources = [{ source_type: 'wikipedia', ... }]).
    Returns True if profile was updated (sections or facts added).
    """
    name_domain = _get_canonical_name_for_profile(entity_profile_id)
    if not name_domain:
        logger.debug("enrich_entity_profile: no canonical name for profile %s", entity_profile_id)
        return False
    canonical_name, _domain_key = name_domain
    if not canonical_name or len(canonical_name) < 2:
        return False

    summary = _fetch_wikipedia_summary(canonical_name)
    if not summary:
        # Mark profile so we don't retry forever
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.entity_profiles
                        SET metadata = jsonb_set(
                                COALESCE(metadata, '{}')::jsonb,
                                '{wiki_enrichment_status}',
                                '"not_found"'
                            ),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (entity_profile_id,),
                    )
                conn.commit()
            except Exception as e:
                logger.debug("Failed to mark wiki_enrichment_status for profile %s: %s", entity_profile_id, e)
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                conn.close()
        return False
    conn = get_db_connection()
    if not conn:
        return False

    updated = False
    try:
        with conn.cursor() as cur:
            # Current sections
            cur.execute(
                "SELECT sections FROM intelligence.entity_profiles WHERE id = %s",
                (entity_profile_id,),
            )
            row = cur.fetchone()
            existing = (row[0] if row and row[0] else []) if row else []
            if not isinstance(existing, list):
                existing = json.loads(existing) if isinstance(existing, str) else []
            merged = _merge_wikipedia_section_into_sections(existing, summary)
            cur.execute(
                """
                UPDATE intelligence.entity_profiles
                SET sections = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(merged), entity_profile_id),
            )
            if cur.rowcount:
                updated = True

            # Versioned facts (1 summary fact)
            facts = _facts_from_wikipedia_summary(summary, canonical_name)
            source_entry = {
                "source_type": "wikipedia",
                "title": summary.get("title", canonical_name),
                "url": summary.get("url", ""),
            }
            for f in facts[:5]:
                cur.execute(
                    """
                    INSERT INTO intelligence.versioned_facts
                    (entity_profile_id, fact_type, fact_text, confidence, sources, extraction_method, verification_status)
                    VALUES (%s, %s, %s, %s, %s, 'wikipedia', 'unverified')
                    """,
                    (
                        entity_profile_id,
                        f.get("fact_type", "ATTRIBUTE"),
                        (f.get("fact_text") or "")[:10000],
                        f.get("confidence", 0.8),
                        json.dumps([source_entry]),
                    ),
                )
                if cur.rowcount:
                    updated = True
        conn.commit()
    except Exception as e:
        logger.warning("enrich_entity_profile %s failed: %s", entity_profile_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return updated


def get_entity_profile_ids_to_enrich(limit: int = 20) -> list[int]:
    """Return entity_profile IDs missing Wikipedia section and/or wiki versioned_facts."""
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ep.id FROM intelligence.entity_profiles ep
                WHERE ep.metadata->>'canonical_name' IS NOT NULL
                  AND ep.metadata->>'canonical_name' != ''
                  AND COALESCE(ep.metadata->>'wiki_enrichment_status', 'pending') = 'pending'
                  AND (
                    ep.sections IS NULL
                    OR ep.sections::text NOT ILIKE '%%Background (Wikipedia)%%'
                    OR NOT EXISTS (
                      SELECT 1 FROM intelligence.versioned_facts vf
                      WHERE vf.entity_profile_id = ep.id
                        AND vf.extraction_method = 'wikipedia'
                      LIMIT 1
                    )
                  )
                ORDER BY ep.updated_at ASC NULLS FIRST
                LIMIT %s
                """,
                (limit,),
            )
            return [r[0] for r in cur.fetchall()]
    except Exception as e:
        if "versioned_facts" in str(e).lower() or "does not exist" in str(e).lower():
            logger.debug("versioned_facts table may not exist yet: %s", e)
        return []
    finally:
        conn.close()


# Log-only threshold: large backlog used to skip all work and block enrichment forever (v8 fix).
ENTITY_ENRICHMENT_QUEUE_WARN_THRESHOLD = int(
    os.environ.get("ENTITY_ENRICHMENT_QUEUE_WARN_THRESHOLD", "5000")
)


def run_enrichment_batch(limit: int = 20) -> int:
    """
    Enrich up to `limit` entity profiles. Returns number updated.
    Production: max 20/run, ~10s timeout per entity.

    Previously: queue depth > 1000 skipped the entire run, which stalled enrichment whenever
    a large backlog existed (no profiles ever got ``updated_at`` / sections writes).
    """
    ids = get_entity_profile_ids_to_enrich(limit=limit)
    if not ids:
        return 0
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.entity_profiles ep
                    WHERE ep.metadata->>'canonical_name' IS NOT NULL
                      AND ep.metadata->>'canonical_name' != ''
                      AND COALESCE(ep.metadata->>'wiki_enrichment_status', 'pending') = 'pending'
                      AND (
                        ep.sections IS NULL
                        OR ep.sections::text NOT ILIKE '%%Background (Wikipedia)%%'
                        OR NOT EXISTS (
                          SELECT 1 FROM intelligence.versioned_facts vf
                          WHERE vf.entity_profile_id = ep.id
                            AND vf.extraction_method = 'wikipedia'
                          LIMIT 1
                        )
                      )
                    """
                )
                (queue_depth,) = cur.fetchone()
                if queue_depth > ENTITY_ENRICHMENT_QUEUE_WARN_THRESHOLD:
                    logger.warning(
                        "Entity enrichment backlog %s profiles (threshold %s); still processing batch of %s",
                        queue_depth,
                        ENTITY_ENRICHMENT_QUEUE_WARN_THRESHOLD,
                        limit,
                    )
        finally:
            conn.close()
    updated = 0
    for profile_id in ids:
        if enrich_entity_profile(profile_id):
            updated += 1
    if updated > 0:
        logger.info("Entity enrichment: %s processed, %s updated", len(ids), updated)
    return updated
