"""
Sanctions ingest — OFAC SDN, EU Consolidated, UN SCR into intelligence.sanctions_actions.

Daily refresh when SANCTIONS_INGEST_ENABLED=true.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

OFAC_SDN_CSV = "https://www.treasury.gov/ofac/downloads/sdn.csv"
EU_FSF_XML = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
UN_CONSOLIDATED_XML = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"


def _parse_http_date(resp: requests.Response) -> datetime:
    raw = resp.headers.get("Last-Modified")
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def fetch_ofac_sdn_csv() -> tuple[str, datetime]:
    r = requests.get(OFAC_SDN_CSV, timeout=120)
    r.raise_for_status()
    return r.text, _parse_http_date(r)


def parse_ofac_rows(csv_text: str, *, file_vintage: datetime, limit: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reader = csv.reader(io.StringIO(csv_text))
    for i, parts in enumerate(reader):
        if i >= limit:
            break
        if len(parts) < 2:
            continue
        ent_num = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else ""
        prog = parts[2].strip() if len(parts) > 2 else ""
        if not ent_num or not name:
            continue
        rows.append(
            {
                "source": "ofac_sdn",
                "external_id": ent_num,
                "action_date": file_vintage,
                "action_type": "listing",
                "entity_qids": [],
                "entity_names": [name],
                "program": prog,
                "summary": f"OFAC SDN: {name}",
                "raw": {"parts": parts[:6], "file_vintage": file_vintage.isoformat()},
            }
        )
    return rows


def parse_eu_sanctions_xml(xml_text: str, *, file_vintage: datetime, limit: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("EU sanctions XML parse error: %s", e)
        return rows
    ns = {"eu": "http://eu.europa.eu/ec/dgs/jrc/fatf/schemas/sanctionlist"}
    entities = root.findall(".//eu:sanctionEntity", ns) or root.findall(".//sanctionEntity")
    for i, ent in enumerate(entities):
        if i >= limit:
            break
        eid = ent.get("logicalId") or ent.get("euReferenceNumber") or f"eu_{i}"
        name_el = ent.find(".//eu:nameAlias", ns) or ent.find(".//nameAlias")
        name = (name_el.get("wholeName") if name_el is not None else None) or eid
        prog_el = ent.find(".//eu:regulation", ns) or ent.find(".//regulation")
        prog = prog_el.get("programme") if prog_el is not None else ""
        action_date = file_vintage
        for date_tag in ("eu:publicationDate", "publicationDate", "eu:entryIntoForceDate"):
            d_el = ent.find(f".//{date_tag}", ns if date_tag.startswith("eu:") else None)
            if d_el is not None and d_el.text:
                try:
                    action_date = datetime.fromisoformat(d_el.text[:10]).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
                break
        rows.append(
            {
                "source": "eu_consolidated",
                "external_id": str(eid),
                "action_date": action_date,
                "action_type": "listing",
                "entity_qids": [],
                "entity_names": [name],
                "program": prog or "",
                "summary": f"EU sanctions: {name}",
                "raw": {"logical_id": eid},
            }
        )
    return rows


def parse_un_sanctions_xml(xml_text: str, *, file_vintage: datetime, limit: int = 500) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("UN sanctions XML parse error: %s", e)
        return rows
    for i, ind in enumerate(root.findall(".//INDIVIDUAL")):
        if i >= limit:
            break
        uid = ind.findtext("DATAID") or f"un_ind_{i}"
        name = " ".join(
            p
            for p in (
                ind.findtext("FIRST_NAME"),
                ind.findtext("SECOND_NAME"),
                ind.findtext("THIRD_NAME"),
            )
            if p
        ).strip() or uid
        listed = ind.findtext("LISTED_ON")
        action_date = file_vintage
        if listed:
            try:
                action_date = datetime.fromisoformat(listed[:10]).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        rows.append(
            {
                "source": "un_scr",
                "external_id": str(uid),
                "action_date": action_date,
                "action_type": "listing",
                "entity_qids": [],
                "entity_names": [name],
                "program": ind.findtext("UN_LIST_TYPE") or "",
                "summary": f"UN SCR: {name}",
                "raw": {"listed_on": listed},
            }
        )
    for i, ent in enumerate(root.findall(".//ENTITY")):
        if len(rows) >= limit:
            break
        uid = ent.findtext("DATAID") or f"un_ent_{i}"
        name = ent.findtext("FIRST_NAME") or uid
        listed = ent.findtext("LISTED_ON")
        action_date = file_vintage
        if listed:
            try:
                action_date = datetime.fromisoformat(listed[:10]).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        rows.append(
            {
                "source": "un_scr",
                "external_id": str(uid),
                "action_date": action_date,
                "action_type": "listing",
                "entity_qids": [],
                "entity_names": [name],
                "program": ent.findtext("UN_LIST_TYPE") or "",
                "summary": f"UN SCR entity: {name}",
                "raw": {"listed_on": listed},
            }
        )
    return rows[:limit]


def upsert_sanctions_actions(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    import json

    n = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO intelligence.sanctions_actions (
                        source, external_id, action_date, action_type,
                        entity_qids, entity_names, program, summary, raw,
                        ingestion_date, vintage_date
                    ) VALUES (
                        %s, %s, %s, %s, %s::text[], %s::text[], %s, %s, %s::jsonb,
                        NOW(), NOW()
                    )
                    ON CONFLICT (source, external_id) DO UPDATE SET
                        action_date = EXCLUDED.action_date,
                        entity_names = EXCLUDED.entity_names,
                        program = EXCLUDED.program,
                        summary = EXCLUDED.summary,
                        raw = EXCLUDED.raw,
                        vintage_date = NOW()
                    """,
                    (
                        row["source"],
                        row["external_id"],
                        row["action_date"],
                        row.get("action_type"),
                        row.get("entity_qids") or [],
                        row.get("entity_names") or [],
                        row.get("program"),
                        row.get("summary"),
                        json.dumps(row.get("raw") or {}),
                    ),
                )
                n += 1
        conn.commit()
    return n


