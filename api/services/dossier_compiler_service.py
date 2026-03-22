"""
Dossier compiler: build entity_dossiers chronicle from articles and storylines.
Given (domain_key, entity_id) where entity_id = entity_canonical.id in that domain,
gathers articles that mention the entity and optionally storylines; writes to intelligence.entity_dossiers.
Includes LLM-generated narrative_summary for reporter-quality output.
Phase 1: T1.3 entity dossier basic compilation. See docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md.
"""

import json
import logging
from datetime import date
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import is_valid_domain_key, resolve_domain_schema

logger = logging.getLogger(__name__)


def _generate_dossier_narrative(
    entity_name: str,
    entity_type: str,
    chronicle_data: list,
    positions: list,
    relationships: list,
    storyline_refs: list,
    patterns: dict,
) -> str | None:
    """Generate a readable narrative summary for the entity dossier using LLM."""
    parts = [f"Entity: {entity_name} ({entity_type})"]

    if chronicle_data:
        recent = chronicle_data[:8]
        parts.append(f"\nRecent mentions ({len(chronicle_data)} total):")
        for c in recent:
            parts.append(
                f"- {c.get('title', 'Untitled')} ({c.get('source_domain', '')}, {c.get('published_at', '?')})"
            )

    if positions:
        parts.append(f"\nKnown positions ({len(positions)}):")
        for p in positions[:6]:
            parts.append(f"- On {p.get('topic', '?')}: {p.get('position', '?')}")

    if relationships:
        parts.append(f"\nRelationships ({len(relationships)}):")
        for r in relationships[:5]:
            parts.append(
                f"- {r.get('relationship_type', '?')} with entity {r.get('target_entity_id', '?')} in {r.get('target_domain', '?')}"
            )

    if storyline_refs:
        parts.append(f"\nConnected storylines ({len(storyline_refs)}):")
        for s in storyline_refs[:5]:
            parts.append(f"- {s.get('title', 'Untitled')}")

    if patterns and patterns.get("discoveries"):
        parts.append("\nDetected patterns:")
        for pat in patterns["discoveries"][:3]:
            data = pat.get("data", {})
            desc = (
                data.get("description", "")
                or data.get("summary", "")
                or str(pat.get("pattern_type", ""))
            )
            parts.append(f"- [{pat.get('pattern_type', '')}] {desc[:150]}")

    context = "\n".join(parts)

    prompt = (
        f"You are an intelligence analyst writing a dossier summary for {entity_name}.\n\n"
        f"Data:\n{context[:3000]}\n\n"
        "Write a 150-300 word narrative dossier summary that:\n"
        "1. Opens with who/what this entity is and why they matter\n"
        "2. Summarizes their recent activity based on the mentions\n"
        "3. Notes their known positions or stances on key topics\n"
        "4. Highlights notable relationships or cross-domain connections\n"
        "5. Flags any patterns detected\n"
        "Write in a professional intelligence briefing tone. No JSON, no bullet points — flowing prose."
    )

    try:
        import asyncio

        from shared.services.llm_service import TaskType, llm_service

        async def _gen():
            result = await llm_service.generate_summary(
                prompt[:3500], task_type=TaskType.QUICK_SUMMARY
            )
            if result.get("success"):
                return (result.get("summary") or "").strip() or None
            return None

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(_gen())).result(timeout=60)
            else:
                return loop.run_until_complete(_gen())
        except Exception:
            return asyncio.run(_gen())
    except Exception as e:
        logger.debug("Dossier narrative LLM failed: %s", e)
        return None


