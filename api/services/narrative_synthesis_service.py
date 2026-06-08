"""
Narrative Synthesis Service for News Intelligence v5.0 (Phase 4)

Generates journalist-quality chronological narratives from a storyline's
event timeline. Two modes:

  - Chronological narrative: full timeline walkthrough
  - Executive briefing: concise summary of the latest developments
"""

import logging
from datetime import datetime, timezone
from typing import Any

from shared.services.llm_service import LLMService, ModelType

logger = logging.getLogger(__name__)

CHRONOLOGICAL_PROMPT = """You are a senior journalist writing a comprehensive timeline article about: "{title}"

Here are the verified events in chronological order:
{events_block}

Source count across events: {source_count}

Write a journalistic narrative that:
1. Starts with the most recent development as a lede
2. Then walks through the full chronology from the beginning
3. Explains the significance of each major event
4. Notes when multiple sources corroborated key facts
5. Identifies unanswered questions or upcoming expected developments
6. Maintains a neutral, factual tone

Format: Use clear date markers and section breaks for major phases of the story.
Keep the article between 500-1500 words depending on the number of events."""

BRIEFING_PROMPT = """You are an intelligence analyst writing a concise briefing about: "{title}"

Latest event: {latest_event}
Total events in this story: {event_count}
Time span: {time_span}

Recent events (last 5):
{recent_events}

Key entities: {entities}

Write a 200-300 word executive briefing that:
1. Summarises the current situation
2. Highlights the most important recent development
3. Notes any pending or expected follow-up events
4. Assesses the story's trajectory (escalating, de-escalating, stalled)

Use a professional, concise tone."""


