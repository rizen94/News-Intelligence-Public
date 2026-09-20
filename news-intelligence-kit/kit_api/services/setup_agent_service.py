"""Lightweight Ollama agent for setup domain proposals (JSON only, no SQL)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from config.runtime import env_str

logger = logging.getLogger(__name__)


def _slug_domain_key(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:48] or "custom-domain"


def _schema_from_key(domain_key: str) -> str:
    return domain_key.replace("-", "_")


def _load_feed_hints() -> dict[str, list[str]]:
    try:
        import yaml
        from pathlib import Path

        p = Path(__file__).resolve().parents[2] / "config" / "setup" / "feed_hints.yaml"
        if p.is_file():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return {str(k): list(v or []) for k, v in data.items()}
    except Exception as e:
        logger.debug("feed_hints: %s", e)
    return {}


async def _ollama_generate(prompt: str) -> str:
    host = env_str("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = env_str("OLLAMA_MODEL_PRIMARY", "llama3.1:8b")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return (r.json().get("response") or "").strip()
    except Exception as e:
        logger.warning("setup agent ollama: %s", e)
        return ""


def _parse_domains_json(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def _fallback_domains(interests: str) -> list[dict[str, Any]]:
    """Rule-based fallback when Ollama unavailable."""
    hints = _load_feed_hints()
    parts = [p.strip() for p in re.split(r"[,;]+", interests) if p.strip()]
    if not parts:
        parts = ["general news"]
    out: list[dict[str, Any]] = []
    for part in parts[:5]:
        dk = _slug_domain_key(part)
        feeds = hints.get(part.lower(), hints.get("general", []))[:5]
        out.append(
            {
                "domain_key": dk,
                "schema_name": _schema_from_key(dk),
                "display_name": part.title(),
                "description": f"News and updates about {part}.",
                "focus_areas": [part.lower()],
                "llm_prompt_guidance": f"Focus on credible sources for {part}.",
                "rss": {"feeds": [{"url": u, "title": u} for u in feeds]},
            }
        )
    return out


async def propose_domains_from_interests(interests: str) -> list[dict[str, Any]]:
    hints = _load_feed_hints()
    hint_sample = json.dumps({k: v[:3] for k, v in list(hints.items())[:8]})
    tier = env_str("KIT_HARDWARE_TIER", "standard")
    max_domains = {"minimal": 2, "standard": 4, "performance": 6}.get(tier, 4)
    prompt = f"""You are a news intelligence setup assistant. Given user interests, propose 1-{max_domains} domain silos as JSON array ONLY.
Each object must have: domain_key (lowercase hyphenated), schema_name (underscores), display_name, description,
focus_areas (array of strings), llm_prompt_guidance (string), rss.feeds (array of {{url, title}}).
Use only RSS URLs from these hints when possible: {hint_sample}
User interests: {interests}
Return JSON array only, no markdown."""

    raw = await _ollama_generate(prompt)
    domains = _parse_domains_json(raw)
    if not domains:
        domains = _fallback_domains(interests)

    normalized: list[dict[str, Any]] = []
    for d in domains[:max_domains]:
        dk = _slug_domain_key(str(d.get("domain_key") or d.get("display_name") or "domain"))
        normalized.append(
            {
                "domain_key": dk,
                "schema_name": str(d.get("schema_name") or _schema_from_key(dk)),
                "display_name": str(d.get("display_name") or dk.replace("-", " ").title())[:100],
                "description": str(d.get("description") or "")[:500],
                "focus_areas": list(d.get("focus_areas") or [])[:10],
                "llm_prompt_guidance": str(d.get("llm_prompt_guidance") or "")[:1000],
                "rss": d.get("rss") or {"feeds": []},
            }
        )
    return normalized


async def suggest_feeds(domain_key: str, query: str) -> list[dict[str, str]]:
    hints = _load_feed_hints()
    q = query.lower()
    found: list[dict[str, str]] = []
    for cat, urls in hints.items():
        if q in cat or cat in q:
            for u in urls[:8]:
                found.append({"url": u, "title": cat})
    if not found:
        for urls in hints.values():
            for u in urls[:3]:
                found.append({"url": u, "title": u})
            if len(found) >= 5:
                break
    return found[:10]