def compile_dossier(domain_key: str, entity_id: int) -> dict[str, Any]:
    """
    Build or refresh the entity dossier for (domain_key, entity_id).
    Fetches articles where article_entities.canonical_entity_id = entity_id,
    builds chronicle_data (article refs with title, url, published_at, snippet),
    and storylines that contain those articles. Upserts into intelligence.entity_dossiers.
    Returns the dossier row (id, domain_key, entity_id, compilation_date, chronicle_data, ...).
    """
    if not is_valid_domain_key(domain_key):
        return {"success": False, "error": f"Unknown domain_key: {domain_key}"}
    schema = resolve_domain_schema(domain_key)

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database unavailable"}

    try:
        with conn.cursor() as cur:
            # Check entity_canonical exists
            cur.execute(
                f'SELECT id, canonical_name, entity_type FROM "{schema}".entity_canonical WHERE id = %s',
                (entity_id,),
            )
            entity_row = cur.fetchone()
            if not entity_row:
                return {
                    "success": False,
                    "error": f"Entity {entity_id} not found in domain {domain_key}",
                }

            # Articles that mention this entity (canonical_entity_id)
            cur.execute(
                f"""
                SELECT a.id, a.title, a.url, a.published_at, a.source_domain, LEFT(a.content, 400) AS snippet
                FROM "{schema}".article_entities ae
                JOIN "{schema}".articles a ON a.id = ae.article_id
                WHERE ae.canonical_entity_id = %s
                ORDER BY a.published_at DESC NULLS LAST
                LIMIT 200
                """,
                (entity_id,),
            )
            article_rows = cur.fetchall()
            chronicle_data: list[dict[str, Any]] = []
            article_ids: list[int] = []
            for row in article_rows:
                aid, title, url, published_at, source_domain, snippet = row
                article_ids.append(aid)
                chronicle_data.append(
                    {
                        "article_id": aid,
                        "title": title or "",
                        "url": url or "",
                        "published_at": published_at.isoformat() if published_at else None,
                        "source_domain": source_domain or "",
                        "snippet": (snippet[:300] + "…")
                        if snippet and len(snippet) > 300
                        else (snippet or ""),
                    }
                )

            # Storylines that contain any of these articles (for relationships / context)
            storyline_refs: list[dict[str, Any]] = []
            if article_ids:
                cur.execute(
                    f"""
                    SELECT DISTINCT s.id, s.title, s.created_at
                    FROM "{schema}".storyline_articles sa
                    JOIN "{schema}".storylines s ON s.id = sa.storyline_id
                    WHERE sa.article_id = ANY(%s)
                    ORDER BY s.created_at DESC
                    LIMIT 50
                    """,
                    (article_ids,),
                )
                for row in cur.fetchall():
                    storyline_refs.append(
                        {
                            "storyline_id": row[0],
                            "title": row[1] or "",
                            "created_at": row[2].isoformat() if row[2] else None,
                        }
                    )

            # T2.2: Relationship web from intelligence.entity_relationships
            cur.execute(
                """
                SELECT source_domain, source_entity_id, target_domain, target_entity_id, relationship_type, confidence
                FROM intelligence.entity_relationships
                WHERE (source_domain = %s AND source_entity_id = %s) OR (target_domain = %s AND target_entity_id = %s)
                """,
                (domain_key, entity_id, domain_key, entity_id),
            )
            relationship_rows: list[dict[str, Any]] = []
            for r in cur.fetchall():
                relationship_rows.append(
                    {
                        "source_domain": r[0],
                        "source_entity_id": r[1],
                        "target_domain": r[2],
                        "target_entity_id": r[3],
                        "relationship_type": r[4],
                        "confidence": float(r[5]) if r[5] is not None else None,
                    }
                )
            relationships = relationship_rows

            compilation_date = date.today()

            # T2.2: Pull positions from entity_positions
            cur.execute(
                """
                SELECT id, topic, position, confidence, evidence_refs, created_at
                FROM intelligence.entity_positions
                WHERE domain_key = %s AND entity_id = %s
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (domain_key, entity_id),
            )
            positions: list[dict[str, Any]] = []
            for prow in cur.fetchall():
                positions.append(
                    {
                        "id": prow[0],
                        "topic": prow[1],
                        "position": prow[2],
                        "confidence": float(prow[3]) if prow[3] is not None else None,
                        "evidence_refs": prow[4] or [],
                        "created_at": prow[5].isoformat() if prow[5] else None,
                    }
                )

            # T2.2: Pull pattern_discoveries that mention this entity's profile
            patterns: dict[str, Any] = {}
            try:
                cur.execute(
                    """
                    SELECT ep.id FROM intelligence.entity_profiles ep
                    WHERE ep.domain_key = %s AND ep.canonical_entity_id = %s
                    LIMIT 1
                    """,
                    (domain_key, entity_id),
                )
                profile_row = cur.fetchone()
                if profile_row:
                    profile_id = profile_row[0]
                    cur.execute(
                        """
                        SELECT id, pattern_type, confidence, data, created_at
                        FROM intelligence.pattern_discoveries
                        WHERE %s = ANY(entity_profile_ids)
                        ORDER BY created_at DESC
                        LIMIT 20
                        """,
                        (profile_id,),
                    )
                    pattern_list = []
                    for pd_row in cur.fetchall():
                        pattern_list.append(
                            {
                                "id": pd_row[0],
                                "pattern_type": pd_row[1],
                                "confidence": float(pd_row[2]) if pd_row[2] is not None else None,
                                "data": pd_row[3] or {},
                                "created_at": pd_row[4].isoformat() if pd_row[4] else None,
                            }
                        )
                    if pattern_list:
                        patterns = {
                            "count": len(pattern_list),
                            "discoveries": pattern_list,
                        }
            except Exception as pat_err:
                logger.debug("Pattern linking: %s", pat_err)

            # Generate narrative summary from all collected data
            narrative = _generate_dossier_narrative(
                entity_name=entity_row[1],
                entity_type=entity_row[2],
                chronicle_data=chronicle_data,
                positions=positions,
                relationships=relationships,
                storyline_refs=storyline_refs,
                patterns=patterns,
            )

            metadata = {
                "article_count": len(chronicle_data),
                "storyline_count": len(storyline_refs),
                "storyline_refs": storyline_refs,
                "relationship_count": len(relationships),
                "narrative_summary": narrative,
            }

            cur.execute(
                """
                INSERT INTO intelligence.entity_dossiers
                (domain_key, entity_id, compilation_date, chronicle_data, relationships, positions, patterns, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (domain_key, entity_id) DO UPDATE SET
                    compilation_date = EXCLUDED.compilation_date,
                    chronicle_data = EXCLUDED.chronicle_data,
                    relationships = EXCLUDED.relationships,
                    positions = EXCLUDED.positions,
                    patterns = EXCLUDED.patterns,
                    metadata = EXCLUDED.metadata
                """,
                (
                    domain_key,
                    entity_id,
                    compilation_date,
                    json.dumps(chronicle_data),
                    json.dumps(relationships),
                    json.dumps(positions),
                    json.dumps(patterns),
                    json.dumps(metadata),
                ),
            )
            conn.commit()

            cur.execute(
                """
                SELECT id, domain_key, entity_id, compilation_date, chronicle_data, relationships, positions, patterns, metadata, created_at
                FROM intelligence.entity_dossiers
                WHERE domain_key = %s AND entity_id = %s
                """,
                (domain_key, entity_id),
            )
            row = cur.fetchone()
        conn.close()

        if not row:
            return {"success": False, "error": "Upsert succeeded but read-back failed"}

        return {
            "success": True,
            "dossier": {
                "id": row[0],
                "domain_key": row[1],
                "entity_id": row[2],
                "compilation_date": str(row[3]) if row[3] else None,
                "chronicle_data": row[4],
                "relationships": row[5],
                "positions": row[6],
                "patterns": row[7],
                "metadata": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
            },
        }
    except Exception as e:
        logger.exception("compile_dossier failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def _run_scheduled_dossier_compiles(
    max_dossiers: int,
    get_db_connection_fn: Any | None = None,
    stale_days: int = 7,
) -> int:
    """
    Phase 5: Used by OrchestratorCoordinator. Select up to max_dossiers (domain_key, entity_id)
    from entity_profiles that have no dossier or dossier older than stale_days; compile each.
    Returns number of dossiers successfully compiled.
    """
    from shared.database.connection import get_db_connection

    fn = get_db_connection_fn or get_db_connection
    conn = fn() if callable(fn) else None
    if not conn:
        return 0
    candidates: list[tuple] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ep.domain_key, ep.canonical_entity_id
                FROM intelligence.entity_profiles ep
                LEFT JOIN intelligence.entity_dossiers ed
                  ON ed.domain_key = ep.domain_key AND ed.entity_id = ep.canonical_entity_id
                WHERE ed.id IS NULL OR ed.compilation_date < CURRENT_DATE - %s
                ORDER BY ed.compilation_date ASC NULLS FIRST
                LIMIT %s
                """,
                (stale_days, max_dossiers),
            )
            candidates = [(r[0], r[1]) for r in cur.fetchall() if r[1] is not None]
    except Exception as e:
        logger.debug("_run_scheduled_dossier_compiles: select failed: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    compiled = 0
    for domain_key, entity_id in candidates:
        result = compile_dossier(domain_key, entity_id)
        if result.get("success"):
            compiled += 1
    return compiled
