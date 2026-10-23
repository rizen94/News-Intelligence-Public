"""
Second-brain vault MVP: Capture → Organize → Distill for each article.

- Capture: immutable clipping under ``20_Clippings/`` (news) or
  ``50_Science/20_Clippings/`` (medicine / AI / neurodiversity research)
- Organize: science *subjects* → ``50_Science/40_Topics/``; shared refs
  (orgs, places, people, labs, …) stay under ``40_Reference/entities/``.
  Tags (including ``place/*``) are shared freely across branches.
- Distill: append timeline bullets + update/new on wiki notes

Does not merge storyline_articles. Feature: vault_mvp_spine / NI_VAULT_MVP_SPINE.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import (
    AUTO_TIMELINE_END,
    AUTO_TIMELINE_START,
    MAX_MVP_WIKI_TARGETS,
    SCIENCE_TOPIC_DIR,
    clipping_vault_rel_path,
    entity_vault_rel_path,
    is_clipping_vault_path,
    is_science_vault_domain,
    merge_tags,
    science_topic_vault_rel_path,
    slugify_entity_name,
    structural_tags_for_note,
)

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def vault_mvp_spine_enabled() -> bool:
    raw = os.environ.get("NI_VAULT_MVP_SPINE", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    try:
        from config.feature_registry import is_feature_enabled

        return is_feature_enabled("vault_mvp_spine", default=True)
    except Exception:
        return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _schema(domain_key: str) -> str:
    return domain_key.replace("-", "_")


def _load_article(domain_key: str, article_id: int) -> dict[str, Any] | None:
    schema = _schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id, COALESCE(a.title, ''), a.url,
                       a.published_at::date,
                       LEFT(COALESCE(a.content, a.summary, ''), 4000)
                FROM {schema}.articles a
                WHERE a.id = %s
                """,
                (int(article_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                f"""
                SELECT ae.canonical_entity_id, ec.canonical_name,
                       lower(COALESCE(ec.entity_type, '')),
                       COALESCE((
                         SELECT COUNT(*)::int FROM {schema}.article_entities x
                         WHERE x.canonical_entity_id = ae.canonical_entity_id
                       ), 0) AS mentions
                FROM {schema}.article_entities ae
                JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                WHERE ae.article_id = %s AND ae.canonical_entity_id IS NOT NULL
                ORDER BY mentions DESC, ae.id ASC
                LIMIT 16
                """,
                (int(article_id),),
            )
            ents = [
                {
                    "id": int(r[0]),
                    "name": r[1] or f"entity-{r[0]}",
                    "entity_type": r[2] or "",
                    "mentions": int(r[3] or 0),
                }
                for r in (cur.fetchall() or [])
            ]
    pub = row[3].isoformat() if isinstance(row[3], date) else (str(row[3])[:10] if row[3] else "")
    return {
        "id": int(row[0]),
        "title": row[1] or f"Article {article_id}",
        "url": row[2] or "",
        "published": pub,
        "excerpt": (row[4] or "").strip(),
        "entities": ents,
        "domain_key": domain_key,
    }


def classify_wiki_targets(
    domain_key: str,
    article: dict[str, Any],
    *,
    limit: int = MAX_MVP_WIKI_TARGETS,
) -> list[dict[str, Any]]:
    """Organize: related wiki notes + stubs to seed."""
    from services.vault_note_rag_service import find_similar_vault_notes
    from services.vault_notes_registry_service import get_vault_note

    targets: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for ent in article.get("entities") or []:
        if len(targets) >= limit:
            break
        name = ent["name"]
        etype = ent.get("entity_type") or ""
        path = entity_vault_rel_path(name, domain_key=domain_key, entity_type=etype)
        if path in seen_paths:
            continue
        existing = get_vault_note(
            domain_key=domain_key, note_type="entity", object_id=int(ent["id"])
        )
        if existing and existing.get("vault_path"):
            path = existing["vault_path"]
        seen_paths.add(path)
        targets.append(
            {
                "note_type": "entity",
                "object_id": int(ent["id"]),
                "vault_path": path,
                "title": name,
                "wikilink": name,
                "reason": "entity",
                "exists": bool(existing),
                "seed": not bool(existing),
                "entity_type": etype,
            }
        )

    query = f"{article.get('title') or ''} {article.get('excerpt') or ''}"[:1500]
    for note_type in ("entity", "cluster", "storyline", "event"):
        if len(targets) >= limit:
            break
        try:
            sims = find_similar_vault_notes(
                domain_key=domain_key,
                note_type=note_type,
                query_text=query,
                limit=4,
            )
        except Exception:
            sims = []
        for s in sims:
            path = s.get("vault_path") or ""
            if not path or path in seen_paths or is_clipping_vault_path(path):
                continue
            if float(s.get("score") or 0) < 0.12:
                continue
            seen_paths.add(path)
            targets.append(
                {
                    "note_type": note_type,
                    "object_id": 0,
                    "vault_path": path,
                    "title": s.get("title") or path.split("/")[-1].replace(".md", ""),
                    "wikilink": (s.get("title") or "").strip()
                    or path.split("/")[-1].replace(".md", "").replace("_", " "),
                    "reason": "similarity",
                    "exists": True,
                    "seed": False,
                    "score": s.get("score"),
                }
            )
            if len(targets) >= limit:
                break

    # Gap fill: prefer attach-to-existing over headline cluster stubs
    if not targets and (article.get("entities") or []):
        ent = article["entities"][0]
        etype = ent.get("entity_type") or ""
        path = entity_vault_rel_path(
            ent["name"], domain_key=domain_key, entity_type=etype
        )
        targets.append(
            {
                "note_type": "entity",
                "object_id": int(ent["id"]),
                "vault_path": path,
                "title": ent["name"],
                "wikilink": ent["name"],
                "reason": "gap_stub",
                "exists": False,
                "seed": True,
                "entity_type": etype,
            }
        )
    elif not targets:
        # Wider similarity pass (lower score floor) across durable wiki types
        for note_type in ("entity", "cluster", "storyline", "event"):
            if targets:
                break
            try:
                sims = find_similar_vault_notes(
                    domain_key=domain_key,
                    note_type=note_type,
                    query_text=query,
                    limit=6,
                )
            except Exception:
                sims = []
            for s in sims:
                path = s.get("vault_path") or ""
                if not path or path in seen_paths or is_clipping_vault_path(path):
                    continue
                if float(s.get("score") or 0) < 0.06:
                    continue
                seen_paths.add(path)
                targets.append(
                    {
                        "note_type": note_type,
                        "object_id": 0,
                        "vault_path": path,
                        "title": s.get("title") or path.split("/")[-1].replace(".md", ""),
                        "wikilink": (s.get("title") or "").strip()
                        or path.split("/")[-1].replace(".md", "").replace("_", " "),
                        "reason": "similarity_gap",
                        "exists": True,
                        "seed": False,
                        "score": s.get("score"),
                    }
                )
                break

        if not targets:
            # Title / token ILIKE against existing vault notes (no new file)
            title = (article.get("title") or "").strip()
            tokens = [
                t
                for t in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", title)
                if t.lower()
                not in {
                    "the",
                    "and",
                    "for",
                    "with",
                    "from",
                    "that",
                    "this",
                    "watch",
                    "live",
                    "new",
                    "says",
                    "after",
                    "over",
                }
            ][:6]
            if tokens:
                try:
                    with get_db_connection_context() as conn:
                        with conn.cursor() as cur:
                            like_parts = " OR ".join(
                                ["title ILIKE %s OR vault_path ILIKE %s"] * len(tokens)
                            )
                            params: list[Any] = [domain_key]
                            for tok in tokens:
                                params.extend([f"%{tok}%", f"%{slugify_entity_name(tok)}%"])
                            cur.execute(
                                f"""
                                SELECT vault_path, title, note_type
                                FROM intelligence.vault_notes
                                WHERE domain_key = %s
                                  AND note_type IN ('entity', 'cluster', 'storyline', 'event')
                                  AND lifecycle <> 'frozen'
                                  AND ({like_parts})
                                ORDER BY
                                  CASE note_type
                                    WHEN 'entity' THEN 0
                                    WHEN 'cluster' THEN 1
                                    WHEN 'storyline' THEN 2
                                    ELSE 3
                                  END,
                                  note_updated_at DESC NULLS LAST
                                LIMIT 3
                                """,
                                params,
                            )
                            for path, ttitle, ntype in cur.fetchall() or []:
                                if not path or path in seen_paths or is_clipping_vault_path(str(path)):
                                    continue
                                seen_paths.add(path)
                                targets.append(
                                    {
                                        "note_type": ntype,
                                        "object_id": 0,
                                        "vault_path": path,
                                        "title": ttitle or path.split("/")[-1].replace(".md", ""),
                                        "wikilink": (ttitle or "").strip()
                                        or path.split("/")[-1].replace(".md", "").replace("_", " "),
                                        "reason": "title_match",
                                        "exists": True,
                                        "seed": False,
                                    }
                                )
                                break
                except Exception as e:
                    logger.debug("classify title_match %s: %s", article.get("id"), e)

        if not targets:
            # Last resort: topic stub from title (avoid when any attach worked)
            stub_title = (article.get("title") or "Untitled topic")[:80]
            if is_science_vault_domain(domain_key):
                path = science_topic_vault_rel_path(stub_title)
                note_type = "cluster"
            else:
                key = slugify_entity_name(stub_title, max_len=40) or f"topic-{article['id']}"
                path = f"40_Reference/clusters/{key}.md"
                note_type = "cluster"
            targets.append(
                {
                    "note_type": note_type,
                    "object_id": 92_000_000 + (int(article["id"]) % 1_000_000),
                    "vault_path": path,
                    "title": stub_title,
                    "wikilink": stub_title,
                    "reason": "gap_topic_stub",
                    "exists": False,
                    "seed": True,
                }
            )

    return targets[:limit]


def _summarize_clipping(article: dict[str, Any], *, domain_key: str = "") -> str:
    """Short grounded summary; LLM preferred, extractive fallback."""
    title = article.get("title") or "Untitled"
    excerpt = (article.get("excerpt") or "")[:2800]
    science = is_science_vault_domain(domain_key)
    purpose = (
        "research paper / scientific article for a science-vault clipping note"
        if science
        else "news article for a second-brain clipping note"
    )
    extra_focus = " (labs, methods, findings)" if science else ""
    prompt = f"""Summarize this {purpose}.
2–4 short paragraphs max. Ground only in the text. No speculation.
Include who/what/where when present{extra_focus}.

Title: {title}

Text:
{excerpt}
"""

    async def _gen() -> str:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.INTERACTIVE_SUMMARY,
            urgency="standard",
            approx_prompt_chars=len(prompt),
        )
        return (result.text or "").strip()

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with ThreadPoolExecutor(max_workers=1) as pool:
                text = pool.submit(lambda: asyncio.run(_gen())).result(timeout=120)
        else:
            text = asyncio.run(_gen())
        if text:
            return text[:2000]
    except Exception as e:
        logger.debug("clipping LLM summary fallback: %s", e)

    # Extractive fallback
    paras = [p.strip() for p in re.split(r"\n\s*\n", excerpt) if p.strip()]
    if not paras:
        return f"{title}."
    return "\n\n".join(paras[:2])[:1500]


