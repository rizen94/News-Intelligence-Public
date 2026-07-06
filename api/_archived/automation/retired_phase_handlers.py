"""POST_SPINE_RETIRED phase handlers extracted from automation_manager (v10.1 prune).

Invoked only when ASSEMBLY_PIPELINE_MODE=legacy or phase explicitly scheduled.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.automation_manager import AutomationManager

logger = logging.getLogger(__name__)

async def execute_storyline_synthesis(automation: AutomationManager, task: Any) -> None:
        """Auto-synthesize storylines (Wikipedia-style) that have 3+ articles."""
        import asyncio

        try:
            from services.deep_content_synthesis import DeepContentSynthesisService

            svc = DeepContentSynthesisService()
            loop = asyncio.get_event_loop()

            for domain_key, schema in pipeline_url_schema_pairs():
                conn = await automation._get_db_connection()
                if not conn:
                    continue
                try:
                    cur = conn.cursor()
                    # Storylines with 3+ articles: no synthesis yet, or stale (newest article newer than synthesized_at)
                    try:
                        cur.execute(
                            f"""
                            SELECT s.id FROM {schema}.storylines s
                            JOIN (SELECT storyline_id, COUNT(*) AS c FROM {schema}.storyline_articles GROUP BY storyline_id) sa
                              ON sa.storyline_id = s.id AND sa.c >= 3
                            WHERE s.synthesized_content IS NULL
                               OR EXISTS (
                                 SELECT 1 FROM {schema}.storyline_articles sa2
                                 JOIN {schema}.articles a ON a.id = sa2.article_id
                                 WHERE sa2.storyline_id = s.id
                                 AND a.created_at > COALESCE(s.synthesized_at, '1970-01-01'::timestamptz)
                               )
                            ORDER BY s.synthesized_at NULLS FIRST,
                                     (SELECT MAX(a2.created_at) FROM {schema}.storyline_articles sa3
                                      JOIN {schema}.articles a2 ON a2.id = sa3.article_id
                                      WHERE sa3.storyline_id = s.id) DESC NULLS LAST
                            LIMIT 4
                            """
                        )
                    except Exception:
                        # Fallback if synthesized_at column missing
                        cur.execute(
                            f"""
                            SELECT s.id FROM {schema}.storylines s
                            JOIN (SELECT storyline_id, COUNT(*) AS c FROM {schema}.storyline_articles GROUP BY storyline_id) sa
                              ON sa.storyline_id = s.id AND sa.c >= 3
                            WHERE s.synthesized_content IS NULL
                            ORDER BY s.updated_at DESC
                            LIMIT 4
                            """
                        )
                    rows = cur.fetchall()
                    cur.close()
                    conn.close()
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue
                for (storyline_id,) in rows:
                    try:
                        await loop.run_in_executor(
                            None,
                            lambda d=domain_key, sid=storyline_id: svc.synthesize_storyline_content(
                                d, sid, depth="standard", save_to_db=True
                            ),
                        )
                        logger.info(
                            f"Storyline synthesis (v8): {domain_key} storyline {storyline_id}"
                        )
                    except Exception as e:
                        logger.warning(f"Storyline synthesis {storyline_id} failed: {e}")
        except Exception as e:
            logger.warning(f"Storyline synthesis phase failed: {e}")



async def execute_daily_briefing_synthesis(automation: AutomationManager, task: Any) -> None:
        """Generate breaking-news synthesis per domain for briefing page."""
        import asyncio

        try:
            from services.deep_content_synthesis import DeepContentSynthesisService

            svc = DeepContentSynthesisService()
            loop = asyncio.get_event_loop()
            for domain_key in get_pipeline_active_domain_keys():
                try:
                    await loop.run_in_executor(
                        None,
                        lambda d=domain_key: svc.synthesize_breaking_news(
                            d, hours=72, min_articles=3
                        ),  # v8
                    )
                    logger.info(f"Daily briefing synthesis (v8): {domain_key}")
                except Exception as e:
                    logger.warning(f"Daily briefing synthesis {domain_key} failed: {e}")
        except Exception as e:
            logger.warning(f"Daily briefing synthesis phase failed: {e}")



async def execute_investigation_report_refresh(automation: AutomationManager, task: Any) -> None:
        """Regenerate investigation reports for events whose context set has changed (Phase 2.4)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("investigation_report_refresh"):
                return
        except Exception:
            pass
        from services.investigation_report_service import (
            create_initial_reports_for_new_events,
            refresh_stale_investigation_reports,
        )

        try:
            created = await create_initial_reports_for_new_events(limit=5)
            refreshed = await refresh_stale_investigation_reports(limit=3)
            if created > 0 or refreshed > 0:
                logger.info(f"Investigation report refresh: {created} new, {refreshed} updated")
            else:
                logger.debug("Investigation report refresh: no new or stale reports")
        except Exception as e:
            logger.warning(f"Investigation report refresh failed: {e}")



