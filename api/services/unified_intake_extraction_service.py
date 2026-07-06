"""
Unified intake extraction — Intake Fusion: one batched LLM call, bulk fan-out per article.

Replaces separate entity_extraction, event_extraction, claim_extraction (context),
sentiment_analysis, and quality_scoring when UNIFIED_INTAKE_EXTRACTION_ENABLED=true.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_str
from config.settings import OLLAMA_HOST
from services.article_entity_extraction_service import ArticleEntityExtractionService
from services.claim_extraction_service import insert_parsed_claims_for_context
from services.context_processor_service import ensure_context_for_article, link_context_to_article_entities
from services.event_extraction_service import EventExtractionService, VALID_EVENT_TYPES
from shared.fast_ner_lane import (
    extract_fast_entities,
    format_ner_hints_for_prompt,
    merge_entity_dicts,
)
from shared.database.connection import get_db_connection
from shared.intake_fusion_schema import fusion_prompt_schema_block, normalize_topic_tags
from shared.pipeline_pass_marker import (
    infer_entity_extraction_terminal,
    infer_event_extraction_terminal,
    record_article_phase_pass,
)
from shared.services.ollama_model_caller import get_ollama_model_caller
from shared.services.ollama_model_policy import InvocationKind
from shared.monitor_pulse_debug import monitor_pulse_debug
from shared.spine_phase_order import intake_fusion_enabled

logger = logging.getLogger(__name__)

_EVENT_TYPES_STR = ", ".join(sorted(VALID_EVENT_TYPES))


def _bulk_catchup_fast_path() -> bool:
    return env_str("BULK_CATCHUP_ACTIVE", "").lower() in ("1", "true", "yes")


def _defer_context_during_bulk() -> bool:
    if env_str("UNIFIED_INTAKE_DEFER_CONTEXT_SYNC", "").lower() in ("1", "true", "yes"):
        return True
    return _bulk_catchup_fast_path()


class UnifiedIntakeExtractionService:
    """Batched structured extraction with fan-out to existing storage paths."""

    def __init__(self) -> None:
        self._caller = get_ollama_model_caller()
        self._entity_svc = ArticleEntityExtractionService(ollama_url=OLLAMA_HOST)
        self._event_svc = EventExtractionService()

    async def close(self) -> None:
        await self._event_svc.close()

    async def extract_batch(
        self,
        articles: list[dict[str, Any]],
    ) -> dict[int, dict[str, Any]]:
        if not articles:
            return {}

        blocks: list[str] = []
        valid: list[dict[str, Any]] = []
        fast_by_id: dict[int, dict[str, list[dict[str, Any]]]] = {}
        for art in articles:
            aid = int(art["article_id"])
            title = art.get("title") or ""
            content = art.get("content") or ""
            combined = f"{title}\n\n{content}"[:8000]
            if len(combined.strip()) < 50:
                continue
            fast_by_id[aid] = extract_fast_entities(title, content)
            ner_count = sum(len(v) for v in (fast_by_id[aid] or {}).values())
            if len(combined.strip()) < 400 and ner_count < 2:
                schema = art.get("schema") or art.get("schema_name") or ""
                if schema:
                    from shared.pipeline_pass_marker import (
                        TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
                        record_article_phase_pass,
                    )

                    record_article_phase_pass(
                        schema,
                        aid,
                        "unified_intake_extraction",
                        "fast_ner_sparse_skip",
                        TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
                    )
                continue
            pub = art.get("pub_date")
            pub_s = pub.strftime("%Y-%m-%d") if isinstance(pub, datetime) else "unknown"
            hint = format_ner_hints_for_prompt(fast_by_id[aid])
            hint_block = f"\n{hint}\n" if hint else ""
            blocks.append(
                f"=== ARTICLE {aid} ===\n"
                f"Headline: {title}\n"
                f"Publication date: {pub_s}\n"
                f"{hint_block}\n"
                f"{combined}"
            )
            valid.append(art)

        if not blocks:
            return {}

        prompt = self._build_prompt(blocks)
        llm_t0 = time.monotonic()
        try:
            gen = await self._caller.generate(
                prompt,
                kind=InvocationKind.STRUCTURED_EXTRACTION,
                approx_prompt_chars=len(prompt),
            )
            raw = (gen.text or "") if gen is not None else ""
            extraction_model = getattr(gen, "model", None)
        except Exception as e:
            logger.error("unified_intake_extraction LLM failed: %s", e)
            return {}
        llm_elapsed = time.monotonic() - llm_t0

        parsed_by_id = self._parse_batch_response(raw)
        fan_t0 = time.monotonic()

        async def _fan_out_one(art: dict[str, Any]) -> tuple[int, dict[str, Any]]:
            aid = int(art["article_id"])
            payload = parsed_by_id.get(aid)
            if not payload:
                return aid, {"success": False, "reason": "parse_missing"}
            try:
                summary = await self._fan_out_article(
                    art,
                    payload,
                    extraction_model=extraction_model,
                    fast_entities=fast_by_id.get(aid) or {},
                )
                return aid, summary
            except Exception as e:
                logger.error("unified fan-out failed article %s: %s", aid, e)
                return aid, {"success": False, "error": str(e)}

        fan_pairs = await asyncio.gather(*[_fan_out_one(art) for art in valid])
        out = dict(fan_pairs)
        fan_elapsed = time.monotonic() - fan_t0
        articles_per_call = len(valid)
        monitor_pulse_debug(
            "unified_intake_extraction_service.py:extract_batch",
            "intake_fusion timing",
            {
                "article_count": articles_per_call,
                "llm_seconds": round(llm_elapsed, 2),
                "fan_out_seconds": round(fan_elapsed, 2),
                "llm_passes_per_article": round(1.0 / max(1, articles_per_call), 4),
                "bulk_fast": _bulk_catchup_fast_path(),
                "fusion_enabled": intake_fusion_enabled(),
            },
            hypothesis_id="throughput",
            run_id="fusion",
        )
        try:
            from services.spine_throughput_metrics import record_fusion_batch_metrics

            record_fusion_batch_metrics(
                article_count=articles_per_call,
                llm_seconds=llm_elapsed,
                fan_out_seconds=fan_elapsed,
            )
        except Exception:
            pass
        return out

    def _build_prompt(self, blocks: list[str]) -> str:
        schema_block = fusion_prompt_schema_block(_EVENT_TYPES_STR)
        fusion_note = ""
        if intake_fusion_enabled():
            fusion_note = (
                "\n- topic_tags: 3-8 specific themes/entities for clustering (not generic words).\n"
                "- storyline_hints: optional 0-2 short storyline labels with primary_entities.\n"
            )
        return f"""Extract structured intelligence from {len(blocks)} news articles below.
