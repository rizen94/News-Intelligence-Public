"""
Editorial package Research modality (v11).

Package-centric pass: deterministic claim extract → promote facts → optional
literature appraisal (scoped to package members), then LLM attaches claims /
facts / papers / hypotheses and research links. Routes:

- changes > 0 → Reduction
- changes == 0 and last Reduction also 0 → Editor (cycle escape)
- changes == 0 and Reduction not yet run → Reduction once
- max rounds → Editor

Never deletes source articles/claims/facts/docs — package membership only.
Gated by EDITORIAL_RESEARCH_ENABLED. LLM: PopOS STRUCTURED_EXTRACTION.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_int
from shared.database.connection import get_ui_db_connection_context
from shared.editorial_package_vocab import (
    INFERENCE_STAGES,
    RESEARCH_MEMBER_TYPES,
    provenance_has_citeable_source,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "package_research.v1"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "research"
    / "package_research.md"
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_VALID_ROLES = frozenset({"core_claim", "supporting", "hypothesis"})
_RESEARCH_LINK_TYPES = frozenset(
    {"supports", "corroborates", "contradicts", "derived_from", "near_in_time"}
)
_REATTACH_MIN_CONF = 0.85
_CLAIMISH = frozenset(
    {
        "extracted_claim",
        "versioned_fact",
        "claim_evidence_appraisal",
        "hypothesis",
    }
)


def is_enabled() -> bool:
    return env_bool("EDITORIAL_RESEARCH_ENABLED", True)


def auto_apply_enabled() -> bool:
    return env_bool("EDITORIAL_RESEARCH_AUTO_APPLY", True)


def max_rounds() -> int:
    return max(1, env_int("RESEARCH_MAX_ROUNDS", 3))


def candidate_limit() -> int:
    return max(5, min(env_int("RESEARCH_CANDIDATE_LIMIT", 40), 80))


def _package_default_domain(package: dict[str, Any] | None) -> str | None:
    """Prefer package.domain_keys, else first active member domain."""
    if not package:
        return None
    for dk in list(package.get("domain_keys") or []):
        s = str(dk or "").strip()
        if s:
            return s
    for m in package.get("members") or []:
        st = m.get("status")
        if st is not None and st != "active":
            continue
        s = str(m.get("domain_key") or "").strip()
        if s:
            return s
    return None


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("research prompt missing: %s", e)
        return (
            "Assemble research package members and links. Output JSON with "
            "summary_stub, attach[], role_updates[], links[]. Prefer versioned_fact "
            "over raw claim. Never delete sources. Refuse attach without citeable provenance."
        )


def _parse_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _JSON_FENCE.search(raw)
    if m:
        raw = m.group(1).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _merge_package_metadata(package_id: int, patch: dict[str, Any]) -> None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.editorial_packages
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(patch), package_id),
            )
            conn.commit()


def _append_summary_decision(
    package_id: int,
    *,
    action: str,
    rationale: str,
    metadata: dict[str, Any],
    model: str | None = None,
) -> None:
    from services.editorial_package_service import _append_decision

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            _append_decision(
                cur,
                package_id=package_id,
                action=action,
                actor="research_llm",
                modal="research",
                rationale=rationale,
                model_prompt_version=PROMPT_VERSION,
                metadata={**metadata, **({"model": model} if model else {})},
            )
            conn.commit()


def _candidate_key(member_type: str, member_id: int, domain_key: str | None = None) -> str:
    dk = (domain_key or "").strip()
    if dk and member_type in ("article", "context", "entity"):
        return f"{member_type}:{dk}:{int(member_id)}"
    return f"{member_type}:{int(member_id)}"


def _active_research_members(package: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in package.get("members") or []:
        if m.get("status") != "active":
            continue
        mt = str(m.get("member_type") or "")
        fam = str(m.get("member_family") or "")
        if mt in RESEARCH_MEMBER_TYPES or fam == "research":
            out.append(m)
    return out


def _collect_package_scope_ids(package: dict[str, Any]) -> dict[str, list[int]]:
    """IDs for package-scoped spine (contexts, claims, docs, articles)."""
    context_ids: set[int] = set()
    claim_ids: set[int] = set()
    doc_ids: set[int] = set()
    article_ids: set[int] = set()
    appraisal_ids: set[int] = set()

    for m in _active_research_members(package):
        mt = str(m.get("member_type") or "")
        try:
            mid = int(m["member_id"])
        except (TypeError, ValueError, KeyError):
            continue
        if mt == "context":
            context_ids.add(mid)
        elif mt == "extracted_claim":
            claim_ids.add(mid)
        elif mt == "processed_document":
            doc_ids.add(mid)
        elif mt == "article":
            article_ids.add(mid)
        elif mt == "claim_evidence_appraisal":
            appraisal_ids.add(mid)

    # Resolve article → context when article is on package
    if article_ids:
        try:
            with get_ui_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id FROM intelligence.contexts
                        WHERE article_id = ANY(%s)
                        """,
                        (list(article_ids),),
                    )
                    for (cid,) in cur.fetchall() or []:
                        context_ids.add(int(cid))
        except Exception as e:
            logger.debug("article→context resolve failed: %s", e)

    return {
        "context_ids": sorted(context_ids),
        "claim_ids": sorted(claim_ids),
        "document_ids": sorted(doc_ids),
        "article_ids": sorted(article_ids),
        "appraisal_ids": sorted(appraisal_ids),
    }


def _contexts_missing_claims(context_ids: list[int]) -> list[int]:
    if not context_ids:
        return []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id
                    FROM intelligence.contexts c
                    WHERE c.id = ANY(%s)
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.extracted_claims ec
                        WHERE ec.context_id = c.id
                      )
                    ORDER BY c.id
                    """,
                    (context_ids,),
                )
                return [int(r[0]) for r in cur.fetchall() or []]
    except Exception as e:
        logger.debug("contexts_missing_claims: %s", e)
        return []


def _claims_lacking_facts(claim_ids: list[int]) -> list[int]:
    if not claim_ids:
        return []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ec.id
                    FROM intelligence.extracted_claims ec
                    WHERE ec.id = ANY(%s)
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.versioned_facts vf
                        WHERE vf.metadata->>'source_claim_id' = ec.id::text
                           OR COALESCE(vf.metadata->'source_claim_ids', '[]'::jsonb)
                              ? ec.id::text
                      )
                    ORDER BY ec.id
                    """,
                    (claim_ids,),
                )
                return [int(r[0]) for r in cur.fetchall() or []]
    except Exception as e:
        logger.debug("claims_lacking_facts: %s", e)
        return list(claim_ids)


