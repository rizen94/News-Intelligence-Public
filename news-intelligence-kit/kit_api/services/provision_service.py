"""Trusted domain provisioning (kit_provision_domain + RSS seed)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def validate_feed_url(url: str) -> dict[str, Any]:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        return {"valid": False, "error": "URL must start with http:// or https://"}
    try:
        import feedparser
        import httpx

        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "NewsIntelligence-Kit/1.0"})
            if r.status_code >= 400:
                return {"valid": False, "error": f"HTTP {r.status_code}"}
            parsed = feedparser.parse(r.content)
            if parsed.bozo and not parsed.entries:
                return {"valid": False, "error": "Could not parse feed"}
            title = (parsed.feed.get("title") if parsed.feed else None) or url
            return {"valid": True, "title": title, "entries": len(parsed.entries or [])}
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}


def provision_domain(domain: dict[str, Any]) -> dict[str, Any]:
    from shared.database.connection import get_db_connection_context

    dk = domain["domain_key"]
    schema = domain["schema_name"]
    display = domain["display_name"]
    desc = domain.get("description") or ""

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT public.kit_provision_domain(%s, %s, %s, %s)",
                (dk, schema, display, desc),
            )
            feeds = (domain.get("rss") or {}).get("feeds") or []
            for f in feeds:
                url = (f.get("url") if isinstance(f, dict) else str(f)).strip()
                if not url:
                    continue
                v = validate_feed_url(url)
                if not v.get("valid"):
                    logger.warning("skip invalid feed %s: %s", url, v.get("error"))
                    continue
                title = f.get("title") if isinstance(f, dict) else v.get("title", url)
                cur.execute(
                    f"""
                    INSERT INTO {schema}.rss_feeds (name, url, category, is_active)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (url) DO NOTHING
                    """,
                    (title[:255], url, "Setup"),
                )
        conn.commit()

    _write_domain_yaml(domain)
    _append_synthesis_config(domain)
    return {"domain_key": dk, "schema_name": schema, "feeds_seeded": len(feeds)}


def _kit_config_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "domains"


def _write_domain_yaml(domain: dict[str, Any]) -> None:
    cfg_dir = _kit_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    dk = domain["domain_key"]
    feeds = []
    for f in (domain.get("rss") or {}).get("feeds") or []:
        if isinstance(f, dict):
            feeds.append(f.get("url", ""))
        else:
            feeds.append(str(f))
    doc = {
        "domain_key": dk,
        "schema_name": domain["schema_name"],
        "display_name": domain["display_name"],
        "description": domain.get("description", ""),
        "is_active": True,
        "data_sources": {"rss": {"seed_feed_urls": [u for u in feeds if u]}},
        "focus_areas": domain.get("focus_areas") or [],
        "llm_prompt_guidance": domain.get("llm_prompt_guidance") or "",
    }
    path = cfg_dir / f"{dk}.yaml"
    path.write_text(yaml.dump(doc, default_flow_style=False, allow_unicode=True), encoding="utf-8")


def _append_synthesis_config(domain: dict[str, Any]) -> None:
    synth_path = Path(__file__).resolve().parents[2] / "config" / "domain_synthesis_config.yaml"
    data: dict[str, Any] = {}
    if synth_path.is_file():
        data = yaml.safe_load(synth_path.read_text(encoding="utf-8")) or {}
    dk = domain["domain_key"]
    if dk not in data:
        data[dk] = {
            "topic_clustering": {"graduation_confidence": 0.85},
            "storyline_development": {"proactive": {"lookback_hours": 72}},
        }
        synth_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def apply_setup_plan(draft: dict[str, Any]) -> dict[str, Any]:
    results = []
    errors = []
    for domain in draft.get("domains") or []:
        try:
            results.append(provision_domain(domain))
        except Exception as e:
            logger.exception("provision %s", domain.get("domain_key"))
            errors.append({"domain_key": domain.get("domain_key"), "error": str(e)[:300]})
    return {"provisioned": results, "errors": errors}
