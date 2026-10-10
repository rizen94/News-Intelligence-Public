"""
Living proteins + established beaker bonds for linear arc chronicles.

Politics/finance/geopolitics frames only — not medicine/legal/AI ledgers.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

from services.arc_catalog_service import get_arc_definition
from services.domain_synthesis_config import get_domain_synthesis_config

logger = logging.getLogger(__name__)

# Domains whose story_kind is linear (chronicle-attachable).
_LINEAR_STORY_KINDS = frozenset({"event_narrative", "market_regulatory_arc"})


def load_chronicle_protein_attachments(
    arc_id: str,
    *,
    max_proteins: int = 40,
    max_bonds: int = 30,
) -> dict[str, Any]:
    """
    Return supporting proteins (linear kinds only), established bond counts,
    and tracked-event anchors for an arc chronicle.
    """
    arc = get_arc_definition(arc_id)
    if not arc:
        return {"success": False, "error": "arc_not_found", "arc_id": arc_id}

    entity_qids = list(arc.get("primary_entity_qids") or [])
    proteins = _load_linear_proteins(entity_qids, limit=max_proteins)
    protein_keys = {(p["domain_key"], int(p["storyline_id"])) for p in proteins}
    bonds = _load_established_bonds(protein_keys, limit=max_bonds)
    tracked = _load_tracked_events(protein_keys, limit=max_proteins)

    return {
        "success": True,
        "arc_id": arc_id,
        "supporting_proteins": proteins,
        "established_bonds": bonds,
        "established_bond_count": len(bonds),
        "tracked_events": tracked,
        "protein_count": len(proteins),
    }


def _load_linear_proteins(entity_qids: list[str], *, limit: int) -> list[dict[str, Any]]:
    if not entity_qids:
        return []
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        for dk in get_pipeline_active_domain_keys():
            try:
                cfg = get_domain_synthesis_config(dk)
                kind = str(cfg.story_kind or "")
                if kind not in _LINEAR_STORY_KINDS or cfg.is_chemistry_kind():
                    continue
            except Exception:
                continue
            schema = resolve_domain_schema(dk)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT DISTINCT s.id, s.title, s.status, s.updated_at,
                               COALESCE(s.total_articles, 0)
                        FROM {schema}.storylines s
                        JOIN {schema}.story_entity_index sei ON sei.storyline_id = s.id
                        JOIN {schema}.entity_canonical ec
                          ON lower(ec.canonical_name) = lower(sei.entity_name)
                        WHERE ec.wikidata_qid = ANY(%s)
                        ORDER BY s.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (entity_qids, limit),
                    )
                    for sid, title, status, updated_at, article_count in cur.fetchall():
                        out.append(
                            {
                                "domain_key": dk,
                                "storyline_id": int(sid),
                                "title": title,
                                "status": status,
                                "story_kind": kind,
                                "article_count": int(article_count or 0),
                                "updated_at": updated_at.isoformat() if updated_at else None,
                            }
                        )
            except Exception as e:
                logger.debug("chronicle proteins %s: %s", schema, e)
    out.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return out[:limit]


def _load_established_bonds(
    protein_keys: set[tuple[str, int]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if not protein_keys:
        return []
    ids = sorted({sid for _, sid in protein_keys})
    if not ids:
        return []
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT id, domain_key, left_kind, left_id, right_kind, right_id,
                           link_role, confidence,
                           COALESCE(inference_stage, 'established') AS inference_stage,
                           created_at
                    FROM intelligence.graph_connection_links
                    WHERE COALESCE(inference_stage, 'established') = 'established'
                      AND (
                        (left_kind = 'storyline' AND left_id = ANY(%s))
                        OR (right_kind = 'storyline' AND right_id = ANY(%s))
                      )
                    ORDER BY created_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (ids, ids, limit),
                )
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
                        d["created_at"] = d["created_at"].isoformat()
                    if d.get("confidence") is not None:
                        try:
                            d["confidence"] = float(d["confidence"])
                        except (TypeError, ValueError):
                            pass
                    out.append(d)
            except Exception as e:
                logger.debug("chronicle bonds: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass
    return out


def _load_tracked_events(
    protein_keys: set[tuple[str, int]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if not protein_keys:
        return []
    # storyline_id on tracked_events is often "domain:id"
    keys = [f"{dk}:{sid}" for dk, sid in protein_keys]
    numeric = sorted({sid for _, sid in protein_keys})
    out: list[dict[str, Any]] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT id, title, status, storyline_id, domain_keys, updated_at
                    FROM intelligence.tracked_events
                    WHERE storyline_id = ANY(%s)
                       OR (
                         storyline_id ~ '^[0-9]+$'
                         AND storyline_id::int = ANY(%s)
                       )
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (keys, numeric, limit),
                )
                cols = [d[0] for d in cur.description]
                for row in cur.fetchall():
                    d = dict(zip(cols, row))
                    if d.get("updated_at") and hasattr(d["updated_at"], "isoformat"):
                        d["updated_at"] = d["updated_at"].isoformat()
                    out.append(d)
            except Exception as e:
                logger.debug("chronicle tracked_events: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass
    return out