async def execute_event_coherence_review(automation: AutomationManager, task: Any) -> None:
        """LLM-powered review: verify each context in an event actually belongs (Phase 3)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("event_coherence_review"):
                return
        except Exception:
            pass
        from services.event_coherence_reviewer import review_all_open_events

        try:
            result = await review_all_open_events(relevance_threshold=0.5, auto_remove=True)
            removed = result.get("total_contexts_removed", 0)
            reviewed = result.get("events_reviewed", 0)
            if removed > 0:
                logger.info(
                    f"Event coherence review: {removed} contexts removed from {reviewed} events"
                )
            else:
                logger.debug(f"Event coherence review: {reviewed} events reviewed, all coherent")
        except Exception as e:
            logger.warning(f"Event coherence review failed: {e}")



async def execute_entity_position_tracker(automation: AutomationManager, task: Any) -> None:
        """Extract entity positions (stances, votes, policy) from articles; populate intelligence.entity_positions."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("entity_position_tracker"):
                return
        except Exception:
            pass
        from services.entity_position_tracker_service import run_position_tracker_batch

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                automation._executor,
                run_position_tracker_batch,
                None,  # domain_key -> all domains
                5,  # min_mentions
                8,  # max_entities
                25,  # max_articles_per_entity (v8)
            )
            total = sum(
                r.get("total_positions", 0) for r in (results or {}).values() if isinstance(r, dict)
            )
            if total > 0:
                logger.info("Entity position tracker: %s positions extracted", total)
        except Exception as e:
            logger.warning("Entity position tracker failed: %s", e)



async def execute_story_enhancement(automation: AutomationManager, task: Any) -> None:
        """Phase 3 RAG: facts/queue during bulk; full enrich+build only in refinement window."""
        from services.enhancement_orchestrator_service import run_enhancement_cycle
        from shared.pipeline_resource_policy import story_enhancement_facts_only

        try:
            def _int_env(name: str, default: int) -> int:
                try:
                    return int(env_str(name, str(default)))
                except ValueError:
                    return default

            fact_batch = max(10, min(500, _int_env("STORY_ENHANCEMENT_FACT_BATCH", 100)))
            queue_batch = max(1, min(50, _int_env("STORY_ENHANCEMENT_QUEUE_BATCH", 10)))
            facts_only = story_enhancement_facts_only()
            enrich_limit = 0 if facts_only else max(1, min(50, _int_env("STORY_ENHANCEMENT_ENRICH_LIMIT", 10)))
            build_limit = 0 if facts_only else max(1, min(50, _int_env("STORY_ENHANCEMENT_BUILD_LIMIT", 10)))
            result = await run_enhancement_cycle(
                fact_batch=fact_batch,
                queue_batch=queue_batch,
                enrich_limit=enrich_limit,
                build_limit=build_limit,
            )
            total = (
                result.get("fact_change_log_processed", 0)
                + result.get("story_update_queue_processed", 0)
                + result.get("entity_profiles_enriched", 0)
                + result.get("entity_profiles_built", 0)
            )
            if total > 0 or result.get("errors"):
                logger.info(
                    "Story enhancement cycle: fact_log=%s queue=%s enriched=%s built=%s",
                    result.get("fact_change_log_processed", 0),
                    result.get("story_update_queue_processed", 0),
                    result.get("entity_profiles_enriched", 0),
                    result.get("entity_profiles_built", 0),
                )
            if result.get("errors"):
                logger.warning("Story enhancement errors: %s", result["errors"])
        except Exception as e:
            logger.warning(f"Story enhancement failed: {e}")



