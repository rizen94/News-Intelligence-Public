"""unitedstates/congress-legislators → spine with bioguide/FEC/QID anchors."""

from __future__ import annotations

import hashlib
from typing import Any

import httpx
import yaml

LEGISLATORS_URL = (
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/"
    "main/legislators-current.yaml"
)


def _entity_id_for_bioguide(bioguide: str) -> str:
    return hashlib.sha1(f"congress:{bioguide}".encode()).hexdigest()[:16]


def fetch_legislators_yaml() -> list[dict[str, Any]]:
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(LEGISLATORS_URL)
        resp.raise_for_status()
        return yaml.safe_load(resp.text) or []


def ingest_congress_legislators(limit: int | None = None) -> int:
    from nri_core.spine.store import postgres_store

    legislators = fetch_legislators_yaml()
    count = 0
    for leg in legislators:
        bio = leg.get("id") or {}
        bioguide = bio.get("bioguide")
        if not bioguide:
            continue
        name = leg.get("name") or {}
        caption = name.get("official_full") or f"{name.get('first', '')} {name.get('last', '')}".strip()
        entity_id = _entity_id_for_bioguide(bioguide)

        fec_raw = bio.get("fec")
        if isinstance(fec_raw, list):
            fec_id = fec_raw[0] if fec_raw else None
        else:
            fec_id = fec_raw
        govtrack = bio.get("govtrack")
        wikidata = bio.get("wikidata")
        opensecrets = bio.get("opensecrets")

        postgres_store.upsert_entity(
            entity_id=entity_id,
            schema_name="Person",
            caption=caption,
            dataset="congress",
            referents=[f"bioguide:{bioguide}"],
        )
        postgres_store.upsert_statement(
            entity_id=entity_id,
            dataset="congress",
            schema_name="Person",
            prop="name",
            value=caption,
            origin="congress",
        )
        postgres_store.upsert_anchor(entity_id, "bioguide", bioguide)
        if fec_id:
            postgres_store.upsert_anchor(entity_id, "fec_id", str(fec_id))
        if govtrack:
            postgres_store.upsert_anchor(entity_id, "govtrack", str(govtrack))
        if wikidata:
            qid = str(wikidata).upper()
            if not qid.startswith("Q"):
                qid = f"Q{qid}"
            postgres_store.upsert_anchor(entity_id, "qid", qid)
        if opensecrets:
            postgres_store.upsert_anchor(entity_id, "opensecrets", str(opensecrets))

        count += 1
        if limit and count >= limit:
            break
    return count
