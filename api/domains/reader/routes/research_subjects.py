"""GET /api/reader/research/subjects — subject fact board (is / is_not / open)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()

_RESEARCH_DOMAINS = frozenset(
    {"medicine", "neurodiversity", "artificial-intelligence"}
)


def _assertion_counts(profile: dict) -> dict[str, int]:
    return {
        "is": len(profile.get("is_assertions") or []),
        "is_not": len(profile.get("is_not_assertions") or []),
        "open": len(profile.get("open_questions") or []),
    }


@router.get("/research/subjects")
async def list_research_subjects(
    domain: str | None = Query(None, description="Filter to one research domain"),
    limit: int = Query(50, ge=1, le=200),
):
    """Topic index: curated subjects + vault keywords under each domain."""
    from services.knowledge_profile_service import KNOWLEDGE_PROFILE_DOMAINS, list_profiles
    from services.research_subject_topics import (
        domain_fallback_subjects,
        list_domain_topic_index,
    )

    domains: list[str]
    if domain:
        dk = domain.strip()
        if dk not in KNOWLEDGE_PROFILE_DOMAINS:
            raise HTTPException(status_code=400, detail="domain_not_research_kind")
        domains = [dk]
    else:
        domains = sorted(KNOWLEDGE_PROFILE_DOMAINS)

    from shared.database.connection import get_ui_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    fallback_map = domain_fallback_subjects()
    subjects: list[dict] = []
    seen: set[tuple[str, int]] = set()

    for dk in domains:
        curated = list(fallback_map.get(dk) or [])
        curated_lower = {n.lower(): n for n in curated}

        try:
            profiles = list_profiles(domain_key=dk, status=None, limit=max(limit, 100))
        except Exception as exc:
            logger.warning("list research subjects %s: %s", dk, exc)
            profiles = []

        for p in profiles:
            title = (p.get("title") or "").strip()
            if title.lower() not in curated_lower:
                continue
            status = (p.get("status") or "").strip()
            if status not in ("published", "draft"):
                continue
            eid = int(p["canonical_entity_id"])
            seen.add((dk, eid))
            counts = _assertion_counts(p)
            subjects.append(
                {
                    "domain_key": dk,
                    "canonical_entity_id": eid,
                    "profile_id": p.get("id"),
                    "title": curated_lower.get(title.lower(), title),
                    "status": status,
                    "material_updated_at": p.get("material_updated_at"),
                    "assertion_counts": counts,
                    "href": f"/research/subjects/{dk}/{eid}",
                }
            )

        try:
            schema = resolve_domain_schema(dk)
            with get_ui_db_connection_context() as conn:
                with conn.cursor() as cur:
                    for name in curated:
                        cur.execute(
                            f"""
                            SELECT id, canonical_name
                            FROM {schema}.entity_canonical
                            WHERE lower(trim(canonical_name)) = lower(trim(%s))
                            ORDER BY
                              CASE WHEN lower(coalesce(entity_type,'')) = 'subject'
                                   THEN 0 ELSE 1 END,
                              id ASC
                            LIMIT 1
                            """,
                            (name,),
                        )
                        row = cur.fetchone()
                        if not row:
                            continue
                        eid = int(row[0])
                        if (dk, eid) in seen:
                            continue
                        seen.add((dk, eid))
                        subjects.append(
                            {
                                "domain_key": dk,
                                "canonical_entity_id": eid,
                                "profile_id": None,
                                "title": name,
                                "status": "draft",
                                "material_updated_at": None,
                                "assertion_counts": {
                                    "is": 0,
                                    "is_not": 0,
                                    "open": 0,
                                },
                                "href": f"/research/subjects/{dk}/{eid}",
                            }
                        )
        except Exception as exc:
            logger.debug("curated entity fallback %s: %s", dk, exc)

    subjects.sort(
        key=lambda s: (
            0 if (s.get("status") == "published") else 1,
            -(
                (s.get("assertion_counts") or {}).get("is", 0)
                + (s.get("assertion_counts") or {}).get("is_not", 0)
                + (s.get("assertion_counts") or {}).get("open", 0)
            ),
            str(s.get("title") or ""),
        ),
    )

    domain_blocks = list_domain_topic_index()
    if domain:
        domain_blocks = [d for d in domain_blocks if d["domain_key"] == domain.strip()]

    return {
        "ok": True,
        "subjects": subjects[:limit],
        "count": min(len(subjects), limit),
        "domains": domain_blocks,
    }


@router.get("/research/subjects/{domain_key}/{entity_id}")
async def get_research_subject_board(domain_key: str, entity_id: int):
    """Subject fact board: supported / not supported / open + ledger claims."""
    from services.knowledge_profile_service import get_profile
    from services.research_subject_ledger_service import get_research_subject
    from services.research_subject_topics import domain_keywords, domain_label

    dk = (domain_key or "").strip()
    if dk not in _RESEARCH_DOMAINS:
        raise HTTPException(status_code=400, detail="domain_not_research_kind")

    try:
        subject = get_research_subject(
            dk, canonical_entity_id=int(entity_id), limit_claims=80
        )
    except Exception as exc:
        logger.exception("get research subject failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not subject.get("success"):
        raise HTTPException(
            status_code=404, detail=subject.get("error") or "entity_not_found"
        )

    profile = None
    try:
        profile = get_profile(
            domain_key=dk,
            canonical_entity_id=int(entity_id),
            include_citations=True,
        )
    except Exception as exc:
        logger.debug("knowledge profile load: %s", exc)

    is_assertions = (profile or {}).get("is_assertions") or []
    is_not_assertions = (profile or {}).get("is_not_assertions") or []
    open_questions = (profile or {}).get("open_questions") or []

    vault_path = None
    vault_title = None
    try:
        from shared.database.connection import get_ui_db_connection_context

        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                # Prefer exact object_id; fall back to same title under this domain
                # (older seeds sometimes registered org ids before subject boards).
                cur.execute(
                    """
                    SELECT vault_path, title
                    FROM intelligence.vault_notes
                    WHERE domain_key = %s
                      AND note_type = 'entity'
                      AND COALESCE(object_id_secondary, 0) = 0
                      AND (
                        object_id = %s
                        OR lower(trim(title)) = lower(trim(%s))
                      )
                    ORDER BY
                      CASE WHEN object_id = %s THEN 0 ELSE 1 END,
                      CASE WHEN lifecycle IN ('living', 'seeded') THEN 0 ELSE 1 END,
                      updated_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (
                        dk,
                        int(entity_id),
                        (profile or {}).get("title")
                        or (subject.get("entity") or {}).get("canonical_name")
                        or "",
                        int(entity_id),
                    ),
                )
                vrow = cur.fetchone()
                if vrow:
                    vault_path = vrow[0]
                    vault_title = vrow[1]
    except Exception as exc:
        logger.debug("vault note lookup: %s", exc)

    return {
        "ok": True,
        "domain_key": dk,
        "domain_label": domain_label(dk),
        "domain_keywords": domain_keywords(dk),
        "entity": subject.get("entity"),
        "knowledge_profile_id": (profile or {}).get("id")
        or subject.get("knowledge_profile_id"),
        "title": (profile or {}).get("title")
        or (subject.get("entity") or {}).get("canonical_name"),
        "status": (profile or {}).get("status"),
        "body_md": (profile or {}).get("body_md"),
        "material_updated_at": (profile or {}).get("material_updated_at"),
        "supported": is_assertions,
        "not_supported": is_not_assertions,
        "open": open_questions,
        "assertion_counts": {
            "is": len(is_assertions),
            "is_not": len(is_not_assertions),
            "open": len(open_questions),
        },
        "claims": subject.get("claims") or [],
        "claim_verdict_counts": subject.get("claim_verdict_counts") or {},
        "citations": (profile or {}).get("citations") or [],
        "vault_path": vault_path,
        "vault_title": vault_title,
    }