def _write_clipping(
    domain_key: str,
    article: dict[str, Any],
    targets: list[dict[str, Any]],
    summary: str,
) -> dict[str, Any]:
    from services.vault_bridge_service import _render_frontmatter, vault_root, vault_write_enabled
    from services.vault_notes_registry_service import upsert_vault_note
    from services.vault_note_rag_service import reindex_vault_note
    from services.vault_quality_gates import is_junk_title, sanitize_vault_prose

    if not vault_write_enabled():
        return {"ok": False, "error": "vault_write_disabled"}

    title = sanitize_vault_prose(str(article.get("title") or ""), max_length=220)
    if is_junk_title(title):
        return {"ok": False, "error": "junk_title", "skipped": True}

    aid = int(article["id"])
    rel = clipping_vault_rel_path(
        published=article.get("published") or "",
        article_id=aid,
        title=title or "",
        domain_key=domain_key,
    )
    links = " · ".join(f"[[{t['wikilink']}]]" for t in targets if t.get("wikilink"))
    day = (article.get("published") or _now_iso()[:10])[:10]
    summary_clean = sanitize_vault_prose(summary, max_length=2000)
    fm = {
        "ni_domain": domain_key,
        "note_type": "clipping",
        "article_id": aid,
        "object_id": aid,
        "source": article.get("url") or "",
        "status": "processed",
        "created": day,
        "updated": _now_iso()[:10],
        "ni_auto": True,
        "clipping": True,
        "tags": structural_tags_for_note(
            note_type="clipping",
            domain_key=domain_key,
            extra=["clipping"],
        ),
    }
    body = f"""# {title or f'Article {aid}'}

## Summary

{summary_clean.strip()}

## Related

{links or '_No related wiki notes._'}

## Source

- article:`{aid}`
- date: {day}
- url: {article.get('url') or '_none_'}
"""
    md = _render_frontmatter(fm) + body
    path = vault_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    # Idempotent: if same article path exists, refresh summary/related but keep file
    path.write_text(md, encoding="utf-8")

    upsert_vault_note(
        domain_key=domain_key,
        note_type="clipping",
        object_id=aid,
        vault_path=rel,
        title=title or f"Article {aid}",
        note_status="note_ready",
        lifecycle="seeded",
        last_article_id=aid,
        tags=list(fm["tags"]),
        metadata={
            "clipping": True,
            "article_id": aid,
            "source": article.get("url") or "",
            "related_paths": [t["vault_path"] for t in targets],
        },
        tags_source="ni_structural",
    )
    try:
        reindex_vault_note(
            rel,
            title=title or "",
            body=body,
            domain_key=domain_key,
            note_type="clipping",
        )
    except Exception:
        pass
    return {"ok": True, "vault_path": rel, "title": title}