Return ONE JSON object mapping each article_id (string key) to an extraction object.

Per-article object schema:
{schema_block}

Rules:
- Use empty arrays when a section has no items. No placeholder names like "None" or "N/A".
- claims: subject and predicate required; object optional; confidence 0.0-1.0.
- events: event_title required per event; use publication context for relative dates.
- scoring.sentiment_score: 0.0 (negative) to 1.0 (positive); quality_score: 0.0-1.0.{fusion_note}

Articles:
{chr(10).join(blocks)}

Return ONLY valid JSON. Example empty article:
{{"12345": {{"entities": {{"people": [], "organizations": [], "subjects": [], "recurring_events": [], "dates": [], "times": [], "countries": [], "keywords": []}}, "claims": [], "events": [], "scoring": {{"sentiment_score": 0.5, "sentiment_label": "neutral", "quality_score": 0.5}}, "topic_tags": [], "storyline_hints": []}}}}
"""

    def _parse_batch_response(self, raw: str) -> dict[int, dict[str, Any]]:
        text = (raw or "").strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                chunk = part.strip()
                if chunk.lower().startswith("json"):
                    chunk = chunk[4:].strip()
                if chunk.startswith("{"):
                    text = chunk
                    break
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            logger.warning("unified_intake_extraction parse: no JSON object in response (len=%s)", len(raw or ""))
            return {}
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            logger.warning(
                "unified_intake_extraction parse: JSON decode failed (len=%s): %s",
                len(raw or ""),
                e,
            )
            return {}
        if not isinstance(parsed, dict):
            return {}
        out: dict[int, dict[str, Any]] = {}
        for k, v in parsed.items():
            try:
                aid = int(k)
                if isinstance(v, dict):
                    out[aid] = v
            except (TypeError, ValueError):
                pass
        return out

    async def _fan_out_article(
        self,
        art: dict[str, Any],
        payload: dict[str, Any],
        *,
        extraction_model: str | None,
        fast_entities: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        article_id = int(art["article_id"])
        schema = art.get("schema") or "politics"
        domain_key = art.get("domain_key") or schema.replace("_", "-")
        title = art.get("title") or ""
        content = art.get("content") or ""
        pub_date = art.get("pub_date") or datetime.now(timezone.utc)
        storyline_id = art.get("storyline_id")

        entity_obj = payload.get("entities") if isinstance(payload.get("entities"), dict) else {}
        if fast_entities:
            entity_obj = merge_entity_dicts(entity_obj, fast_entities)
        parsed, parse_ok = self._entity_svc._parse_response(json.dumps(entity_obj), title)

        topic_tags = normalize_topic_tags(payload.get("topic_tags"))

        counts: dict[str, int] = {}
        entities_ok = False
        claims_inserted = 0
        events_saved = 0
        context_id = None

        conn = get_db_connection()
        if not conn:
            return {"success": False, "error": "no_db_connection"}

        try:
            cur = conn.cursor()
            cur.execute(f"SET search_path TO {schema}, public")

            if parse_ok:
                counts = await self._entity_svc._store_all(
                    conn, article_id, schema, parsed, title, content
                )
                entities_ok = True

            if topic_tags and intake_fusion_enabled():
                _store_topic_tags(cur, schema, article_id, topic_tags)

            if not _defer_context_during_bulk():
                context_id = ensure_context_for_article(domain_key, article_id)
                if context_id:
                    claims_raw = payload.get("claims") if isinstance(payload.get("claims"), list) else []
                    claims_inserted = insert_parsed_claims_for_context(
                        context_id,
                        claims_raw,
                        context_domain_key=domain_key,
                        cred_mult=1.0,
                    )
                    try:
                        link_context_to_article_entities(context_id, domain_key, article_id)
                    except Exception as e:
                        logger.debug("fusion profile link inline %s: %s", article_id, e)

            events_raw = payload.get("events") if isinstance(payload.get("events"), list) else []
            events: list[dict[str, Any]] = []
            for idx, raw_evt in enumerate(events_raw):
                if not isinstance(raw_evt, dict):
                    continue
                evt = self._event_svc._normalise_event(
                    raw_evt,
                    article_id,
                    pub_date,
                    storyline_id,
                    idx,
                    extraction_model=extraction_model or "unified_intake",
                )
                if evt:
                    events.append(evt)

            if events:
                events_saved = int(
                    await self._event_svc.save_events(events, conn, commit=False) or 0
                )

            scoring = payload.get("scoring") if isinstance(payload.get("scoring"), dict) else {}
            sentiment_score = scoring.get("sentiment_score")
            sentiment_label = scoring.get("sentiment_label")
            quality_score = scoring.get("quality_score")
            cur.execute(
                f"""
                UPDATE {schema}.articles
                SET sentiment_score = COALESCE(%s, sentiment_score),
                    sentiment_label = COALESCE(%s, sentiment_label),
                    quality_score = COALESCE(%s, quality_score),
                    timeline_processed = CASE WHEN %s > 0 THEN true ELSE timeline_processed END,
                    timeline_events_generated = CASE WHEN %s > 0 THEN %s ELSE timeline_events_generated END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    sentiment_score,
                    sentiment_label,
                    quality_score,
                    events_saved,
                    events_saved,
                    len(events),
                    article_id,
                ),
            )

            conn.commit()
            cur.close()
        except Exception as e:
            conn.rollback()
            logger.error("unified fusion fan-out %s: %s", article_id, e)
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

        entity_cnt = int(sum(counts.values()) if counts else 0)
        terminal, outcome = infer_entity_extraction_terminal(
            entities_count=entity_cnt,
            content_length=len(content or ""),
            success=entities_ok or parse_ok,
        )
        record_article_phase_pass(
            schema, article_id, "entity_extraction", outcome, terminal_state=terminal
        )

        evt_terminal, evt_outcome = infer_event_extraction_terminal(
            events_count=events_saved,
            content_length=len(content or ""),
            success=True,
        )
        record_article_phase_pass(
            schema,
            article_id,
            "event_extraction",
            evt_outcome,
            terminal_state=evt_terminal,
        )

        if scoring:
            record_article_phase_pass(schema, article_id, "sentiment_analysis", "scored")
            record_article_phase_pass(schema, article_id, "quality_scoring", "scored")

        unified_ok = entities_ok or claims_inserted > 0 or events_saved > 0 or bool(scoring)
        record_article_phase_pass(
            schema,
            article_id,
            "unified_intake_extraction",
            "processed_with_output" if unified_ok else "partial_or_empty",
            terminal_state="processed_with_output" if unified_ok else "processed_empty_legitimate",
        )

        return {
            "success": unified_ok,
            "attempted": True,
            "entities": entity_cnt,
            "claims": claims_inserted,
            "events": events_saved,
            "context_id": context_id,
            "topic_tags": len(topic_tags),
        }


def _store_topic_tags(cur, schema: str, article_id: int, topic_tags: list[dict[str, Any]]) -> None:
    """Seed article_keywords from fusion topic_tags for fast topic match."""
    from shared.database.connection import get_db_connection
    from shared.pg_savepoint import execute_with_savepoint

    conn = getattr(cur, "connection", None) or get_db_connection()
    sp_seq = 0
    for tag in topic_tags:
        kw = (tag.get("keyword") or "").strip()
        if not kw:
            continue
        try:
            conf = float(tag.get("confidence", 0.75))
        except (TypeError, ValueError):
            conf = 0.75
        kw_type = (tag.get("type") or "subject")[:30]
        sp_seq += 1
        execute_with_savepoint(
            cur,
            conn,
            f"fusion_tag_{article_id}_{sp_seq}",
            f"""
                INSERT INTO {schema}.article_keywords
                (article_id, keyword, keyword_type, confidence, in_headline)
                VALUES (%s, %s, %s, %s, false)
                ON CONFLICT (article_id, keyword) DO UPDATE SET
                    confidence = GREATEST({schema}.article_keywords.confidence, EXCLUDED.confidence)
            """,
            (article_id, kw[:255], kw_type, max(0.0, min(1.0, conf))),
        )
