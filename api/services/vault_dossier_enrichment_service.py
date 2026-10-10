"""Enrich living vault entity notes from ``intelligence.entity_dossiers``.

Writes a replaceable ``## Entity dossier`` section using only stored dossier
JSON/text (chronicle, positions, relationships, storyline refs, optional
narrative_summary). Does **not** call LLMs.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

DOSSIER_SECTION_HEADER = "## Entity dossier"
_DOSSIER_SECTION_RE = re.compile(
    r"\n## Entity dossier\n(?:.*?)(?=\n## |\Z)",
    re.S,
)

# Priority living / seeded entities (Fed, oil, gold, State, OPEC, …)
PRIORITY_ENTITY_TITLES: tuple[str, ...] = (
    "Federal Reserve",
    "oil",
    "gold",
    "OPEC+",
    "Strait of Hormuz",
    "International Energy Agency",
    "State Department",
    "Pentagon",
    "Supreme Court",
    "White House",
    "Nigel Farage",
    "OpenAI",
    "Venezuela",
    "Iran",
    "China",
    "Congress",
    "United Nations",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(val: Any) -> list[Any]:
    if isinstance(val, list):
        return val
    return []


def _as_dict(val: Any) -> dict[str, Any]:
    return val if isinstance(val, dict) else {}


def load_dossier(domain_key: str, entity_id: int) -> dict[str, Any] | None:
    """Load one entity_dossiers row; closes DB before return."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, entity_id, compilation_date,
                       chronicle_data, relationships, positions, patterns, metadata
                FROM intelligence.entity_dossiers
                WHERE domain_key = %s AND entity_id = %s
                """,
                (domain_key, int(entity_id)),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))


def _resolve_entity_name(domain_key: str, entity_id: int) -> str | None:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT canonical_name FROM "{domain_key}".entity_canonical WHERE id = %s',
                    (int(entity_id),),
                )
                row = cur.fetchone()
                return str(row[0]).strip() if row and row[0] else None
    except Exception as e:
        logger.debug("canonical_name %s/%s: %s", domain_key, entity_id, e)
        return None


def build_dossier_section(
    dossier: dict[str, Any],
    *,
    label: str,
    entity_name: str | None = None,
    max_chronicle: int = 8,
    max_positions: int = 6,
    max_relationships: int = 6,
    max_storylines: int = 5,
) -> str:
    """Render grounded markdown from stored dossier fields only."""
    meta = _as_dict(dossier.get("metadata"))
    chronicle = _as_list(dossier.get("chronicle_data"))
    positions = _as_list(dossier.get("positions"))
    relationships = _as_list(dossier.get("relationships"))
    patterns = _as_dict(dossier.get("patterns"))
    storyline_refs = _as_list(meta.get("storyline_refs"))
    narrative = (meta.get("narrative_summary") or "").strip()
    compiled = dossier.get("compilation_date")
    compiled_s = str(compiled)[:10] if compiled else "unknown"

    lines = [
        DOSSIER_SECTION_HEADER,
        "",
        f"_Compiled {compiled_s} from ``intelligence.entity_dossiers`` "
        f"(domain=`{dossier.get('domain_key')}`, entity_id=`{dossier.get('entity_id')}`). "
        f"Stored fields only — not live LLM prose._",
        "",
        f"_Target: {label}_",
        "",
    ]
    if entity_name:
        lines.append(f"**Canonical:** {entity_name}")
        lines.append("")

    arts = meta.get("article_count")
    sl_n = meta.get("storyline_count")
    rel_n = meta.get("relationship_count")
    stats = []
    if arts is not None:
        stats.append(f"articles={arts}")
    if sl_n is not None:
        stats.append(f"storylines={sl_n}")
    if rel_n is not None:
        stats.append(f"relationships={rel_n}")
    if stats:
        lines.append(f"- Counts: {', '.join(stats)}")
        lines.append("")

    # Prefer stored narrative when present (already compiled into dossier metadata)
    if narrative and len(narrative) > 40 and not meta.get("narrative_pending"):
        lines.append("### Narrative summary (stored)")
        lines.append("")
        # Truncate long narratives; still grounded in DB
        lines.append(narrative[:1200].strip())
        lines.append("")

    lines.append("### Recent mentions (chronicle)")
    lines.append("")
    if not chronicle:
        lines.append("- _No chronicle_data rows._")
    else:
        for c in chronicle[:max_chronicle]:
            if not isinstance(c, dict):
                continue
            title = (c.get("title") or "Untitled").strip()
            pub = (c.get("published_at") or "")[:10]
            src = (c.get("source_domain") or "").strip()
            aid = c.get("article_id")
            url = (c.get("url") or "").strip()
            cite = f" (article:{aid})" if aid else ""
            head = f"- {pub} — " if pub else "- "
            if url:
                lines.append(f"{head}[{title}]({url}){cite}" + (f" · {src}" if src else ""))
            else:
                lines.append(f"{head}{title}{cite}" + (f" · {src}" if src else ""))
            snippet = (c.get("snippet") or "").replace("\n", " ").strip()
            if snippet:
                lines.append(f"  - _{snippet[:220]}_")
    lines.append("")

    lines.append("### Positions")
    lines.append("")
    if not positions:
        lines.append("- _No positions stored._")
    else:
        for p in positions[:max_positions]:
            if not isinstance(p, dict):
                continue
            topic = (p.get("topic") or "?").strip()
            pos = (p.get("position") or "?").strip()
            conf = p.get("confidence")
            conf_s = f" (conf {conf:.0%})" if isinstance(conf, (int, float)) else ""
            lines.append(f"- On {topic}: **{pos}**{conf_s}")
            refs = _as_list(p.get("evidence_refs"))
            for ref in refs[:2]:
                if not isinstance(ref, dict):
                    continue
                rt = (ref.get("title") or "").strip()
                raid = ref.get("article_id")
                if rt:
                    cite = f" (article:{raid})" if raid else ""
                    lines.append(f"  - evidence: {rt}{cite}")
    lines.append("")

    lines.append("### Storyline refs")
    lines.append("")
    if not storyline_refs:
        lines.append("- _No storyline_refs in dossier metadata._")
    else:
        for s in storyline_refs[:max_storylines]:
            if not isinstance(s, dict):
                continue
            st = (s.get("title") or "Untitled").strip()
            sid = s.get("storyline_id")
            cite = f" (storyline:{sid})" if sid else ""
            lines.append(f"- {st}{cite}")
    lines.append("")

    lines.append("### Relationships (sample)")
    lines.append("")
    if not relationships:
        lines.append("- _No relationships stored._")
    else:
        self_id = int(dossier.get("entity_id") or 0)
        for r in relationships[:max_relationships]:
            if not isinstance(r, dict):
                continue
            rtype = (r.get("relationship_type") or "related").strip()
            t_dom = str(r.get("target_domain") or dossier.get("domain_key") or "")
            t_id = r.get("target_entity_id")
            s_dom = str(r.get("source_domain") or dossier.get("domain_key") or "")
            s_id = r.get("source_entity_id")
            peer_dom, peer_id = t_dom, t_id
            if t_id is not None and int(t_id) == self_id and s_id is not None:
                peer_dom, peer_id = s_dom, s_id
            peer_label = f"{peer_dom}:{peer_id}"
            conf = r.get("confidence")
            conf_s = f" · conf {conf:.2f}" if isinstance(conf, (int, float)) else ""
            lines.append(f"- {rtype} → `{peer_label}`{conf_s}")
    lines.append("")

    discoveries = _as_list(patterns.get("discoveries"))
    if discoveries:
        lines.append("### Patterns")
        lines.append("")
        for pat in discoveries[:3]:
            if not isinstance(pat, dict):
                continue
            ptype = pat.get("pattern_type") or "pattern"
            data = _as_dict(pat.get("data"))
            desc = (
                data.get("description")
                or data.get("summary")
                or str(ptype)
            )
            lines.append(f"- [{ptype}] {str(desc)[:160]}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def patch_dossier_section(body: str, dossier_md: str) -> str:
    text = body or ""
    block = "\n" + dossier_md.strip() + "\n"
    if _DOSSIER_SECTION_RE.search(text):
        return _DOSSIER_SECTION_RE.sub(block, text, count=1)
    # Prefer before Wikipedia / Non-RSS / Sources
    for marker in (
        "\n## Wikipedia background\n",
        "\n## Non-RSS evidence (API)\n",
        "\n## Sources\n",
        "\n## Timeline\n",
    ):
        if marker in text:
            return text.replace(marker, block + marker, 1)
    return text.rstrip() + "\n" + block


def _list_priority_entity_notes(
    *,
    titles: list[str] | None = None,
    limit: int = 20,
    living_only: bool = False,
) -> list[dict[str, Any]]:
    title_list = list(titles or PRIORITY_ENTITY_TITLES)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            lifecycle_sql = "AND lifecycle = 'living'" if living_only else ""
            cur.execute(
                f"""
                SELECT id, domain_key, object_id, vault_path, title, lifecycle,
                       metadata, body_md, summary_md, note_type
                FROM intelligence.vault_notes
                WHERE note_type = 'entity'
                  AND title = ANY(%s)
                  {lifecycle_sql}
                ORDER BY
                  CASE WHEN lifecycle = 'living' THEN 0 ELSE 1 END,
                  mention_count DESC NULLS LAST
                LIMIT %s
                """,
                (title_list, limit),
            )
            cols = [d[0] for d in cur.description]
            notes = [dict(zip(cols, r)) for r in (cur.fetchall() or [])]

            if len(notes) < limit and not living_only:
                have = {n["vault_path"] for n in notes}
                cur.execute(
                    """
                    SELECT id, domain_key, object_id, vault_path, title, lifecycle,
                           metadata, body_md, summary_md, note_type
                    FROM intelligence.vault_notes
                    WHERE note_type = 'entity'
                      AND lifecycle = 'living'
                    ORDER BY mention_count DESC NULLS LAST
                    LIMIT %s
                    """,
                    (limit * 2,),
                )
                for r in cur.fetchall() or []:
                    row = dict(zip(cols, r))
                    if row["vault_path"] in have:
                        continue
                    notes.append(row)
                    have.add(row["vault_path"])
                    if len(notes) >= limit:
                        break
            return notes[:limit]


def apply_dossier_to_entity(
    note: dict[str, Any],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    from services.vault_bridge_service import vault_root
    from services.vault_notes_registry_service import upsert_vault_note

    path = str(note.get("vault_path") or "")
    title = str(note.get("title") or "").strip()
    domain = str(note.get("domain_key") or "politics")
    oid = note.get("object_id")
    if not path or not title or not oid:
        return {"ok": False, "kind": "entity", "error": "missing_path_title_or_oid", "title": title}

    meta = note.get("metadata") if isinstance(note.get("metadata"), dict) else {}
    meta = dict(meta or {})
    if meta.get("dossier_enriched_at") and not force:
        return {
            "ok": True,
            "kind": "entity",
            "title": title,
            "skipped": "already_enriched",
            "path": path,
        }

    dossier = load_dossier(domain, int(oid))
    if not dossier:
        return {
            "ok": False,
            "kind": "entity",
            "title": title,
            "error": "dossier_missing",
            "path": path,
            "domain_key": domain,
            "object_id": int(oid),
        }

    entity_name = _resolve_entity_name(domain, int(oid)) or title
    dossier_md = build_dossier_section(
        dossier,
        label=f"Entity `{title}`",
        entity_name=entity_name,
    )
    chron_n = len(_as_list(dossier.get("chronicle_data")))
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "kind": "entity",
            "title": title,
            "path": path,
            "compilation_date": str(dossier.get("compilation_date") or "")[:10],
            "chronicle_n": chron_n,
            "dossier_chars": len(dossier_md),
        }

    root = vault_root()
    fp = root / path
    if not fp.is_file():
        return {
            "ok": False,
            "kind": "entity",
            "title": title,
            "error": "file_missing",
            "path": path,
        }
    existing = fp.read_text(encoding="utf-8")
    patched = patch_dossier_section(existing, dossier_md).replace("\x00", "")
    fp.write_text(patched, encoding="utf-8")

    meta["dossier_enriched_at"] = _now_iso()
    meta["dossier_enrichment_source"] = "vault_dossier_enrichment_service"
    meta["dossier_compilation_date"] = str(dossier.get("compilation_date") or "")[:10]
    meta["dossier_id"] = dossier.get("id")
    upsert_vault_note(
        domain_key=domain,
        note_type="entity",
        object_id=int(oid),
        vault_path=path,
        title=title,
        note_status="note_ready",
        lifecycle=str(note.get("lifecycle") or "living"),
        body_md=patched,
        summary_md=(note.get("summary_md") or None),
        metadata=meta,
        tags_source="ni_structural",
    )
    return {
        "ok": True,
        "kind": "entity",
        "title": title,
        "path": path,
        "compilation_date": str(dossier.get("compilation_date") or "")[:10],
        "chronicle_n": chron_n,
        "dossier_chars": len(dossier_md),
    }


def enrich_priority_entity_dossiers(
    *,
    titles: list[str] | None = None,
    limit: int = 15,
    force: bool = False,
    dry_run: bool = False,
    living_only: bool = False,
) -> dict[str, Any]:
    """Capped operator pass over priority vault entity notes with dossiers."""
    notes = _list_priority_entity_notes(
        titles=titles,
        limit=max(0, limit),
        living_only=living_only,
    )
    results: list[dict[str, Any]] = []
    for note in notes:
        try:
            results.append(
                apply_dossier_to_entity(note, force=force, dry_run=dry_run)
            )
        except Exception as e:
            logger.exception("dossier entity %s", note.get("title"))
            results.append(
                {
                    "ok": False,
                    "kind": "entity",
                    "title": note.get("title"),
                    "error": str(e),
                }
            )
    updated = [
        r
        for r in results
        if r.get("ok") and not r.get("skipped") and not r.get("dry_run")
    ]
    return {
        "ok": True,
        "entity_n": len(results),
        "entity_ok": sum(1 for r in results if r.get("ok")),
        "updated_n": len(updated),
        "skipped_n": sum(1 for r in results if r.get("skipped")),
        "missing_dossier_n": sum(1 for r in results if r.get("error") == "dossier_missing"),
        "results": results,
    }