def _ensure_wiki_note(domain_key: str, target: dict[str, Any]) -> None:
    from services.vault_bridge_service import _render_frontmatter, vault_root, vault_write_enabled
    from services.vault_notes_registry_service import upsert_vault_note
    from services.vault_quality_gates import entity_md_write_allowed, is_junk_title

    if not vault_write_enabled():
        return
    path = vault_root() / target["vault_path"]
    if path.is_file():
        return
    note_type = target.get("note_type") or "entity"
    title = target.get("title") or "Untitled"
    if is_junk_title(str(title)):
        logger.info("mvp skip wiki seed junk title: %s", title[:80])
        return
    if note_type == "entity":
        oid = int(target.get("object_id") or 0)
        allowed, reason = entity_md_write_allowed(
            domain_key=domain_key,
            canonical_entity_id=oid if oid > 0 else None,
            file_exists=False,
        )
        if not allowed:
            logger.debug(
                "mvp skip entity md create id=%s reason=%s", oid, reason
            )
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = structural_tags_for_note(
        note_type=note_type,
        domain_key=domain_key,
        entity_type=target.get("entity_type"),
        extra=["seed"],
    )
    fm = {
        "ni_domain": domain_key,
        "note_type": note_type,
        "object_id": int(target.get("object_id") or 0),
        "lifecycle": "stub",
        "status": "seeded",
        "ni_auto": True,
        "created": _now_iso()[:10],
        "updated": _now_iso()[:10],
        "tags": tags,
    }
    if note_type == "entity" and target.get("object_id"):
        fm["canonical_entity_id"] = int(target["object_id"])
    body = f"""# {title}

## Basics

Stub seeded by vault MVP ingest (second-brain gap fill).

## Timeline

{AUTO_TIMELINE_START}
- _Awaiting updates._
{AUTO_TIMELINE_END}
"""
    path.write_text(_render_frontmatter(fm) + body, encoding="utf-8")
    if int(target.get("object_id") or 0) > 0:
        upsert_vault_note(
            domain_key=domain_key,
            note_type=note_type,
            object_id=int(target["object_id"]),
            vault_path=target["vault_path"],
            title=title,
            note_status="note_ready",
            lifecycle="stub",
            tags=tags,
            metadata={"mvp_seed": True},
            tags_source="ni_structural",
        )


