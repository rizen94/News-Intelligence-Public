"""
Claim subject gap catalog — unpromoted high-confidence claims whose subjects are not yet in the
entity pool (no matching entity_profile canonical_name, no entity_canonical in that domain).

Refresh builds a research snapshot for operators; seed inserts a placeholder row into
``{domain}.entity_canonical`` and runs ``sync_domain_entity_profiles`` for that domain.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import get_active_domain_keys, is_valid_domain_key, resolve_domain_schema

logger = logging.getLogger(__name__)


def _min_confidence(confidence: float | None) -> float:
    if confidence is not None:
        return float(confidence)
    try:
        from services.claim_extraction_service import get_claims_to_facts_min_confidence

        return float(get_claims_to_facts_min_confidence())
    except Exception:
        return 0.75


def refresh_claim_subject_gap_catalog(
    *,
    min_confidence: float | None = None,
    max_per_domain: int = 2000,
) -> dict[str, Any]:
    """
    Recompute per-domain aggregates of unpromoted claim subjects that lack catalog coverage,
    upsert into ``intelligence.claim_subject_gap_catalog``, and delete rows not touched this run
    (so the table stays aligned with the latest snapshot).

    Returns counts: domains_processed, rows_upserted, rows_deleted_stale.
    """
    conf = _min_confidence(min_confidence)
    try:
        cap = max(100, min(50_000, int(max_per_domain)))
    except (TypeError, ValueError):
        cap = 2000

    ts = datetime.now(timezone.utc)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db", "domains_processed": 0, "rows_upserted": 0, "rows_deleted_stale": 0}

    upserted_total = 0
    domains_processed = 0
    try:
        with conn.cursor() as cur:
            for domain_key in get_active_domain_keys():
                if not is_valid_domain_key(domain_key):
                    continue
                schema = resolve_domain_schema(domain_key)
                domains_processed += 1
                cur.execute(
                    f"""
                    INSERT INTO intelligence.claim_subject_gap_catalog (
                        subject_norm, sample_subject, domain_key, unpromoted_claim_count,
                        last_refreshed_at, status, notes
                    )
                    SELECT subject_norm,
                           sample_subject,
                           domain_key_agg,
                           ccount,
                           %s,
                           'open',
                           NULL
                    FROM (
                        SELECT
                            lower(trim(ec.subject_text)) AS subject_norm,
                            max(ec.subject_text) AS sample_subject,
                            max(atc.domain_key) AS domain_key_agg,
                            count(*)::integer AS ccount
                        FROM intelligence.extracted_claims ec
                        INNER JOIN intelligence.article_to_context atc
                          ON atc.context_id = ec.context_id AND atc.domain_key = %s
                        WHERE ec.confidence >= %s
                          AND length(trim(ec.subject_text)) >= 2
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.versioned_facts vf
                              WHERE vf.metadata->>'source_claim_id' = ec.id::text
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.entity_profiles ep
                              WHERE lower(trim(COALESCE(ep.metadata->>'canonical_name', '')))
                                    = lower(trim(ec.subject_text))
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM {schema}.entity_canonical ecn
                              WHERE lower(trim(ecn.canonical_name)) = lower(trim(ec.subject_text))
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM intelligence.claim_subject_gap_catalog g
                              WHERE g.subject_norm = lower(trim(ec.subject_text))
                                AND g.domain_key = %s
                                AND g.status = 'ignored'
                          )
                        GROUP BY 1
                        ORDER BY ccount DESC
                        LIMIT %s
                    ) sub
                    ON CONFLICT (subject_norm, domain_key) DO UPDATE SET
                        sample_subject = EXCLUDED.sample_subject,
                        unpromoted_claim_count = EXCLUDED.unpromoted_claim_count,
                        last_refreshed_at = EXCLUDED.last_refreshed_at
                    WHERE intelligence.claim_subject_gap_catalog.status <> 'ignored'
                    """,
                    (ts, domain_key, conf, domain_key, cap),
                )
                upserted_total += cur.rowcount or 0

            cur.execute(
                """
                DELETE FROM intelligence.claim_subject_gap_catalog
                WHERE status = 'open' AND last_refreshed_at < %s
                """,
                (ts,),
            )
            deleted = cur.rowcount or 0
            conn.commit()
        return {
            "success": True,
            "domains_processed": domains_processed,
            "rows_upserted": upserted_total,
            "rows_deleted_stale": deleted,
            "min_confidence": conf,
            "max_per_domain": cap,
            "refreshed_at": ts.isoformat(),
        }
    except Exception as e:
        logger.warning("refresh_claim_subject_gap_catalog: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "success": False,
            "error": str(e)[:500],
            "domains_processed": domains_processed,
            "rows_upserted": upserted_total,
            "rows_deleted_stale": 0,
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass


def list_claim_subject_gaps(
    *,
    limit: int = 200,
    status: str | None = None,
    domain_key: str | None = None,
) -> list[dict[str, Any]]:
    conn = get_db_connection()
    if not conn:
        return []
    lim = max(1, min(2000, int(limit)))
    where: list[str] = ["1=1"]
    params: list[Any] = []
    if status:
        where.append("status = %s")
        params.append(status)
    if domain_key:
        where.append("domain_key = %s")
        params.append(domain_key)
    params.append(lim)
    sql = f"""
        SELECT id, subject_norm, sample_subject, domain_key, unpromoted_claim_count,
               last_refreshed_at, status, notes
        FROM intelligence.claim_subject_gap_catalog
        WHERE {" AND ".join(where)}
        ORDER BY unpromoted_claim_count DESC, subject_norm ASC
        LIMIT %s
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": int(r[0]),
                    "subject_norm": r[1],
                    "sample_subject": r[2],
                    "domain_key": r[3],
                    "unpromoted_claim_count": int(r[4] or 0),
                    "last_refreshed_at": r[5].isoformat() if r[5] else None,
                    "status": r[6],
                    "notes": r[7],
                }
            )
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