def _resolve_entity_qids(cur, names: list[str]) -> list[str]:
    qids: list[str] = []
    for name in names[:3]:
        if not name:
            continue
        cur.execute(
            """
            SELECT wikidata_qid FROM politics.entity_canonical
            WHERE lower(canonical_name) = lower(%s) AND wikidata_qid IS NOT NULL
            LIMIT 1
            """,
            (name,),
        )
        row = cur.fetchone()
        if row and row[0]:
            qids.append(row[0])
    return qids


def run_sanctions_refresh(*, limit: int = 500) -> dict[str, Any]:
    if os.environ.get("SANCTIONS_INGEST_ENABLED", "false").lower() not in ("1", "true", "yes"):
        return {"success": True, "skipped": True, "reason": "SANCTIONS_INGEST_ENABLED off"}
    all_rows: list[dict[str, Any]] = []
    sources: dict[str, int] = {}
    try:
        csv_text, ofac_vintage = fetch_ofac_sdn_csv()
        ofac_rows = parse_ofac_rows(csv_text, file_vintage=ofac_vintage, limit=limit)
        all_rows.extend(ofac_rows)
        sources["ofac_sdn"] = len(ofac_rows)
    except Exception as e:
        logger.warning("OFAC sanctions fetch failed: %s", e)

    if os.environ.get("SANCTIONS_EU_UN_ENABLED", "true").lower() in ("1", "true", "yes"):
        try:
            eu_resp = requests.get(EU_FSF_XML, timeout=120)
            eu_resp.raise_for_status()
            eu_vintage = _parse_http_date(eu_resp)
            eu_rows = parse_eu_sanctions_xml(eu_resp.text, file_vintage=eu_vintage, limit=limit)
            all_rows.extend(eu_rows)
            sources["eu_consolidated"] = len(eu_rows)
        except Exception as e:
            logger.warning("EU sanctions fetch failed: %s", e)
        try:
            un_resp = requests.get(UN_CONSOLIDATED_XML, timeout=120)
            un_resp.raise_for_status()
            un_vintage = _parse_http_date(un_resp)
            un_rows = parse_un_sanctions_xml(un_resp.text, file_vintage=un_vintage, limit=limit)
            all_rows.extend(un_rows)
            sources["un_scr"] = len(un_rows)
        except Exception as e:
            logger.warning("UN sanctions fetch failed: %s", e)

    if all_rows:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for row in all_rows:
                    if not row.get("entity_qids"):
                        row["entity_qids"] = _resolve_entity_qids(cur, row.get("entity_names") or [])

    n = upsert_sanctions_actions(all_rows)
    return {"success": True, "upserted": n, "sources": sources}
