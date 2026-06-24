"""
NRI-compatible config shim — delegates to api.config kernel.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.database_targets import news_intel_dsn, spine_dsn
from config.runtime import get_runtime_config, investigation_schema


@dataclass(frozen=True)
class NriCoreConfig:
    news_intel_dsn: str
    identity_spine_dsn: str
    nri_schema: str
    skip_subject_mentions: bool
    write_resolved_mentions: bool
    lazy_mint_enabled: bool
    opensanctions_lazy_enabled: bool
    allow_prod_news_intel: bool
    vault_path: str
    vault_write: bool
    loop_enabled: bool
    ftm_auto_link_threshold: float
    ftm_park_threshold: float
    nas_datasets_root: str
    ollama_url: str


def get_config() -> NriCoreConfig:
    rt = get_runtime_config()
    return NriCoreConfig(
        news_intel_dsn=news_intel_dsn(),
        identity_spine_dsn=spine_dsn(),
        nri_schema=investigation_schema(),
        skip_subject_mentions=bool(rt["nri_skip_subject_mentions"]),
        write_resolved_mentions=bool(rt["nri_write_resolved_mentions"]),
        lazy_mint_enabled=bool(rt["nri_lazy_mint_enabled"]),
        opensanctions_lazy_enabled=bool(rt["nri_opensanctions_lazy_enabled"]),
        allow_prod_news_intel=bool(rt["nri_allow_prod_news_intel"]),
        vault_path=str(rt["nri_vault_path"] or ""),
        vault_write=bool(rt["nri_vault_write"]),
        loop_enabled=bool(rt["nri_loop_enabled"]),
        ftm_auto_link_threshold=float(rt["ftm_auto_link_threshold"]),
        ftm_park_threshold=float(rt["ftm_park_threshold"]),
        nas_datasets_root=str(rt["nas_datasets_root"]),
        ollama_url=str(rt["ollama_url"]),
    )


def require_prod_safety() -> None:
    cfg = get_config()
    if not cfg.allow_prod_news_intel:
        raise RuntimeError("NRI_ALLOW_PROD_NEWS_INTEL=false — writes blocked")
