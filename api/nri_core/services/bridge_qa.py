"""Read-only QA assessment for nri.entity_bridge rows."""

from __future__ import annotations

import difflib
import re
from typing import Any, Literal

from nri_core.constants import (
    BRIDGE_QA_OK_SIMILARITY,
    BRIDGE_QA_SUSPECT_SIMILARITY,
    GENERIC_FTM_CAPTIONS,
)

QaStatus = Literal["ok", "suspect", "mismatch", "unknown"]

_ORG_TYPES = frozenset({"organization", "company", "legalentity", "legal_entity"})
_PERSON_TYPES = frozenset({"person", "family"})
_FTM_ORG_SCHEMAS = frozenset({"legalentity", "company", "organization"})
_FTM_PERSON_SCHEMAS = frozenset({"person"})


def _norm_name(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def _python_name_similarity(a: str, b: str) -> float:
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _qid_from_anchors(anchors: dict[str, Any] | None) -> str | None:
    if not anchors:
        return None
    qid = anchors.get("qid")
    if qid is None:
        return None
    text = str(qid).strip()
    if not text:
        return None
    return text if text.upper().startswith("Q") else f"Q{text}"


def _schema_type_mismatch(
    ni_entity_type: str | None,
    ftm_schema_name: str | None,
) -> bool:
    ni = (ni_entity_type or "").strip().lower()
    schema = (ftm_schema_name or "").strip().lower()
    if not ni or not schema:
        return False
    if ni in _PERSON_TYPES and schema in _FTM_ORG_SCHEMAS:
        return True
    if ni in _ORG_TYPES and schema in _FTM_PERSON_SCHEMAS:
        return True
    return False


def assess_bridge_qa(
    *,
    ni_canonical_name: str | None,
    ftm_caption: str | None,
    ni_entity_type: str | None = None,
    ftm_schema_name: str | None = None,
    ftm_dataset: str | None = None,
    mention_text: str | None = None,
    anchors: dict[str, Any] | None = None,
    mint_qid: str | None = None,
    name_similarity: float | None = None,
) -> dict[str, Any]:
    """
    Compute QA status for an entity_bridge without mutating storage.

    Returns dict with qa_status, name_similarity, qa_flags.
    """
    flags: list[str] = []
    sim = name_similarity
    if sim is None:
        sim = _python_name_similarity(ni_canonical_name, ftm_caption)

    na = _norm_name(ni_canonical_name)
    caption_norm = _norm_name(ftm_caption)

    if na and caption_norm and na == caption_norm:
        sim = 1.0

    anchor_qid = _qid_from_anchors(anchors if isinstance(anchors, dict) else None)
    if mint_qid and anchor_qid and _norm_name(mint_qid) == _norm_name(anchor_qid):
        sim = max(sim, 1.0)

    if _schema_type_mismatch(ni_entity_type, ftm_schema_name):
        flags.append("person_org_schema_swap")

    mention = (mention_text or ni_canonical_name or "").strip()
    if len(mention) > 0 and len(mention) < 4:
        flags.append("wikidata_lazy_short_name")

    if (ftm_dataset or "").strip().lower() == "wikidata_lazy" and (
        ftm_schema_name or ""
    ).strip().lower() == "person":
        if sim < BRIDGE_QA_OK_SIMILARITY and "person_org_schema_swap" not in flags:
            flags.append("wikidata_lazy_person_fuzzy")

    if caption_norm in GENERIC_FTM_CAPTIONS:
        flags.append("generic_caption")

    if sim < BRIDGE_QA_SUSPECT_SIMILARITY:
        flags.append("name_mismatch")
    elif sim < BRIDGE_QA_OK_SIMILARITY and na != caption_norm:
        flags.append("name_partial_match")

    if sim >= BRIDGE_QA_OK_SIMILARITY or na == caption_norm:
        status: QaStatus = "ok"
    elif sim >= BRIDGE_QA_SUSPECT_SIMILARITY and not flags:
        status = "suspect"
    elif sim >= BRIDGE_QA_SUSPECT_SIMILARITY or (
        flags and "name_partial_match" in flags
    ):
        status = "suspect"
    else:
        status = "mismatch"

    if "person_org_schema_swap" in flags and status == "ok":
        status = "suspect"
    if "name_mismatch" in flags:
        status = "mismatch" if sim < BRIDGE_QA_SUSPECT_SIMILARITY else "suspect"
    if "generic_caption" in flags and status == "ok":
        status = "suspect"

    if not ni_canonical_name and not ftm_caption:
        status = "unknown"

    return {
        "qa_status": status,
        "name_similarity": round(float(sim), 4),
        "qa_flags": flags,
        "ni_canonical_name": ni_canonical_name,
    }


def pg_trgm_similarity(cur, a: str, b: str) -> float | None:
    """Return pg_trgm similarity when extension is available."""
    try:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm' LIMIT 1")
        if not cur.fetchone():
            return None
        cur.execute(
            "SELECT similarity(lower(trim(%s)), lower(trim(%s)))",
            (a or "", b or ""),
        )
        row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def enrich_bridge_with_qa(
    bridge: dict[str, Any],
    *,
    ni_canonical_name: str | None,
    ni_entity_type: str | None,
    mention_text: str | None = None,
    cur=None,
) -> dict[str, Any]:
    """Merge QA fields into a bridge dict."""
    caption = bridge.get("caption")
    sim = None
    if cur is not None and ni_canonical_name and caption:
        sim = pg_trgm_similarity(cur, ni_canonical_name, caption)

    qa = assess_bridge_qa(
        ni_canonical_name=ni_canonical_name,
        ftm_caption=caption,
        ni_entity_type=ni_entity_type,
        ftm_schema_name=bridge.get("schema_name"),
        ftm_dataset=bridge.get("dataset"),
        mention_text=mention_text,
        anchors=bridge.get("anchors") if isinstance(bridge.get("anchors"), dict) else None,
        name_similarity=sim,
    )
    return {**bridge, **qa}
