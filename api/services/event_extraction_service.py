"""
Event Extraction Service for News Intelligence v5.0

Extracts discrete, structured events from articles with temporal grounding.
Each article may contain multiple events. Events are fingerprinted for
cross-source deduplication (Phase 2) and tagged with continuation signals
for story matching (Phase 3).

Integration Point: Stores events in `chronological_events` table for downstream processing
by Event Deduplication (Phase 4) and Story Continuation (Phase 5) phases.

Error Handling:
- LLM processing failures are logged and skipped
- Database connection issues trigger retry mechanisms
- Invalid event formats are logged and skipped

Monitoring:
- Events extracted per article
- LLM model usage tracking
- Processing time metrics
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any

from psycopg2.extras import Json

from shared.services.llm_service import LLMService, ModelType
from shared.services.ollama_model_caller import get_ollama_model_caller
from shared.services.ollama_model_policy import InvocationKind

from services.domain_synthesis_config import get_domain_synthesis_config
from services.temporal_parser import extract_temporal_expressions, resolve_date

logger = logging.getLogger(__name__)

VALID_DATE_PRECISIONS = frozenset({"exact", "week", "month", "quarter", "year", "unknown"})
_DATE_PRECISION_ALIASES = {"day": "exact", "term": "unknown", "daily": "exact"}


def _normalize_date_precision(raw: str | None) -> str:
    precision = (raw or "unknown").strip().lower()
    precision = _DATE_PRECISION_ALIASES.get(precision, precision)
    if precision not in VALID_DATE_PRECISIONS:
        return "unknown"
    return precision

VALID_EVENT_TYPES = {
    # Core (all domains)
    "legal_action",
    "policy_decision",
    "election",
    "conflict",
    "economic_event",
    "scientific_discovery",
    "natural_disaster",
    "public_statement",
    "investigation",
    "legislation",
    "court_ruling",
    "arrest",
    "protest",
    "agreement",
    "appointment",
    "resignation",
    "death",
    "meeting",
    "report_release",
    "other",
    # Finance
    "market_shift",
    "trade_policy",
    "supply_disruption",
    "commodity_price",
    "tariff_change",
    "sanctions",
    # Science-tech
    "clinical_trial",
    "patent_filing",
    "product_launch",
    "research_publication",
    "regulatory_approval",
    "industry_partnership",
}

EVENT_EXTRACTION_PROMPT = """You are an expert news analyst. Given the following news article, extract ALL discrete real-world events described.

For EACH event, return a JSON object with these fields:
- event_title: A concise title (max 15 words)
- event_type: one of [legal_action, policy_decision, election, conflict, economic_event, scientific_discovery, natural_disaster, public_statement, investigation, legislation, court_ruling, arrest, protest, agreement, appointment, resignation, death, meeting, report_release, market_shift, trade_policy, supply_disruption, commodity_price, tariff_change, sanctions, clinical_trial, patent_filing, product_launch, research_publication, regulatory_approval, industry_partnership, other]
- event_date: The actual date this event occurred (NOT the publication date). Use ISO format YYYY-MM-DD if exact. For relative dates like "yesterday" or "last Tuesday", write the relative phrase as-is.
- date_precision: one of [exact, week, month, quarter, year, unknown]
- location: Where it happened (city, state, country). Use "unknown" if not stated.
- key_actors: Array of objects with "name" and "role" fields for people and organizations involved.
- outcome: What was the result or current status (1-2 sentences).
- is_ongoing: true if this event is part of a continuing process (trial, investigation, negotiations), false otherwise.
- continuation_signals: Array of phrases from the article suggesting this connects to past events (e.g., "the latest in a series of", "following last month's ruling", "continued from", "as part of the ongoing").

Article publication date: {pub_date}

Article text:
{content}

Respond with ONLY a JSON array of event objects (preferred), or a single event object if there is exactly one event. If no discrete events are found, return an empty array [].
Do NOT include any text outside the JSON. Use valid JSON only (double quotes, no trailing commas)."""

# Batched prompt: extracts events from multiple articles in one LLM call
BATCH_EVENT_EXTRACTION_PROMPT = """You are an expert news analyst. Given {article_count} news articles below, extract ALL discrete real-world events from EACH article.

For EACH article, return a JSON object with the article_id as key and an array of events as value.