async def execute_pattern_matching(automation: AutomationManager, task: Any) -> None:
        """Phase 4 RAG: Run watch pattern matching for all domains; record pattern_matches and create watchlist alerts."""
        from services.watch_pattern_service import run_pattern_matching_all_domains

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: run_pattern_matching_all_domains(limit_per_domain=30)
            )
            if result.get("matches_stored", 0) > 0:
                logger.info(
                    "Pattern matching: matches_stored=%s alerts_created=%s "
                    "skipped_no_storyline=%s skipped_not_on_watchlist=%s",
                    result.get("matches_stored", 0),
                    result.get("alerts_created", 0),
                    result.get("alerts_skipped_no_storyline", 0),
                    result.get("alerts_skipped_not_on_watchlist", 0),
                )
        except Exception as e:
            logger.warning("Pattern matching failed: %s", e)



async def execute_pattern_recognition(automation: AutomationManager, task: Any) -> None:
        """Discover patterns (network, temporal, behavioral, event) and persist to pattern_discoveries (Phase 2.2)."""
        try:
            from config.context_centric_config import is_context_centric_task_enabled

            if not is_context_centric_task_enabled("pattern_recognition"):
                return
            from shared.intelligence_phase_gates import should_skip_automation_phase

            if should_skip_automation_phase("pattern_recognition"):
                return
        except Exception:
            pass
        import asyncio

        from services.pattern_recognition_service import run_pattern_discovery_batch

        try:
            total = await asyncio.get_event_loop().run_in_executor(
                None, run_pattern_discovery_batch
            )
            if total > 0:
                logger.info(f"Pattern recognition: {total} patterns discovered")
        except Exception as e:
            logger.warning(f"Pattern recognition failed: {e}")



async def execute_arc_report_generation(automation: AutomationManager, task: Any) -> None:
        import asyncio
        import os

        from services.arc_catalog_service import list_active_arcs, sync_arc_definitions_from_yaml
        from services.nightly_ingest_window_service import in_nightly_pipeline_window_est
        from services.slow_report_service import generate_slow_report

        anytime = env_str("ARC_REPORT_ANYTIME", "false").lower() in ("1", "true", "yes")
        if not anytime and not in_nightly_pipeline_window_est():
            logger.info("Arc report generation skipped outside nightly pipeline window")
            return
        from shared.intelligence_phase_gates import should_skip_automation_phase

        if should_skip_automation_phase("arc_report_generation"):
            logger.debug("Arc report generation skipped (intelligence.arc_definitions empty)")
            return

        try:
            await asyncio.get_event_loop().run_in_executor(None, sync_arc_definitions_from_yaml)
            arcs = await asyncio.get_event_loop().run_in_executor(None, list_active_arcs)
            for arc in arcs:
                aid = arc.get("arc_id")
                if not aid:
                    continue
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda a=aid: generate_slow_report(a, report_type="weekly_brief")
                )
                logger.info("Arc report %s: %s", aid, result.get("validation"))
        except Exception as e:
            logger.warning("Arc report generation failed: %s", e)



async def execute_editorial_document_generation(automation: AutomationManager, task: Any) -> None:
        """Generate/refine editorial_document for active storylines across all domains."""
        from services.editorial_document_service import generate_storyline_editorial
        from services.content_validation_service import content_validation_service

        for domain in get_pipeline_active_domain_keys():
            try:
                # Validate content before proceeding with editorial generation
                # This ensures that downstream processes have sufficient content
                logger.debug(f"Checking content availability for editorial document generation in domain {domain}")
                
                # Get storylines that need editorial work
                schema = resolve_domain_schema(domain)
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                f"""
                                SELECT s.id, s.title, s.description, s.analysis_summary,
                                       s.editorial_document, s.document_version, s.last_refinement,
                                       s.updated_at
                                FROM {schema}.storylines s
                                WHERE s.status IN ('active', 'developing', 'ongoing')
                                  AND (
                                      s.editorial_document IS NULL
                                      OR s.editorial_document = '{{}}'::jsonb
                                      OR s.updated_at > COALESCE(s.last_refinement, '1970-01-01'::timestamptz)
                                  )
                                ORDER BY s.updated_at DESC
                                LIMIT 10
                                """
                            )
                            storylines = cursor.fetchall()
                        
                        # Validate that these storylines have sufficient content
                        for row in storylines:
                            sid, title, description, analysis_summary, existing_doc, doc_version, last_refined, updated_at = row
                            storyline_validation = await content_validation_service.validate_storyline_content_requirements(domain, sid)
                            if not storyline_validation.get("valid", False):
                                logger.warning(f"Skipping storyline {sid} in domain {domain} - insufficient content")
                                continue
                            
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"Content validation check failed for domain {domain}: {e}")
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            pass
                
                result = await generate_storyline_editorial(domain, limit=5)
                logger.info("Editorial doc generation (%s): %s", domain, result)
            except Exception as e:
                logger.warning("editorial_document_generation (%s): %s", domain, e)



