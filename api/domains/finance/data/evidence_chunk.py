"""
Evidence chunk — canonical object before embedding.
Ledger and vector store reference by chunk_id.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EvidenceChunk:
    """Canonical representation of a chunk before embedding."""

    text: str
    source: str  # e.g. "fred_iq12260", "edgar_10k", "gdelt"
    document_id: str
    chunk_index: int
    timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def chunk_id(self) -> str:
        """Unique ID for ledger and vector store."""
        return f"{self.source}:{self.document_id}:{self.chunk_index}"
