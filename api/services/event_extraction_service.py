"""
Event Extraction Service for News Intelligence v5.0

Extracts discrete, structured events from articles with temporal grounding.
Each article may contain multiple events. Events are fingerprinted for
cross-source deduplication (Phase 2) and tagged with continuation signals
for story matching (Phase 3).
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.temporal_parser import extract_temporal_expressions, resolve_date
from shared.services.llm_service import LLMService, ModelType
from services.domain_synthesis_config import get_domain_synthesis_config

logger = logging.getLogger(__name__)

VALID_EVENT_TYPES = {
    # Core (all domains)
    'legal_action', 'policy_decision', 'election', 'conflict',
    'economic_event', 'scientific_discovery', 'natural_disaster',
    'public_statement', 'investigation', 'legislation', 'court_ruling',
    'arrest', 'protest', 'agreement', 'appointment', 'resignation',
    'death', 'meeting', 'report_release', 'other',
    # Finance
    'market_shift', 'trade_policy', 'supply_disruption',
    'commodity_price', 'tariff_change', 'sanctions',
    # Science-tech
    'clinical_trial', 'patent_filing', 'product_launch',
    'research_publication', 'regulatory_approval', 'industry_partnership',
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

Respond with ONLY a JSON array of event objects. If no discrete events are found, return an empty array [].
Do NOT include any text outside the JSON array."""

# Science-tech: fewer “political” discrete beats; stress evidence and avoid invented links.
SCIENCE_TECH_EVENT_ADDENDUM = """
Science & technology domain addendum:
- Prefer event types: research_publication, scientific_discovery, clinical_trial, regulatory_approval,
  patent_filing, product_launch, industry_partnership, report_release, meeting, public_statement.
- Do NOT invent causal links or “breakthrough” narratives unless the article states them clearly.
- For continuation_signals, only use phrases explicitly tying this work to prior studies, trials,
  or product generations described in the text (not generic “could revolutionize” language).
- If the article only describes potential future applications, treat as ongoing research with cautious outcome wording.
"""


def _is_science_tech_domain(domain: Optional[str]) -> bool:
    if not domain:
        return False
    k = domain.lower().strip().replace("_", "-")
    return k in ("science-tech", "sciencetech", "science tech")


def compute_event_fingerprint(
    event_type: str,
    key_actors: List[Dict[str, str]],
    location: str,
    event_date: Optional[str],
) -> str:
    """
    Build a deterministic fingerprint from the normalised core fields
    so that the same real-world event reported by different sources
    produces the same hash.
    """
    actor_names = sorted(
        a.get('name', '').strip().lower() for a in (key_actors or [])
    )
    parts = [
        (event_type or '').strip().lower(),
        '|'.join(actor_names),
        (location or 'unknown').strip().lower(),
        (event_date or 'unknown').strip(),
    ]
    raw = '::'.join(parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:64]


