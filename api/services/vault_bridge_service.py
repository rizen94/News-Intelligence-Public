"""
Obsidian news vault bridge for Widow automation.

Reads/writes work-queue cursors, tracking-candidates, and 30_Stories stubs at
NEWS_INTEL_VAULT_PATH (same mount as Homelab obsidian-news-vault MCP).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_str
from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def vault_root() -> Path:
    root = Path(env_str("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault"))
    return root.resolve()


def vault_write_enabled() -> bool:
    return env_bool("NEWS_INTEL_VAULT_WRITE", True)


def _parse_frontmatter(text: str) -> dict[str, Any]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, Any] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        out[key] = val
    return out


def _render_frontmatter(data: dict[str, Any]) -> str:
    lines = ["---"]
    for k, v in data.items():
        if isinstance(v, (list, dict)):
            lines.append(f"{k}: {json.dumps(v)}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def read_work_queue() -> dict[str, Any]:
    path = vault_root() / "00_Inbox" / "work-queue.md"
    if not path.is_file():
        return {"found": False, "cursors": {}, "body": ""}
    text = path.read_text(encoding="utf-8")
    cursors = _parse_frontmatter(text)
    return {"found": True, "path": str(path), "cursors": cursors, "body": text}


def read_cursors() -> dict[str, str | None]:
    wq = read_work_queue()
    c = wq.get("cursors") or {}
    return {
        "last_tracking_scan_at": c.get("last_tracking_scan_at"),
        "last_reviewed_at": c.get("last_reviewed_at"),
        "last_context_id": c.get("last_context_id"),
        "last_connection_loop_at": c.get("last_connection_loop_at"),
    }


def update_cursors(
    *,
    last_tracking_scan_at: str | None = None,
    last_reviewed_at: str | None = None,
    last_context_id: str | None = None,
    last_connection_loop_at: str | None = None,
) -> dict[str, Any]:
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}
    path = vault_root() / "00_Inbox" / "work-queue.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_work_queue()
    fm = dict(existing.get("cursors") or {})
    now = datetime.now(timezone.utc).isoformat()
    if last_tracking_scan_at is not None:
        fm["last_tracking_scan_at"] = last_tracking_scan_at or now
    if last_reviewed_at is not None:
        fm["last_reviewed_at"] = last_reviewed_at
    if last_context_id is not None:
        fm["last_context_id"] = last_context_id
    if last_connection_loop_at is not None:
        fm["last_connection_loop_at"] = last_connection_loop_at or now
    body = existing.get("body") or ""
    if _FRONTMATTER_RE.match(body):
        body = _FRONTMATTER_RE.sub("", body, count=1).lstrip()
    content = _render_frontmatter(fm) + body
    path.write_text(content, encoding="utf-8")
    sync_cursors_to_automation_state(fm)
    return {"ok": True, "cursors": fm}


def sync_cursors_to_automation_state(cursors: dict[str, Any]) -> None:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES ('vault_work_queue', %s, NOW())
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (json.dumps(cursors),),
                )
            conn.commit()
    except Exception as e:
        logger.debug("sync_cursors_to_automation_state: %s", e)


def build_coverage_set() -> dict[str, set[str]]:
    """Light vault inventory for tracking discovery reconcile (Pass 0/4)."""
    root = vault_root()
    coverage: dict[str, set[str]] = {
        "storyline_slugs": set(),
        "investigation_slugs": set(),
        "entity_ftm_ids": set(),
        "context_ids": set(),
        "connection_slugs": set(),
    }
    if not root.is_dir():
        return coverage

    def _scan_dir(rel: str, bucket: str, id_re: re.Pattern[str] | None = None) -> None:
        base = root / rel
        if not base.is_dir():
            return
        for p in base.rglob("*.md"):
            slug = p.stem.lower()
            coverage[bucket].add(slug)
            if id_re:
                m = id_re.search(p.name)
                if m:
                    coverage[bucket].add(m.group(1))

    _scan_dir("30_Stories", "storyline_slugs")
    _scan_dir("20_Investigations", "investigation_slugs")
    _scan_dir("25_Connections", "connection_slugs")
    _scan_dir("40_Reference/entities", "entity_ftm_ids", re.compile(r"([A-Za-z0-9-]{8,})"))
    _scan_dir("40_Reference/contexts", "context_ids", re.compile(r"(\d+)"))
    return coverage


def _is_vault_covered(candidate: dict[str, Any], coverage: dict[str, set[str]]) -> bool:
    title_slug = re.sub(r"[^a-z0-9]+", "-", (candidate.get("title") or "").lower()).strip("-")
    if title_slug and title_slug in coverage["storyline_slugs"]:
        return True
    if title_slug and title_slug in coverage["investigation_slugs"]:
        return True
    ftm = candidate.get("ftm_id") or candidate.get("canonical_entity_id")
    if ftm and str(ftm) in coverage["entity_ftm_ids"]:
        return True
    ctx = candidate.get("context_id")
    if ctx and str(ctx) in coverage["context_ids"]:
        return True
    sl = candidate.get("storyline_id")
    if sl and f"{candidate.get('domain_key', '')}-{sl}".lower() in coverage["storyline_slugs"]:
        return True
    return False


def write_candidates(
    candidates: list[dict[str, Any]],
    *,
    scan_since: str,
    domains_scanned: list[str],
) -> dict[str, Any]:
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    rel = f"00_Inbox/tracking-candidates-{today}.md"
    path = vault_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    ranked = [c for c in candidates if c.get("status") != "already_tracked"]
    deferred = [c for c in candidates if c.get("status") == "deferred"]
    demoted = [c for c in candidates if c.get("status") == "already_tracked"]
    fm = {
        "scan_since": scan_since,
        "domains_scanned": domains_scanned,
        "candidate_count": len(ranked),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    lines = [_render_frontmatter(fm).rstrip(), "", "## Ranked candidates", ""]
    lines.append("| Rank | Type | Domain(s) | Title | IDs | Score | Why | Action |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, c in enumerate(ranked[:40], start=1):
        ids = ", ".join(
            filter(
                None,
                [
                    f"sl={c.get('storyline_id')}" if c.get("storyline_id") else None,
                    f"ctx={c.get('context_id')}" if c.get("context_id") else None,
                    f"ftm={c.get('ftm_id')}" if c.get("ftm_id") else None,
                ],
            )
        )
        lines.append(
            f"| {i} | {c.get('type', '')} | {c.get('domain_keys', c.get('domain_key', ''))} "
            f"| {c.get('title', '')} | {ids} | {c.get('score', '')}/25 "
            f"| {c.get('why', '')} | {c.get('suggested_action', '')} |"
        )
    if demoted:
        lines.extend(["", "## Already tracked", ""])
        for c in demoted[:5]:
            lines.append(f"- {c.get('title')} — {c.get('vault_path', 'vault match')}")
    if deferred:
        lines.extend(["", "## Deferred", ""])
        for c in deferred[:10]:
            lines.append(f"- {c.get('title')} — {c.get('why', 'low score')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "path": rel, "candidate_count": len(ranked)}


def write_story_stub(
    *,
    domain_key: str,
    storyline_id: int,
    title: str,
    tracked_event_id: int | None = None,
) -> dict[str, Any]:
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "story"
    rel = f"30_Stories/{domain_key}-{storyline_id}-{slug}.md"
    path = vault_root() / rel
    if path.is_file():
        return {"ok": True, "path": rel, "created": False}
    fm = {
        "storyline_id": storyline_id,
        "domain_key": domain_key,
        "tracked_event_id": tracked_event_id or "",
        "stub": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    body = f"# {title}\n\n_Automation stub — expand in Journalism/Editorial or Stories UI._\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_frontmatter(fm) + body, encoding="utf-8")
    return {"ok": True, "path": rel, "created": True}


def write_connection_note(action: dict[str, Any]) -> dict[str, Any]:
    """Write LLM-drafted connection to 25_Connections/."""
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}
    title = str(action.get("title") or action.get("subject_summary") or "connection")[:60]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50] or "connection"
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rel = f"25_Connections/{date}-{slug}.md"
    path = vault_root() / rel
    if path.is_file():
        return {"ok": True, "path": rel, "created": False}
    fm = {
        "domain_key": action.get("domain_key") or "",
        "storyline_id": action.get("storyline_id") or "",
        "tracked_event_id": action.get("tracked_event_id") or "",
        "canonical_entity_id": action.get("canonical_entity_id") or "",
        "context_id": action.get("context_id") or "",
        "claim_id": action.get("claim_id") or "",
        "confidence": action.get("confidence") or "",
        "source": "editorial_room_loop",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rationale = str(action.get("rationale") or action.get("subject_summary") or "").strip()
    body = f"# {title}\n\n{rationale}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_frontmatter(fm) + body, encoding="utf-8")
    return {"ok": True, "path": rel, "created": True}


def append_session_log(summary: str) -> dict[str, Any]:
    if not vault_write_enabled():
        return {"ok": False, "error": "vault write disabled"}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rel = f"00_Inbox/sessions/{today}.md"
    path = vault_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
    block = f"\n\n## {stamp} — tracking discovery loop\n\n{summary}\n"
    if path.is_file():
        path.write_text(path.read_text(encoding="utf-8").rstrip() + block, encoding="utf-8")
    else:
        path.write_text(f"# Session log {today}\n{block}", encoding="utf-8")
    return {"ok": True, "path": rel}
