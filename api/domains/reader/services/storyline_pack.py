"""
Reader pack for a single storyline: summary, timeline, citations, dossier rail.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.services.domain_aware_service import validate_domain

logger = logging.getLogger(__name__)

_HEADING_ONLY_STUB = re.compile(
    r"^(key\s+takeaways|summary|timeline|background|overview)\s*:?\s*$",
    re.IGNORECASE,
)


def _parse_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _article_grounded_summary(
    citations: list[dict[str, Any]], *, title: str = "", max_chars: int = 1400
) -> str:
    """
    Build a short reader brief from member article body/summary when stored
    narratives are inventory fluff or empty.
    """
    from shared.llm_text_sanitize import html_to_visible_text

    chunks: list[str] = []
    # Prefer longest bodies first (substance over thin liveblog stubs)
    ranked = sorted(
        citations,
        key=lambda c: len(str(c.get("content") or c.get("summary") or "")),
        reverse=True,
    )
    for cite in ranked[:3]:
        raw = cite.get("content") or cite.get("summary") or ""
        prose = html_to_visible_text(str(raw), max_length=700)
        if not prose or len(re.sub(r"\W+", "", prose)) < 80:
            continue
        # Drop leading markdown H2 that is often a liveblog section title
        prose = re.sub(r"^##\s+[^\n]+\n+", "", prose).strip()
        # First 2 paragraphs
        paras = [p.strip() for p in re.split(r"\n\s*\n+", prose) if p.strip()]
        excerpt = " ".join(paras[:2]) if paras else prose
        excerpt = re.sub(r"\s+", " ", excerpt).strip()
        if len(excerpt) < 80:
            continue
        src = (cite.get("source_domain") or "").strip()
        headline = (cite.get("title") or "").strip()
        lead = excerpt if len(excerpt) <= 520 else excerpt[:500].rsplit(" ", 1)[0] + "…"
        if headline and headline.casefold() != (title or "").casefold():
            prefix = f"**{headline}**" + (f" ({src})" if src else "")
            chunks.append(f"{prefix} — {lead}")
        else:
            chunks.append(lead)
        if sum(len(c) for c in chunks) >= max_chars:
            break
    if not chunks:
        return ""
    out = "\n\n".join(chunks)
    if len(out) > max_chars:
        out = out[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return out


def _usable_summary_text(raw: Any) -> str:
    """Return stripped text, or empty if missing / heading-only stub."""
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    if _HEADING_ONLY_STUB.match(text):
        return ""
    return text


def _build_dossier_tree(entities: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nest entities by member_of_family / family-like edges when present."""
    by_id = {e["id"]: {**e, "children": []} for e in entities if e.get("id") is not None}
    roots: list[dict[str, Any]] = []
    child_ids: set[Any] = set()

    for rel in relationships:
        rtype = (rel.get("relationship_type") or rel.get("type") or "").lower()
        if rtype not in ("member_of_family", "member_of", "part_of", "subsidiary_of", "works_for"):
            continue
        parent = rel.get("target_entity_id") or rel.get("to_entity_id") or rel.get("parent_id")
        child = rel.get("source_entity_id") or rel.get("from_entity_id") or rel.get("child_id")
        if parent in by_id and child in by_id and parent != child:
            by_id[parent]["children"].append(by_id[child])
            child_ids.add(child)

    for eid, node in by_id.items():
        if eid not in child_ids:
            roots.append(node)

    if not roots:
        return list(by_id.values())
    return roots