def _distill_onto_wiki(
    domain_key: str,
    article: dict[str, Any],
    target: dict[str, Any],
    clipping_title: str,
) -> dict[str, Any]:
    from services.vault_bridge_service import (
        _parse_frontmatter_rich,
        _render_frontmatter,
        vault_root,
        vault_write_enabled,
    )
    from services.vault_note_patch import append_timeline_bullet, ensure_fences
    from services.vault_notes_registry_service import upsert_vault_note
    from services.vault_quality_gates import entity_md_write_allowed

    if not vault_write_enabled():
        return {"ok": False, "error": "vault_write_disabled"}

    note_type = str(target.get("note_type") or "entity")
    root = vault_root()
    path = root / target["vault_path"]
    if note_type == "entity":
        oid = int(target.get("object_id") or 0)
        existing_life = None
        try:
            from services.vault_notes_registry_service import get_vault_note

            existing = get_vault_note(
                domain_key=domain_key, note_type="entity", object_id=oid
            )
            existing_life = (existing or {}).get("lifecycle")
        except Exception:
            existing = None
        allowed, reason = entity_md_write_allowed(
            domain_key=domain_key,
            canonical_entity_id=oid if oid > 0 else None,
            existing_lifecycle=str(existing_life) if existing_life else None,
            file_exists=path.is_file(),
        )
        if not allowed:
            return {
                "ok": True,
                "skipped": True,
                "reason": f"entity_policy:{reason}",
                "path": target.get("vault_path"),
            }

    _ensure_wiki_note(domain_key, target)
    if not path.is_file():
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_md_file",
            "path": target.get("vault_path"),
        }
    rel = target["vault_path"]
    path = vault_root() / rel
    if not path.is_file():
        return {"ok": False, "error": "missing_file", "path": rel}

    existing = path.read_text(encoding="utf-8")
    fm = _parse_frontmatter_rich(existing)
    body = (
        _FRONTMATTER_RE.sub("", existing, count=1).lstrip("\n")
        if _FRONTMATTER_RE.match(existing)
        else existing
    )
    aid = int(article["id"])
    day = (article.get("published") or _now_iso()[:10])[:10]
    title = (article.get("title") or "Untitled").strip()[:140]
    bullet = (
        f"- {day} — {title} (article:{aid}) "
        f"— [[{clipping_title}]]"
    )
    body = append_timeline_bullet(ensure_fences(body), bullet)

    tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
    tags = merge_tags(
        tags,
        structural_tags_for_note(
            note_type=str(target.get("note_type") or fm.get("note_type") or "entity"),
            domain_key=domain_key,
            entity_type=target.get("entity_type"),
            extra=["update/new"],
        ),
    )
    fm = {
        **fm,
        "ni_domain": domain_key,
        "note_type": fm.get("note_type") or target.get("note_type") or "entity",
        "last_article_id": aid,
        "updated": _now_iso()[:10],
        "ni_auto": True,
        "tags": tags,
    }
    path.write_text(_render_frontmatter(fm) + body, encoding="utf-8")

    oid = int(target.get("object_id") or fm.get("object_id") or fm.get("canonical_entity_id") or 0)
    if oid > 0:
        upsert_vault_note(
            domain_key=domain_key,
            note_type=str(fm.get("note_type") or target.get("note_type") or "entity"),
            object_id=oid,
            vault_path=rel,
            title=target.get("title"),
            note_status="note_ready",
            lifecycle=str(fm.get("lifecycle") or "seeded"),
            last_article_id=aid,
            tags=tags,
            metadata={"last_clipping_article_id": aid},
            tags_source="ni_structural",
        )
    return {"ok": True, "path": rel, "article_id": aid}


