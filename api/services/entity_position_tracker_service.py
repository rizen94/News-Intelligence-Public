"""
Entity position tracker — extracts entity stances, policy positions, and public statements
from articles where the entity is mentioned, stores in intelligence.entity_positions.

Designed for politics domain (voting records, policy stances) and finance domain
(company strategy, market positions). Uses LLM to extract structured positions from
article content and ml_data.

T2.2 of V6_QUALITY_FIRST_TODO.md.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}

POSITION_EXTRACTION_PROMPT = """Analyze the following article about {entity_name} and extract any policy positions, stances, votes, or public statements.

For each position found, provide:
- topic: the issue or subject (e.g., "immigration reform", "interest rates", "AI regulation")
- position: their stance or action (e.g., "supports increased border funding", "voted against", "announced merger")
- confidence: 0.0-1.0 how clearly stated this position is

Return a JSON array of objects. If no clear positions are found, return an empty array [].

Article title: {title}
Article content:
{content}

Respond with ONLY a JSON array, no other text."""


def extract_positions_for_entity(
    domain_key: str,
    entity_id: int,
    max_articles: int = 20,
    skip_existing: bool = True,
) -> Dict[str, Any]:
    """
    For a canonical entity, scan recent articles mentioning it and extract positions via LLM.
    Stores results in intelligence.entity_positions.

    Returns {success, positions_extracted, articles_scanned}.
    """
    schema = DOMAIN_SCHEMA.get(domain_key)
    if not schema:
        return {"success": False, "error": f"Unknown domain: {domain_key}"}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            # Get entity name
            cur.execute(
                f"SELECT canonical_name, entity_type FROM {schema}.entity_canonical WHERE id = %s",
                (entity_id,),
            )
            entity_row = cur.fetchone()
            if not entity_row:
                conn.close()
                return {"success": False, "error": f"Entity {entity_id} not found"}

            entity_name, entity_type = entity_row

            # Get articles mentioning this entity (with content)
            cur.execute(
                f"""
                SELECT DISTINCT a.id, a.title, LEFT(a.content, 2000), a.ml_data, a.published_at
                FROM {schema}.article_entities ae
                JOIN {schema}.articles a ON a.id = ae.article_id
                WHERE ae.canonical_entity_id = %s
                  AND a.content IS NOT NULL
                  AND LENGTH(a.content) > 100
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT %s
                """,
                (entity_id, max_articles),
            )
            articles = cur.fetchall()

            if not articles:
                conn.close()
                return {"success": True, "positions_extracted": 0, "articles_scanned": 0, "note": "No articles with content"}

            # Get existing positions to skip already-extracted articles
            existing_article_ids = set()
            if skip_existing:
                cur.execute(
                    """
                    SELECT DISTINCT jsonb_array_elements(evidence_refs)->>'article_id'
                    FROM intelligence.entity_positions
                    WHERE domain_key = %s AND entity_id = %s
                    """,
                    (domain_key, entity_id),
                )
                for row in cur.fetchall():
                    if row[0]:
                        try:
                            existing_article_ids.add(int(row[0]))
                        except (ValueError, TypeError):
                            pass

        conn.close()

        # Extract positions from each article
        positions_extracted = 0
        articles_scanned = 0

        for article_id, title, content, ml_data, published_at in articles:
            if article_id in existing_article_ids:
                continue

            articles_scanned += 1
            positions = _extract_positions_from_article(
                entity_name, title or "", content or "", ml_data,
            )

            if positions:
                _store_positions(
                    domain_key, entity_id, article_id, title,
                    published_at, positions,
                )
                positions_extracted += len(positions)

        logger.info(
            "Position tracker %s/%s (%s): %d positions from %d articles",
            domain_key, entity_id, entity_name, positions_extracted, articles_scanned,
        )
        return {
            "success": True,
            "entity_name": entity_name,
            "positions_extracted": positions_extracted,
            "articles_scanned": articles_scanned,
        }
    except Exception as e:
        logger.warning("extract_positions_for_entity: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def _extract_positions_from_article(
    entity_name: str,
    title: str,
    content: str,
    ml_data: Any,
) -> List[Dict[str, Any]]:
    """Use LLM to extract positions from a single article."""
    try:
        from shared.services.llm_service import LLMService
        llm = LLMService()
    except Exception:
        return _extract_positions_heuristic(entity_name, title, content, ml_data)

    # Build context from ml_data if available
    context_text = content[:1500]
    if ml_data and isinstance(ml_data, dict):
        summary = ml_data.get("summary", "")
        key_points = ml_data.get("key_points", [])
        if summary:
            context_text = f"{summary}\n\n{content[:800]}"
        if key_points:
            context_text += "\n\nKey points:\n" + "\n".join(f"- {p}" for p in key_points[:5])

    prompt = POSITION_EXTRACTION_PROMPT.format(
        entity_name=entity_name,
        title=title,
        content=context_text,
    )

    try:
        response = llm.generate(prompt, max_tokens=500)
        if not response:
            return []
        # Parse JSON from response
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        positions = json.loads(text)
        if not isinstance(positions, list):
            return []
        return [
            {
                "topic": p.get("topic", "")[:255],
                "position": p.get("position", ""),
                "confidence": min(1.0, max(0.0, float(p.get("confidence", 0.5)))),
            }
            for p in positions
            if p.get("topic") and p.get("position")
        ]
    except (json.JSONDecodeError, ValueError, TypeError):
        return _extract_positions_heuristic(entity_name, title, content, ml_data)
    except Exception as e:
        logger.debug("LLM position extraction failed: %s", e)
        return _extract_positions_heuristic(entity_name, title, content, ml_data)


def _extract_positions_heuristic(
    entity_name: str,
    title: str,
    content: str,
    ml_data: Any,
) -> List[Dict[str, Any]]:
    """Fallback heuristic extraction when LLM is unavailable."""
    positions = []
    combined = f"{title} {content}".lower()

    stance_keywords = {
        "supports": 0.7,
        "opposes": 0.7,
        "voted for": 0.8,
        "voted against": 0.8,
        "announced": 0.6,
        "proposed": 0.6,
        "rejected": 0.7,
        "endorsed": 0.7,
        "criticized": 0.6,
        "praised": 0.6,
        "called for": 0.6,
        "pledged": 0.7,
        "committed to": 0.7,
        "signed": 0.8,
        "vetoed": 0.9,
    }

    entity_lower = entity_name.lower()
    # Only extract if entity is actually mentioned near a stance keyword
    for keyword, confidence in stance_keywords.items():
        idx = combined.find(keyword)
        if idx == -1:
            continue
        # Check entity appears within 200 chars of keyword
        nearby = combined[max(0, idx - 200):idx + 200]
        if entity_lower not in nearby and entity_lower.split()[-1] not in nearby:
            continue

        # Extract surrounding context as topic
        context_start = max(0, idx - 100)
        context_end = min(len(combined), idx + len(keyword) + 100)
        context = combined[context_start:context_end].strip()
        # Trim to sentence boundaries
        for end_char in ".!?\n":
            sent_end = context.find(end_char, len(context) // 2)
            if sent_end > 0:
                context = context[:sent_end + 1]
                break

        positions.append({
            "topic": title[:255] if title else context[:255],
            "position": keyword,
            "confidence": confidence,
        })
        if len(positions) >= 3:
            break

    return positions


def _store_positions(
    domain_key: str,
    entity_id: int,
    article_id: int,
    article_title: str,
    published_at: Any,
    positions: List[Dict[str, Any]],
) -> int:
    """Store extracted positions in intelligence.entity_positions."""
    conn = get_db_connection()
    if not conn:
        return 0

    stored = 0
    try:
        with conn.cursor() as cur:
            for pos in positions:
                evidence = json.dumps([{
                    "article_id": article_id,
                    "title": article_title or "",
                    "published_at": published_at.isoformat() if published_at else None,
                }])
                cur.execute(
                    """
                    INSERT INTO intelligence.entity_positions
                    (domain_key, entity_id, topic, position, confidence, evidence_refs)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        domain_key,
                        entity_id,
                        pos["topic"],
                        pos["position"],
                        pos["confidence"],
                        evidence,
                    ),
                )
                stored += 1
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("_store_positions: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
    return stored


def run_position_tracker_batch(
    domain_key: Optional[str] = None,
    min_mentions: int = 5,
    max_entities: int = 10,
    max_articles_per_entity: int = 10,
) -> Dict[str, Any]:
    """
    Batch position extraction: find top entities by mention count, extract positions for each.
    Suitable for orchestrator scheduling.
    """
    domains = [domain_key] if domain_key else list(DOMAIN_SCHEMA.keys())
    results: Dict[str, Any] = {}

    for d in domains:
        schema = DOMAIN_SCHEMA.get(d)
        if not schema:
            continue

        conn = get_db_connection()
        if not conn:
            results[d] = {"success": False, "error": "Database connection failed"}
            continue

        try:
            with conn.cursor() as cur:
                # Top entities by mention count that don't have many positions yet
                cur.execute(
                    f"""
                    SELECT ec.id, ec.canonical_name, COUNT(ae.id) AS mentions
                    FROM {schema}.entity_canonical ec
                    JOIN {schema}.article_entities ae ON ae.canonical_entity_id = ec.id
                    LEFT JOIN intelligence.entity_positions ep
                        ON ep.domain_key = %s AND ep.entity_id = ec.id
                    GROUP BY ec.id, ec.canonical_name
                    HAVING COUNT(ae.id) >= %s
                    ORDER BY COUNT(ep.id) ASC NULLS FIRST, COUNT(ae.id) DESC
                    LIMIT %s
                    """,
                    (d, min_mentions, max_entities),
                )
                entities = cur.fetchall()
            conn.close()

            domain_result = {"entities_processed": 0, "total_positions": 0, "details": []}
            for eid, ename, mentions in entities:
                r = extract_positions_for_entity(d, eid, max_articles=max_articles_per_entity)
                domain_result["entities_processed"] += 1
                domain_result["total_positions"] += r.get("positions_extracted", 0)
                domain_result["details"].append({
                    "entity_name": ename,
                    "positions": r.get("positions_extracted", 0),
                    "articles_scanned": r.get("articles_scanned", 0),
                })

            results[d] = {"success": True, **domain_result}
        except Exception as e:
            logger.warning("run_position_tracker_batch %s: %s", d, e)
            try:
                conn.close()
            except Exception:
                pass
            results[d] = {"success": False, "error": str(e)}

    return results


def get_entity_positions(
    domain_key: str,
    entity_id: int,
    limit: int = 50,
) -> Dict[str, Any]:
    """Retrieve stored positions for an entity."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "positions": [], "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, topic, position, confidence, evidence_refs, date_range, created_at
                FROM intelligence.entity_positions
                WHERE domain_key = %s AND entity_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (domain_key, entity_id, limit),
            )
            positions = []
            for row in cur.fetchall():
                positions.append({
                    "id": row[0],
                    "topic": row[1],
                    "position": row[2],
                    "confidence": float(row[3]) if row[3] else None,
                    "evidence_refs": row[4] or [],
                    "date_range": str(row[5]) if row[5] else None,
                    "created_at": row[6].isoformat() if row[6] else None,
                })
        conn.close()
        return {"success": True, "positions": positions}
    except Exception as e:
        logger.warning("get_entity_positions: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "positions": [], "error": str(e)}