Event fields (per event):
- event_title: A concise title (max 15 words)
- event_type: one of [legal_action, policy_decision, election, conflict, economic_event, scientific_discovery, natural_disaster, public_statement, investigation, legislation, court_ruling, arrest, protest, agreement, appointment, resignation, death, meeting, report_release, market_shift, trade_policy, supply_disruption, commodity_price, tariff_change, sanctions, clinical_trial, patent_filing, product_launch, research_publication, regulatory_approval, industry_partnership, other]
- event_date: The actual date this event occurred (NOT the publication date). Use ISO format YYYY-MM-DD if exact. For relative dates like "yesterday" or "last Tuesday", write the relative phrase as-is.
- date_precision: one of [exact, week, month, quarter, year, unknown]
- location: Where it happened (city, state, country). Use "unknown" if not stated.
- key_actors: Array of objects with "name" and "role" fields for people and organizations involved.
- outcome: What was the result or current status (1-2 sentences).
- is_ongoing: true if this event is part of a continuing process (trial, investigation, negotiations), false otherwise.
- continuation_signals: Array of phrases from the article suggesting this connects to past events.

Output format example:
{{
  "12345": [
    {{"event_title": "Supreme Court ruling on EPA", "event_type": "court_ruling", "event_date": "2026-06-15", "date_precision": "exact", "location": "Washington DC", "key_actors": [{{"name": "Supreme Court", "role": "court"}}], "outcome": "Ruled against EPA overreach", "is_ongoing": false, "continuation_signals": []}}
  ],
  "12346": []
}}

Articles:
{articles}

Respond with ONLY a single JSON object mapping article_id to event arrays. If no discrete events are found for an article, return empty array [] for that article_id.
Do NOT include any text outside the JSON object. Use valid JSON only (double quotes, no trailing commas)."""

_JSON_RETRY_SUFFIX = (
    "\n\nYour previous answer was not valid JSON. "
    "Reply with ONLY a JSON array `[{...}, ...]` — no markdown, no commentary."
)


def _repair_json_array_text(text: str) -> str:
    """Best-effort fixes for common LLM JSON mistakes."""
    t = text.strip()
    t = re.sub(r",\s*]", "]", t)
    t = re.sub(r",\s*}", "}", t)
    return t


def _coerce_events_payload(parsed: Any) -> list[dict]:
    """Normalize LLM JSON (array, single event object, or wrapped list) to event dicts."""
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    if isinstance(parsed, dict):
        for k in ("events", "items", "data", "results"):
            v = parsed.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        # Single event object (common when the article yields one beat)
        if parsed.get("event_title") or parsed.get("title"):
            return [parsed]
    return []


def _raw_decode_json_value(text: str, start: int) -> Any | None:
    """Decode one JSON value starting at ``start`` (skips leading whitespace)."""
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(text, start)
        return value
    except json.JSONDecodeError:
        return None


def _extract_event_dicts_from_text(text: str) -> list[dict]:
    """Fallback: scan for JSON objects/arrays that look like event payloads."""
    out: list[dict] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch not in "{[":
            i += 1
            continue
        value = _raw_decode_json_value(text, i)
        if value is None:
            i += 1
            continue
        # Advance past the decoded value
        try:
            _, end = json.JSONDecoder().raw_decode(text, i)
            i = end
        except json.JSONDecodeError:
            i += 1
            continue
        for obj in _coerce_events_payload(value):
            if obj.get("event_title") or obj.get("title"):
                out.append(obj)
    return out

# Research-oriented silos (AI, medicine, climate): fewer “political” discrete beats; stress evidence.
RESEARCH_DOMAIN_EVENT_ADDENDUM = """
Research & technology domain addendum:
- Prefer event types: research_publication, scientific_discovery, clinical_trial, regulatory_approval,
  patent_filing, product_launch, industry_partnership, report_release, meeting, public_statement.
- Do NOT invent causal links or “breakthrough” narratives unless the article states them clearly.
- For continuation_signals, only use phrases explicitly tying this work to prior studies, trials,
  or product generations described in the text (not generic “could revolutionize” language).