async def execute_editorial_briefing_generation(automation: AutomationManager, task: Any) -> None:
        """Global narrative + domain lenses first, then legacy briefing for events without a spine."""
        from services.editorial_document_service import generate_event_editorial
        from services.tracked_event_narrative_service import run_tracked_event_narrative_stack

        try:
            stack = await run_tracked_event_narrative_stack(limit=5)
            logger.info("Tracked event narrative stack: %s", stack)
        except Exception as e:
            logger.warning("tracked_event_narrative_stack: %s", e)
        try:
            result = await generate_event_editorial(limit=5)
            logger.info("Editorial briefing generation: %s", result)
        except Exception as e:
            logger.warning("editorial_briefing_generation: %s", e)



async def execute_narrative_thread_build(automation: AutomationManager, task: Any) -> None:
        """Build narrative threads from storylines across all domains, then synthesize."""
        import asyncio

        from services.narrative_thread_service import build_threads_for_domain

        loop = asyncio.get_event_loop()
        for domain in get_pipeline_active_domain_keys():
            try:
                result = await loop.run_in_executor(
                    None, lambda d=domain: build_threads_for_domain(d, limit=30)
                )
                built = result.get("built", 0)
                if built > 0:
                    logger.info("Narrative thread build (%s): %s threads", domain, built)
            except Exception as e:
                logger.warning("narrative_thread_build (%s): %s", domain, e)



async def execute_digest_generation(automation: AutomationManager, task: Any) -> None:
        """Execute digest generation task"""
        from services.digest_automation_service import get_digest_service

        digest_service = get_digest_service()
        await digest_service.generate_digest_if_needed()



async def execute_rag_enhancement(automation: AutomationManager, task: Any) -> None:
        """Execute RAG enhancement per domain (v8): enhance storylines with Wikipedia/GDELT context, store by (domain, storyline_id)."""
        from shared.database.connection import get_db_connection

        from services.rag import get_rag_service

        rag_service = get_rag_service()
        enhanced_count = 0
        for domain in get_pipeline_active_domain_keys():
            schema = resolve_domain_schema(domain)
            try:
                conn = get_db_connection()
                if not conn:
                    continue
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"""
                            SELECT s.id, s.title, s.rag_enhanced_at,
                                   COALESCE(array_agg(sa.article_id) FILTER (WHERE sa.article_id IS NOT NULL), '{{}}') AS article_ids
                            FROM {schema}.storylines s
                            LEFT JOIN {schema}.storyline_articles sa ON sa.storyline_id = s.id
                            WHERE s.status = 'active'
                            GROUP BY s.id, s.title, s.rag_enhanced_at
                            HAVING COUNT(sa.article_id) > 0
                        """)
                        rows = cur.fetchall()
                finally:
                    conn.close()

                for row in rows:
                    sid, title, rag_enhanced_at, article_ids = row[0], row[1], row[2], row[3] or []
                    try:
                        if rag_enhanced_at:
                            elapsed = (datetime.now(timezone.utc) - rag_enhanced_at).total_seconds()
                            if elapsed < 3600:
                                continue
                        # Fetch article summaries for context
                        articles_for_rag = []
                        if article_ids:
                            conn = get_db_connection()
                            if conn:
                                try:
                                    with conn.cursor() as cur:
                                        cur.execute(
                                            f"""
                                            SELECT id, title, content, summary, source_domain
                                            FROM {schema}.articles WHERE id = ANY(%s)
                                        """,
                                            (list(article_ids)[:30],),
                                        )
                                        for r in cur.fetchall():
                                            articles_for_rag.append(
                                                {
                                                    "id": r[0],
                                                    "title": r[1],
                                                    "content": r[2] or "",
                                                    "summary": r[3],
                                                    "source": r[4],
                                                }
                                            )
                                finally:
                                    conn.close()
                        await rag_service.enhance_storyline_context(
                            storyline_id=str(sid),
                            storyline_title=title or "",
                            articles=articles_for_rag,
                            domain=domain,
                        )
                        enhanced_count += 1
                    except Exception as e:
                        logger.debug("RAG enhance %s storyline %s: %s", domain, sid, e)
            except Exception as e:
                logger.warning("RAG enhancement domain %s: %s", domain, e)
        logger.info(
            "RAG enhancement completed: %s storylines enhanced (all domains)", enhanced_count
        )



