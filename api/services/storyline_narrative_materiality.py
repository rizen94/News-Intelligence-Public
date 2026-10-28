"""
Evidence materiality gate for storyline narrative finisher (~70B).

Computes a cheap fingerprint of membership + facts + chronological spine + prompt
version. Refresh jobs skip or defer the LLM when the pile has not changed enough
to justify a full rewrite.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import domain_key_to_schema, is_valid_domain_key

logger = logging.getLogger(__name__)

# Keep in sync with storyline_narrative_finisher_service.PROMPT_VERSION
DEFAULT_PROMPT_VERSION = "storyline_walkthrough.v1"


def materiality_gate_enabled() -> bool:
    return os.environ.get("NARRATIVE_FINISHER_MATERIALITY_GATE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def material_article_delta_threshold() -> int:
    try:
        return max(1, int(os.environ.get("NARRATIVE_FINISHER_MATERIAL_ARTICLE_DELTA", "2")))
    except ValueError:
        return 2


def force_narrative_finisher() -> bool:
    return os.environ.get("NARRATIVE_FINISHER_FORCE", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _schema_name(domain_key: str) -> str | None:
    if not is_valid_domain_key(domain_key):
        return None
    try:
        return domain_key_to_schema(domain_key)
    except KeyError:
        return None


def _hash_parts(parts: dict[str, Any]) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _load_membership_parts(cur, schema: str, storyline_id: int) -> dict[str, Any]:
    cur.execute(
        f"""
        SELECT article_id
        FROM {schema}.storyline_articles
        WHERE storyline_id = %s
        ORDER BY article_id ASC
        """,
        (storyline_id,),
    )
    ids = [int(r[0]) for r in cur.fetchall() or [] if r and r[0] is not None]
    ids_fingerprint = _hash_parts({"ids": ids}) if ids else "empty"
    return {
        "article_count": len(ids),
        "article_ids_fp": ids_fingerprint,
    }


def _load_fact_parts(cur, domain_key: str, schema: str, storyline_id: int) -> dict[str, Any]:
    """Aggregate versioned_facts for entities indexed on this storyline."""
    names: list[str] = []
    try:
        cur.execute(
            f"""
            SELECT DISTINCT LOWER(TRIM(entity_name))
            FROM {schema}.story_entity_index
            WHERE storyline_id = %s
              AND entity_name IS NOT NULL
              AND btrim(entity_name) <> ''
            LIMIT 80
            """,
            (storyline_id,),
        )
        names = [r[0] for r in cur.fetchall() or [] if r and r[0]]
    except Exception as e:
        logger.debug("materiality story_entity_index: %s", e)

    if not names:
        try:
            cur.execute(
                f"""
                SELECT DISTINCT LOWER(TRIM(ec.canonical_name))
                FROM {schema}.storyline_articles sa
                JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                WHERE sa.storyline_id = %s
                  AND ec.canonical_name IS NOT NULL
                  AND btrim(ec.canonical_name) <> ''
                LIMIT 80
                """,
                (storyline_id,),
            )
            names = [r[0] for r in cur.fetchall() or [] if r and r[0]]
        except Exception as e:
            logger.debug("materiality article_entities: %s", e)

    if not names:
        return {"fact_count": 0, "fact_max_id": 0}

    try:
        cur.execute(
            """
            SELECT COUNT(*)::int, COALESCE(MAX(vf.id), 0)::bigint
            FROM intelligence.versioned_facts vf
            JOIN intelligence.entity_profiles ep ON ep.id = vf.entity_profile_id
            WHERE ep.domain_key = %s
              AND vf.superseded_by_id IS NULL
              AND LOWER(COALESCE(ep.metadata->>'canonical_name', ep.metadata->>'name', ''))
                  = ANY(%s)
            """,
            (domain_key, names),
        )
        row = cur.fetchone()
        return {
            "fact_count": int(row[0] or 0) if row else 0,
            "fact_max_id": int(row[1] or 0) if row else 0,
        }
    except Exception as e:
        logger.debug("materiality versioned_facts: %s", e)
        return {"fact_count": 0, "fact_max_id": 0}


def _load_chrono_parts(cur, storyline_id: int) -> dict[str, Any]:
    try:
        cur.execute(
            """
            SELECT COUNT(*)::int, COALESCE(MAX(id), 0)::bigint
            FROM public.chronological_events
            WHERE storyline_id = %s
            """,
            (str(storyline_id),),
        )
        row = cur.fetchone()
        return {
            "chrono_count": int(row[0] or 0) if row else 0,
            "chrono_max_id": int(row[1] or 0) if row else 0,
        }
    except Exception as e:
        logger.debug("materiality chronological_events: %s", e)
        return {"chrono_count": 0, "chrono_max_id": 0}


def _load_prior_finisher_state(
    cur, schema: str, storyline_id: int
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """
    Returns (canonical_empty, prior_fingerprint, prior_parts).
    """
    cur.execute(
        f"""
        SELECT
          (canonical_narrative IS NULL OR btrim(canonical_narrative) = ''),
          COALESCE(narrative_finisher_meta, '{{}}'::jsonb)
        FROM {schema}.storylines
        WHERE id = %s
        """,
        (storyline_id,),
    )
    row = cur.fetchone()
    if not row:
        return True, None, None
    canonical_empty = bool(row[0])
    meta = row[1] if isinstance(row[1], dict) else {}
    if isinstance(row[1], str):
        try:
            meta = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            meta = {}
    prior_fp = meta.get("evidence_fingerprint")
    prior_parts = meta.get("evidence_fingerprint_parts")
    if prior_fp is not None:
        prior_fp = str(prior_fp)
    if not isinstance(prior_parts, dict):
        prior_parts = None
    return canonical_empty, prior_fp, prior_parts


def compute_narrative_evidence_fingerprint(
    domain_key: str,
    storyline_id: int,
    *,
    prompt_version: str | None = None,
    conn=None,
) -> dict[str, Any]:
    """
    Cheap evidence fingerprint for materiality gating.

    Returns dict with fingerprint, parts, and optional error.
    """
    pv = (prompt_version or DEFAULT_PROMPT_VERSION).strip() or DEFAULT_PROMPT_VERSION
    schema = _schema_name(domain_key)
    if not schema:
        return {"success": False, "error": "invalid_domain", "fingerprint": "", "parts": {}}

    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db_connection", "fingerprint": "", "parts": {}}

    try:
        with conn.cursor() as cur:
            membership = _load_membership_parts(cur, schema, storyline_id)
            facts = _load_fact_parts(cur, domain_key, schema, storyline_id)
            chrono = _load_chrono_parts(cur, storyline_id)
        parts: dict[str, Any] = {
            "prompt_version": pv,
            **membership,
            **facts,
            **chrono,
        }
        return {
            "success": True,
            "fingerprint": _hash_parts(parts),
            "parts": parts,
        }
    except Exception as e:
        logger.warning(
            "compute_narrative_evidence_fingerprint %s/%s: %s",
            domain_key,
            storyline_id,
            e,
        )
        return {"success": False, "error": str(e), "fingerprint": "", "parts": {}}
    finally:
        if own_conn and conn:
            conn.close()


def _classify_delta(
    prior_parts: dict[str, Any] | None,
    current_parts: dict[str, Any],
    *,
    fingerprint_match: bool,
) -> str:
    """Return unchanged | narrow | material."""
    if fingerprint_match:
        return "unchanged"
    if not prior_parts:
        return "material"

    if str(prior_parts.get("prompt_version") or "") != str(
        current_parts.get("prompt_version") or ""
    ):
        return "material"

    prior_facts = (
        int(prior_parts.get("fact_count") or 0),
        int(prior_parts.get("fact_max_id") or 0),
    )
    curr_facts = (
        int(current_parts.get("fact_count") or 0),
        int(current_parts.get("fact_max_id") or 0),
    )
    if prior_facts != curr_facts:
        return "material"

    prior_articles = int(prior_parts.get("article_count") or 0)
    curr_articles = int(current_parts.get("article_count") or 0)
    article_delta = curr_articles - prior_articles
    prior_ids_fp = str(prior_parts.get("article_ids_fp") or "")
    curr_ids_fp = str(current_parts.get("article_ids_fp") or "")
    membership_changed = prior_ids_fp != curr_ids_fp or article_delta != 0

    prior_chrono = (
        int(prior_parts.get("chrono_count") or 0),
        int(prior_parts.get("chrono_max_id") or 0),
    )
    curr_chrono = (
        int(current_parts.get("chrono_count") or 0),
        int(current_parts.get("chrono_max_id") or 0),
    )
    chrono_changed = prior_chrono != curr_chrono

    threshold = material_article_delta_threshold()
    if membership_changed and article_delta >= threshold:
        return "material"
    if membership_changed and article_delta < 0:
        # Removals / reshuffles can change the frame
        return "material"
    if membership_changed and article_delta >= 1 and curr_facts != prior_facts:
        return "material"

    # Single-article drip and/or chronology-only advance → narrow
    if (membership_changed and 0 < article_delta < threshold) or (
        chrono_changed and not membership_changed
    ):
        return "narrow"
    if membership_changed and article_delta == 0 and prior_ids_fp != curr_ids_fp:
        # Same count, different membership set
        return "material"

    # Fallback: any other mismatch is material
    return "material"


def classify_narrative_materiality(
    domain_key: str,
    storyline_id: int,
    *,
    force: bool = False,
    prompt_version: str | None = None,
    conn=None,
) -> dict[str, Any]:
    """
    Decide whether a narrative_finisher job should run, skip, or defer.

    Returns:
      action: "run" | "skip" | "defer"
      class: "initial" | "unchanged" | "narrow" | "material" | "forced" | "gate_disabled"
      reason, fingerprint, parts, prior_fingerprint
    """
    pv = (prompt_version or DEFAULT_PROMPT_VERSION).strip() or DEFAULT_PROMPT_VERSION
    schema = _schema_name(domain_key)
    if not schema:
        return {
            "action": "run",
            "class": "material",
            "reason": "invalid_domain",
            "fingerprint": "",
            "parts": {},
            "prior_fingerprint": None,
        }

    if force or force_narrative_finisher():
        fp = compute_narrative_evidence_fingerprint(
            domain_key, storyline_id, prompt_version=pv, conn=conn
        )
        return {
            "action": "run",
            "class": "forced",
            "reason": "force",
            "fingerprint": fp.get("fingerprint") or "",
            "parts": fp.get("parts") or {},
            "prior_fingerprint": None,
        }

    if not materiality_gate_enabled():
        fp = compute_narrative_evidence_fingerprint(
            domain_key, storyline_id, prompt_version=pv, conn=conn
        )
        return {
            "action": "run",
            "class": "gate_disabled",
            "reason": "materiality_gate_off",
            "fingerprint": fp.get("fingerprint") or "",
            "parts": fp.get("parts") or {},
            "prior_fingerprint": None,
        }

    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    if not conn:
        return {
            "action": "run",
            "class": "material",
            "reason": "no_db_connection",
            "fingerprint": "",
            "parts": {},
            "prior_fingerprint": None,
        }

    try:
        with conn.cursor() as cur:
            canonical_empty, prior_fp, prior_parts = _load_prior_finisher_state(
                cur, schema, storyline_id
            )

        if canonical_empty:
            fp = compute_narrative_evidence_fingerprint(
                domain_key, storyline_id, prompt_version=pv, conn=conn
            )
            return {
                "action": "run",
                "class": "initial",
                "reason": "empty_canonical",
                "fingerprint": fp.get("fingerprint") or "",
                "parts": fp.get("parts") or {},
                "prior_fingerprint": prior_fp,
            }

        fp = compute_narrative_evidence_fingerprint(
            domain_key, storyline_id, prompt_version=pv, conn=conn
        )
        current_fp = fp.get("fingerprint") or ""
        current_parts = fp.get("parts") or {}
        match = bool(prior_fp) and prior_fp == current_fp
        delta_class = _classify_delta(
            prior_parts, current_parts, fingerprint_match=match
        )

        if delta_class == "unchanged":
            return {
                "action": "skip",
                "class": "unchanged",
                "reason": "fingerprint_match",
                "fingerprint": current_fp,
                "parts": current_parts,
                "prior_fingerprint": prior_fp,
            }
        if delta_class == "narrow":
            return {
                "action": "defer",
                "class": "narrow",
                "reason": "narrow_delta",
                "fingerprint": current_fp,
                "parts": current_parts,
                "prior_fingerprint": prior_fp,
            }
        return {
            "action": "run",
            "class": "material",
            "reason": "material_delta",
            "fingerprint": current_fp,
            "parts": current_parts,
            "prior_fingerprint": prior_fp,
        }
    except Exception as e:
        logger.warning(
            "classify_narrative_materiality %s/%s: %s", domain_key, storyline_id, e
        )
        return {
            "action": "run",
            "class": "material",
            "reason": f"classify_error:{e}",
            "fingerprint": "",
            "parts": {},
            "prior_fingerprint": None,
        }
    finally:
        if own_conn and conn:
            conn.close()


def set_narrow_debt_pending(
    domain_key: str,
    storyline_id: int,
    *,
    pending: bool = True,
    reason: str | None = None,
    conn=None,
) -> bool:
    """
    Mark or clear narrow_debt_pending on narrative_finisher_meta.

    Set when a refresh is deferred as narrow so nightly drain can force a full finish.
    Cleared on successful finisher persist.
    """
    from datetime import datetime, timezone

    schema = _schema_name(domain_key)
    if not schema:
        return False

    patch: dict[str, Any] = {
        "narrow_debt_pending": bool(pending),
    }
    if pending:
        patch["narrow_debt_at"] = datetime.now(timezone.utc).isoformat()
        if reason:
            patch["narrow_debt_reason"] = str(reason)[:200]
    else:
        patch["narrow_debt_at"] = None
        patch["narrow_debt_reason"] = None

    own_conn = conn is None
    if own_conn:
        conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET narrative_finisher_meta =
                      COALESCE(narrative_finisher_meta, '{{}}'::jsonb) || %s::jsonb
                WHERE id = %s
                """,
                (json.dumps(patch), storyline_id),
            )
        if own_conn:
            conn.commit()
        return True
    except Exception as e:
        logger.debug(
            "set_narrow_debt_pending %s/%s: %s", domain_key, storyline_id, e
        )
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        if own_conn and conn:
            conn.close()


def narrow_debt_drain_enabled() -> bool:
    return os.environ.get("NARRATIVE_NARROW_DEBT_DRAIN", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def narrow_debt_min_age_hours() -> float:
    try:
        return max(0.0, float(os.environ.get("NARRATIVE_NARROW_DEBT_MIN_AGE_HOURS", "6")))
    except ValueError:
        return 6.0


def narrow_debt_per_domain_limit() -> int:
    try:
        return max(1, int(os.environ.get("NARRATIVE_NARROW_DEBT_PER_DOMAIN", "4")))
    except ValueError:
        return 4