- If the article only describes potential future applications, treat as ongoing research with cautious outcome wording.
"""


def _uses_research_event_addendum(domain: str | None) -> bool:
    if not domain:
        return False
    from shared.pipeline_domain_sql import normalize_legacy_domain_key

    k = normalize_legacy_domain_key(domain)
    return k in (
        "artificial-intelligence",
        "medicine",
        "environment-climate",
    )


def compute_event_fingerprint(
    event_type: str,
    key_actors: list[dict[str, str]],
    location: str,
    event_date: str | None,
) -> str:
    """
    Build a deterministic fingerprint from the normalised core fields
    so that the same real-world event reported by different sources
    produces the same hash.
    """
    actor_names = sorted(a.get("name", "").strip().lower() for a in (key_actors or []))
    parts = [
        (event_type or "").strip().lower(),
        "|".join(actor_names),
        (location or "unknown").strip().lower(),
        (event_date or "unknown").strip(),
    ]
    raw = "::".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def compute_temporal_status(resolved_date: date | None, pub_date: datetime | None) -> str:
    """
    occurred: event date is on or before the source article's publication calendar date.
    scheduled: event date is strictly after publication date (e.g. upcoming payment date).
    unknown: missing event date or publication date.
    """
    if resolved_date is None or pub_date is None:
        return "unknown"
    pub_d = pub_date.date() if isinstance(pub_date, datetime) else pub_date
    if resolved_date > pub_d:
        return "scheduled"
    return "occurred"


class EventExtractionService:
    """Extracts structured events from processed articles via LLM."""

    def __init__(self, llm_service: LLMService | None = None):
        self.llm = llm_service or LLMService()
        self._caller = get_ollama_model_caller()

    async def extract_events_from_article(
        self,
        article_id: int,
        content: str,
        pub_date: datetime,
        storyline_id: str | None = None,
        domain: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Send article text through the event-extraction prompt, parse the
        LLM response, resolve temporal expressions, compute fingerprints,
        and return a list of event dicts ready for DB insertion.
        """
        if not content or len(content.strip()) < 100:
            logger.warning(f"Article {article_id}: content too short for event extraction")
            return []

        prompt = EVENT_EXTRACTION_PROMPT.format(
            pub_date=pub_date.strftime("%Y-%m-%d"),
            content=content[:4000],
        )
        if domain:
            cfg = get_domain_synthesis_config(domain)
            if cfg.llm_context:
                prompt = f"Domain: {domain}\n{cfg.llm_context}\n\n{prompt}"
            if cfg.event_type_priorities:
                prompt += f"\n\nPrioritise these event types for this domain: {', '.join(cfg.event_type_priorities[:10])}"
            if _uses_research_event_addendum(domain):
                prompt += RESEARCH_DOMAIN_EVENT_ADDENDUM

        try:
            gen = await self._caller.generate(
                prompt,
                kind=InvocationKind.STRUCTURED_EXTRACTION,
                approx_prompt_chars=len(prompt),
            )
            raw_response = gen.text
            extraction_model = gen.model
            events_raw, parsed_ok = self._parse_json_response_detailed(raw_response)
            # Only retry a malformed answer; a valid empty answer means no events.
            if not events_raw and not parsed_ok:
                retry_prompt = prompt + _JSON_RETRY_SUFFIX
                gen2 = await self._caller.generate(
                    retry_prompt,
                    kind=InvocationKind.STRUCTURED_EXTRACTION,
                    approx_prompt_chars=len(retry_prompt),
                )
                raw_response = gen2.text
                extraction_model = gen2.model
                events_raw = self._parse_json_response(raw_response)
            logger.info(
                "event_extraction_parsed article_id=%s model=%s json_array_nonempty=%s",
                article_id,
                extraction_model,
                bool(events_raw),
            )
        except Exception as e:
            logger.error(f"Article {article_id}: LLM event extraction failed: {e}")
            return []

        if not events_raw:
            logger.info(f"Article {article_id}: no events extracted")
            return []

        events: list[dict[str, Any]] = []
        for idx, raw_evt in enumerate(events_raw):
            if not isinstance(raw_evt, dict):
                logger.debug("Article %s skip non-dict event %s", article_id, idx)
                continue
            try:
                evt = self._normalise_event(
                    raw_evt,
                    article_id,
                    pub_date,
                    storyline_id,
                    idx,
                    extraction_model=extraction_model,
                )
                if evt:
                    events.append(evt)
            except Exception as e:
                logger.warning(f"Article {article_id}, event {idx}: normalisation error: {e}")

        logger.info(f"Article {article_id}: extracted {len(events)} events")
        return events

    # === Batched extraction ===
    async def extract_events_batch(
        self,
        articles: list[dict[str, Any]],
        *,
        domain: str | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        """
        Extract events from multiple articles in a single LLM call.

        Args:
            articles: List of dicts with keys: article_id, content, pub_date, domain, storyline_id
            domain: Domain key (optional, for domain-specific prompt tuning)

        Returns:
            Dict mapping article_id -> list of event dicts
        """
        if not articles:
            return {}

        # Build batched prompt
        article_blocks = []
        valid_articles = 0
        for art in articles:
            aid = art["article_id"]
            content = art["content"] or ""
            pub = art["pub_date"]
            sid = art.get("storyline_id") or ""
            if not content or len(content.strip()) < 100:
                logger.warning(f"Article {aid}: content too short for event extraction")
                continue
            article_blocks.append(
                f"=== ARTICLE {aid} ===\n"
                f"Publication date: {pub.strftime('%Y-%m-%d')}\n"
                f"Storyline ID: {sid}\n"
                f"Content:\n{content[:3000]}"
            )
            valid_articles += 1

        if not article_blocks:
            return {}

        batched_prompt = BATCH_EVENT_EXTRACTION_PROMPT.format(
            article_count=len(article_blocks),
            articles="\n\n".join(article_blocks),
        )

        if domain:
            cfg = get_domain_synthesis_config(domain)
            if cfg.llm_context:
                batched_prompt = f"Domain: {domain}\n{cfg.llm_context}\n\n{batched_prompt}"
            if cfg.event_type_priorities:
                batched_prompt += f"\n\nPrioritise these event types: {', '.join(cfg.event_type_priorities[:10])}"

        try:
            gen = await self._caller.generate(
                batched_prompt,
                kind=InvocationKind.STRUCTURED_EXTRACTION,
                approx_prompt_chars=len(batched_prompt),
            )
            raw_response = gen.text
            extraction_model = gen.model
            events_by_article = self._parse_batch_json_response(raw_response)
            if not events_by_article:
                retry_prompt = batched_prompt + _JSON_RETRY_SUFFIX
                gen2 = await self._caller.generate(
                    retry_prompt,
                    kind=InvocationKind.STRUCTURED_EXTRACTION,
                    approx_prompt_chars=len(retry_prompt),
                )
                raw_response = gen2.text
                extraction_model = gen2.model
                events_by_article = self._parse_batch_json_response(raw_response)

            total_events = sum(len(v) for v in events_by_article.values())

            logger.info(
                "batch_event_extraction articles=%s model=%s events_found=%s",
                len(articles),
                extraction_model,
                total_events,
            )
        except Exception as e:
            logger.error(f"Batch event extraction failed: {e}")
            return {}

        # Normalise events per article
        result: dict[int, list[dict[str, Any]]] = {}
        total_normalized = 0
        for aid, events_raw in events_by_article.items():
            events: list[dict[str, Any]] = []
            for idx, raw_evt in enumerate(events_raw):
                if not isinstance(raw_evt, dict):
                    continue
                try:
                    # Find pub_date and storyline_id for this article_id
                    pub_date_for_article = next((a["pub_date"] for a in articles if a["article_id"] == aid), None)
                    storyline_id_for_article = next((a.get("storyline_id") for a in articles if a["article_id"] == aid), None)

                    evt = self._normalise_event(
                        raw_evt,
                        aid,
                        pub_date_for_article if pub_date_for_article else datetime.now(timezone.utc),
                        storyline_id_for_article,
                        idx,
                        extraction_model=extraction_model,
                    )
                    if evt:
                        events.append(evt)
                except Exception as e:
                    logger.warning(f"Article {aid}, event {idx}: normalisation error: {e}")
            if events:
                result[aid] = events
                total_normalized += len(events)
                logger.info(f"Article {aid}: extracted {len(events)} events (batch)")

        return result

    def _parse_batch_json_response(self, response: str) -> dict[int, list[dict]]:
        """Parse batched response: expects JSON object mapping article_id -> array of events."""
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        # Try object format first: {"123": [...], "456": [...]}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                result = {}
                for k, v in parsed.items():
                    try:
                        aid = int(k)
                        if isinstance(v, list):
                            result[aid] = [x for x in v if isinstance(x, dict)]
                    except ValueError:
                        pass
                if result:
                    return result
        except json.JSONDecodeError:
            pass

        # Fallback: try to find JSON object with regex
        import re
        obj_match = re.search(r"\{.*\}", text, re.DOTALL)
        if obj_match:
            try:
                parsed = json.loads(obj_match.group())
                if isinstance(parsed, dict):
                    result = {}
                    for k, v in parsed.items():
                        try:
                            aid = int(k)
                            if isinstance(v, list):
                                result[aid] = [x for x in v if isinstance(x, dict)]
                        except ValueError:
                            pass
                    if result:
                        return result
            except json.JSONDecodeError:
                pass

        logger.warning("No valid batched JSON object found in LLM response")
        return {}

    def _parse_json_response(self, response: str) -> list[dict]:
        events, _ = self._parse_json_response_detailed(response)
        return events

    def _parse_json_response_detailed(self, response: str) -> tuple[list[dict], bool]:
        """Extract event dicts from LLM JSON, reporting whether the payload parsed.

        Returns ``(events, parsed_ok)``. ``parsed_ok`` is True when the response was
        decodable JSON — including a well-formed empty answer such as ``{}`` or ``[]``.
        Callers use it to avoid a pointless retry: with Ollama ``format=json`` an empty
        object means "no events here", not "the model broke the format".

        Note: do **not** naively slice from the first ``[`` to the last ``]`` — a single
        event object contains nested arrays (e.g. ``key_actors``), and that heuristic
        grabs the wrong span.
        """
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
        if not text:
            return [], False

        repaired = _repair_json_array_text(text)

        # 1) Whole-payload decode (preferred)
        try:
            return _coerce_events_payload(json.loads(repaired)), True
        except json.JSONDecodeError:
            pass

        # 2) First complete JSON value (array or object) via raw_decode
        for opener in ("[", "{"):
            start = repaired.find(opener)
            if start == -1:
                continue
            value = _raw_decode_json_value(repaired, start)
            if value is None:
                continue
            coerced = _coerce_events_payload(value)
            if coerced:
                return coerced, True

        # 3) Scan for embedded event-shaped objects
        fallback = _extract_event_dicts_from_text(repaired)
        if fallback:
            logger.info("event_extraction: recovered %s events via object fallback", len(fallback))
            return fallback, True

        logger.warning("No JSON array found in LLM response")
        return [], False

    def _normalise_event(
        self,
        raw: dict,
        article_id: int,
        pub_date: datetime,
        storyline_id: str | None,
        sequence: int,
        *,
        extraction_model: str,
    ) -> dict[str, Any] | None:
        """Validate, resolve dates, compute fingerprint, return DB-ready dict."""
        if not isinstance(raw, dict):
            return None
        title = (raw.get("event_title") or raw.get("title") or "").strip()
        if not title:
            return None

        event_type = (raw.get("event_type") or "other").strip().lower()
        if event_type not in VALID_EVENT_TYPES:
            event_type = "other"

        raw_date = raw.get("event_date") or ""
        date_precision = _normalize_date_precision(raw.get("date_precision"))
        resolved_date, resolved_precision = resolve_date(str(raw_date), pub_date)

        if resolved_date is None and raw_date:
            temporal_hits = extract_temporal_expressions(raw_date)
            if temporal_hits:
                resolved_date, resolved_precision = resolve_date(temporal_hits[0], pub_date)

        if resolved_precision != "unknown":
            date_precision = _normalize_date_precision(resolved_precision)

        location = (raw.get("location") or "unknown").strip()
        key_actors = raw.get("key_actors") or []
        if isinstance(key_actors, list):
            key_actors = [
                a if isinstance(a, dict) else {"name": str(a), "role": "unknown"}
                for a in key_actors
            ]
        else:
            key_actors = []

        outcome = (raw.get("outcome") or "").strip()
        is_ongoing = bool(raw.get("is_ongoing", False))
        continuation_signals = raw.get("continuation_signals") or []
        if not isinstance(continuation_signals, list):
            continuation_signals = [str(continuation_signals)]

        fingerprint = compute_event_fingerprint(
            event_type,
            key_actors,
            location,
            resolved_date.isoformat() if resolved_date else None,
        )

        temporal_status = compute_temporal_status(resolved_date, pub_date)

        return {
            "event_id": str(uuid.uuid4()),
            "storyline_id": storyline_id or "",
            "title": title,
            "description": outcome,
            "event_type": event_type,
            "actual_event_date": resolved_date,
            "relative_temporal_expression": str(raw_date) if raw_date else None,
            "temporal_confidence": 0.9 if date_precision == "exact" else 0.5,
            "source_article_id": article_id,
            "extraction_method": "ml",
            "extraction_model": extraction_model or ModelType.LLAMA_8B.value,
            "extraction_confidence": 0.8,
            "importance_score": 0.5,
            "location": location,
            "entities": Json(key_actors),
            "event_fingerprint": fingerprint,
            "source_count": 1,
            "key_actors": Json(key_actors),
            "outcome": outcome,
            "is_ongoing": is_ongoing,
            "continuation_signals": Json(continuation_signals),
            "date_precision": date_precision,
            "event_sequence_position": sequence,
            "temporal_status": temporal_status,
            # Dual timestamps: world time vs source publication vs ingest
            "event_date": (
                datetime.combine(resolved_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                if resolved_date is not None
                else None
            ),
            "ingestion_date": datetime.now(timezone.utc),
            "vintage_date": pub_date if isinstance(pub_date, datetime) else None,
        }

    async def save_events(
        self,
        events: list[dict[str, Any]],
        conn,
        *,
        commit: bool = True,
    ) -> int:
        """Persist extracted events into the chronological_events table."""
        if not events:
            return 0

        from shared.pg_savepoint import (
            execute_with_savepoint,
            rollback_transaction,
            transaction_in_error,
        )

        if transaction_in_error(conn):
            rollback_transaction(conn)

        cursor = conn.cursor()
        saved = 0
        for idx, evt in enumerate(events):
            evt["date_precision"] = _normalize_date_precision(evt.get("date_precision"))
            row = dict(evt)
            for json_key in ("entities", "key_actors", "continuation_signals"):
                val = row.get(json_key)
                if isinstance(val, str):
                    try:
                        row[json_key] = Json(json.loads(val))
                    except json.JSONDecodeError:
                        row[json_key] = Json([])
                elif isinstance(val, (list, dict)):
                    row[json_key] = Json(val)
            ok = execute_with_savepoint(
                cursor,
                conn,
                f"evt_save_{idx}",
                """
                    INSERT INTO public.chronological_events (
                        event_id, storyline_id, title, description, event_type,
                        actual_event_date, relative_temporal_expression,
                        temporal_confidence, source_article_id, extraction_method,
                        extraction_model, extraction_confidence, importance_score,
                        location, entities, event_fingerprint, source_count,
                        key_actors, outcome, is_ongoing, continuation_signals,
                        date_precision, event_sequence_position, temporal_status,
                        event_date, ingestion_date, vintage_date
                    ) VALUES (
                        %(event_id)s, %(storyline_id)s, %(title)s, %(description)s,
                        %(event_type)s, %(actual_event_date)s,
                        %(relative_temporal_expression)s, %(temporal_confidence)s,
                        %(source_article_id)s, %(extraction_method)s,
                        %(extraction_model)s, %(extraction_confidence)s,
                        %(importance_score)s, %(location)s, %(entities)s,
                        %(event_fingerprint)s, %(source_count)s,
                        %(key_actors)s, %(outcome)s, %(is_ongoing)s,
                        %(continuation_signals)s, %(date_precision)s,
                        %(event_sequence_position)s, %(temporal_status)s,
                        %(event_date)s, %(ingestion_date)s, %(vintage_date)s
                    )
                    ON CONFLICT (event_fingerprint, source_article_id) DO NOTHING
                """,
                row,
            )
            if ok:
                saved += 1
            else:
                logger.error(
                    "Failed to save event %r (article_id=%s)",
                    evt.get("title"),
                    evt.get("source_article_id"),
                )

        if commit:
            conn.commit()
        cursor.close()
        logger.info("Saved %s/%s events to database", saved, len(events))
        return saved

    async def close(self):
        await self.llm.close()
