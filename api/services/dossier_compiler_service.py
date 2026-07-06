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

from shared.database.connection import get_db_connection, get_db_connection_context
from shared.domain_registry import is_valid_domain_key, resolve_domain_schema

logger = logging.getLogger(__name__)


def _dossier_skip_narrative_enabled() -> bool:
    """Skip per-dossier LLM narrative during bulk catch-up (much higher throughput)."""
    from config.runtime import env_bool, env_str

    explicit = env_str("DOSSIER_CATCHUP_SKIP_NARRATIVE", "").strip().lower()
    if explicit in ("1", "true", "yes"):
        return True
    if explicit in ("0", "false", "no"):
        return False
    return env_str("BULK_CATCHUP_ACTIVE", "").lower() in ("1", "true", "yes")


def _dossier_compile_parallel_workers() -> int:
    from config.runtime import env_int, env_str

    raw = env_str("DOSSIER_COMPILE_PARALLEL", "").strip()
    if raw:
        try:
            return max(1, min(32, int(raw)))
        except ValueError:
            pass
    if _dossier_skip_narrative_enabled():
        return max(1, min(32, env_int("DOSSIER_CATCHUP_PARALLEL_DEFAULT", 8)))
    return 1


def _dossier_narrative_execution_lane() -> str | None:
    """PopOS GPU during catch-up narrative backfill; Widow CPU for normal bulk otherwise."""
    from config.runtime import env_bool, env_str

    if env_bool("DOSSIER_CATCHUP_GPU_NARRATIVE", False):
        return "gpu"
    bulk_catchup = env_str("BULK_CATCHUP_ACTIVE", "").lower() in ("1", "true", "yes")
    sprint_gpu_only = env_str("BACKLOG_SPRINT_GPU_ONLY", "").lower() in ("1", "true", "yes")
    if sprint_gpu_only:
        return "gpu"
    if bulk_catchup:
        return "cpu"
    return None


def _dossier_narrative_parallel_workers() -> int:
    from config.runtime import env_int, env_str

    raw = env_str("DOSSIER_NARRATIVE_PARALLEL", "").strip()
    if raw:
        try:
            return max(1, min(16, int(raw)))
        except ValueError:
            pass
    return max(1, min(16, env_int("DOSSIER_NARRATIVE_PARALLEL_DEFAULT", 4)))


def _dossier_narrative_cpu_parallel_workers() -> int:
    from config.runtime import env_int, env_str

    raw = env_str("DOSSIER_NARRATIVE_CPU_PARALLEL", "").strip()
    if raw:
        try:
            return max(0, min(16, int(raw)))
        except ValueError:
            pass
    return max(1, min(16, env_int("DOSSIER_NARRATIVE_CPU_PARALLEL_DEFAULT", 4)))


def _dossier_narrative_model() -> str:
    from config.runtime import env_str

    return env_str("DOSSIER_NARRATIVE_MODEL", "qwen2.5:7b-instruct")


