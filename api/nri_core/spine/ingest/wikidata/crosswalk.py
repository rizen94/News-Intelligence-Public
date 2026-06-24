"""Wikidata Phase 1 — crosswalk hub (entities with external ID statements only)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from nri_core.config import get_config
from nri_core.spine.store import postgres_store

# Property keys in export JSONL → spine anchor types
CROSSWALK_PROPS = {
    "P3347": "perm_id",
    "P1278": "lei",
    "P946": "ticker",
    "P414": "stock_exchange",
    "P213": "cik",  # often formatted
    "P2397": "youtube",  # skip
    "P856": "website",
    "P244": "loc_id",
    "P268": "bnf_id",
    "P269": "sudoc",
    "P2139": "cik_str",
    "P127": "owned_by",
    "P159": "hq_location",
    "P17": "country",
    "P31": "instance_of",
    "P106": "occupation",
    "P39": "position",
    "P102": "political_party",
    "P3602": "fec_id",
    "P488": "chairperson",
    "P1128": "employees",
    "P1454": "legal_form",
    "P154": "logo",
    "P18": "image",
    "P646": "freebase_id",
    "P227": "gnd_id",
    "P214": "viaf_id",
    "P213": "isin",
    "P249": "ticker",
    "P1699": "cik",
}

ANCHOR_PROP_MAP = {
    "cik": "cik",
    "cik_str": "cik",
    "P1699": "cik",
    "lei": "lei",
    "P1278": "lei",
    "wikidataId": "qid",
    "qid": "qid",
    "fec_id": "fec_id",
    "P3602": "fec_id",
    "perm_id": "perm_id",
    "P3347": "perm_id",
    "opencorporates": "opencorporates",
    "P1320": "opencorporates",
}


def _entity_id_for_qid(qid: str) -> str:
    return hashlib.sha1(f"wikidata:{qid}".encode()).hexdigest()[:16]


def iter_crosswalk_entities(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _normalize_anchor(prop: str, value: str) -> tuple[str, str] | None:
    anchor_type = ANCHOR_PROP_MAP.get(prop)
    if not anchor_type:
        return None
    value = str(value).strip()
    if not value:
        return None
    if anchor_type == "cik":
        digits = "".join(c for c in value if c.isdigit())
        if digits:
            value = digits.zfill(10)
    if anchor_type == "qid" and not value.upper().startswith("Q"):
        value = f"Q{value}"
    return anchor_type, value


def ingest_crosswalk_file(path: Path | None = None, limit: int | None = None) -> int:
    cfg = get_config()
    export_path = path or (Path(cfg.nas_datasets_root) / "wikidata" / "crosswalk.jsonl")
    if not export_path.exists():
        return 0

    count = 0
    for record in iter_crosswalk_entities(export_path):
        qid = record.get("qid") or record.get("id")
        if not qid:
            continue
        qid = str(qid).upper()
        if not qid.startswith("Q"):
            qid = f"Q{qid}"

        crosswalk = record.get("crosswalk") or record.get("properties") or {}
        anchors: list[tuple[str, str]] = []
        for prop, values in crosswalk.items():
            if not isinstance(values, list):
                values = [values]
            for val in values:
                if val is None:
                    continue
                parsed = _normalize_anchor(prop, str(val))
                if parsed:
                    anchors.append(parsed)

        if not anchors:
            continue

        entity_id = _entity_id_for_qid(qid)
        caption = record.get("label") or record.get("caption") or qid
        schema_name = record.get("schema") or "LegalEntity"

        postgres_store.upsert_entity(
            entity_id=entity_id,
            schema_name=schema_name,
            caption=caption,
            dataset="wikidata",
            referents=[f"wikidata:{qid}"],
        )
        postgres_store.upsert_anchor(entity_id, "qid", qid)
        postgres_store.upsert_statement(
            entity_id=entity_id,
            dataset="wikidata",
            schema_name=schema_name,
            prop="wikidataId",
            value=qid,
            origin="wikidata",
        )
        for anchor_type, anchor_value in anchors:
            postgres_store.upsert_anchor(entity_id, anchor_type, anchor_value)
            postgres_store.upsert_statement(
                entity_id=entity_id,
                dataset="wikidata",
                schema_name=schema_name,
                prop=anchor_type,
                value=anchor_value,
                origin="wikidata",
            )
        count += 1
        if limit and count >= limit:
            break
    return count


def fetch_crosswalk_via_api(qid: str) -> dict[str, Any] | None:
    """Fetch crosswalk statements for a single QID (lazy enrichment)."""
    import httpx

    url = "https://www.wikidata.org/wiki/Special:EntityData/" + qid + ".json"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, headers={"User-Agent": "NewsReviewInvestigator/0.1"})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError:
        return None