def file_article_to_vault(
    domain_key: str,
    article_id: int,
    *,
    skip_llm_summary: bool = False,
) -> dict[str, Any]:
    """CODE MVP entry: Capture clipping, Organize links, Distill onto wiki notes."""
    if not vault_mvp_spine_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled"}

    article = _load_article(domain_key, int(article_id))
    if not article:
        return {"ok": False, "error": "article_not_found"}

    targets = classify_wiki_targets(domain_key, article)
    if skip_llm_summary:
        summary = (article.get("excerpt") or article.get("title") or "")[:800]
    else:
        summary = _summarize_clipping(article, domain_key=domain_key)

    clip = _write_clipping(domain_key, article, targets, summary)
    if not clip.get("ok"):
        return {"ok": False, "error": clip.get("error"), "stage": "capture"}

    clipping_title = str(clip.get("title") or article.get("title") or f"Article {article_id}")
    distilled: list[dict[str, Any]] = []
    for t in targets:
        try:
            distilled.append(_distill_onto_wiki(domain_key, article, t, clipping_title))
        except Exception as e:
            logger.warning("mvp distill %s: %s", t.get("vault_path"), e)
            distilled.append({"ok": False, "error": str(e), "path": t.get("vault_path")})

    try:
        from services.vault_tag_link_sync_service import sync_vault_file

        sync_vault_file(clip["vault_path"])
        for d in distilled:
            if d.get("ok") and d.get("path"):
                sync_vault_file(d["path"])
    except Exception as e:
        logger.debug("mvp tag sync: %s", e)

    # Express: Situation briefs for hubs touched by this clipping/wiki distill
    # Express: when morning prime is on, defer Situation briefs / longform to
    # the batch job (no per-article Ollama). Capture + Distill stay incremental.
    express: dict[str, Any] = {"ok": False, "skipped": True, "reason": "not_run"}
    try:
        from services.vault_morning_prime_service import vault_morning_prime_enabled

        if vault_morning_prime_enabled():
            express = {
                "ok": True,
                "skipped": True,
                "reason": "deferred_to_morning_prime",
            }
        else:
            from services.vault_hub_brief_service import express_briefs_from_mvp

            express = express_briefs_from_mvp(
                domain_key,
                article=article,
                clipping_path=str(clip.get("vault_path") or ""),
                clipping_summary=summary,
                targets=targets,
                max_hubs=2,
            )
    except Exception as e:
        logger.debug("mvp express: %s", e)
        express = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "article_id": int(article_id),
        "domain_key": domain_key,
        "clipping": clip,
        "targets": [
            {"path": t["vault_path"], "title": t["title"], "reason": t["reason"], "seed": t.get("seed")}
            for t in targets
        ],
        "distilled": distilled,
        "distilled_ok": sum(1 for d in distilled if d.get("ok")),
        "express": express,
    }
