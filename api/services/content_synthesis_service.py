"""
Centralized content synthesis service — aggregates all intelligence phases into
unified context for editorial generation and briefing construction.

The intelligence cascade produces enrichments at every stage:
  article → ml_data → entities → contexts → claims → events → storylines

This service is the single point that gathers all those enrichments for a given
scope (domain, storyline, event, or entity) and produces a synthesis-ready
context block. Consumers (editorial_document_service, daily_briefing_service,
investigation_report_service) call this instead of each querying the DB
independently.

See docs/DATA_FLOW_ARCHITECTURE.md, docs/CODE_AUDIT_REPORT.md (remaining item).
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}


def _schema(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


# ---------------------------------------------------------------------------
# Core synthesis: gather everything for a domain within a time window
# ---------------------------------------------------------------------------

def synthesize_domain_context(
    domain_key: str,
    hours: int = 24,
    max_articles: int = 30,
    max_storylines: int = 10,
    max_events: int = 10,
    max_entities: int = 20,
    max_quality_tier: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Gather all intelligence for a domain within the last `hours` window.
    Returns a unified context block:
    {
        domain_key, time_window,
        articles: [{id, title, summary, key_points, entities, sentiment, source, published_at, content_excerpt}],
        storylines: [{id, title, summary, editorial_lede, article_count, status}],
        events: [{id, name, type, editorial_briefing, momentum, chronicle_count}],
        entities: [{name, type, mention_count, positions, relationships}],
        claims: [{subject, predicate, object, confidence}],
        patterns: [{type, confidence, data}],
        statistics: {article_count, storyline_count, event_count, entity_count, claim_count},
    }
    """
    schema = _schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result: Dict[str, Any] = {
        "success": True,
        "domain_key": domain_key,
        "time_window_hours": hours,
        "synthesized_at": datetime.now(timezone.utc).isoformat(),
        "articles": [],
        "storylines": [],
        "events": [],
        "entities": [],
        "claims": [],
        "patterns": [],
        "statistics": {},
    }

    try:
        with conn.cursor() as cur:
            # --- Articles with ML enrichments ---
            # When max_quality_tier is set (e.g. 2), restrict to quality_tier <= N and order quality-first.
            quality_clause = ""
            order_clause = "ORDER BY a.published_at DESC NULLS LAST"
            if max_quality_tier is not None:
                quality_clause = " AND COALESCE(a.quality_tier, 4) <= %s"
                order_clause = "ORDER BY COALESCE(a.quality_tier, 4) ASC, COALESCE(a.quality_score, 0) DESC, a.published_at DESC NULLS LAST"
            article_params: tuple = (cutoff, cutoff, max_quality_tier, max_articles) if max_quality_tier is not None else (cutoff, cutoff, max_articles)
            cur.execute(
                f"""
                SELECT a.id, a.title, a.source_domain, a.published_at,
                       LEFT(a.content, 800) AS content_excerpt,
                       a.ml_data, a.entities, a.sentiment_score
                FROM {schema}.articles a
                WHERE (a.published_at >= %s OR a.created_at >= %s){quality_clause}
                {order_clause}
                LIMIT %s
                """,
                article_params,
            )
            articles = []
            article_ids = []
            for row in cur.fetchall():
                aid, title, source, pub_at, content_excerpt, ml_data, entities_json, sentiment = row
                article_ids.append(aid)
                ml = ml_data if isinstance(ml_data, dict) else {}
                articles.append({
                    "id": aid,
                    "title": title or "",
                    "source": source or "",
                    "published_at": pub_at.isoformat() if pub_at else None,
                    "content_excerpt": content_excerpt or "",
                    "summary": ml.get("summary", ""),
                    "key_points": ml.get("key_points", []),
                    "entities_extracted": entities_json if isinstance(entities_json, dict) else {},
                    "sentiment_score": float(sentiment) if sentiment is not None else None,
                    "sentiment_label": ml.get("sentiment_label", ""),
                })
            result["articles"] = articles

            # --- Entity mentions aggregated ---
            if article_ids:
                cur.execute(
                    f"""
                    SELECT ec.canonical_name, ec.entity_type, COUNT(ae.id) AS mentions
                    FROM {schema}.article_entities ae
                    JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                    WHERE ae.article_id = ANY(%s)
                    GROUP BY ec.id, ec.canonical_name, ec.entity_type
                    ORDER BY mentions DESC
                    LIMIT %s
                    """,
                    (article_ids, max_entities),
                )
                entities = []
                for erow in cur.fetchall():
                    entities.append({
                        "name": erow[0],
                        "type": erow[1],
                        "mention_count": erow[2],
                    })
                result["entities"] = entities

            # --- Storylines with editorial content ---
            cur.execute(
                f"""
                SELECT s.id, s.title, s.summary,
                       s.editorial_document->>'lede' AS editorial_lede,
                       s.document_status,
                       (SELECT COUNT(*) FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id) AS article_count
                FROM {schema}.storylines s
                WHERE s.status = 'active'
                ORDER BY s.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (max_storylines,),
            )
            storylines = []
            for srow in cur.fetchall():
                storylines.append({
                    "id": srow[0],
                    "title": srow[1] or "",
                    "summary": srow[2] or "",
                    "editorial_lede": srow[3] or "",
                    "document_status": srow[4],
                    "article_count": srow[5],
                })
            result["storylines"] = storylines

            # --- Tracked events with editorial briefings ---
            cur.execute(
                """
                SELECT te.id, te.event_name, te.event_type,
                       te.editorial_briefing,
                       te.editorial_briefing_json->>'momentum_score' AS momentum,
                       (SELECT COUNT(*) FROM intelligence.event_chronicles ec WHERE ec.event_id = te.id) AS chronicle_count
                FROM intelligence.tracked_events te
                WHERE te.domain_keys @> %s::jsonb OR te.domain_keys IS NULL
                ORDER BY te.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (json.dumps([domain_key]), max_events),
            )
            events = []
            for erow in cur.fetchall():
                events.append({
                    "id": erow[0],
                    "name": erow[1] or "",
                    "type": erow[2] or "",
                    "editorial_briefing": (erow[3] or "")[:500],
                    "momentum": erow[4],
                    "chronicle_count": erow[5],
                })
            result["events"] = events

            # --- Recent claims ---
            cur.execute(
                """
                SELECT ec.subject_text, ec.predicate_text, ec.object_text, ec.confidence
                FROM intelligence.extracted_claims ec
                JOIN intelligence.contexts c ON c.id = ec.context_id
                WHERE c.domain_key = %s
                ORDER BY ec.created_at DESC
                LIMIT 20
                """,
                (domain_key,),
            )
            claims = []
            for crow in cur.fetchall():
                claims.append({
                    "subject": crow[0] or "",
                    "predicate": crow[1] or "",
                    "object": crow[2] or "",
                    "confidence": float(crow[3]) if crow[3] is not None else None,
                })
            result["claims"] = claims

            # --- Pattern discoveries ---
            cur.execute(
                """
                SELECT pattern_type, confidence, data
                FROM intelligence.pattern_discoveries
                WHERE domain_key = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (domain_key,),
            )
            patterns = []
            for prow in cur.fetchall():
                patterns.append({
                    "type": prow[0],
                    "confidence": float(prow[1]) if prow[1] is not None else None,
                    "data": prow[2] or {},
                })
            result["patterns"] = patterns

            # --- Processed documents (PDFs: CRS, GAO, CBO, arXiv) ---
            try:
                cur.execute(
                    """
                    SELECT pd.id, pd.title, pd.source_name, pd.source_url, pd.document_type,
                           pd.publication_date, pd.key_findings, pd.extracted_sections
                    FROM intelligence.processed_documents pd
                    WHERE pd.extracted_sections IS NOT NULL
                      AND pd.extracted_sections != '[]'
                      AND (pd.created_at >= %s OR pd.publication_date >= %s)
                    ORDER BY pd.publication_date DESC NULLS LAST
                    LIMIT 10
                    """,
                    (cutoff, cutoff.date()),
                )
                documents = []
                for drow in cur.fetchall():
                    findings = drow[6] if isinstance(drow[6], list) else []
                    sections = drow[7] if isinstance(drow[7], list) else []
                    documents.append({
                        "id": drow[0],
                        "title": drow[1] or "",
                        "source_name": drow[2] or "",
                        "source_url": drow[3] or "",
                        "document_type": drow[4] or "",
                        "publication_date": str(drow[5]) if drow[5] else None,
                        "key_findings": findings[:5],
                        "section_count": len(sections),
                    })
                result["documents"] = documents
            except Exception as doc_err:
                logger.debug("synthesize_domain_context documents: %s", doc_err)
                result["documents"] = []

            # --- Entity positions (stance tracking) ---
            try:
                cur.execute(
                    f"""
                    SELECT ep.topic, ep.position, ep.confidence, ec.canonical_name, ec.entity_type
                    FROM intelligence.entity_positions ep
                    JOIN {schema}.entity_canonical ec ON ec.id = ep.entity_id
                    WHERE ep.domain_key = %s
                    ORDER BY ep.created_at DESC
                    LIMIT 15
                    """,
                    (domain_key,),
                )
                entity_positions = []
                for eprow in cur.fetchall():
                    entity_positions.append({
                        "topic": eprow[0] or "",
                        "position": eprow[1] or "",
                        "confidence": float(eprow[2]) if eprow[2] is not None else None,
                        "entity_name": eprow[3] or "",
                        "entity_type": eprow[4] or "",
                    })
                result["entity_positions"] = entity_positions
            except Exception as pos_err:
                logger.debug("synthesize_domain_context entity_positions: %s", pos_err)
                result["entity_positions"] = []

            # --- Cross-domain correlations ---
            try:
                cur.execute(
                    """
                    SELECT domain_1, domain_2, correlation_type, correlation_strength, event_ids, entity_profile_ids
                    FROM intelligence.cross_domain_correlations
                    WHERE domain_1 = %s OR domain_2 = %s
                    ORDER BY discovered_at DESC
                    LIMIT 10
                    """,
                    (domain_key, domain_key),
                )
                cross_domain = []
                for cdrow in cur.fetchall():
                    cross_domain.append({
                        "domain_1": cdrow[0],
                        "domain_2": cdrow[1],
                        "correlation_type": cdrow[2] or "",
                        "strength": float(cdrow[3]) if cdrow[3] is not None else None,
                        "event_ids": cdrow[4] or [],
                        "entity_profile_ids": cdrow[5] or [],
                    })
                result["cross_domain"] = cross_domain
            except Exception as cd_err:
                logger.debug("synthesize_domain_context cross_domain: %s", cd_err)
                result["cross_domain"] = []

        conn.close()

        result["statistics"] = {
            "article_count": len(result["articles"]),
            "storyline_count": len(result["storylines"]),
            "event_count": len(result["events"]),
            "entity_count": len(result["entities"]),
            "claim_count": len(result["claims"]),
            "pattern_count": len(result["patterns"]),
            "document_count": len(result.get("documents", [])),
            "entity_position_count": len(result.get("entity_positions", [])),
            "cross_domain_count": len(result.get("cross_domain", [])),
        }

        return result
    except Exception as e:
        logger.warning("synthesize_domain_context %s: %s", domain_key, e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Storyline-scoped synthesis
# ---------------------------------------------------------------------------

def synthesize_storyline_context(
    domain_key: str,
    storyline_id: int,
) -> Dict[str, Any]:
    """
    Gather all intelligence related to a specific storyline:
    articles with full ml_data, entities, claims from those article contexts,
    and the storyline's editorial document.
    """
    schema = _schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            # Storyline metadata
            cur.execute(
                f"""
                SELECT s.id, s.title, s.summary, s.editorial_document,
                       s.document_status, s.document_version
                FROM {schema}.storylines s
                WHERE s.id = %s
                """,
                (storyline_id,),
            )
            srow = cur.fetchone()
            if not srow:
                conn.close()
                return {"success": False, "error": f"Storyline {storyline_id} not found"}

            storyline = {
                "id": srow[0],
                "title": srow[1] or "",
                "summary": srow[2] or "",
                "editorial_document": srow[3] or {},
                "document_status": srow[4],
                "document_version": srow[5],
            }

            # Articles in storyline with full enrichments (quality-first, then recency)
            cur.execute(
                f"""
                SELECT a.id, a.title, a.source_domain, a.published_at,
                       LEFT(a.content, 1200), a.ml_data, a.entities,
                       a.sentiment_score
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                ORDER BY COALESCE(a.quality_tier, 4) ASC, COALESCE(a.quality_score, 0) DESC, a.published_at DESC NULLS LAST
                """,
                (storyline_id,),
            )
            articles = []
            article_ids = []
            for row in cur.fetchall():
                aid = row[0]
                article_ids.append(aid)
                ml = row[5] if isinstance(row[5], dict) else {}
                articles.append({
                    "id": aid,
                    "title": row[1] or "",
                    "source": row[2] or "",
                    "published_at": row[3].isoformat() if row[3] else None,
                    "content_excerpt": row[4] or "",
                    "summary": ml.get("summary", ""),
                    "key_points": ml.get("key_points", []),
                    "entities_extracted": row[6] if isinstance(row[6], dict) else {},
                    "sentiment_score": float(row[7]) if row[7] is not None else None,
                })

            # Entities across these articles
            entities = []
            if article_ids:
                cur.execute(
                    f"""
                    SELECT ec.canonical_name, ec.entity_type, COUNT(ae.id),
                           ec.aliases
                    FROM {schema}.article_entities ae
                    JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                    WHERE ae.article_id = ANY(%s)
                    GROUP BY ec.id, ec.canonical_name, ec.entity_type, ec.aliases
                    ORDER BY COUNT(ae.id) DESC
                    LIMIT 30
                    """,
                    (article_ids,),
                )
                for erow in cur.fetchall():
                    entities.append({
                        "name": erow[0],
                        "type": erow[1],
                        "mention_count": erow[2],
                        "aliases": erow[3] or [],
                    })

            # Claims from contexts linked to these articles
            claims = []
            if article_ids:
                cur.execute(
                    """
                    SELECT ec.subject_text, ec.predicate_text, ec.object_text, ec.confidence
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.contexts c ON c.id = ec.context_id
                    JOIN intelligence.article_to_context atc ON atc.context_id = c.id
                    WHERE atc.article_id = ANY(%s)
                    ORDER BY ec.confidence DESC NULLS LAST
                    LIMIT 20
                    """,
                    (article_ids,),
                )
                for crow in cur.fetchall():
                    claims.append({
                        "subject": crow[0] or "",
                        "predicate": crow[1] or "",
                        "object": crow[2] or "",
                        "confidence": float(crow[3]) if crow[3] is not None else None,
                    })

            # Entity positions relevant to this storyline's entities
            entity_positions = []
            if entities:
                entity_names = [e["name"] for e in entities[:10]]
                try:
                    cur.execute(
                        f"""
                        SELECT ep.topic, ep.position, ep.confidence, ec.canonical_name
                        FROM intelligence.entity_positions ep
                        JOIN {schema}.entity_canonical ec ON ec.id = ep.entity_id
                        WHERE ep.domain_key = %s AND ec.canonical_name = ANY(%s)
                        ORDER BY ep.created_at DESC
                        LIMIT 15
                        """,
                        (domain_key, entity_names),
                    )
                    for eprow in cur.fetchall():
                        entity_positions.append({
                            "entity_name": eprow[3] or "",
                            "topic": eprow[0] or "",
                            "position": eprow[1] or "",
                            "confidence": float(eprow[2]) if eprow[2] is not None else None,
                        })
                except Exception as pos_err:
                    logger.debug("synthesize_storyline_context positions: %s", pos_err)

            # Processed documents linked to this storyline via document_intelligence.storyline_connections JSONB
            documents = []
            try:
                conn_obj = json.dumps({"domain_key": domain_key, "storyline_id": storyline_id})
                cur.execute(
                    """
                    SELECT pd.id, pd.title, pd.source_name, pd.source_url, pd.document_type,
                           pd.key_findings, di.impact_assessment, di.credibility_score
                    FROM intelligence.document_intelligence di
                    JOIN intelligence.processed_documents pd ON pd.id = di.document_id
                    WHERE di.storyline_connections @> %s::jsonb
                    ORDER BY pd.publication_date DESC NULLS LAST
                    LIMIT 10
                    """,
                    (f"[{conn_obj}]",),
                )
                for drow in cur.fetchall():
                    findings = drow[5] if isinstance(drow[5], list) else []
                    documents.append({
                        "id": drow[0],
                        "title": drow[1] or "",
                        "source_name": drow[2] or "",
                        "source_url": drow[3] or "",
                        "document_type": drow[4] or "",
                        "key_findings": findings[:5],
                        "impact_assessment": drow[6] or "",
                        "credibility_score": float(drow[7]) if drow[7] is not None else None,
                    })
            except Exception as doc_err:
                logger.debug("synthesize_storyline_context documents: %s", doc_err)

        conn.close()
        return {
            "success": True,
            "domain_key": domain_key,
            "storyline": storyline,
            "articles": articles,
            "entities": entities,
            "claims": claims,
            "entity_positions": entity_positions,
            "documents": documents,
            "statistics": {
                "article_count": len(articles),
                "entity_count": len(entities),
                "claim_count": len(claims),
                "entity_position_count": len(entity_positions),
                "document_count": len(documents),
            },
        }
    except Exception as e:
        logger.warning("synthesize_storyline_context: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Event-scoped synthesis
# ---------------------------------------------------------------------------

def synthesize_event_context(
    event_id: int,
) -> Dict[str, Any]:
    """
    Gather all intelligence related to a tracked event:
    event metadata, chronicles, related storylines, entity participants.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, event_name, start_date, end_date,
                       geographic_scope, key_participant_entity_ids, milestones,
                       editorial_briefing, editorial_briefing_json,
                       briefing_status, domain_keys
                FROM intelligence.tracked_events
                WHERE id = %s
                """,
                (event_id,),
            )
            erow = cur.fetchone()
            if not erow:
                conn.close()
                return {"success": False, "error": f"Event {event_id} not found"}

            event = {
                "id": erow[0],
                "type": erow[1],
                "name": erow[2] or "",
                "start_date": erow[3].isoformat() if erow[3] else None,
                "end_date": erow[4].isoformat() if erow[4] else None,
                "geographic_scope": erow[5],
                "key_participants": erow[6] or [],
                "milestones": erow[7] or [],
                "editorial_briefing": erow[8] or "",
                "editorial_briefing_json": erow[9] or {},
                "briefing_status": erow[10],
                "domain_keys": erow[11] or [],
            }

            # Chronicles
            cur.execute(
                """
                SELECT id, update_date, developments, analysis, predictions,
                       momentum_score, created_at
                FROM intelligence.event_chronicles
                WHERE event_id = %s
                ORDER BY update_date DESC
                LIMIT 20
                """,
                (event_id,),
            )
            chronicles = []
            for crow in cur.fetchall():
                chronicles.append({
                    "id": crow[0],
                    "update_date": crow[1].isoformat() if crow[1] else None,
                    "developments": crow[2] or [],
                    "analysis": crow[3] or {},
                    "predictions": crow[4] or [],
                    "momentum_score": float(crow[5]) if crow[5] is not None else None,
                    "created_at": crow[6].isoformat() if crow[6] else None,
                })

        conn.close()
        return {
            "success": True,
            "event": event,
            "chronicles": chronicles,
            "statistics": {
                "chronicle_count": len(chronicles),
            },
        }
    except Exception as e:
        logger.warning("synthesize_event_context: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Entity-scoped synthesis
# ---------------------------------------------------------------------------

def synthesize_entity_context(
    domain_key: str,
    entity_id: int,
) -> Dict[str, Any]:
    """
    Gather all intelligence about a canonical entity: dossier, positions,
    relationships, recent articles, storyline references.
    """
    schema = _schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            # Entity info
            cur.execute(
                f"SELECT id, canonical_name, entity_type, aliases FROM {schema}.entity_canonical WHERE id = %s",
                (entity_id,),
            )
            erow = cur.fetchone()
            if not erow:
                conn.close()
                return {"success": False, "error": f"Entity {entity_id} not found"}

            entity = {
                "id": erow[0],
                "canonical_name": erow[1],
                "entity_type": erow[2],
                "aliases": erow[3] or [],
            }

            # Recent articles
            cur.execute(
                f"""
                SELECT a.id, a.title, LEFT(a.content, 500), a.published_at, a.ml_data
                FROM {schema}.article_entities ae
                JOIN {schema}.articles a ON a.id = ae.article_id
                WHERE ae.canonical_entity_id = %s
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT 20
                """,
                (entity_id,),
            )
            articles = []
            for arow in cur.fetchall():
                ml = arow[4] if isinstance(arow[4], dict) else {}
                articles.append({
                    "id": arow[0],
                    "title": arow[1] or "",
                    "content_excerpt": arow[2] or "",
                    "published_at": arow[3].isoformat() if arow[3] else None,
                    "summary": ml.get("summary", ""),
                })

            # Dossier
            cur.execute(
                """
                SELECT chronicle_data, relationships, positions, patterns, metadata, compilation_date
                FROM intelligence.entity_dossiers
                WHERE domain_key = %s AND entity_id = %s
                """,
                (domain_key, entity_id),
            )
            drow = cur.fetchone()
            dossier = None
            if drow:
                dossier = {
                    "chronicle_data": drow[0] or [],
                    "relationships": drow[1] or [],
                    "positions": drow[2] or [],
                    "patterns": drow[3] or {},
                    "metadata": drow[4] or {},
                    "compilation_date": drow[5].isoformat() if drow[5] else None,
                }

            # Positions
            cur.execute(
                """
                SELECT topic, position, confidence, evidence_refs
                FROM intelligence.entity_positions
                WHERE domain_key = %s AND entity_id = %s
                ORDER BY created_at DESC
                LIMIT 30
                """,
                (domain_key, entity_id),
            )
            positions = []
            for prow in cur.fetchall():
                positions.append({
                    "topic": prow[0],
                    "position": prow[1],
                    "confidence": float(prow[2]) if prow[2] is not None else None,
                    "evidence_refs": prow[3] or [],
                })

            # Cross-domain relationships
            cur.execute(
                """
                SELECT source_domain, source_entity_id, target_domain, target_entity_id,
                       relationship_type, confidence
                FROM intelligence.entity_relationships
                WHERE (source_domain = %s AND source_entity_id = %s)
                   OR (target_domain = %s AND target_entity_id = %s)
                LIMIT 30
                """,
                (domain_key, entity_id, domain_key, entity_id),
            )
            relationships = []
            for rrow in cur.fetchall():
                relationships.append({
                    "source_domain": rrow[0],
                    "source_entity_id": rrow[1],
                    "target_domain": rrow[2],
                    "target_entity_id": rrow[3],
                    "relationship_type": rrow[4],
                    "confidence": float(rrow[5]) if rrow[5] is not None else None,
                })

        conn.close()
        return {
            "success": True,
            "domain_key": domain_key,
            "entity": entity,
            "articles": articles,
            "dossier": dossier,
            "positions": positions,
            "relationships": relationships,
            "statistics": {
                "article_count": len(articles),
                "position_count": len(positions),
                "relationship_count": len(relationships),
                "has_dossier": dossier is not None,
            },
        }
    except Exception as e:
        logger.warning("synthesize_entity_context: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Text rendering for LLM consumption
# ---------------------------------------------------------------------------

def render_synthesis_for_llm(synthesis: Dict[str, Any], max_chars: int = 8000) -> str:
    """
    Convert a synthesis result into a structured text block suitable for LLM prompts.
    Used by editorial_document_service and daily_briefing_service to build context
    for narrative generation.
    """
    parts: List[str] = []

    # Articles
    articles = synthesis.get("articles", [])
    if articles:
        parts.append("## Recent Articles")
        for a in articles[:15]:
            line = f"- {a.get('title', 'Untitled')}"
            if a.get("summary"):
                line += f": {a['summary'][:200]}"
            if a.get("key_points"):
                line += " | Key: " + "; ".join(a["key_points"][:3])
            parts.append(line)

    # Storylines
    storylines = synthesis.get("storylines", [])
    if storylines:
        parts.append("\n## Active Storylines")
        for s in storylines:
            line = f"- {s.get('title', 'Untitled')}"
            if s.get("editorial_lede"):
                line += f": {s['editorial_lede'][:200]}"
            elif s.get("summary"):
                line += f": {s['summary'][:200]}"
            parts.append(line)

    # Events
    events = synthesis.get("events", [])
    if events:
        parts.append("\n## Tracked Events")
        for e in events:
            line = f"- {e.get('name', 'Unnamed')} ({e.get('type', '')})"
            if e.get("editorial_briefing"):
                line += f": {e['editorial_briefing'][:200]}"
            parts.append(line)

    # Entities
    entities = synthesis.get("entities", [])
    if entities:
        parts.append("\n## Key Entities")
        for ent in entities[:10]:
            parts.append(f"- {ent.get('name', '')} ({ent.get('type', '')}) — {ent.get('mention_count', 0)} mentions")

    # Claims
    claims = synthesis.get("claims", [])
    if claims:
        parts.append("\n## Recent Claims")
        for c in claims[:10]:
            parts.append(f"- {c.get('subject', '')} {c.get('predicate', '')} {c.get('object', '')}")

    # Entity positions / stances
    positions = synthesis.get("entity_positions", [])
    if positions:
        parts.append("\n## Entity Positions & Stances")
        for p in positions[:10]:
            conf = f" (confidence: {p['confidence']:.0%})" if p.get("confidence") else ""
            parts.append(f"- {p.get('entity_name', '')} on {p.get('topic', '')}: {p.get('position', '')}{conf}")

    # Processed documents (government/research reports)
    documents = synthesis.get("documents", [])
    if documents:
        parts.append("\n## Government & Research Documents")
        for d in documents[:5]:
            line = f"- [{d.get('document_type', 'document').upper()}] {d.get('title', 'Untitled')} ({d.get('source_name', '')})"
            findings = d.get("key_findings", [])
            if findings:
                line += " — Findings: " + "; ".join(str(f) for f in findings[:3])
            parts.append(line)

    # Cross-domain connections
    cross_domain = synthesis.get("cross_domain", [])
    if cross_domain:
        parts.append("\n## Cross-Domain Connections")
        for cd in cross_domain[:5]:
            parts.append(f"- {cd.get('domain_1', '')} ↔ {cd.get('domain_2', '')}: {cd.get('correlation_type', '')} (strength: {cd.get('strength', '?')})")

    # Patterns
    patterns = synthesis.get("patterns", [])
    if patterns:
        parts.append("\n## Detected Patterns")
        for pat in patterns[:5]:
            data = pat.get("data", {})
            desc = data.get("description", "") or data.get("summary", "") or str(data)[:150]
            parts.append(f"- [{pat.get('type', '')}] {desc}")

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(truncated)"
    return text