class EventExtractionService:
    """Extracts structured events from processed articles via LLM."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm = llm_service or LLMService()

    async def extract_events_from_article(
        self,
        article_id: int,
        content: str,
        pub_date: datetime,
        storyline_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Send article text through the event-extraction prompt, parse the
        LLM response, resolve temporal expressions, compute fingerprints,
        and return a list of event dicts ready for DB insertion.
        """
        if not content or len(content.strip()) < 100:
            logger.warning(f"Article {article_id}: content too short for event extraction")
            return []

        prompt = EVENT_EXTRACTION_PROMPT.format(
            pub_date=pub_date.strftime('%Y-%m-%d'),
            content=content[:4000],
        )
        if domain:
            cfg = get_domain_synthesis_config(domain)
            if cfg.llm_context:
                prompt = f"Domain: {domain}\n{cfg.llm_context}\n\n{prompt}"
            if cfg.event_type_priorities:
                prompt += f"\n\nPrioritise these event types for this domain: {', '.join(cfg.event_type_priorities[:10])}"
            if _is_science_tech_domain(domain):
                prompt += SCIENCE_TECH_EVENT_ADDENDUM

        try:
            raw_response = await self.llm._call_ollama(ModelType.LLAMA_8B, prompt)
            events_raw = self._parse_json_response(raw_response)
        except Exception as e:
            logger.error(f"Article {article_id}: LLM event extraction failed: {e}")
            return []

        if not events_raw:
            logger.info(f"Article {article_id}: no events extracted")
            return []

        events: List[Dict[str, Any]] = []
        for idx, raw_evt in enumerate(events_raw):
            try:
                evt = self._normalise_event(raw_evt, article_id, pub_date, storyline_id, idx)
                if evt:
                    events.append(evt)
            except Exception as e:
                logger.warning(f"Article {article_id}, event {idx}: normalisation error: {e}")

        logger.info(f"Article {article_id}: extracted {len(events)} events")
        return events

    def _parse_json_response(self, response: str) -> List[Dict]:
        """Extract a JSON array from the LLM response, tolerating markdown fences."""
        text = response.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[-1]
        if text.endswith('```'):
            text = text.rsplit('```', 1)[0]
        text = text.strip()

        start = text.find('[')
        end = text.rfind(']')
        if start == -1 or end == -1:
            logger.warning("No JSON array found in LLM response")
            return []

        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return []

    def _normalise_event(
        self,
        raw: Dict,
        article_id: int,
        pub_date: datetime,
        storyline_id: Optional[str],
        sequence: int,
    ) -> Optional[Dict[str, Any]]:
        """Validate, resolve dates, compute fingerprint, return DB-ready dict."""
        title = (raw.get('event_title') or '').strip()
        if not title:
            return None

        event_type = (raw.get('event_type') or 'other').strip().lower()
        if event_type not in VALID_EVENT_TYPES:
            event_type = 'other'

        raw_date = raw.get('event_date') or ''
        date_precision = (raw.get('date_precision') or 'unknown').strip().lower()
        resolved_date, resolved_precision = resolve_date(str(raw_date), pub_date)

        if resolved_date is None and raw_date:
            temporal_hits = extract_temporal_expressions(raw_date)
            if temporal_hits:
                resolved_date, resolved_precision = resolve_date(temporal_hits[0], pub_date)

        if resolved_precision != 'unknown':
            date_precision = resolved_precision

        location = (raw.get('location') or 'unknown').strip()
        key_actors = raw.get('key_actors') or []
        if isinstance(key_actors, list):
            key_actors = [
                a if isinstance(a, dict) else {'name': str(a), 'role': 'unknown'}
                for a in key_actors
            ]
        else:
            key_actors = []

        outcome = (raw.get('outcome') or '').strip()
        is_ongoing = bool(raw.get('is_ongoing', False))
        continuation_signals = raw.get('continuation_signals') or []
        if not isinstance(continuation_signals, list):
            continuation_signals = [str(continuation_signals)]

        fingerprint = compute_event_fingerprint(
            event_type, key_actors, location,
            resolved_date.isoformat() if resolved_date else None,
        )

        return {
            'event_id': str(uuid.uuid4()),
            'storyline_id': storyline_id or '',
            'title': title,
            'description': outcome,
            'event_type': event_type,
            'actual_event_date': resolved_date,
            'relative_temporal_expression': str(raw_date) if raw_date else None,
            'temporal_confidence': 0.9 if date_precision == 'exact' else 0.5,
            'source_article_id': article_id,
            'extraction_method': 'ml',
            'extraction_model': ModelType.LLAMA_8B.value,
            'extraction_confidence': 0.8,
            'importance_score': 0.5,
            'location': location,
            'entities': json.dumps(key_actors),
            'event_fingerprint': fingerprint,
            'source_count': 1,
            'key_actors': json.dumps(key_actors),
            'outcome': outcome,
            'is_ongoing': is_ongoing,
            'continuation_signals': json.dumps(continuation_signals),
            'date_precision': date_precision,
            'event_sequence_position': sequence,
        }

    async def save_events(self, events: List[Dict[str, Any]], conn) -> int:
        """Persist extracted events into the chronological_events table."""
        if not events:
            return 0

        cursor = conn.cursor()
        saved = 0
        for evt in events:
            try:
                cursor.execute("""
                    INSERT INTO public.chronological_events (
                        event_id, storyline_id, title, description, event_type,
                        actual_event_date, relative_temporal_expression,
                        temporal_confidence, source_article_id, extraction_method,
                        extraction_model, extraction_confidence, importance_score,
                        location, entities, event_fingerprint, source_count,
                        key_actors, outcome, is_ongoing, continuation_signals,
                        date_precision, event_sequence_position
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
                        %(event_sequence_position)s
                    )
                    ON CONFLICT (event_id) DO NOTHING
                """, evt)
                saved += 1
            except Exception as e:
                # Do not rollback the whole batch — other events in this article can still persist
                logger.error(f"Failed to save event '{evt.get('title')}': {e}")

        conn.commit()
        cursor.close()
        logger.info(f"Saved {saved}/{len(events)} events to database")
        return saved

    async def close(self):
        await self.llm.close()
