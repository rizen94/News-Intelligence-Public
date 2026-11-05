"""NlpPipelineExecutor — handles NLP pipeline phases.

Responsible for: entity_extraction, headline_analysis, sentiment_analysis,
text_summarization (future).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class NlpPipelineExecutor:
    """Execute NLP pipeline phases."""

    def __init__(self, task: Any) -> None:
        self._task = task
        self._params = task.parameters or {}
        # Lazy service cache
        self._enrichment_cycle: Any = None

    @classmethod
    def create(cls, task: Any) -> "NlpPipelineExecutor":
        return cls(task)

    # -- public entry point --------------------------------------------------

    async def run(self) -> None:
        """Dispatch to the correct NLP phase based on ``task.name``."""
        name = self._task.name
        handlers = {
            "entity_extraction": self._execute_entity_extraction,
            "headline_analysis": self._execute_headline_analysis,
            "sentiment_analysis": self._execute_sentiment_analysis,
            "text_summarization": self._execute_text_summarization,
        }
        handler = handlers.get(name)
        if handler is None:
            raise ValueError(f"Unsupported NLP phase: {name}")
        await handler()

    # -- helpers -------------------------------------------------------------

    @property
    def task(self) -> Any:
        return self._task

    @property
    def params(self) -> dict[str, Any]:
        return self._params

    # -- phases --------------------------------------------------------------

    async def _execute_entity_extraction(self) -> None:
        """Extract entities from content."""
        url = self._params.get("url", "")
        domain = self._params.get("domain", "finance")
        logger.info("Entity extraction: domain=%s url=%s", domain, url)

        if not url:
            logger.warning("Entity extraction: no URL provided")
            return

        await self._run_enrichment_step(
            url=url,
            phase="entity_extraction",
            params=self._params,
            budget=300.0,  # 5 min default
        )

    async def _execute_headline_analysis(self) -> None:
        """Analyze headlines for sentiment/sigificance."""
        url = self._params.get("url", "")
        domain = self._params.get("domain", "finance")
        logger.info("Headline analysis: domain=%s url=%s", domain, url)

        if not url:
            logger.warning("Headline analysis: no URL provided")
            return

        await self._run_enrichment_step(
            url=url,
            phase="headline_analysis",
            params=self._params,
            budget=120.0,  # 2 min default
        )

    async def _execute_sentiment_analysis(self) -> None:
        """Perform sentiment analysis on content."""
        url = self._params.get("url", "")
        domain = self._params.get("domain", "finance")
        logger.info("Sentiment analysis: domain=%s url=%s", domain, url)

        if not url:
            logger.warning("Sentiment analysis: no URL provided")
            return

        await self._run_enrichment_step(
            url=url,
            phase="sentiment_analysis",
            params=self._params,
            budget=120.0,  # 2 min default
        )

    async def _execute_text_summarization(self) -> None:
        """Summarize content (future phase)."""
        url = self._params.get("url", "")
        domain = self._params.get("domain", "finance")
        logger.info("Text summarization: domain=%s url=%s", domain, url)

        if not url:
            logger.warning("Text summarization: no URL provided")
            return

        await self._run_enrichment_step(
            url=url,
            phase="text_summarization",
            params=self._params,
            budget=180.0,  # 3 min default
        )

    # -- private helpers -----------------------------------------------------

    async def _run_enrichment_step(
        self,
        url: str,
        phase: str,
        params: dict[str, Any],
        budget: float,
    ) -> None:
        """Run a single enrichment cycle step for NLP phases."""
        try:
            from shared.enrichment.pipelines import enrichment_cycle
        except ImportError as exc:
            logger.error("Missing enrichment_cycle dependency: %s", exc)
            raise

        try:
            await enrichment_cycle(
                url=url,
                phase=phase,
                params=params,
                budget=budget,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Enrichment step failed for %s (%s): %s", url, phase, exc)
            raise