async def execute_storyline_processing(automation: AutomationManager, task: Any) -> None:
        """Execute storyline processing per domain: generates analysis_summary, seeds editorial_document.
        Uses domain-aware StorylineService so active-domain storylines get narratives.
        Includes content validation to ensure downstream processes have sufficient content."""
        from domains.storyline_management.services.storyline_service import (
            StorylineService as DomainStorylineService,
        )
        from shared.database.connection import get_db_connection
        from services.content_validation_service import content_validation_service

        processed_count = 0
        for domain, schema in pipeline_url_schema_pairs():
            try:
                conn = get_db_connection()
                if not conn:
                    continue
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"""
                            SELECT s.id, s.title,
                                   COALESCE(s.analysis_summary, '') AS analysis_summary,
                                   COALESCE(s.master_summary, '') AS master_summary,
                                   (s.editorial_document IS NOT NULL AND s.editorial_document != '{{}}'::jsonb) AS has_ed
                            FROM {schema}.storylines s
                            WHERE s.status = 'active'
                              AND EXISTS (
                                  SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id
                              )
                        """)
                        rows = cur.fetchall()
                finally:
                    conn.close()

                svc = DomainStorylineService(domain=domain)
                for row in rows:
                    sid, _title, analysis_summary, master_summary, has_ed = (
                        row[0],
                        row[1],
                        row[2] or "",
                        row[3] or "",
                        row[4],
                    )
                    summary_for_check = analysis_summary or master_summary
                    
                    # Validate content before proceeding with processing
                    storyline_validation = await content_validation_service.validate_storyline_content_requirements(domain, sid)
                    if not storyline_validation.get("valid", False):
                        logger.warning("Skipping storyline %s/%s: insufficient content", domain, sid)
                        continue
                    
                    if len(summary_for_check) < 100:
                        try:
                            result = await svc.generate_storyline_summary(sid)
                            if not result.get("success"):
                                continue
                            summary_text = (result.get("data") or {}).get("summary", "")
                            if summary_text:
                                from shared.llm_text_sanitize import sanitize_briefing_lede

                                summary_text = sanitize_briefing_lede(summary_text, max_length=400)
                                processed_count += 1
                                if not has_ed:
                                    try:
                                        conn = get_db_connection()
                                        if conn:
                                            try:
                                                with conn.cursor() as cur:
                                                    cur.execute(
                                                        f"""
                                                        UPDATE {schema}.storylines
                                                        SET editorial_document = jsonb_build_object(
                                                                'lede', LEFT(%s, 300),
                                                                'developments', '[]'::jsonb,
                                                                'analysis', %s,
                                                                'outlook', '',
                                                                'generated_at', NOW()::text
                                                            ),
                                                            document_version = COALESCE(document_version, 0) + 1,
                                                            document_status = 'auto_seeded'
                                                        WHERE id = %s AND (editorial_document IS NULL OR editorial_document = '{{}}'::jsonb)
                                                    """,
                                                        (summary_text, summary_text, sid),
                                                    )
                                                conn.commit()
                                            finally:
                                                conn.close()
                                    except Exception as ed_err:
                                        logger.debug(
                                            "Seed editorial_document %s/%s: %s", domain, sid, ed_err
                                        )
                        except Exception as e:
                            logger.warning(
                                "Error processing storyline %s/%s (generate_storyline_summary): %s",
                                domain,
                                sid,
                                e,
                            )
            except Exception as e:
                logger.warning("Storyline processing domain %s: %s", domain, e)

        logger.info(
            "Storyline processing completed: %s storylines processed (all domains)", processed_count
        )



