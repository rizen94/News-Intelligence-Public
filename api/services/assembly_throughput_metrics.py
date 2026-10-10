"""
Post-spine assembly and editorial room throughput metrics for Monitor.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_lock = Lock()
_link_batches: deque[dict[str, int]] = deque(maxlen=200)
_assembly_cycles: deque[dict[str, Any]] = deque(maxlen=100)
_editorial_cycles: deque[dict[str, Any]] = deque(maxlen=100)


@dataclass
class AssemblyThroughputSnapshot:
    links_indexed_articles: int = 0
    entity_edges: int = 0
    proposals_created: int = 0
    assembly_rounds: int = 0
    editorial_room_rounds: int = 0
    vault_connections_written: int = 0
    ollama_calls_per_loop: float = 0.0
    promotions_from_vault: int = 0


_snapshot = AssemblyThroughputSnapshot()


def record_link_indexer_batch(totals: dict[str, int]) -> None:
    with _lock:
        _link_batches.append(dict(totals))
        _recompute()


def record_assembly_cycle(stats: dict[str, Any]) -> None:
    with _lock:
        _assembly_cycles.append(dict(stats))
        _recompute()


def record_editorial_room_cycle(stats: dict[str, Any]) -> None:
    with _lock:
        _editorial_cycles.append(dict(stats))
        _recompute()


def _recompute() -> None:
    global _snapshot
    snap = AssemblyThroughputSnapshot()
    if _link_batches:
        snap.links_indexed_articles = sum(int(b.get("articles") or 0) for b in _link_batches)
        snap.entity_edges = sum(int(b.get("entity_edges") or 0) for b in _link_batches)
        snap.proposals_created = sum(
            int(b.get("event_proposals") or 0) + int(b.get("cross_domain_proposals") or 0)
            for b in _link_batches
        )
    snap.assembly_rounds = len(_assembly_cycles)
    if _editorial_cycles:
        last = _editorial_cycles[-1]
        snap.editorial_room_rounds = int(last.get("rounds") or len(_editorial_cycles))
        snap.vault_connections_written = sum(
            int(c.get("connections_written") or 0) for c in _editorial_cycles
        )
        calls = sum(int(c.get("ollama_calls") or 0) for c in _editorial_cycles)
        snap.ollama_calls_per_loop = calls / max(1, len(_editorial_cycles))
        snap.promotions_from_vault = sum(int(c.get("promotions") or 0) for c in _editorial_cycles)
    _snapshot = snap


def get_assembly_throughput_snapshot() -> dict[str, Any]:
    with _lock:
        s = _snapshot
        return {
            "links_indexed_articles": s.links_indexed_articles,
            "entity_edges": s.entity_edges,
            "proposals_created": s.proposals_created,
            "assembly_rounds": s.assembly_rounds,
            "editorial_room_rounds": s.editorial_room_rounds,
            "vault_connections_written": s.vault_connections_written,
            "ollama_calls_per_loop": round(s.ollama_calls_per_loop, 2),
            "promotions_from_vault": s.promotions_from_vault,
        }