class NarrativeSynthesisService:
    """Generates narrative text from structured timeline data."""

    def __init__(self, llm: LLMService | None = None):
        self.llm = llm or LLMService()

    async def generate_chronological_narrative(
        self,
        timeline: dict[str, Any],
        *,
        historical_context_rendered: str = "",
        context_bundle: dict[str, Any] | None = None,
        storyline_id: int | None = None,
        domain_key: str | None = None,
        retrieval_query: str | None = None,
    ) -> dict[str, Any]:
        """
        Produce a long-form chronological narrative from a timeline dict
        (as returned by TimelineBuilderService.build_timeline).
        """
        events = timeline.get("events", [])
        if not events:
            return {"success": False, "error": "No events in timeline"}

        events_block = self._format_events_block(events, timeline.get("gaps", []))

        context_block = await self._resolve_context_block(
            timeline=timeline,
            historical_context_rendered=historical_context_rendered,
            context_bundle=context_bundle,
            storyline_id=storyline_id,
            domain_key=domain_key,
            retrieval_query=retrieval_query,
            max_chars=8000,
        )
        hist_block = ""
        if context_block:
            hist_block = (
                "\n\nEstablished facts and long-horizon context (use for arc, not only recent events):\n"
                + context_block
            )
        prompt = CHRONOLOGICAL_PROMPT.format(
            title=self._storyline_title(timeline),
            events_block=events_block,
            source_count=timeline.get("source_count", 0),
        ) + hist_block

        try:
            raw = await self.llm._call_ollama(ModelType.LLAMA_8B, prompt)
            return {
                "success": True,
                "narrative": raw.strip(),
                "mode": "chronological",
                "event_count": len(events),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Narrative generation failed: {e}")
            return {"success": False, "error": str(e)}

    async def generate_briefing(
        self,
        timeline: dict[str, Any],
        *,
        historical_context_rendered: str = "",
        context_bundle: dict[str, Any] | None = None,
        storyline_id: int | None = None,
        domain_key: str | None = None,
        retrieval_query: str | None = None,
    ) -> dict[str, Any]:
        """Produce a short executive briefing from timeline data."""
        events = timeline.get("events", [])
        if not events:
            return {"success": False, "error": "No events in timeline"}

        recent = events[-5:] if len(events) > 5 else events
        latest = events[-1]
        all_entities = set()
        for e in events:
            for a in e.get("key_actors") or []:
                name = a.get("name", "") if isinstance(a, dict) else str(a)
                if name:
                    all_entities.add(name)

        span = timeline.get("time_span")
        span_str = f"{span['start']} to {span['end']} ({span['days']} days)" if span else "unknown"

        prompt = BRIEFING_PROMPT.format(
            title=self._storyline_title(timeline),
            latest_event=f"{latest['title']} ({latest.get('event_date') or 'date unknown'})",
            event_count=len(events),
            time_span=span_str,
            recent_events="\n".join(
                f"- [{e.get('event_date') or '?'}] {e['title']}" for e in recent
            ),
            entities=", ".join(sorted(all_entities)[:15]),
        )
        context_block = await self._resolve_context_block(
            timeline=timeline,
            historical_context_rendered=historical_context_rendered,
            context_bundle=context_bundle,
            storyline_id=storyline_id,
            domain_key=domain_key,
            retrieval_query=retrieval_query or self._storyline_title(timeline),
            max_chars=4000,
        )
        if context_block:
            prompt += "\n\nLong-horizon context:\n" + context_block

        try:
            raw = await self.llm._call_ollama(ModelType.LLAMA_8B, prompt)
            return {
                "success": True,
                "briefing": raw.strip(),
                "mode": "briefing",
                "event_count": len(events),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Briefing generation failed: {e}")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    async def _resolve_context_block(
        self,
        *,
        timeline: dict[str, Any],
        historical_context_rendered: str,
        context_bundle: dict[str, Any] | None,
        storyline_id: int | None,
        domain_key: str | None,
        retrieval_query: str | None,
        max_chars: int,
    ) -> str:
        if context_bundle and context_bundle.get("rendered_for_prompt"):
            return str(context_bundle["rendered_for_prompt"]).strip()[:max_chars]

        sid = storyline_id or timeline.get("storyline_id")
        dk = domain_key or timeline.get("domain_key")
        query = (retrieval_query or self._storyline_title(timeline) or "").strip()
        if sid and dk and query:
            try:
                from services.context_bundle_service import ContextBundleService

                bundle = await ContextBundleService().build_context_bundle(
                    storyline_id=int(sid),
                    domain_key=dk,
                    query=query,
                )
                if bundle.get("rendered_for_prompt"):
                    return str(bundle["rendered_for_prompt"]).strip()[:max_chars]
            except Exception as e:
                logger.debug("context_bundle build skipped: %s", e)

        if historical_context_rendered and historical_context_rendered.strip():
            return historical_context_rendered.strip()[:max_chars]
        return ""

    @staticmethod
    def _format_events_block(events: list[dict], gaps: list[dict]) -> str:
        gap_map = {g["after_event_id"]: g for g in gaps}
        lines = []
        for evt in events:
            date_str = str(evt.get("event_date") or "date unknown")
            prec = evt.get("date_precision", "")
            if prec and prec != "exact":
                date_str += f" (approx: {prec})"
            sources = ""
            if evt.get("source_count", 1) > 1:
                sources = f" [{evt['source_count']} sources]"
            source_info = ""
            if evt.get("source", {}).get("domain"):
                source_info = f" (via {evt['source']['domain']})"

            lines.append(
                f"[{date_str}] {evt['title']}{sources}{source_info}\n"
                f"  {evt.get('description') or evt.get('outcome') or ''}"
            )
            if evt.get("is_ongoing"):
                lines.append("  (ongoing)")

            gap = gap_map.get(evt["id"])
            if gap:
                lines.append(f"\n  --- {gap['gap_days']}-day gap ---\n")

        return "\n\n".join(lines)

    @staticmethod
    def _storyline_title(timeline: dict) -> str:
        if timeline.get("events"):
            first = timeline["events"][0]
            return first.get("title", "Untitled Storyline")
        return "Untitled Storyline"

    async def close(self):
        await self.llm.close()