async def execute_storyline_enrichment(automation: AutomationManager, task: Any) -> None:
        """v8: Enrich existing storylines with full-history RAG (past articles/contexts from entire DB)."""
        from services.storyline_automation_service import StorylineAutomationService

        meta = task.metadata or {}
        storyline_id = meta.get("storyline_id")
        domain = meta.get("domain")
        if storyline_id and domain:
            try:
                svc = StorylineAutomationService(domain=domain)
                result = await svc.discover_articles_for_storyline(
                    storyline_id, force_refresh=True, enrichment_mode=True
                )
                count = len(result.get("articles", []))
                logger.info(
                    "Storyline enrichment: storyline_id=%s domain=%s discovered %s articles (full history)",
                    storyline_id,
                    domain,
                    count,
                )
            except Exception as e:
                logger.warning(
                    "Storyline enrichment failed for storyline_id=%s: %s", storyline_id, e
                )
        else:
            for d in get_pipeline_active_domain_keys():
                try:
                    svc = StorylineAutomationService(domain=d)
                    conn = await automation._get_db_connection()
                    schema = resolve_domain_schema(d)
                    try:
                        with conn.cursor() as cur:
                            cur.execute(f"""
                                SELECT s.id FROM {schema}.storylines s
                                WHERE s.automation_enabled = true
                                AND EXISTS (SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.storyline_id = s.id)
                                ORDER BY s.last_automation_run ASC NULLS FIRST
                                LIMIT 3
                            """)
                            storyline_rows = cur.fetchall()
                    finally:
                        conn.close()
                    for row in storyline_rows:
                        await svc.discover_articles_for_storyline(
                            row[0], force_refresh=True, enrichment_mode=True
                        )
                except Exception as e:
                    logger.debug("Storyline enrichment batch %s: %s", d, e)
            logger.info("Storyline enrichment: full-history batch run across domains completed")



async def execute_storyline_discovery(automation: AutomationManager, task: Any) -> None:
        """Auto-discover storylines from recent article clusters using AI similarity.
        Runs AIStorylineDiscovery.discover_storylines() for each domain (full backlog,
        newest-first cap), creating new storylines from high-similarity clusters."""
        import asyncio

        try:
            from services.ai_storyline_discovery import get_discovery_service

            service = get_discovery_service()
            total_created = 0
            for domain in get_pipeline_active_domain_keys():
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None,
                        lambda d=domain: service.discover_storylines(
                            domain=d, hours=None, save_to_db=True
                        ),
                    )
                    saved = len(result.get("saved_storylines", []))
                    clusters = result.get("summary", {}).get("clusters_found", 0)
                    total_created += saved
                    cp = (result.get("stats") or {}).get("clustering_params") or {}
                    sd = (result.get("stats") or {}).get("storyline_development") or {}
                    logger.info(
                        "Storyline discovery [%s]: clusters=%d saved=%d thresholds=%s development=%s",
                        domain,
                        clusters,
                        saved,
                        cp,
                        sd,
                    )
                    if saved > 0:
                        logger.info(
                            "Storyline discovery [%s]: %d clusters → %d new storylines",
                            domain,
                            clusters,
                            saved,
                        )
                except Exception as e:
                    logger.warning("Storyline discovery failed for %s: %s", domain, e)
            logger.info("Storyline discovery complete: %d new storylines created", total_created)
        except Exception as e:
            logger.warning("Storyline discovery task failed: %s", e)



async def execute_proactive_detection(automation: AutomationManager, task: Any) -> None:
        """v8: Detect emerging storylines from unlinked articles (per domain)."""
        try:
            from domains.storyline_management.services.proactive_detection_service import (
                ProactiveDetectionService,
            )

            for domain in get_pipeline_active_domain_keys():
                try:
                    svc = ProactiveDetectionService(domain=domain)
                    result = await svc.detect_emerging_storylines()
                    if result.get("success"):
                        d = result.get("data") or {}
                        if (
                            d.get("stored_count", 0) > 0
                            or d.get("promoted_to_domain_storylines", 0) > 0
                        ):
                            logger.info(
                                "Proactive detection [%s]: emerging_stored=%s promoted_to_domain_storylines=%s",
                                domain,
                                d.get("stored_count", 0),
                                d.get("promoted_to_domain_storylines", 0),
                            )
                except Exception as e:
                    logger.debug("Proactive detection failed for %s: %s", domain, e)
        except Exception as e:
            logger.warning("Proactive detection task failed: %s", e)



