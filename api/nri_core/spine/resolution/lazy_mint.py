"""Demand-driven provisional mint on resolution miss — Wikidata + OpenSanctions API."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg2.extras

from config.investigation_tables import T_PROVISIONAL_MINTS
from nri_core.evidence import ni_reader
from nri_core.config import get_config
from nri_core.spine.store import postgres_store

WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php"
OPENSANCTIONS_MATCH = "https://api.opensanctions.org/match/default"


@dataclass
class LazyMintResult:
    ftm_id: str | None
    score: float
    source_api: str
    status: str
    evidence: dict[str, Any]


def _provisional_entity_id(source: str, external_id: str) -> str:
    return hashlib.sha1(f"lazy:{source}:{external_id}".encode()).hexdigest()[:16]


def search_wikidata(name: str, limit: int = 3) -> list[dict[str, Any]]:
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "format": "json",
        "limit": limit,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                WIKIDATA_SEARCH,
                params=params,
                headers={"User-Agent": "NewsReviewInvestigator/0.1"},
            )
            resp.raise_for_status()
            return resp.json().get("search", [])
    except httpx.HTTPError:
        return []


def match_opensanctions(name: str) -> dict[str, Any] | None:
    payload = {
        "queries": {
            "q1": {
                "schema": "Person",
                "properties": {"name": [name]},
            }
        }
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(OPENSANCTIONS_MATCH, json=payload)
            resp.raise_for_status()
            data = resp.json()
            responses = data.get("responses", {}).get("q1", {})
            results = responses.get("results", [])
            return results[0] if results else None
    except httpx.HTTPError:
        return None


def _mint_provisional_spine(
    entity_id: str,
    caption: str,
    schema_name: str,
    dataset: str,
    anchors: list[tuple[str, str]],
    evidence: dict[str, Any],
) -> str:
    with postgres_store.spine_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO spine_entities (id, schema_name, caption, dataset, status, mint_evidence)
                VALUES (%s, %s, %s, %s, 'provisional', %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    caption = EXCLUDED.caption,
                    mint_evidence = EXCLUDED.mint_evidence,
                    last_seen = NOW()
                """,
                (entity_id, schema_name, caption, dataset, psycopg2.extras.Json(evidence)),
            )
    for anchor_type, anchor_value in anchors:
        postgres_store.upsert_anchor(entity_id, anchor_type, anchor_value)
    return entity_id


def _record_provisional_mint(
    mention_text: str,
    context_id: int | None,
    entity_profile_id: int | None,
    ftm_id: str | None,
    source_api: str,
    score: float,
    evidence: dict[str, Any],
) -> None:
    with ni_reader.news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {T_PROVISIONAL_MINTS}
                    (mention_text, context_id, entity_profile_id, ftm_id,
                     source_api, match_score, mint_evidence, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'provisional')
                """,
                (
                    mention_text,
                    context_id,
                    entity_profile_id,
                    ftm_id,
                    source_api,
                    score,
                    psycopg2.extras.Json(evidence),
                ),
            )
        conn.commit()


def lazy_mint_on_miss(
    mention_text: str,
    context_id: int | None = None,
    entity_profile_id: int | None = None,
    entity_type: str | None = None,
) -> LazyMintResult:
    cfg = get_config()
    if not cfg.lazy_mint_enabled:
        return LazyMintResult(None, 0.0, "disabled", "parked", {})

    # Wikidata first
    wd_hits = search_wikidata(mention_text, limit=3)
    if wd_hits:
        best = wd_hits[0]
        qid = best.get("id", "")
        label = best.get("label", mention_text)
        score = 0.75  # search rank proxy
        entity_id = _provisional_entity_id("wikidata", qid)
        evidence = {"api": "wikidata_search", "response": best}
        _mint_provisional_spine(
            entity_id=entity_id,
            caption=label,
            schema_name="Person" if entity_type == "person" else "LegalEntity",
            dataset="wikidata_lazy",
            anchors=[("qid", qid)],
            evidence=evidence,
        )
        _record_provisional_mint(
            mention_text, context_id, entity_profile_id, entity_id, "wikidata", score, evidence
        )
        return LazyMintResult(entity_id, score, "wikidata", "provisional", evidence)

    # OpenSanctions lazy (no bulk)
    if cfg.opensanctions_lazy_enabled:
        os_hit = match_opensanctions(mention_text)
        if os_hit:
            os_id = os_hit.get("id", "")
            caption = os_hit.get("caption") or mention_text
            score = float(os_hit.get("score", 0.7))
            entity_id = _provisional_entity_id("opensanctions", os_id)
            evidence = {"api": "opensanctions_match", "response": os_hit}
            _mint_provisional_spine(
                entity_id=entity_id,
                caption=caption,
                schema_name=os_hit.get("schema", "Person"),
                dataset="opensanctions_lazy",
                anchors=[("opensanctions", os_id)],
                evidence=evidence,
            )
            _record_provisional_mint(
                mention_text, context_id, entity_profile_id, entity_id, "opensanctions", score, evidence
            )
            return LazyMintResult(entity_id, score, "opensanctions", "provisional", evidence)

    return LazyMintResult(None, 0.0, "none", "parked", {})