def build_storyline_reader_pack(domain: str, storyline_id: int) -> dict[str, Any]:
    if not validate_domain(domain):
        raise ValueError(f"Invalid or inactive domain: {domain}")

    schema = resolve_domain_schema(domain)
    timeline: dict[str, Any] = {"events": []}

    with get_ui_db_connection_context() as conn:
        try:
            from shared.episode_attach_gate import episode_container_assembly_enabled
            from services.episode_container_timeline_service import episode_timeline

            if episode_container_assembly_enabled():
                packed = episode_timeline(domain, storyline_id, limit=100) or {}
                events = packed.get("events") or []
                timeline = {
                    "events": [
                        {
                            "id": e.get("id"),
                            "title": e.get("title"),
                            "date": (
                                e.get("actual_event_date").isoformat()
                                if hasattr(e.get("actual_event_date"), "isoformat")
                                else e.get("actual_event_date")
                            ),
                            "event_type": e.get("event_type"),
                            "summary": e.get("summary"),
                            "source_article_id": e.get("source_article_id"),
                            "link_type": e.get("link_type"),
                            "matched_anchors": e.get("matched_anchors"),
                        }
                        for e in events
                        if isinstance(e, dict)
                    ]
                }
            else:
                from services.timeline_builder_service import TimelineBuilderService

                timeline = (
                    TimelineBuilderService(conn, schema_name=schema).build_timeline(
                        storyline_id
                    )
                    or {"events": []}
                )
        except Exception as exc:
            logger.warning("timeline build failed for %s/%s: %s", domain, storyline_id, exc)
            timeline = {"events": [], "error": str(exc)}

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    s.id, s.title, s.description, s.status,
                    s.created_at, s.updated_at, s.article_count, s.quality_score,
                    s.master_summary, s.background_information,
                    s.editorial_document, s.document_version, s.document_status,
                    s.canonical_narrative, s.timeline_narrative_chronological,
                    s.timeline_narrative_briefing, s.key_entities,
                    s.parent_storyline_id, COALESCE(s.is_mega_storyline, FALSE),
                    s.last_refinement
                FROM {schema}.storylines s
                WHERE s.id = %s AND s.merged_into_id IS NULL
                """,
                (storyline_id,),
            )
            row = cur.fetchone()
            if not row:
                raise LookupError(f"Storyline {storyline_id} not found in {domain}")

            (
                sid,
                title,
                description,
                status,
                created_at,
                updated_at,
                article_count,
                quality_score,
                master_summary,
                background_information,
                editorial_document,
                document_version,
                document_status,
                canonical_narrative,
                timeline_narrative_chronological,
                timeline_narrative_briefing,
                key_entities,
                parent_storyline_id,
                is_mega_storyline,
                last_refinement,
            ) = row

            editorial = _parse_json(editorial_document) or {}

            # Citations: prefer EEL (event-grain) when assembly on; bag is fallback only.
            citations: list[dict[str, Any]] = []
            use_eel = False
            try:
                from shared.episode_attach_gate import episode_container_assembly_enabled
                from shared.episode_membership import list_episode_articles_sql

                use_eel = bool(episode_container_assembly_enabled())
            except Exception:
                use_eel = False

            if use_eel:
                try:
                    cur.execute(
                        list_episode_articles_sql(schema, with_content=True) + "\nLIMIT 50",
                        (domain, storyline_id),
                    )
                    citations = [
                        {
                            "id": r[0],
                            "title": r[1],
                            "url": r[2],
                            "source_domain": r[3],
                            "published_at": r[4].isoformat() if r[4] else None,
                            "summary": r[5],
                            "content": r[6] if len(r) > 6 else None,
                        }
                        for r in cur.fetchall()
                    ]
                except Exception as exc:
                    logger.debug("EEL citations failed, bag fallback: %s", exc)
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    citations = []

            if not citations:
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary,
                           left(coalesce(a.content, ''), 8000) AS content
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at DESC NULLS LAST
                    LIMIT 50
                    """,
                    (storyline_id,),
                )
                citations = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "url": r[2],
                        "source_domain": r[3],
                        "published_at": r[4].isoformat() if r[4] else None,
                        "summary": r[5],
                        "content": r[6],
                    }
                    for r in cur.fetchall()
                ]

            # Entities: EEL-linked articles when assembly on
            entities: list[dict[str, Any]] = []
            relationships: list[dict[str, Any]] = []
            try:
                if use_eel:
                    from shared.episode_membership import list_episode_entities_sql

                    cur.execute(list_episode_entities_sql(schema), (domain, storyline_id))
                else:
                    cur.execute(
                        f"""
                        SELECT DISTINCT ON (e.id)
                            e.id, e.name, e.entity_type, e.description
                        FROM {schema}.entities e
                        JOIN {schema}.article_entities ae ON ae.entity_id = e.id
                        JOIN {schema}.storyline_articles sa ON sa.article_id = ae.article_id
                        WHERE sa.storyline_id = %s
                        ORDER BY e.id, e.name
                        LIMIT 40
                        """,
                        (storyline_id,),
                    )
                for r in cur.fetchall():
                    entities.append(
                        {
                            "id": r[0],
                            "name": r[1],
                            "entity_type": r[2],
                            "description_short": (r[3] or "")[:240],
                            "who": None,
                            "what": None,
                            "why": None,
                            "href": f"/entities/{r[0]}?domain={domain}",
                        }
                    )
            except Exception as exc:
                logger.debug("entity join fallback: %s", exc)
                conn.rollback()
                # Fall back to key_entities JSON
                ke = _parse_json(key_entities)
                if isinstance(ke, list):
                    for i, item in enumerate(ke[:20]):
                        if isinstance(item, dict):
                            entities.append(
                                {
                                    "id": item.get("id") or f"ke-{i}",
                                    "name": item.get("name") or "Entity",
                                    "entity_type": item.get("type") or item.get("entity_type"),
                                    "description_short": (item.get("description") or "")[:240],
                                    "href": None,
                                }
                            )
                        elif isinstance(item, str):
                            entities.append(
                                {
                                    "id": f"ke-{i}",
                                    "name": item,
                                    "entity_type": None,
                                    "description_short": "",
                                    "href": None,
                                }
                            )

            # Enrich from dossiers when available
            for ent in entities:
                eid = ent.get("id")
                if not isinstance(eid, int):
                    continue
                try:
                    cur.execute(
                        """
                        SELECT chronicle_data, relationships, metadata
                        FROM intelligence.entity_dossiers
                        WHERE entity_id = %s
                        ORDER BY updated_at DESC NULLS LAST
                        LIMIT 1
                        """,
                        (eid,),
                    )
                    drow = cur.fetchone()
                    if drow:
                        chronicle = _parse_json(drow[0]) or {}
                        rels = _parse_json(drow[1]) or []
                        meta = _parse_json(drow[2]) or {}
                        ent["who"] = chronicle.get("who") or meta.get("who") or ent.get("description_short")
                        ent["what"] = chronicle.get("what") or meta.get("what")
                        ent["why"] = chronicle.get("why") or meta.get("why")
                        if isinstance(rels, list):
                            for rel in rels:
                                if isinstance(rel, dict):
                                    relationships.append({**rel, "source_entity_id": eid})
                except Exception:
                    conn.rollback()
                    break  # dossier table may be absent

            # Hierarchy siblings / children
            hierarchy = {
                "parent_storyline_id": parent_storyline_id,
                "is_mega_storyline": bool(is_mega_storyline),
                "children": [],
            }
            try:
                cur.execute(
                    f"""
                    SELECT id, title
                    FROM {schema}.storylines
                    WHERE parent_storyline_id = %s AND merged_into_id IS NULL
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 20
                    """,
                    (storyline_id,),
                )
                hierarchy["children"] = [
                    {"id": r[0], "title": r[1], "href": f"/storylines/{domain}/{r[0]}"}
                    for r in cur.fetchall()
                ]
            except Exception:
                conn.rollback()

    from shared.llm_text_sanitize import (
        is_desk_walkthrough,
        is_inventory_metadata_summary,
        is_multi_topic_excerpt_mash,
        sanitize_briefing_lede,
        sanitize_reader_dek,
        strip_inventory_metadata_summary,
        strip_llm_wrapping_artifacts,
        strip_trailing_llm_json,
    )

    ed = editorial if isinstance(editorial, dict) else {}
    lede_raw = _usable_summary_text(ed.get("lede"))
    analysis_raw = _usable_summary_text(ed.get("analysis"))
    master_raw = strip_inventory_metadata_summary(
        strip_trailing_llm_json(_usable_summary_text(master_summary))
    )
    canonical_raw = strip_inventory_metadata_summary(
        strip_trailing_llm_json(_usable_summary_text(canonical_narrative))
    )
    description_raw = strip_inventory_metadata_summary(_usable_summary_text(description))
    briefing_raw = _usable_summary_text(timeline_narrative_briefing)

    lede = sanitize_reader_dek(lede_raw, title=title, max_length=400) or sanitize_briefing_lede(
        lede_raw, max_length=400
    )

    def _cap_summary(text: str) -> str:
        if len(text) > 12000:
            return text[:11980].rstrip() + "\n…"
        return text

    def _developments_blob(doc: dict[str, Any]) -> str:
        for key in ("developments", "what"):
            raw = doc.get(key)
            if isinstance(raw, list):
                parts = [str(x).strip() for x in raw if str(x).strip()]
                if parts:
                    return "\n".join(f"- {p}" for p in parts[:6])
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    # Durable package/desk projection: prefer composed editorial over thin seeds.
    try:
        from services.editorial_projection_service import QUALITY_DOCUMENT_STATUSES

        quality_status = str(document_status or "") in QUALITY_DOCUMENT_STATUSES
    except Exception:
        quality_status = str(document_status or "") in (
            "package_projected",
            "desk_promoted",
            "refined",
            "rag_analyzed",
            "draft",
        )
    durable_brief = ""
    if quality_status and (lede_raw or analysis_raw):
        parts = [p for p in (lede_raw, analysis_raw, _developments_blob(ed)) if p]
        durable_brief = _cap_summary("\n\n".join(parts))

    # Prefer desk walkthrough; never promote ML inventory (Story Overview counts).
    # When neither is a desk walkthrough, prefer the longer article-grounded prose
    # (avoids short hallucinated canonical beating rebuilt master excerpts).
    summary = ""
    if durable_brief and not is_desk_walkthrough(canonical_raw):
        summary = durable_brief
    elif is_desk_walkthrough(canonical_raw):
        summary = _cap_summary(canonical_raw)
    elif is_desk_walkthrough(master_raw):
        summary = _cap_summary(master_raw)
    else:
        candidates: list[str] = []
        for blob in (
            durable_brief,
            master_raw,
            canonical_raw,
            description_raw,
            analysis_raw,
            lede_raw,
            briefing_raw,
        ):
            if not blob or is_inventory_metadata_summary(blob):
                continue
            if is_multi_topic_excerpt_mash(blob):
                continue
            candidates.append(blob)
        if candidates:
            best = max(candidates, key=len)
            if is_desk_walkthrough(best) or (
                "## " in best and len(best) > 800 and not is_inventory_metadata_summary(best)
            ):
                summary = _cap_summary(best)
            elif len(best) >= 500:
                summary = _cap_summary(best)
            else:
                summary = sanitize_reader_dek(
                    best, title=title, max_length=900
                ) or sanitize_briefing_lede(best, max_length=900) or best
            if summary.lstrip().startswith("```"):
                summary = strip_llm_wrapping_artifacts(summary, max_length=12000) or summary
    # Last resort: grounded excerpts — but never stitch unrelated headlines into one "story"
    if not summary or is_inventory_metadata_summary(summary):
        grounded = _article_grounded_summary(citations, title=title)
        if grounded and not is_multi_topic_excerpt_mash(grounded):
            summary = grounded
        else:
            summary = ""
    if summary and is_multi_topic_excerpt_mash(summary):
        summary = ""
    summary = strip_trailing_llm_json(strip_inventory_metadata_summary(summary or ""))

    # Flag kitchen-sink bags so the UI can avoid presenting them as one arc
    try:
        from services.storyline_coherence_guardrails import title_looks_mega_bag

        mega_bag = bool(is_mega_storyline) or title_looks_mega_bag(title or "")
    except Exception:
        mega_bag = bool(is_mega_storyline)
    if mega_bag:
        summary = (
            "This listing mixed unrelated coverage under one title and is flagged "
            "for split — use the citations below by topic rather than reading this "
            "as a single story."
        )

    dossier_tree = _build_dossier_tree(entities, relationships)

    vault_pack = None
    try:
        pack_ids = [
            int(e["id"])
            for e in entities
            if isinstance(e.get("id"), int)
        ][:8]
        if pack_ids:
            from .vault_context_pack import build_vault_context_pack

            vault_pack = build_vault_context_pack(
                domain_key=domain, entity_ids=pack_ids, hops=2, max_notes=8
            )
    except Exception:
        vault_pack = None

    vault_expansion = None
    try:
        from services.vault_notes_registry_service import get_expansion_for_storyline

        exp = get_expansion_for_storyline(domain, sid)
        if exp and (exp.get("body_md") or exp.get("summary_md")):
            from services.article_context_pull_service import reader_brief_from_expansion

            brief = reader_brief_from_expansion(exp)
            vault_expansion = {
                "title": exp.get("title"),
                "vault_path": exp.get("vault_path"),
                "body_md": brief,
                "summary_md": None,
                "updated_at": exp.get("note_updated_at") or exp.get("updated_at"),
                "source_article_id": (exp.get("metadata") or {}).get(
                    "source_article_id"
                ),
            }
    except Exception:
        vault_expansion = None

    # F8: surface other storyline homes for multi-linked articles (exclusive bag UX).
    # Prefer EEL article ids when assembly is on; bag only as fallback.
    also_in: list[dict[str, Any]] = []
    try:
        article_ids = [int(c["id"]) for c in citations if c.get("id") is not None][:40]
        if article_ids:
            with get_ui_db_connection_context() as conn2:
                with conn2.cursor() as cur2:
                    use_eel_also = False
                    try:
                        from shared.episode_attach_gate import episode_container_assembly_enabled

                        use_eel_also = bool(episode_container_assembly_enabled())
                    except Exception:
                        use_eel_also = False
                    if use_eel_also:
                        cur2.execute(
                            f"""
                            SELECT a.id, a.title, s.id, s.title, COALESCE(s.article_count, 0)
                            FROM intelligence.event_episode_links eel
                            JOIN public.chronological_events ce ON ce.id = eel.event_id
                            JOIN {schema}.articles a ON a.id = ce.source_article_id
                            JOIN {schema}.storylines s ON s.id = eel.episode_id
                            WHERE ce.source_article_id = ANY(%s)
                              AND eel.domain_key = %s
                              AND eel.episode_id <> %s
                              AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                              AND COALESCE(s.status, '') NOT IN ('merged','deleted','archived')
                            ORDER BY COALESCE(s.article_count, 0) DESC, s.id
                            LIMIT 24
                            """,
                            (article_ids, domain, sid),
                        )
                    else:
                        cur2.execute(
                            f"""
                            SELECT a.id, a.title, s.id, s.title, COALESCE(s.article_count, 0)
                            FROM {schema}.storyline_articles sa
                            JOIN {schema}.articles a ON a.id = sa.article_id
                            JOIN {schema}.storylines s ON s.id = sa.storyline_id
                            WHERE sa.article_id = ANY(%s)
                              AND sa.storyline_id <> %s
                              AND COALESCE(s.status, '') NOT IN ('merged','deleted','archived')
                            ORDER BY COALESCE(s.article_count, 0) DESC, s.id
                            LIMIT 24
                            """,
                            (article_ids, sid),
                        )
                    seen_homes: set[int] = set()
                    for aid, atitle, osid, otitle, oac in cur2.fetchall() or []:
                        oid = int(osid)
                        if oid in seen_homes:
                            continue
                        seen_homes.add(oid)
                        also_in.append(
                            {
                                "article_id": int(aid),
                                "article_title": atitle,
                                "domain": domain,
                                "storyline_id": oid,
                                "title": otitle,
                                "article_count": int(oac or 0),
                                "href": f"/storylines/{domain}/{oid}",
                            }
                        )
                        if len(also_in) >= 12:
                            break
    except Exception:
        also_in = []

    # Reader brief preference without Pull: vault expansion → durable → summary.
    # UI overlays Pull as brief_source=pull when a living context pull is present.
    expansion_text = ""
    if isinstance(vault_expansion, dict):
        expansion_text = str(
            vault_expansion.get("body_md") or vault_expansion.get("summary_md") or ""
        ).strip()
    if expansion_text:
        brief_source = "vault_expansion"
    elif durable_brief:
        brief_source = "durable"
    elif (summary or "").strip():
        brief_source = "summary"
    else:
        brief_source = "none"

    return {
        "domain": domain,
        "storyline_id": sid,
        "title": title,
        "status": status,
        "summary": summary,
        "lede": lede,
        "durable_brief": durable_brief or None,
        "brief_source": brief_source,
        "editorial_document": editorial if isinstance(editorial, dict) else {},
        "background_information": background_information,
        "timeline_narrative": timeline_narrative_chronological,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "last_refinement": last_refinement.isoformat() if last_refinement else None,
        "article_count": len(citations) if citations else article_count,
        "quality_score": float(quality_score) if quality_score is not None else None,
        "is_mega_storyline": bool(is_mega_storyline) or mega_bag,
        "document_version": document_version,
        "document_status": document_status,
        "timeline": timeline,
        "citations": [
            {k: v for k, v in c.items() if k != "content"} for c in citations
        ],
        "also_in": also_in,
        "dossier_rail": {
            "entities": entities,
            "tree": dossier_tree,
            "hierarchy": hierarchy,
        },
        "vault_context_pack": vault_pack,
        "vault_expansion": vault_expansion,
    }