async def execute_timeline_generation(automation: AutomationManager, task: Any) -> None:
        """
        Summarize existing chronological_events into storylines.timeline_summary text.

        Does not extract events (that is event_extraction + story_continuation). Optional
        historical_context enriches summaries with older facts when STORYLINE_HISTORICAL_IN_TIMELINE_SUMMARY=1.
        """
        from services.timeline_builder_service import TimelineBuilderService

        use_historical = env_str(
            "STORYLINE_HISTORICAL_IN_TIMELINE_SUMMARY", "1"
        ).strip().lower() in ("1", "true", "yes")
        generated_count = 0

        for schema in get_pipeline_schema_names_active():
            conn_sel = await automation._get_db_connection()
            storyline_ids: list[int] = []
            try:
                with conn_sel.cursor() as cur:
                    cur.execute(f"""
                        SELECT s.id FROM {schema}.storylines s
                        WHERE s.status = 'active'
                          AND EXISTS (
                              SELECT 1 FROM {schema}.storyline_articles sa
                              WHERE sa.storyline_id = s.id
                          )
                          AND (
                              s.timeline_summary IS NULL
                              OR LENGTH(COALESCE(s.timeline_summary, '')) < 100
                          )
                        ORDER BY s.updated_at DESC NULLS LAST
                        LIMIT 12
                    """)
                    storyline_ids = [row[0] for row in cur.fetchall() if row and row[0] is not None]
            finally:
                conn_sel.close()

            for sid in storyline_ids:
                conn = await automation._get_db_connection()
                try:
                    tb = TimelineBuilderService(conn, schema_name=schema)
                    timeline = tb.build_timeline(sid)
                    events = timeline.get("events") or []
                    if not events:
                        continue
                    parts = []
                    for e in events[:25]:
                        title = (e.get("title") or "").strip()
                        d = e.get("event_date")
                        ds = d.isoformat() if hasattr(d, "isoformat") else (str(d) if d else "")
                        if title:
                            parts.append(f"{ds}: {title}" if ds else title)
                    summary = f"Timeline ({len(events)} events): " + " | ".join(parts[:12])
                    if use_historical:
                        try:
                            from shared.domain_registry import schema_to_primary_domain_key
                            from services.storyline_historical_context_service import (
                                build_storyline_historical_context,
                                render_historical_context_for_llm,
                            )

                            dk = schema_to_primary_domain_key(schema)
                            hctx = build_storyline_historical_context(dk, sid, conn=conn)
                            if hctx.get("success"):
                                hist = render_historical_context_for_llm(hctx, max_chars=2000)
                                if hist:
                                    summary = summary + "\n\n" + hist
                        except Exception as hist_err:
                            logger.debug("timeline_summary historical_context: %s", hist_err)
                    if len(summary) > 12000:
                        summary = summary[:11997] + "..."
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET timeline_summary = %s
                            WHERE id = %s
                        """,
                            (summary, sid),
                        )
                        conn.commit()
                    generated_count += 1
                except Exception as e:
                    logger.error(
                        "Timeline generation failed for storyline %s (%s): %s",
                        sid,
                        schema,
                        e,
                    )
                finally:
                    conn.close()

        logger.info(
            "Timeline summary generation completed: %s storyline summaries from existing "
            "chronological_events (no event extraction in this phase)",
            generated_count,
        )




PHASE_NAMES = (
    "storyline_synthesis", "daily_briefing_synthesis", "investigation_report_refresh",
    "event_coherence_review", "entity_position_tracker", "story_enhancement",
    "pattern_matching", "pattern_recognition", "arc_report_generation",
    "editorial_document_generation", "editorial_briefing_generation",
    "narrative_thread_build", "digest_generation", "rag_enhancement",
    "storyline_processing", "storyline_enrichment", "storyline_discovery",
    "proactive_detection", "timeline_generation",
)


async def dispatch_retired_phase(automation, phase_name: str, task) -> None:
    fn = globals().get(f"execute_{phase_name}")
    if fn is None:
        raise ValueError(f"no archived handler for phase {phase_name}")
    await fn(automation, task)
