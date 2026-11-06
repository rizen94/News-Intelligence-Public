"""CollectionExecutor — handles data collection pipeline phases.

Responsible for: rss_processing, document_collection, research_paper_profiling,
document_processing, claim_evidence_appraisal.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CollectionExecutor:
    """Execute collection-related pipeline phases."""

    def __init__(self, task: Any) -> None:
        self._task = task
        self._params = task.parameters or {}
        self._infra = {}

    @classmethod
    def create(cls, task: Any) -> "CollectionExecutor":
        return cls(task)

    # -- public entry point --------------------------------------------------

    async def run(self) -> None:
        """Dispatch to the correct collection phase based on ``task.name``."""
        name = self._task.name
        handlers = {
            "rss_processing": self._execute_rss_processing,
            "content_enrichment": self._execute_content_enrichment,
            "research_paper_profiling": self._execute_research_paper_profiling,
            "document_collection": self._execute_document_collection,
            "document_processing": self._execute_document_processing,
            "claim_evidence_appraisal": self._execute_claim_evidence_appraisal,
        }
        handler = handlers.get(name)
        if handler is None:
            raise ValueError(f"Unsupported collection phase: {name}")
        await handler()

    # -- helpers -------------------------------------------------------------

    @property
    def task(self) -> Any:
        return self._task

    @property
    def params(self) -> dict[str, Any]:
        return self._params

    def _get_phase(self) -> str:
        """Return the active enrichment/research phase name."""
        phase = self._params.get("phase")
        if phase:
            return phase
        task_name = self._task.name
        if task_name == "content_enrichment":
            return "enrichment"
        if task_name == "research_paper_profiling":
            return "research_profiling"
        return "collection"

    # -- phases --------------------------------------------------------------

    async def _execute_rss_processing(self) -> None:
        """Process RSS article data or synchronize feeds."""
        task_name = self._task.name
        feed_url = self._params.get("feed_url", "")

        if task_name == "rss_processing":
            await self._fetch_rss_articles(feed_url)
        else:
            # feed_sync — sync feed metadata/status into the DB
            await self._sync_feeds_to_pg(feed_url)

    async def _execute_content_enrichment(self) -> None:
        """Enrich items across configured enrichment cycles."""
        from services.domain_feed_service import get_domain_config
        api.shared.pipeline_batch_drain import phase_run_budget_seconds

        domain = self._params.get("domain", "finance")
        config = get_domain_config(domain)
        enrichment_cycles = config.get("enrichment_cycles", [])
        item_limit = config.get("enrichment_item_limit", 100)

        # Gather items across all cycles, dedup by URL
        items: list[dict] = []
        seen_urls: set[str] = set()
        for cycle in enrichment_cycles:
            subtypes = cycle.get("subtypes", []) or []
            for item in (cycle.get("items") or []):
                url = str(item.get("url", "")).strip().lower()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    items.append(item)

        # Process each item with budget tracking
        step_time_budget = phase_run_budget_seconds(
            f"{domain}_enrichment",
        )
        remaining_budget = step_time_budget - 15  # reserve buffer

        for item in items:
            if remaining_budget <= 0:
                logger.info("Content enrichment budget exhausted (%s)", domain)
                break

            url = str(item.get("url", ""))
            cycle_copy = {**cycle} if isinstance(cycle, dict) else dict(cycle)
            cycle_params = {
                **self._params,
                "enrichment_item_limit": min(
                    item_limit, item.get("item_limit", item_limit),
                ),
                "current_cycle": cycle_copy,
            }

            try:
                await self._run_enrichment_step(
                    url=url,
                    params=cycle_params,
                    budget=remaining_budget,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Enrichment cycle failed for %s: %s", url, exc)
                continue

            remaining_budget -= 5

    async def _execute_research_paper_profiling(self) -> None:
        """Profile research papers in science_tech / finance domains."""
        from services.domain_feed_service import get_domain_config
        api.shared.pipeline_batch_drain import phase_run_budget_seconds

        domain = self._params.get("domain", "science_tech")
        config = get_domain_config(domain)
        phases = config.get("analysis_phases", [])
        time_budgets = config.get("step_time_budgets", {})

        profile_cycles = [
            p for p in phases if isinstance(p, dict) and p.get("type") == "research_paper_profiling"
        ]
        step_time_budget = phase_run_budget_seconds(
            f"{domain}_research_profiling",
            time_budgets.get(f"{domain}_research_profiling"),
        )

        # Gather items from enrichment cycles
        cycles = config.get("enrichment_cycles", [])
        items: list[dict] = []
        seen_urls: set[str] = set()
        for cycle in cycles:
            if isinstance(cycle, dict) and cycle.get("items"):
                for item in cycle["items"]:
                    url = str(item.get("url", "")).strip().lower()
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        items.append(item)

        remaining_budget = step_time_budget - 30  # reserve overhead
        processed = 0

        for item in items:
            url = str(item.get("url", "")).strip()
            if not url:
                continue

            try:
                await self._run_enrichment_step(
                    url=url,
                    params={**self._params, "enrichment_item_limit": 1},
                    budget=remaining_budget,
                )
                processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Research profiling failed for %s: %s", url, exc)
                continue

            remaining_budget -= 15
            if remaining_budget <= 0:
                break

        logger.info(
            "Research profiling complete: %d papers (%.1fs remaining)",
            processed, remaining_budget,
        )

    async def _execute_document_collection(self) -> None:
        """Collect documents from configured sources."""
        task_name = self._task.name
        doc_type = self._params.get("doc_type", "gov_pdf")
        domain = self._params.get("domain", "finance")

        logger.info("Document collection: type=%s domain=%s", doc_type, domain)

        if doc_type == "gov_pdf" or task_name == "gov_pdf_fetcher":
            uri = self._params.get("uri", "")
            await self._fetch_gov_pdfs(uri)
        elif doc_type == "academic_pdf" or task_name == "academic_pdf_fetcher":
            url = self._params.get("url", "")
            await self._fetch_academic_pdfs(url)

    async def _execute_document_processing(self) -> None:
        """Process collected documents."""
        doc_type = self._params.get("doc_type", "gov_pdf")
        domain = self._params.get("domain", "finance")

        logger.info("Document processing: type=%s domain=%s", doc_type, domain)

        if doc_type == "gov_pdf" or doc_type == "pdf":
            uri = self._params.get("uri", "")
            await self._extract_pdf_content(uri)
        elif doc_type == "text_sections":
            text_uri = self._params.get("url", "")
            await self._extract_text_sections(text_uri, domain)

    async def _execute_claim_evidence_appraisal(self) -> None:
        """Appraise evidence for claims."""
        domain = self._params.get("domain", "finance")
        logger.info("Claim evidence appraisal: domain=%s", domain)
        await self._run_evidence_appraisal(domain)

    # -- private helpers (call actual services) ------------------------------

    async def _fetch_rss_articles(self, feed_url: str) -> None:
        """Fetch/update RSS articles via the domain service."""
        from services.rss_processor import run_rss_articles
        logger.info("rss_processing for %s", feed_url)
        try:
            await run_rss_articles(feed_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rss_processing failed for %s: %s", feed_url, exc)
            raise

    async def _sync_feeds_to_pg(self, feed_url: str) -> None:
        """Sync feed metadata/status into the DB."""
        from services.rss_processor import sync_feeds_to_pg
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, lambda: sync_feeds_to_pg(feed_url))
            logger.info("feed_sync %s → %s", feed_url, result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("feed_sync %s failed: %s", feed_url, exc)
            raise

    async def _run_enrichment_step(
        self,
        url: str,
        params: dict[str, Any],
        budget: float,
    ) -> None:
        """Run a single enrichment cycle step."""
        api.shared.enrichment.pipelines import enrichment_cycle
        task_phase = self._get_phase()

        try:
            await enrichment_cycle(
                url=url,
                params=params,
                phase=task_phase,
                budget=budget,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Enrichment step failed for %s (%s): %s", url, task_phase, exc)
            raise

    async def _fetch_gov_pdfs(self, uri: str) -> None:
        """Fetch government PDFs."""
        from services.gov_pdf_scanner import fetch_gov_pdfs_for_domain
        domain = self._params.get("domain", "finance")
        logger.info("Fetching gov PDFs: domain=%s uri=%s", domain, uri)
        try:
            await fetch_gov_pdfs_for_domain(uri)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gov PDF fetch failed: %s", exc)
            raise

    async def _fetch_academic_pdfs(self, url: str) -> None:
        """Fetch academic PDFs."""
        from services.academic_pdf_fetcher import fetch_academic_pdfs_for_domain
        domain = self._params.get("domain", "finance")
        logger.info("Fetching academic PDFs: domain=%s url=%s", domain, url)
        try:
            await fetch_academic_pdfs_for_domain(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Academic PDF fetch failed: %s", exc)
            raise

    async def _extract_pdf_content(self, uri: str) -> None:
        """Extract text content from a PDF."""
        from services.pdf_content_extractor import extract_pdf_content
        domain = self._params.get("domain", "finance")
        logger.info("Extracting PDF content: uri=%s", uri)
        try:
            await extract_pdf_content(uri, domain=domain)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF content extraction failed: %s", exc)
            raise

    async def _extract_text_sections(self, url: str, domain: str) -> None:
        """Extract text sections from a document."""
        from services.text_section_extractor import extract_text_sections
        logger.info("Extracting text sections: domain=%s", domain)
        try:
            await extract_text_sections(url, domain=domain)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Text section extraction failed: %s", exc)
            raise

    async def _run_evidence_appraisal(self, domain: str) -> None:
        """Run evidence appraisal for a domain."""
        from services.claim_evidence_service import appraise_claim_evidence_pairs
        try:
            await appraise_claim_evidence_pairs(domain)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Evidence appraisal failed for %s: %s", domain, exc)
            raise