def _docs_lacking_appraisal(document_ids: list[int]) -> list[int]:
    if not document_ids:
        return []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pd.id
                    FROM intelligence.processed_documents pd
                    WHERE pd.id = ANY(%s)
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.claim_evidence_appraisal a
                        WHERE a.document_id = pd.id
                      )
                    ORDER BY pd.id
                    """,
                    (document_ids,),
                )
                return [int(r[0]) for r in cur.fetchall() or []]
    except Exception as e:
        logger.debug("docs_lacking_appraisal: %s", e)
        return list(document_ids)


def _fetch_new_claim_rows(context_ids: list[int], *, limit: int = 40) -> list[dict[str, Any]]:
    if not context_ids:
        return []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, subject_text, predicate_text, object_text, confidence, context_id
                    FROM intelligence.extracted_claims
                    WHERE context_id = ANY(%s)
                    ORDER BY confidence DESC NULLS LAST, id DESC
                    LIMIT %s
                    """,
                    (context_ids, limit),
                )
                cols = [d[0] for d in cur.description or []]
                return [dict(zip(cols, row)) for row in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("fetch claims: %s", e)
        return []


def _fetch_claims_by_ids(claim_ids: list[int], *, limit: int = 40) -> list[dict[str, Any]]:
    if not claim_ids:
        return []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, subject_text, predicate_text, object_text, confidence, context_id
                    FROM intelligence.extracted_claims
                    WHERE id = ANY(%s)
                    ORDER BY confidence DESC NULLS LAST, id DESC
                    LIMIT %s
                    """,
                    (claim_ids, limit),
                )
                cols = [d[0] for d in cur.description or []]
                return [dict(zip(cols, row)) for row in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("fetch claims by id: %s", e)
        return []


def _fetch_facts_for_claims(claim_ids: list[int], *, limit: int = 40) -> list[dict[str, Any]]:
    if not claim_ids:
        return []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, fact_text, metadata, confidence
                    FROM intelligence.versioned_facts
                    WHERE metadata->>'source_claim_id' = ANY(
                            SELECT unnest(%s::int[])::text
                          )
                       OR EXISTS (
                            SELECT 1
                            FROM unnest(%s::int[]) AS cid(id)
                            WHERE COALESCE(metadata->'source_claim_ids', '[]'::jsonb)
                                  ? cid.id::text
                          )
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (claim_ids, claim_ids, limit),
                )
                cols = [d[0] for d in cur.description or []]
                rows = [dict(zip(cols, row)) for row in (cur.fetchall() or [])]
                for r in rows:
                    meta = r.get("metadata") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except json.JSONDecodeError:
                            meta = {}
                    r["source_claim_id"] = meta.get("source_claim_id")
                    r["subject_text"] = None
                    r["predicate_text"] = None
                    r["object_text"] = r.get("fact_text")
                return rows
    except Exception as e:
        logger.debug("fetch facts: %s", e)
        return []


def _fetch_appraisals_for_docs(document_ids: list[int], *, limit: int = 40) -> list[dict[str, Any]]:
    if not document_ids:
        return []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.id, a.document_id, a.domain_key, a.finding_text,
                           a.evidence_grade, a.paper_support, pd.source_url
                    FROM intelligence.claim_evidence_appraisal a
                    LEFT JOIN intelligence.processed_documents pd ON pd.id = a.document_id
                    WHERE a.document_id = ANY(%s)
                    ORDER BY a.id DESC
                    LIMIT %s
                    """,
                    (document_ids, limit),
                )
                cols = [d[0] for d in cur.description or []]
                return [dict(zip(cols, row)) for row in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("fetch appraisals: %s", e)
        return []


async def run_research_spine(package: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic package-scoped spine before LLM assembly.

    Does not drain global claim/appraisal backlogs.
    """
    from services.claim_extraction_service import (
        extract_claims_for_context,
        promote_claims_to_versioned_facts,
    )

    scope = _collect_package_scope_ids(package)
    gaps: list[str] = []
    stats: dict[str, Any] = {
        "claims_extracted": 0,
        "contexts_extracted": 0,
        "facts_promoted": 0,
        "appraisals_inserted": 0,
        "appraisal_skipped": False,
        "replication_updated": 0,
        "new_claim_ids": [],
        "new_fact_ids": [],
        "new_appraisal_ids": [],
    }

    missing_ctx = _contexts_missing_claims(scope["context_ids"])
    for cid in missing_ctx[:12]:
        try:
            n = await extract_claims_for_context(cid)
            stats["contexts_extracted"] += 1
            stats["claims_extracted"] += int(n or 0)
        except Exception as e:
            logger.warning("research spine extract context=%s: %s", cid, e)
            gaps.append(f"claim_extract_failed:{cid}")

    # Refresh claim ids from package contexts after extract
    claim_ids = list(scope["claim_ids"])
    if scope["context_ids"]:
        for row in _fetch_new_claim_rows(scope["context_ids"], limit=80):
            try:
                claim_ids.append(int(row["id"]))
            except (TypeError, ValueError, KeyError):
                pass
    claim_ids = sorted(set(claim_ids))

    unpromoted = _claims_lacking_facts(claim_ids)
    if unpromoted:
        try:
            promo = promote_claims_to_versioned_facts(
                claim_ids=unpromoted,
                limit=max(len(unpromoted), 1),
            )
            stats["facts_promoted"] = int(promo.get("promoted") or 0)
            if int(promo.get("unresolved_subject") or 0) > 0:
                gaps.append(
                    f"unresolved_subjects:{int(promo.get('unresolved_subject') or 0)}"
                )
        except Exception as e:
            logger.warning("research spine promote failed: %s", e)
            gaps.append("promote_failed")

    facts = _fetch_facts_for_claims(claim_ids, limit=40)
    stats["new_fact_ids"] = [int(f["id"]) for f in facts if f.get("id") is not None]
    stats["new_claim_ids"] = claim_ids[:40]

    still_missing_facts = _claims_lacking_facts(claim_ids)
    if still_missing_facts:
        gaps.append(f"claims_lacking_facts:{len(still_missing_facts)}")

    docs_missing = _docs_lacking_appraisal(scope["document_ids"])
    if docs_missing:
        from services.claim_evidence_appraisal_service import (
            is_enabled as appraisal_enabled,
            run_claim_evidence_appraisal_for_documents_async,
        )

        if not appraisal_enabled():
            stats["appraisal_skipped"] = True
            gaps.append(f"appraisal_disabled_docs:{len(docs_missing)}")
        else:
            domains = list(package.get("domain_keys") or [])
            dk = domains[0] if domains else None
            try:
                ap = await run_claim_evidence_appraisal_for_documents_async(
                    docs_missing[:8], domain_key=dk
                )
                stats["appraisals_inserted"] = int(ap.get("inserted") or 0)
                stats["new_appraisal_ids"] = list(ap.get("appraisal_ids") or [])
            except Exception as e:
                logger.warning("research spine appraisal failed: %s", e)
                gaps.append("appraisal_failed")

    # Replication status for package appraisals when available
    appraisal_ids = list(scope["appraisal_ids"]) + list(stats["new_appraisal_ids"])
    if scope["document_ids"]:
        for row in _fetch_appraisals_for_docs(scope["document_ids"], limit=40):
            try:
                appraisal_ids.append(int(row["id"]))
            except (TypeError, ValueError, KeyError):
                pass
    appraisal_ids = sorted(set(appraisal_ids))
    if appraisal_ids:
        try:
            from services.claim_similarity_service import update_appraisal_replication_status

            for aid in appraisal_ids[:15]:
                try:
                    update_appraisal_replication_status(aid)
                    stats["replication_updated"] += 1
                except Exception:
                    pass
        except Exception as e:
            logger.debug("replication update skipped: %s", e)

    still_missing_docs = _docs_lacking_appraisal(scope["document_ids"])
    if still_missing_docs and not stats["appraisal_skipped"]:
        gaps.append(f"docs_lacking_appraisal:{len(still_missing_docs)}")

    return {"scope": scope, "gaps": gaps, "stats": stats}


def _collect_search_candidates(
    package: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    from services.editorial_package_service import search_attachable

    title = str(package.get("working_title") or "").strip()
    summary = str(package.get("summary_stub") or "").strip()
    query = " ".join(x for x in (title, summary[:120]) if x).strip()
    if len(query) < 2:
        query = title or "research"
    domains = list(package.get("domain_keys") or []) or None
    try:
        result = search_attachable(
            modal="research",
            q=query[:200],
            domains=domains,
            limit=limit,
        )
    except Exception as e:
        logger.debug("research search_attachable failed: %s", e)
        return []
    hits = result.get("hits") or []
    out: list[dict[str, Any]] = []
    for h in hits:
        mt = str(h.get("member_type") or "")
        if mt not in RESEARCH_MEMBER_TYPES:
            continue
        try:
            mid = int(h["member_id"])
        except (KeyError, TypeError, ValueError):
            continue
        dk = h.get("domain_key")
        key = _candidate_key(mt, mid, str(dk) if dk else None)
        out.append(
            {
                "candidate_key": key,
                "member_type": mt,
                "member_id": mid,
                "member_family": "research",
                "domain_key": dk,
                "role": h.get("role") or "supporting",
                "label": h.get("label"),
                "provenance": h.get("provenance") or {},
                "source": "search",
            }
        )
    return out


def _spine_candidates(
    spine: dict[str, Any],
    *,
    default_domain: str | None = None,
) -> list[dict[str, Any]]:
    """Turn newly created / package-linked claim/fact/appraisal rows into candidates."""
    out: list[dict[str, Any]] = []
    stats = spine.get("stats") or {}
    scope = spine.get("scope") or {}
    fallback_dk = (default_domain or "").strip() or None

    claim_ids = list(stats.get("new_claim_ids") or scope.get("claim_ids") or [])
    claim_rows = _fetch_claims_by_ids(claim_ids, limit=40)
    if not claim_rows and scope.get("context_ids"):
        claim_rows = _fetch_new_claim_rows(list(scope.get("context_ids") or []), limit=40)
    for row in claim_rows:
        try:
            mid = int(row["id"])
        except (TypeError, ValueError, KeyError):
            continue
        dk = (str(row.get("domain_key") or "").strip() or fallback_dk)
        key = _candidate_key("extracted_claim", mid, dk)
        quote = " ".join(
            str(x)
            for x in (row.get("subject_text"), row.get("predicate_text"), row.get("object_text"))
            if x
        )[:400]
        out.append(
            {
                "candidate_key": key,
                "member_type": "extracted_claim",
                "member_id": mid,
                "member_family": "research",
                "domain_key": dk,
                "role": "supporting",
                "label": quote[:120] or f"claim:{mid}",
                "provenance": {
                    "quote": quote or None,
                    "context_id": row.get("context_id"),
                    "confidence": row.get("confidence"),
                },
                "source": "spine",
            }
        )

    for row in _fetch_facts_for_claims(claim_ids, limit=40):
        try:
            mid = int(row["id"])
        except (TypeError, ValueError, KeyError):
            continue
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        dk = (
            str(meta.get("domain_key") or row.get("domain_key") or "").strip()
            or fallback_dk
        )
        key = _candidate_key("versioned_fact", mid, dk)
        quote = str(row.get("fact_text") or row.get("object_text") or "")[:400]
        out.append(
            {
                "candidate_key": key,
                "member_type": "versioned_fact",
                "member_id": mid,
                "member_family": "research",
                "domain_key": dk,
                "role": "core_claim",
                "label": quote[:120] or f"fact:{mid}",
                "provenance": {
                    "quote": quote or None,
                    "source_claim_id": row.get("source_claim_id"),
                },
                "source": "spine",
            }
        )

    doc_ids = list(scope.get("document_ids") or [])
    for row in _fetch_appraisals_for_docs(doc_ids, limit=40):
        try:
            mid = int(row["id"])
        except (TypeError, ValueError, KeyError):
            continue
        dk = (str(row.get("domain_key") or "").strip() or fallback_dk)
        key = _candidate_key("claim_evidence_appraisal", mid, dk)
        finding = str(row.get("finding_text") or "")[:400]
        out.append(
            {
                "candidate_key": key,
                "member_type": "claim_evidence_appraisal",
                "member_id": mid,
                "member_family": "research",
                "domain_key": dk,
                "role": "supporting",
                "label": finding[:120] or f"appraisal:{mid}",
                "provenance": {
                    "quote": finding or None,
                    "source_url": row.get("source_url"),
                    "document_id": row.get("document_id"),
                    "evidence_grade": row.get("evidence_grade"),
                    "paper_support": row.get("paper_support"),
                },
                "source": "spine",
            }
        )
    return out


def build_research_payload(
    package: dict[str, Any],
    *,
    spine: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact payload for LLM: members, candidates, gaps, uncoupled history."""
    members = list(package.get("members") or [])
    links = list(package.get("links") or [])
    active = [m for m in members if m.get("status") == "active"]
    uncoupled = [
        m
        for m in members
        if m.get("status") in ("removed", "quarantined")
        and (
            m.get("member_type") in RESEARCH_MEMBER_TYPES
            or m.get("member_family") == "research"
        )
    ]

    lim = candidate_limit()
    search_cands = _collect_search_candidates(package, limit=lim)
    spine = spine or {"gaps": [], "stats": {}, "scope": _collect_package_scope_ids(package)}
    spine_cands = _spine_candidates(
        spine, default_domain=_package_default_domain(package)
    )

    active_keys: set[str] = set()
    for m in active:
        mt = str(m.get("member_type") or "")
        try:
            mid = int(m["member_id"])
        except (TypeError, ValueError, KeyError):
            continue
        active_keys.add(_candidate_key(mt, mid, m.get("domain_key")))

    uncoupled_keys: set[str] = set()
    uncoupled_hist: list[dict[str, Any]] = []
    for m in uncoupled:
        mt = str(m.get("member_type") or "")
        try:
            mid = int(m["member_id"])
        except (TypeError, ValueError, KeyError):
            continue
        key = _candidate_key(mt, mid, m.get("domain_key"))
        uncoupled_keys.add(key)
        uncoupled_hist.append(
            {
                "candidate_key": key,
                "member_row_id": m.get("id"),
                "member_type": mt,
                "member_id": mid,
                "status": m.get("status"),
                "label": m.get("display_label"),
            }
        )

    candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set(active_keys)
    # Prefer facts (spine) before search hits
    for c in spine_cands + search_cands:
        key = c["candidate_key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        c = {**c, "was_uncoupled": key in uncoupled_keys}
        candidates.append(c)
        if len(candidates) >= lim:
            break

    member_rows = []
    for m in active:
        mt = str(m.get("member_type") or "")
        if mt not in RESEARCH_MEMBER_TYPES and m.get("member_family") != "research":
            continue
        if m.get("member_id") is None:
            continue
        member_rows.append(
            {
                "member_row_id": int(m["id"]),
                "member_type": mt,
                "member_id": m.get("member_id"),
                "domain_key": m.get("domain_key"),
                "role": m.get("role"),
                "display_label": m.get("display_label"),
                "candidate_key": _candidate_key(mt, int(m["member_id"]), m.get("domain_key")),
                "provenance": {
                    k: _as_dict(m.get("provenance")).get(k)
                    for k in ("quote", "source_url", "label", "context_id", "document_id")
                    if _as_dict(m.get("provenance")).get(k) is not None
                },
            }
        )

    link_rows = []
    for ln in links:
        if ln.get("status") != "active":
            continue
        link_rows.append(
            {
                "link_id": int(ln["id"]),
                "from_member_id": ln.get("from_member_id"),
                "to_member_id": ln.get("to_member_id"),
                "link_type": ln.get("link_type"),
                "inference_stage": ln.get("inference_stage"),
            }
        )

    scope = spine.get("scope") or {}
    return {
        "package_id": package.get("id"),
        "working_title": package.get("working_title"),
        "summary_stub": package.get("summary_stub"),
        "domain_keys": list(package.get("domain_keys") or []),
        "presentation_kind": package.get("presentation_kind"),
        "readiness": package.get("readiness"),
        "members": member_rows,
        "links": link_rows,
        "candidates": candidates,
        "uncoupled_history": uncoupled_hist,
        "gaps": list(spine.get("gaps") or []),
        "scope": {
            "context_ids": scope.get("context_ids") or [],
            "claim_ids": scope.get("claim_ids") or [],
            "document_ids": scope.get("document_ids") or [],
            "article_ids": scope.get("article_ids") or [],
        },
        "spine_stats": spine.get("stats") or {},
    }


def _resolve_ref(
    ref: str,
    *,
    member_by_row: dict[int, dict[str, Any]],
    candidate_by_key: dict[str, dict[str, Any]],
    attached_keys: dict[str, int],
) -> tuple[str, Any] | None:
    raw = (ref or "").strip()
    if raw.startswith("member:"):
        try:
            rid = int(raw.split(":", 1)[1])
        except (IndexError, ValueError):
            return None
        if rid in member_by_row or rid in attached_keys.values():
            return ("member_row", rid)
        return None
    if raw.startswith("candidate:"):
        key = raw[len("candidate:") :]
        if key in attached_keys:
            return ("member_row", attached_keys[key])
        cand = candidate_by_key.get(key)
        if cand:
            return ("candidate", cand)
        return None
    if raw in attached_keys:
        return ("member_row", attached_keys[raw])
    if raw in candidate_by_key:
        return ("candidate", candidate_by_key[raw])
    return None


def validate_research_payload(
    raw: dict[str, Any] | None,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Coerce LLM output. Drop unknown IDs; require citeable provenance for new
    attaches; protect uncoupled history unless high-confidence + citeable.
    """
    if not isinstance(raw, dict):
        return {
            "summary_stub": None,
            "working_title": None,
            "insufficient_evidence": True,
            "gaps": ["empty LLM payload"],
            "attach": [],
            "role_updates": [],
            "links": [],
            "rejected": ["empty_payload"],
        }

    candidates = {c["candidate_key"]: c for c in payload.get("candidates") or []}
    members = {
        int(m["member_row_id"]): m
        for m in payload.get("members") or []
        if m.get("member_row_id")
    }
    uncoupled = {
        h["candidate_key"]: h
        for h in (payload.get("uncoupled_history") or [])
        if h.get("candidate_key")
    }

    rejected: list[str] = []
    attach: list[dict[str, Any]] = []
    seen_attach: set[str] = set()
    for item in raw.get("attach") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("candidate_key") or "").strip()
        if not key or key not in candidates or key in seen_attach:
            if key:
                rejected.append(f"attach_unknown:{key}")
            continue
        cand = candidates[key]
        if cand.get("member_type") not in RESEARCH_MEMBER_TYPES:
            rejected.append(f"attach_type:{key}")
            continue
        role = str(item.get("role") or "supporting").strip().lower()
        if role not in _VALID_ROLES:
            role = "supporting"
        try:
            conf = float(item.get("confidence") if item.get("confidence") is not None else 0.5)
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(1.0, conf))

        prov = cand.get("provenance") or {}
        if not provenance_has_citeable_source(prov):
            rejected.append(f"not_citeable:{key}")
            continue

        if key in uncoupled:
            if conf < _REATTACH_MIN_CONF or not provenance_has_citeable_source(prov):
                rejected.append(f"reattach_blocked:{key}")
                continue

        seen_attach.add(key)
        attach.append(
            {
                "candidate_key": key,
                "role": role,
                "confidence": conf,
                "reason": str(item.get("reason") or "")[:500],
                "candidate": cand,
            }
        )

    role_updates: list[dict[str, Any]] = []
    for item in raw.get("role_updates") or []:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item.get("member_row_id"))
        except (TypeError, ValueError):
            continue
        if rid not in members:
            rejected.append(f"role_unknown:{rid}")
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in _VALID_ROLES:
            rejected.append(f"role_invalid:{rid}")
            continue
        try:
            conf = float(item.get("confidence") if item.get("confidence") is not None else 0.5)
        except (TypeError, ValueError):
            conf = 0.5
        role_updates.append(
            {
                "member_row_id": rid,
                "role": role,
                "confidence": max(0.0, min(1.0, conf)),
                "reason": str(item.get("reason") or "")[:500],
            }
        )

    pending_keys = {a["candidate_key"] for a in attach}
    member_by_key = {
        m["candidate_key"]: int(m["member_row_id"])
        for m in members.values()
        if m.get("candidate_key")
    }

    links: list[dict[str, Any]] = []
    for item in raw.get("links") or []:
        if not isinstance(item, dict):
            continue
        link_type = str(item.get("link_type") or "").strip().lower()
        if link_type not in _RESEARCH_LINK_TYPES:
            rejected.append(f"link_type_invalid:{link_type}")
            continue
        stage = str(item.get("inference_stage") or "hypothesized").strip().lower()
        if stage not in INFERENCE_STAGES:
            stage = "hypothesized"
        from_r = _resolve_ref(
            str(item.get("from_ref") or ""),
            member_by_row=members,
            candidate_by_key=candidates,
            attached_keys=member_by_key,
        )
        to_r = _resolve_ref(
            str(item.get("to_ref") or ""),
            member_by_row=members,
            candidate_by_key=candidates,
            attached_keys=member_by_key,
        )
        if not from_r or not to_r:
            rejected.append("link_endpoint_unknown")
            continue
        skip_link = False
        for label, resolved in (("from", from_r), ("to", to_r)):
            if resolved[0] == "candidate":
                key = resolved[1]["candidate_key"]
                if key not in pending_keys and key not in member_by_key:
                    rejected.append(f"link_{label}_not_attached:{key}")
                    skip_link = True
                    break
        if skip_link:
            continue
        if from_r[0] == "member_row" and to_r[0] == "member_row" and int(from_r[1]) == int(
            to_r[1]
        ):
            rejected.append("link_self")
            continue
        if (
            from_r[0] == "candidate"
            and to_r[0] == "candidate"
            and from_r[1].get("candidate_key") == to_r[1].get("candidate_key")
        ):
            rejected.append("link_self")
            continue
        try:
            conf = float(item.get("confidence") if item.get("confidence") is not None else 0.5)
        except (TypeError, ValueError):
            conf = 0.5
        links.append(
            {
                "from_ref": from_r,
                "to_ref": to_r,
                "link_type": link_type,
                "inference_stage": stage,
                "confidence": max(0.0, min(1.0, conf)),
                "reason": str(item.get("reason") or "")[:500],
            }
        )

    summary_stub = raw.get("summary_stub")
    if summary_stub is not None:
        summary_stub = str(summary_stub).strip()[:4000] or None
    working_title = raw.get("working_title")
    if working_title is not None:
        working_title = str(working_title).strip()[:500] or None

    insufficient = bool(raw.get("insufficient_evidence"))
    gaps = [str(g)[:300] for g in (raw.get("gaps") or []) if g][:20]
    for g in payload.get("gaps") or []:
        gs = str(g)[:300]
        if gs and gs not in gaps:
            gaps.append(gs)

    has_core = (
        any(a["role"] == "core_claim" for a in attach)
        or any(r["role"] == "core_claim" for r in role_updates)
        or any(
            (m.get("role") == "core_claim" or m.get("member_type") in _CLAIMISH)
            for m in members.values()
        )
    )
    if not has_core and not attach:
        insufficient = True
        if not gaps:
            gaps.append("no_core_claim")

    return {
        "summary_stub": summary_stub,
        "working_title": working_title,
        "insufficient_evidence": insufficient,
        "gaps": gaps[:20],
        "attach": attach,
        "role_updates": role_updates,
        "links": links,
        "rejected": rejected,
    }


_validate_research_payload = validate_research_payload


def _deterministic_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    """When LLM fails: attach top citeable fact/claim/appraisal candidates."""
    attach: list[dict[str, Any]] = []
    preferred = ("versioned_fact", "claim_evidence_appraisal", "extracted_claim", "hypothesis")
    cands = [
        c
        for c in (payload.get("candidates") or [])
        if not c.get("was_uncoupled")
        and provenance_has_citeable_source(c.get("provenance") or {})
    ]
    cands.sort(
        key=lambda c: (
            preferred.index(c["member_type"])
            if c.get("member_type") in preferred
            else 99
        )
    )
    for i, c in enumerate(cands[:5]):
        attach.append(
            {
                "candidate_key": c["candidate_key"],
                "role": "core_claim" if i == 0 and c.get("member_type") in _CLAIMISH else "supporting",
                "confidence": 0.55,
                "reason": "deterministic:spine/search fallback",
            }
        )
    role_updates: list[dict[str, Any]] = []
    if not attach:
        for m in payload.get("members") or []:
            if m.get("member_type") in _CLAIMISH:
                role_updates.append(
                    {
                        "member_row_id": m["member_row_id"],
                        "role": "core_claim",
                        "confidence": 0.6,
                        "reason": "deterministic:existing claimish as core",
                    }
                )
                break
    return {
        "summary_stub": payload.get("summary_stub")
        or payload.get("working_title")
        or "Research assembly fallback — review members.",
        "working_title": None,
        "insufficient_evidence": not attach and not role_updates,
        "gaps": ["llm_unavailable"] if not attach and not role_updates else list(
            payload.get("gaps") or []
        )[:5],
        "attach": attach,
        "role_updates": role_updates,
        "links": [],
    }


async def _call_research_llm(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    prompt = (
        f"{_load_prompt()}\n\n"
        f"## Package to assemble\n"
        f"```json\n{json.dumps(payload, default=str)[:100_000]}\n```\n"
    )
    try:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.STRUCTURED_EXTRACTION,
            urgency="standard",
            approx_prompt_chars=len(prompt),
        )
        return _parse_json_object(result.text), getattr(result, "model", None)
    except Exception as e:
        logger.warning(
            "research LLM failed package_id=%s: %s", payload.get("package_id"), e
        )
        return None, None


def _apply_research(
    package_id: int,
    validated: dict[str, Any],
    *,
    package: dict[str, Any],
    dry_run: bool,
) -> dict[str, int]:
    from services.editorial_package_service import (
        add_link,
        add_member,
        get_package,
        update_package,
    )

    counts = {
        "attached": 0,
        "role_updated": 0,
        "links_added": 0,
        "summary_updated": 0,
        "kind_updated": 0,
        "title_updated": 0,
    }
    if dry_run or not auto_apply_enabled():
        counts["attached"] = len(validated.get("attach") or [])
        counts["role_updated"] = len(validated.get("role_updates") or [])
        counts["links_added"] = len(validated.get("links") or [])
        if validated.get("summary_stub"):
            counts["summary_updated"] = 1
        if validated.get("working_title"):
            counts["title_updated"] = 1
        return counts

    key_to_row: dict[str, int] = {}
    for m in package.get("members") or []:
        if m.get("status") != "active" or m.get("member_id") is None:
            continue
        try:
            key = _candidate_key(
                str(m.get("member_type")),
                int(m["member_id"]),
                m.get("domain_key"),
            )
            key_to_row[key] = int(m["id"])
        except (TypeError, ValueError):
            continue

    for a in validated.get("attach") or []:
        cand = a["candidate"]
        try:
            dk = cand.get("domain_key") or _package_default_domain(package)
            member = add_member(
                package_id,
                member_type=cand["member_type"],
                member_id=int(cand["member_id"]),
                member_family="research",
                domain_key=dk,
                role=a.get("role") or "supporting",
                added_by_modal="research",
                added_by="research_llm",
                provenance={
                    **(cand.get("provenance") or {}),
                    "research_reason": a.get("reason"),
                    "research_confidence": a.get("confidence"),
                },
                actor="research_llm",
            )
            key_to_row[a["candidate_key"]] = int(member["id"])
            counts["attached"] += 1
        except Exception as e:
            logger.warning("research attach failed %s: %s", a.get("candidate_key"), e)

    for ru in validated.get("role_updates") or []:
        row_id = int(ru["member_row_id"])
        src = None
        for m in package.get("members") or []:
            if int(m.get("id") or 0) == row_id:
                src = m
                break
        if not src:
            continue
        try:
            add_member(
                package_id,
                member_type=str(src["member_type"]),
                member_id=int(src["member_id"]),
                member_family=str(src.get("member_family") or "research"),
                domain_key=src.get("domain_key") or _package_default_domain(package),
                role=ru["role"],
                added_by_modal="research",
                added_by="research_llm",
                provenance=_as_dict(src.get("provenance")),
                actor="research_llm",
            )
            counts["role_updated"] += 1
        except Exception as e:
            logger.warning("research role update failed row=%s: %s", row_id, e)

    refreshed = get_package(package_id, include=True) or package
    key_to_row = {}
    row_ids: set[int] = set()
    for m in refreshed.get("members") or []:
        if m.get("status") != "active" or m.get("member_id") is None:
            continue
        try:
            rid = int(m["id"])
            row_ids.add(rid)
            key = _candidate_key(
                str(m.get("member_type")),
                int(m["member_id"]),
                m.get("domain_key"),
            )
            key_to_row[key] = rid
        except (TypeError, ValueError):
            continue

    def _row_from_ref(ref: tuple[str, Any]) -> int | None:
        kind, val = ref
        if kind == "member_row":
            rid = int(val)
            return rid if rid in row_ids or rid > 0 else None
        if kind == "candidate" and isinstance(val, dict):
            return key_to_row.get(val["candidate_key"])
        return None

    existing_pairs: set[tuple[int, int, str]] = set()
    for ln in refreshed.get("links") or []:
        if ln.get("status") != "active":
            continue
        try:
            existing_pairs.add(
                (
                    int(ln["from_member_id"]),
                    int(ln["to_member_id"]),
                    str(ln.get("link_type")),
                )
            )
        except (TypeError, ValueError, KeyError):
            continue

    for link in validated.get("links") or []:
        frm = _row_from_ref(link["from_ref"])
        to = _row_from_ref(link["to_ref"])
        if frm is None or to is None or frm == to:
            continue
        lt = link["link_type"]
        if (frm, to, lt) in existing_pairs or (to, frm, lt) in existing_pairs:
            continue
        evidence = {
            "reason": link.get("reason"),
            "confidence": link.get("confidence"),
            "source": "research_pass",
        }
        try:
            add_link(
                package_id,
                from_member_id=frm,
                to_member_id=to,
                link_type=lt,
                evidence=evidence,
                inference_stage=link.get("inference_stage") or "hypothesized",
                actor="research_llm",
                modal="research",
            )
            existing_pairs.add((frm, to, lt))
            counts["links_added"] += 1
        except Exception as e:
            logger.warning("research link failed: %s", e)

    readiness = _as_dict(refreshed.get("readiness"))
    kind = "research_brief"
    if readiness.get("research_brief_ready") and readiness.get("event_narrative_ready"):
        kind = "hybrid"
    elif refreshed.get("presentation_kind") == "hybrid":
        kind = "hybrid"

    upd_kwargs: dict[str, Any] = {
        "primary_modal": "research",
        "actor": "research_llm",
        "modal": "research",
        "rationale": "research_pass",
    }
    if validated.get("summary_stub"):
        upd_kwargs["summary_stub"] = validated["summary_stub"]
        counts["summary_updated"] = 1
    if validated.get("working_title"):
        upd_kwargs["working_title"] = validated["working_title"]
        counts["title_updated"] = 1
    if refreshed.get("presentation_kind") in (None, "unset", "") or kind != refreshed.get(
        "presentation_kind"
    ):
        upd_kwargs["presentation_kind"] = kind
        counts["kind_updated"] = 1

    if any(k in upd_kwargs for k in ("summary_stub", "working_title", "presentation_kind")):
        try:
            update_package(package_id, **upd_kwargs)
        except Exception as e:
            logger.warning("research update_package failed: %s", e)

    return counts


def resolve_research_route(
    *,
    changed: int,
    meta: dict[str, Any],
    round_n: int,
    max_r: int | None = None,
) -> str:
    """
    Return route target: 'reduction' | 'editor' | 'stay'.

    Escape: both Research and Reduction consecutive zero-change → editor.
    Max rounds → editor. Changes → reduction. Zero without prior Reduction → reduction.
    """
    max_r = max_r if max_r is not None else max_rounds()
    if round_n >= max_r:
        return "editor"
    if changed > 0:
        return "reduction"
    red_rounds = int(meta.get("reduction_rounds") or 0)
    last_red = meta.get("last_reduction_removed_count")
    try:
        last_red_n = int(last_red) if last_red is not None else None
    except (TypeError, ValueError):
        last_red_n = None
    if red_rounds >= 1 and last_red_n == 0:
        return "editor"
    return "reduction"


async def run_research_pass(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if not is_enabled() and not force:
        return {
            "skipped": True,
            "reason": "EDITORIAL_RESEARCH_ENABLED=false",
            "package_id": package_id,
        }

    from services.editorial_package_service import get_package, mark_ready_for_editor
    from services.modal_handoff_service import request_rework

    pkg = get_package(package_id, include=True)
    if not pkg:
        return {"ok": False, "error": "not_found", "package_id": package_id}

    status = str(pkg.get("status") or "")
    if status != "in_research" and not force:
        return {
            "skipped": True,
            "reason": f"status={status} (expected in_research)",
            "package_id": package_id,
        }

    meta = _as_dict(pkg.get("metadata"))
    prior_rounds = int(meta.get("research_rounds") or 0)
    if prior_rounds >= max_rounds() and not force and not dry_run:
        mark_ready_for_editor(
            package_id,
            from_modal="research",
            actor="research_llm",
            rationale=f"research max rounds ({max_rounds()}) — escape to editor",
        )
        _append_summary_decision(
            package_id,
            action="converged",
            rationale="max_rounds escape to editor",
            metadata={"round": prior_rounds, "escape": "max_rounds"},
        )
        return {
            "ok": True,
            "package_id": package_id,
            "skipped": False,
            "converged": True,
            "route_target": "editor",
            "changed": 0,
            "reason": "max_rounds_reached",
        }

    spine = await run_research_spine(pkg)
    # Refresh package after spine may have created attachable rows
    pkg = get_package(package_id, include=True) or pkg
    payload = build_research_payload(pkg, spine=spine)
    parsed, model = await _call_research_llm(payload)
    used_fallback = False
    if not parsed:
        used_fallback = True
        parsed = _deterministic_fallback(payload)

    validated = validate_research_payload(parsed, payload=payload)

    if validated.get("insufficient_evidence") and not validated.get("attach") and not validated.get(
        "role_updates"
    ):
        # Still count a round so thin packages escape to Editor at max_rounds
        # instead of cycling forever with research_rounds stuck at 0.
        round_n = prior_rounds + (0 if dry_run else 1)
        if not dry_run:
            _merge_package_metadata(
                package_id,
                {
                    "research_rounds": round_n,
                    "last_research_change_count": 0,
                    "last_research_insufficient": True,
                    "last_research_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            _append_summary_decision(
                package_id,
                action="research_pass",
                rationale="insufficient_evidence — staying in_research",
                metadata={
                    "gaps": validated.get("gaps"),
                    "rejected": validated.get("rejected"),
                    "used_fallback": used_fallback,
                    "spine": spine.get("stats"),
                    "research_rounds": round_n,
                },
                model=model,
            )
            if round_n >= max_rounds():
                mark_ready_for_editor(
                    package_id,
                    from_modal="research",
                    actor="research_llm",
                    rationale=(
                        f"research max rounds ({max_rounds()}) after "
                        "insufficient_evidence — escape to editor"
                    ),
                )
                _append_summary_decision(
                    package_id,
                    action="converged",
                    rationale="max_rounds escape to editor (insufficient_evidence)",
                    metadata={"round": round_n, "escape": "max_rounds"},
                )
                return {
                    "ok": True,
                    "package_id": package_id,
                    "insufficient_evidence": True,
                    "gaps": validated.get("gaps"),
                    "route_target": "editor",
                    "changed": 0,
                    "converged": True,
                    "reason": "max_rounds_reached",
                    "research_rounds": round_n,
                    "used_fallback": used_fallback,
                    "model": model,
                    "prompt_version": PROMPT_VERSION,
                    "spine": spine.get("stats"),
                }
        return {
            "ok": True,
            "package_id": package_id,
            "insufficient_evidence": True,
            "gaps": validated.get("gaps"),
            "route_target": "stay",
            "changed": 0,
            "research_rounds": round_n,
            "used_fallback": used_fallback,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "spine": spine.get("stats"),
            "validated": {
                "attach": validated.get("attach"),
                "links": [
                    {"link_type": ln.get("link_type"), "reason": ln.get("reason")}
                    for ln in (validated.get("links") or [])
                ],
            },
        }

    apply_dry = dry_run or not auto_apply_enabled()
    counts = _apply_research(package_id, validated, package=pkg, dry_run=apply_dry)
    changed = (
        counts["attached"]
        + counts["role_updated"]
        + counts["links_added"]
        + counts["summary_updated"]
        + counts["kind_updated"]
        + counts["title_updated"]
    )
    round_n = prior_rounds + (0 if apply_dry else 1)
    route_target: str | None = None
    routed: dict[str, Any] | None = None

    if not apply_dry:
        patch = {
            "research_rounds": round_n,
            "last_research_change_count": changed,
            "last_research_at": datetime.now(timezone.utc).isoformat(),
        }
        _merge_package_metadata(package_id, patch)
        meta_after = {**meta, **patch}
        route_target = resolve_research_route(
            changed=changed, meta=meta_after, round_n=round_n
        )

        _append_summary_decision(
            package_id,
            action="research_pass",
            rationale=validated.get("summary_stub")
            or f"research pass round {round_n}",
            metadata={
                "round": round_n,
                "counts": counts,
                "changed": changed,
                "rejected": validated.get("rejected"),
                "gaps": validated.get("gaps"),
                "used_fallback": used_fallback,
                "route_target": route_target,
                "spine": spine.get("stats"),
            },
            model=model,
        )

        if route_target == "editor":
            _append_summary_decision(
                package_id,
                action="converged",
                rationale="research↔reduction escape — both zero-change or max rounds",
                metadata={
                    "round": round_n,
                    "changed": changed,
                    "last_reduction_removed_count": meta.get(
                        "last_reduction_removed_count"
                    ),
                },
                model=model,
            )
            try:
                routed = mark_ready_for_editor(
                    package_id,
                    from_modal="research",
                    actor="research_llm",
                    rationale="cycle escape → editor",
                )
            except Exception as e:
                logger.warning("research escape to editor failed: %s", e)
                routed = {"error": str(e)}
        elif route_target == "reduction":
            try:
                routed = request_rework(
                    package_id,
                    target_modal="reduction",
                    note=f"post-research round {round_n}",
                    actor="research_llm",
                    source_modal="research",
                )
            except Exception as e:
                logger.warning("research→reduction route failed: %s", e)
                routed = {"error": str(e)}

    return {
        "ok": True,
        "package_id": package_id,
        "dry_run": apply_dry,
        "used_fallback": used_fallback,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "summary_stub": validated.get("summary_stub"),
        "counts": counts,
        "changed": changed,
        "research_rounds": round_n if not apply_dry else prior_rounds,
        "route_target": route_target,
        "routed": routed,
        "rejected": validated.get("rejected"),
        "gaps": validated.get("gaps"),
        "spine": spine.get("stats"),
        "candidate_count": len(payload.get("candidates") or []),
    }


def run_research_pass_sync(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    run_research_pass(package_id, dry_run=dry_run, force=force)
                )
            ).result()
    return asyncio.run(run_research_pass(package_id, dry_run=dry_run, force=force))


def list_research_due(*, limit: int = 10) -> list[int]:
    lim = max(1, min(int(limit), 50))
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM intelligence.editorial_packages
                WHERE status = 'in_research'
                  AND COALESCE((metadata->>'research_rounds')::int, 0) < %s
                ORDER BY updated_at ASC, id ASC
                LIMIT %s
                """,
                (max_rounds(), lim),
            )
            return [int(r[0]) for r in cur.fetchall()]


def run_research_batch(*, limit: int | None = None) -> dict[str, Any]:
    if not is_enabled():
        return {
            "skipped": True,
            "reason": "EDITORIAL_RESEARCH_ENABLED=false",
            "processed": 0,
        }
    batch = limit if limit is not None else env_int("EDITORIAL_RESEARCH_BATCH", 5)
    ids = list_research_due(limit=batch)
    results: list[dict[str, Any]] = []
    for pid in ids:
        try:
            results.append(run_research_pass_sync(pid))
        except Exception as e:
            logger.warning("research batch item failed package_id=%s: %s", pid, e)
            results.append({"ok": False, "package_id": pid, "error": str(e)})
    return {
        "processed": len(results),
        "package_ids": ids,
        "results": results,
        "changed_total": sum(int(r.get("changed") or 0) for r in results),
    }


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run editorial research pass")
    parser.add_argument("--package-id", type=int, default=None)
    parser.add_argument("--batch", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.force:
        os.environ["EDITORIAL_RESEARCH_ENABLED"] = "1"
    if args.batch:
        print(json.dumps(run_research_batch(limit=args.batch), indent=2, default=str))
    elif args.package_id:
        print(
            json.dumps(
                run_research_pass_sync(
                    args.package_id, dry_run=args.dry_run, force=args.force
                ),
                indent=2,
                default=str,
            )
        )
    else:
        parser.error("provide --package-id or --batch")