def bulk_ignore_subjects(
    domain_key: str,
    subject_norms: list[str],
    *,
    notes: str | None = None,
) -> dict[str, Any]:
    """
    Upsert ``ignored`` rows so ``promote_claims_to_versioned_facts`` skips those subjects
    (same predicate as ``CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL``).

    ``subject_norms`` are lowercased/stripped; entries shorter than 2 chars are dropped.
    """
    if not is_valid_domain_key(domain_key):
        return {"success": False, "error": "invalid_domain", "upserted": 0}
    norms: list[str] = []
    seen: set[str] = set()
    for raw in subject_norms or []:
        n = (raw or "").strip().lower()
        if len(n) < 2 or n in seen:
            continue
        seen.add(n)
        norms.append(n)
    if not norms:
        return {"success": False, "error": "no_valid_subjects", "upserted": 0}

    note_val = (notes or "").strip() or None
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db", "upserted": 0}
    total = 0
    try:
        with conn.cursor() as cur:
            for i in range(0, len(norms), 500):
                chunk = norms[i : i + 500]
                for sub in chunk:
                    cur.execute(
                        """
                        INSERT INTO intelligence.claim_subject_gap_catalog (
                            subject_norm, sample_subject, domain_key, unpromoted_claim_count,
                            last_refreshed_at, status, notes
                        )
                        VALUES (%s, %s, %s, 0, NOW(), 'ignored', %s)
                        ON CONFLICT (subject_norm, domain_key) DO UPDATE SET
                            status = 'ignored',
                            notes = COALESCE(EXCLUDED.notes, intelligence.claim_subject_gap_catalog.notes),
                            last_refreshed_at = NOW()
                        """,
                        (sub, sub, domain_key, note_val),
                    )
                    total += 1
            conn.commit()
        return {"success": True, "domain_key": domain_key, "upserted": total, "notes": note_val}
    except Exception as e:
        logger.warning("bulk_ignore_subjects: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:500], "upserted": 0}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def set_gap_status(gap_id: int, status: str, notes: str | None = None) -> bool:
    if status not in ("open", "seeded", "ignored"):
        return False
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            if notes:
                cur.execute(
                    """
                    UPDATE intelligence.claim_subject_gap_catalog
                    SET status = %s, notes = %s
                    WHERE id = %s
                    """,
                    (status, notes, gap_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE intelligence.claim_subject_gap_catalog
                    SET status = %s
                    WHERE id = %s
                    """,
                    (status, gap_id),
                )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.debug("set_gap_status: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def seed_canonical_from_gap(
    domain_key: str,
    canonical_name: str,
    entity_type: str = "ORG",
    *,
    gap_id: int | None = None,
    subject_norm: str | None = None,
) -> dict[str, Any]:
    """
    Insert ``entity_canonical`` if missing (case-insensitive name + type), then
    ``sync_domain_entity_profiles`` for that domain.
    """
    if not is_valid_domain_key(domain_key):
        return {"success": False, "error": "invalid_domain"}
    schema = resolve_domain_schema(domain_key)
    from services.entity_seed_catalog_service import normalize_seed_entity_type

    name = (canonical_name or "").strip()
    et = normalize_seed_entity_type(entity_type or "ORG")
    if len(name) < 2:
        return {"success": False, "error": "canonical_name too short"}

    from services.entity_profile_sync_service import sync_domain_entity_profiles

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db"}
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {schema}.entity_canonical (canonical_name, entity_type)
                SELECT %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM {schema}.entity_canonical ec
                    WHERE lower(trim(ec.canonical_name)) = lower(trim(%s))
                      AND ec.entity_type IS NOT DISTINCT FROM %s
                )
                """,
                (name, et, name, et),
            )
            inserted = cur.rowcount or 0
            conn.commit()
        mapped = sync_domain_entity_profiles(domain_key)
        if gap_id:
            set_gap_status(gap_id, "seeded", notes=f"seeded canonical {name!r} ({et})")
        elif subject_norm:
            conn2 = get_db_connection()
            if conn2:
                try:
                    with conn2.cursor() as cur2:
                        cur2.execute(
                            """
                            UPDATE intelligence.claim_subject_gap_catalog
                            SET status = 'seeded', notes = %s
                            WHERE subject_norm = %s AND domain_key = %s AND status = 'open'
                            """,
                            (f"seeded canonical {name!r} ({et})", subject_norm.lower().strip(), domain_key),
                        )
                        conn2.commit()
                finally:
                    conn2.close()
        return {
            "success": True,
            "canonical_insert_attempted": inserted,
            "entity_profile_sync_new_mappings": mapped,
            "domain_key": domain_key,
            "canonical_name": name,
            "entity_type": et,
        }
    except Exception as e:
        logger.warning("seed_canonical_from_gap: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:500]}
    finally:
        try:
            conn.close()
        except Exception:
            pass