def _generate_dossier_narrative(
    entity_name: str,
    entity_type: str,
    chronicle_data: list,
    positions: list,
    relationships: list,
    storyline_refs: list,
    patterns: dict,
    *,
    execution_lane: str | None = None,
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
        from shared.services.llm_service import TaskType, llm_service

        narrative_lane = execution_lane if execution_lane is not None else _dossier_narrative_execution_lane()
        text = llm_service.generate(
            prompt[:3500],
            task_type=TaskType.QUICK_SUMMARY,
            max_tokens=800,
            execution_lane=narrative_lane,
        )
        return text.strip() or None
    except Exception as e:
        logger.debug("Dossier narrative LLM failed: %s", e)
        return None


def compile_dossier(
    domain_key: str,
    entity_id: int,
    *,
    skip_narrative: bool | None = None,
) -> dict[str, Any]:
    """
    Build or refresh the entity dossier for (domain_key, entity_id).
    Fetches articles where article_entities.canonical_entity_id = entity_id,
    builds chronicle_data (article refs with title, url, published_at, snippet),
    and storylines that contain those articles. Upserts into intelligence.entity_dossiers.
    Returns the dossier row (id, domain_key, entity_id, compilation_date, chronicle_data, ...).
    """
    if not is_valid_domain_key(domain_key):
        return {"success": False, "error": f"Unknown domain_key: {domain_key}"}
    from shared.pipeline_domain_sql import is_retired_domain_key

    if is_retired_domain_key(domain_key):
        return {"success": False, "error": f"Retired domain_key: {domain_key}"}
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

            skip_llm = _dossier_skip_narrative_enabled() if skip_narrative is None else bool(skip_narrative)
            narrative = None
            if not skip_llm:
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
            if skip_llm:
                metadata["narrative_pending"] = True
                metadata["catchup_fast_compile"] = True

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

        dossier_meta = row[8] if isinstance(row[8], dict) else {}
        narrative_md = dossier_meta.get("narrative_summary") if dossier_meta else None
        if narrative_md and not dossier_meta.get("catchup_fast_compile"):
            try:
                from services.saved_intel_service import save_intel_output

                save_intel_output(
                    content_type="entity_dossier",
                    subject_type="entity",
                    subject_id=entity_id,
                    content_md=narrative_md,
                    domain_key=domain_key,
                    title=entity_row[1],
                    metadata={
                        "article_count": dossier_meta.get("article_count"),
                        "storyline_count": dossier_meta.get("storyline_count"),
                    },
                )
            except Exception as save_err:
                logger.warning("save_intel_output entity_dossier: %s", save_err)

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
    stale_days: int | None = None,
) -> int:
    """
    Phase 5: Used by OrchestratorCoordinator. Select up to max_dossiers (domain_key, entity_id)
    from entity_profiles missing a dossier or with upstream changes since last compile
    (see ``shared.entity_dossier_eligibility``). Returns number successfully compiled.

    ``stale_days`` is deprecated; set ``ENTITY_DOSSIER_STALE_DAYS`` in env instead.
    """
    from shared.database.connection import get_db_connection
    from shared.entity_dossier_eligibility import sql_entity_dossier_needs_compile
    from shared.pipeline_domain_sql import pipeline_domain_any_sql

    if stale_days is not None and stale_days >= 0:
        import logging as _logging

        _logging.getLogger(__name__).debug(
            "stale_days=%s ignored; use ENTITY_DOSSIER_STALE_DAYS", stale_days
        )

    fn = get_db_connection_fn or get_db_connection
    conn = fn() if callable(fn) else None
    if not conn:
        return 0
    domain_sql, domain_keys = pipeline_domain_any_sql("ep.domain_key")
    if not domain_keys:
        return 0
    needs_compile = sql_entity_dossier_needs_compile("ep", "ed")
    candidates: list[tuple] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ep.domain_key, ep.canonical_entity_id
                FROM intelligence.entity_profiles ep
                LEFT JOIN intelligence.entity_dossiers ed
                  ON ed.domain_key = ep.domain_key AND ed.entity_id = ep.canonical_entity_id
                WHERE ep.canonical_entity_id IS NOT NULL
                  AND {domain_sql}
                  AND {needs_compile}
                ORDER BY ed.compilation_date ASC NULLS FIRST
                LIMIT %s
                """,
                (domain_keys, max_dossiers),
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
    workers = _dossier_compile_parallel_workers()
    if workers <= 1 or len(candidates) <= 1:
        for domain_key, entity_id in candidates:
            result = compile_dossier(domain_key, entity_id)
            if result.get("success"):
                compiled += 1
        return compiled

    from concurrent.futures import ThreadPoolExecutor, as_completed

    logger.info(
        "Dossier catch-up: parallel compile workers=%s candidates=%s skip_narrative=%s",
        workers,
        len(candidates),
        _dossier_skip_narrative_enabled(),
    )

    def _one(pair: tuple) -> bool:
        domain_key, entity_id = pair
        return bool(compile_dossier(domain_key, entity_id).get("success"))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_one, pair): pair for pair in candidates}
        for fut in as_completed(futures):
            try:
                if fut.result():
                    compiled += 1
            except Exception as exc:
                pair = futures[fut]
                logger.warning("compile_dossier %s failed: %s", pair, exc)
    return compiled


def count_dossier_narrative_pending() -> int:
    """Dossiers fast-compiled with narrative_pending awaiting PopOS GPU backfill."""
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int
                FROM intelligence.entity_dossiers
                WHERE COALESCE(metadata->>'narrative_pending', 'false') = 'true'
                """
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception as e:
        logger.debug("count_dossier_narrative_pending: %s", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _load_dossier_narrative_backfill_row(
    domain_key: str,
    entity_id: int,
) -> dict[str, Any] | None:
    """Load dossier fields for narrative backfill; connection closed before return."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ed.chronicle_data, ed.relationships, ed.positions, ed.patterns, ed.metadata,
                       COALESCE(ep.metadata->>'canonical_name', 'Entity ' || ed.entity_id::text),
                       COALESCE(ep.metadata->>'entity_type', 'unknown')
                FROM intelligence.entity_dossiers ed
                LEFT JOIN intelligence.entity_profiles ep
                  ON ep.domain_key = ed.domain_key
                 AND ep.canonical_entity_id = ed.entity_id
                WHERE ed.domain_key = %s AND ed.entity_id = %s
                  AND COALESCE(ed.metadata->>'narrative_pending', 'false') = 'true'
                """,
                (domain_key, entity_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            metadata = row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}")
            return {
                "chronicle_data": row[0] if isinstance(row[0], list) else json.loads(row[0] or "[]"),
                "relationships": row[1] if isinstance(row[1], list) else json.loads(row[1] or "[]"),
                "positions": row[2] if isinstance(row[2], list) else json.loads(row[2] or "[]"),
                "patterns": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
                "metadata": metadata,
                "entity_name": row[5],
                "entity_type": row[6],
                "storyline_refs": metadata.get("storyline_refs") or [],
            }


def _backfill_one_dossier_narrative(
    domain_key: str,
    entity_id: int,
    *,
    execution_lane: str = "gpu",
    model: str | None = None,
) -> bool:
    row = _load_dossier_narrative_backfill_row(domain_key, entity_id)
    if not row:
        return False

    # Do not hold a pooled DB connection across slow Ollama I/O.
    narrative = _generate_dossier_narrative(
        entity_name=row["entity_name"],
        entity_type=row["entity_type"],
        chronicle_data=row["chronicle_data"],
        positions=row["positions"],
        relationships=row["relationships"],
        storyline_refs=row["storyline_refs"],
        patterns=row["patterns"],
        execution_lane=execution_lane,
    )
    if not narrative:
        return False

    metadata = dict(row["metadata"])
    metadata["narrative_summary"] = narrative
    metadata.pop("narrative_pending", None)
    metadata.pop("catchup_fast_compile", None)

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.entity_dossiers
                    SET metadata = %s::jsonb
                    WHERE domain_key = %s AND entity_id = %s
                    """,
                    (json.dumps(metadata), domain_key, entity_id),
                )
            conn.commit()

        try:
            from services.saved_intel_service import save_intel_output

            save_intel_output(
                content_type="entity_dossier",
                subject_type="entity",
                subject_id=entity_id,
                content_md=narrative,
                domain_key=domain_key,
                title=row["entity_name"],
                metadata={
                    "article_count": metadata.get("article_count"),
                    "storyline_count": metadata.get("storyline_count"),
                    "narrative_backfill": True,
                    "narrative_lane": execution_lane,
                    "narrative_model": model,
                },
            )
        except Exception as save_err:
            logger.warning("save_intel_output narrative backfill: %s", save_err)
        return True
    except Exception as e:
        logger.warning("narrative backfill %s/%s: %s", domain_key, entity_id, e)
        return False


def backfill_dossier_narratives(
    max_n: int,
    *,
    parallel: int | None = None,
    cpu_parallel: int | None = None,
    model: str | None = None,
    use_gpu: bool = True,
) -> int:
    """Generate dossier narratives on PopOS GPU and/or Widow CPU for fast-compiled rows."""
    gpu_workers = parallel if parallel is not None else _dossier_narrative_parallel_workers()
    if cpu_parallel is not None:
        cpu_workers = max(0, cpu_parallel)
    else:
        cpu_workers = _dossier_narrative_cpu_parallel_workers()
    narrative_model = model or _dossier_narrative_model()

    conn = get_db_connection()
    if not conn:
        return 0
    candidates: list[tuple[str, int]] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, entity_id
                FROM intelligence.entity_dossiers
                WHERE COALESCE(metadata->>'narrative_pending', 'false') = 'true'
                ORDER BY compilation_date DESC NULLS LAST
                LIMIT %s
                """,
                (max_n,),
            )
            candidates = [(r[0], int(r[1])) for r in cur.fetchall()]
    except Exception as e:
        logger.debug("backfill_dossier_narratives select: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not candidates:
        return 0

    total_workers = 0
    if use_gpu and gpu_workers > 0:
        total_workers += gpu_workers
    if cpu_workers > 0:
        total_workers += cpu_workers

    logger.info(
        "Dossier narrative backfill: gpu_workers=%s cpu_workers=%s candidates=%s model=%s",
        gpu_workers if use_gpu else 0,
        cpu_workers,
        len(candidates),
        narrative_model,
    )

    if total_workers <= 1 or len(candidates) <= 1:
        done = 0
        for dk, eid in candidates:
            lane = "gpu" if use_gpu and gpu_workers > 0 else "cpu"
            if _backfill_one_dossier_narrative(dk, eid, execution_lane=lane, model=narrative_model):
                done += 1
        return done

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Split candidates between GPU and CPU workers
    gpu_candidates = []
    cpu_candidates = []
    if use_gpu and gpu_workers > 0:
        gpu_candidates = candidates[:len(candidates) * gpu_workers // total_workers]
    if cpu_workers > 0:
        cpu_candidates = candidates[len(gpu_candidates):]

    done = 0
    with ThreadPoolExecutor(max_workers=total_workers) as pool:
        futures = {}
        for dk, eid in gpu_candidates:
            futures[pool.submit(_backfill_one_dossier_narrative, dk, eid, execution_lane="gpu", model=narrative_model)] = (dk, eid)
        for dk, eid in cpu_candidates:
            futures[pool.submit(_backfill_one_dossier_narrative, dk, eid, execution_lane="cpu", model=narrative_model)] = (dk, eid)

        for fut in as_completed(futures):
            try:
                if fut.result():
                    done += 1
            except Exception as exc:
                pair = futures[fut]
                logger.warning("narrative backfill %s failed: %s", pair, exc)
    return done
