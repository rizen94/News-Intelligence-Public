"""
Fetch ClinicalTrials.gov study text via the public API v2 (not HTML/trafilatura).

RSS only has titles; the useful brief summary lives on the study record / API.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shared.fulltext_pull_gate import extract_nct_id, is_thin_link_host

logger = logging.getLogger(__name__)

_API = "https://clinicaltrials.gov/api/v2/studies"
_TIMEOUT = 12


def fetch_clinicaltrials_study_body(url: str) -> tuple[str, bool]:
    """
    Return (plain_text_body, ok) for a ClinicalTrials.gov study URL.
    Non-CT.gov URLs return ("", False).
    """
    if not is_thin_link_host(url):
        return "", False
    nct = extract_nct_id(url)
    if not nct:
        return "", False
    try:
        fields = ",".join(
            [
                "NCTId",
                "BriefTitle",
                "OfficialTitle",
                "BriefSummary",
                "Condition",
                "InterventionName",
                "Phase",
                "OverallStatus",
                "StudyType",
            ]
        )
        req_url = f"{_API}/{nct}?{urlencode({'fields': fields})}"
        req = Request(req_url, headers={"Accept": "application/json", "User-Agent": "NewsIntelligence/1.0"})
        with urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        text = _study_json_to_text(data, nct=nct)
        if len(text.strip()) < 80:
            return text, False
        return text, True
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        logger.debug("clinicaltrials API fetch %s: %s", nct, e)
        return "", False
    except Exception as e:
        logger.warning("clinicaltrials API unexpected %s: %s", nct, e)
        return "", False


def _study_json_to_text(data: dict[str, Any], *, nct: str) -> str:
    proto = data.get("protocolSection") or data
    ident = proto.get("identificationModule") or {}
    desc = proto.get("descriptionModule") or {}
    cond = proto.get("conditionsModule") or {}
    design = proto.get("designModule") or {}
    status = proto.get("statusModule") or {}
    arms = proto.get("armsInterventionsModule") or {}

    title = (ident.get("briefTitle") or ident.get("officialTitle") or "").strip()
    official = (ident.get("officialTitle") or "").strip()
    summary = (desc.get("briefSummary") or "").strip()
    conditions = cond.get("conditions") or []
    if isinstance(conditions, str):
        conditions = [conditions]
    interventions = []
    for item in arms.get("interventions") or []:
        if isinstance(item, dict) and item.get("name"):
            interventions.append(str(item["name"]))
        elif isinstance(item, str):
            interventions.append(item)
    phases = design.get("phases") or []
    if isinstance(phases, str):
        phases = [phases]
    study_type = design.get("studyType") or ""
    overall = status.get("overallStatus") or ""

    parts: list[str] = [
        f"ClinicalTrials.gov {nct}",
        title or official,
    ]
    if official and official != title:
        parts.append(f"Official title: {official}")
    if study_type or phases or overall:
        phase_s = ", ".join(str(p) for p in phases if p) or "n/a"
        parts.append(f"Type: {study_type or 'n/a'}; Phase: {phase_s}; Status: {overall or 'n/a'}")
    if conditions:
        parts.append("Conditions: " + "; ".join(str(c) for c in conditions if c))
    if interventions:
        parts.append("Interventions: " + "; ".join(interventions))
    if summary:
        parts.append(summary)
    body = "\n\n".join(p for p in parts if p and str(p).strip())
    # Collapse excess whitespace
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()
