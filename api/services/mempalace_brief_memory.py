"""
MemPalace editorial memory for Morning Briefing Manager.

Wing: News Intelligence. Rooms: morning_brief, watches, preferred_narratives,
brief_diary, skip_list.

Uses Homelab MCPO HTTP gateway when reachable; falls back to empty memory so
morning prime never blocks on MemPalace outage.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from shared.vault_note_contract import (
    MEMPALACE_BRIEF_AGENT,
    MEMPALACE_BRIEF_WING,
    MEMPALACE_ROOMS,
)

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "http://127.0.0.1:18443/mempalace"


def mempalace_brief_enabled() -> bool:
    raw = os.environ.get("NI_MEMPALACE_BRIEF_MEMORY", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return True


def _base_url() -> str:
    return (
        os.environ.get("MEMPALACE_HTTP_BASE", "").strip()
        or os.environ.get("MEMPALACE_API_BASE", "").strip()
        or _DEFAULT_BASE
    ).rstrip("/")


def _auth_header() -> dict[str, str]:
    """MCPO gateway expects Bearer token (OPENWEBUI_MCPO_API_KEY)."""
    key = (
        os.environ.get("MEMPALACE_HTTP_API_KEY", "").strip()
        or os.environ.get("OPENWEBUI_MCPO_API_KEY", "").strip()
        or os.environ.get("MCPO_API_KEY", "").strip()
    )
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def _post(tool: str, payload: dict[str, Any], *, timeout: float = 12.0) -> Any:
    """POST to MCPO form endpoint ``/{tool}_post`` (or ``/{tool}``)."""
    base = _base_url()
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **_auth_header(),
    }
    last_err: Exception | None = None
    for path in (f"{base}/{tool}_post", f"{base}/{tool}"):
        req = urllib.request.Request(
            path,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"text": raw}
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return {}


def load_editorial_memory(*, limit: int = 8) -> dict[str, Any]:
    """Search / diary-read MemPalace rooms for the briefing manager."""
    out: dict[str, Any] = {
        "ok": False,
        "watches": [],
        "preferred": [],
        "skip": [],
        "diary": [],
        "snippets": [],
        "error": None,
    }
    if not mempalace_brief_enabled():
        out["error"] = "disabled"
        return out
    try:
        for room, key in (
            ("watches", "watches"),
            ("preferred_narratives", "preferred"),
            ("skip_list", "skip"),
            ("morning_brief", "snippets"),
        ):
            try:
                res = _post(
                    "mempalace_search",
                    {
                        "query": f"{room} morning brief narratives prefer watch storyline_id",
                        "limit": limit,
                        "wing": MEMPALACE_BRIEF_WING,
                        "room": room,
                        "max_distance": 1.4,
                    },
                )
                items = _normalize_search(res)
                # Always merge room listing for watch/prefer/skip — semantic search
                # alone often returns stale drawers and drops fresh storyline pins.
                if room in (
                    "watches",
                    "preferred_narratives",
                    "skip_list",
                ):
                    try:
                        listed = _post(
                            "mempalace_list_drawers",
                            {
                                "wing": MEMPALACE_BRIEF_WING,
                                "room": room,
                                "limit": max(limit, 24),
                            },
                        )
                        listed_items = _normalize_search(listed)
                        if listed_items:
                            seen = {x for x in items}
                            for text in listed_items:
                                if text not in seen:
                                    items.append(text)
                                    seen.add(text)
                    except Exception as e:
                        logger.debug("mempalace list_drawers %s: %s", room, e)
                        if not items:
                            raise
                out[key] = items[: max(limit, 24)]
            except Exception as e:
                logger.debug("mempalace search %s: %s", room, e)
        try:
            diary = _post(
                "mempalace_diary_read",
                {
                    "agent_name": MEMPALACE_BRIEF_AGENT,
                    "last_n": limit,
                    "wing": MEMPALACE_BRIEF_WING,
                },
            )
            out["diary"] = _normalize_diary(diary)
        except Exception as e:
            logger.debug("mempalace diary_read: %s", e)
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)
        logger.warning("load_editorial_memory failed: %s", e)
    return out


def diary_write_brief(
    *,
    briefing_day: str,
    ongoing: list[dict[str, Any]],
    new_of_note: list[dict[str, Any]],
    rationale: str = "",
) -> dict[str, Any]:
    """Record today's slate so tomorrow's manager has continuity."""
    if not mempalace_brief_enabled():
        return {"ok": False, "error": "disabled"}
    lines = [
        f"day={briefing_day}",
        "ongoing="
        + "; ".join(
            f"{x.get('domain_key')}:{x.get('storyline_id')}:{x.get('title', '')[:60]}"
            for x in ongoing[:20]
        ),
        "new="
        + "; ".join(
            f"{x.get('domain_key')}:{x.get('storyline_id')}:{x.get('title', '')[:60]}"
            for x in new_of_note[:12]
        ),
    ]
    if rationale:
        lines.append(f"why={rationale[:500]}")
    entry = " | ".join(lines)
    try:
        _post(
            "mempalace_diary_write",
            {
                "agent_name": MEMPALACE_BRIEF_AGENT,
                "entry": entry,
                "topic": "brief_diary",
                "wing": MEMPALACE_BRIEF_WING,
            },
        )
        _post(
            "mempalace_add_drawer",
            {
                "wing": MEMPALACE_BRIEF_WING,
                "room": "brief_diary",
                "content": entry,
                "source_file": f"morning_brief/{briefing_day}.md",
                "added_by": MEMPALACE_BRIEF_AGENT,
            },
        )
        return {"ok": True, "entry_chars": len(entry)}
    except Exception as e:
        logger.warning("diary_write_brief failed: %s", e)
        return {"ok": False, "error": str(e)}


def apply_watches_delta(delta: list[dict[str, Any]]) -> dict[str, Any]:
    """Persist watch promote/demote notes from manager JSON."""
    if not mempalace_brief_enabled() or not delta:
        return {"ok": True, "written": 0}
    written = 0
    for item in delta[:20]:
        action = str(item.get("action") or "watch").strip().lower()
        room = "skip_list" if action in ("skip", "stop", "demote") else "watches"
        if action in ("prefer", "lock"):
            room = "preferred_narratives"
        content = (
            f"{action}: {item.get('title') or ''} "
            f"domain={item.get('domain_key')} storyline_id={item.get('storyline_id')} "
            f"reason={item.get('reason') or ''}"
        ).strip()
        if len(content) < 8:
            continue
        try:
            _post(
                "mempalace_add_drawer",
                {
                    "wing": MEMPALACE_BRIEF_WING,
                    "room": room if room in MEMPALACE_ROOMS else "watches",
                    "content": content[:2000],
                    "added_by": MEMPALACE_BRIEF_AGENT,
                },
            )
            written += 1
        except Exception as e:
            logger.debug("apply_watches_delta: %s", e)
    return {"ok": True, "written": written}


def _normalize_search(res: Any) -> list[str]:
    out: list[str] = []
    if isinstance(res, dict):
        for key in ("results", "drawers", "items", "data"):
            val = res.get(key)
            if isinstance(val, list):
                for row in val:
                    text = _row_text(row)
                    if text:
                        out.append(text)
                break
        if not out and res.get("content"):
            out.append(str(res["content"])[:800])
    elif isinstance(res, list):
        for row in res:
            text = _row_text(row)
            if text:
                out.append(text)
    elif isinstance(res, str) and res.strip():
        out.append(res.strip()[:800])
    return out[:12]


def _normalize_diary(res: Any) -> list[str]:
    return _normalize_search(res)


def _row_text(row: Any) -> str:
    if isinstance(row, str):
        return row.strip()[:800]
    if not isinstance(row, dict):
        return ""
    for k in (
        "content",
        "content_preview",
        "entry",
        "text",
        "drawer_content",
        "verbatim",
    ):
        if row.get(k):
            return str(row[k]).strip()[:800]
    return ""
