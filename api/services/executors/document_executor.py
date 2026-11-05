"""DocumentExecutor — handles document operations.

Responsible for: pdf_fetching, pdf_processing.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DocumentExecutor:
    """Execute document-related pipeline phases."""

    def __init__(self, task: Any) -> None:
        self._task = task
        self._params = task.parameters or {}

    @classmethod
    def create(cls, task: Any) -> "DocumentExecutor":
        return cls(task)

    # -- public entry point --------------------------------------------------

    async def run(self) -> None:
        """Dispatch to the correct document phase based on ``task.name``."""
        name = self._task.name
        handlers = {
            "pdf_fetching": self._execute_pdf_fetching,
            "pdf_processing": self._execute_pdf_processing,
        }
        handler = handlers.get(name)
        if handler is None:
            raise ValueError(f"Unsupported document phase: {name}")
        await handler()

    # -- helpers -------------------------------------------------------------

    @property
    def task(self) -> Any:
        return self._task

    @property
    def params(self) -> dict[str, Any]:
        return self._params

    # -- phases --------------------------------------------------------------

    async def _execute_pdf_fetching(self) -> None:
        """Fetch PDFs from configured sources."""
        domain = self._params.get("domain", "finance")
        source = self._params.get("source", "gov")
        logger.info("PDF fetching: domain=%s source=%s", domain, source)

        if source == "gov":
            uri = self._params.get("uri", "")
            await self._fetch_gov_pdf(uri)
        elif source == "academic":
            url = self._params.get("url", "")
            await self._fetch_academic_pdf(url)
        else:
            logger.warning("Unknown PDF source: %s", source)

    async def _execute_pdf_processing(self) -> None:
        """Process fetched PDFs (content extraction)."""
        domain = self._params.get("domain", "finance")
        source = self._params.get("source", "gov")
        logger.info("PDF processing: domain=%s source=%s", domain, source)

        if source == "gov":
            uri = self._params.get("uri", "")
            await self._process_gov_pdf(uri)
        elif source == "academic":
            url = self._params.get("url", "")
            await self._process_academic_pdf(url)
        else:
            logger.warning("Unknown PDF source: %s", source)

    # -- private helpers -----------------------------------------------------

    async def _fetch_gov_pdf(self, uri: str) -> None:
        """Fetch government PDF."""
        from services.gov_pdf_scanner import fetch_gov_pdfs_for_domain
        domain = self._params.get("domain", "finance")
        logger.info("Fetching gov PDF: uri=%s", uri)
        try:
            await fetch_gov_pdfs_for_domain(domain, uri)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gov PDF fetch failed: %s", exc)
            raise

    async def _fetch_academic_pdf(self, url: str) -> None:
        """Fetch academic PDF."""
        from services.academic_pdf_fetcher import fetch_academic_pdfs_for_domain
        domain = self._params.get("domain", "finance")
        logger.info("Fetching academic PDF: url=%s", url)
        try:
            await fetch_academic_pdfs_for_domain(domain, url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Academic PDF fetch failed: %s", exc)
            raise

    async def _process_gov_pdf(self, uri: str) -> None:
        """Extract content from a gov PDF."""
        from services.pdf_content_extractor import extract_pdf_content
        domain = self._params.get("domain", "finance")
        logger.info("Processing gov PDF: uri=%s", uri)
        try:
            await extract_pdf_content(uri, domain=domain)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF content extraction failed: %s", exc)
            raise

    async def _process_academic_pdf(self, url: str) -> None:
        """Extract content from an academic PDF."""
        from services.pdf_content_extractor import extract_pdf_content
        domain = self._params.get("domain", "finance")
        logger.info("Processing academic PDF: url=%s", url)
        try:
            await extract_pdf_content(url, domain=domain)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF content extraction failed: %s", exc)
            raise
