"""
Central configuration for News Intelligence system.
Paths from config.paths; resource limits, model names, API settings here.
"""

import os
from pathlib import Path

from config.paths import (
    PROJECT_ROOT,
    DATA_DIR,
    REPORTS_DIR,
    LOG_DIR,
    CACHE_DB_PATH,
    CHROMA_DIR,
    REPORTS_OUTPUT_DIR,
    MANIFESTS_DIR,
    FINANCE_DATA_DIR,
    FINANCE_CACHE_DB,
    FINANCE_MARKET_DB,
    FINANCE_CHROMA_DIR,
    FINANCE_MANIFESTS_DIR,
    FINANCE_REPORTS_DIR,
)

# Archive storage — large files, raw downloads, model backups
ARCHIVE_DIR = Path(os.environ.get("NEWS_INTEL_ARCHIVE_DIR", "/media/pete/Fortress2/news-intelligence-archive"))

# Ensure directories exist
_ALL_DIRS = [
    DATA_DIR, REPORTS_OUTPUT_DIR, MANIFESTS_DIR, CHROMA_DIR, LOG_DIR,
    FINANCE_DATA_DIR, FINANCE_MANIFESTS_DIR, FINANCE_REPORTS_DIR, FINANCE_CHROMA_DIR,
]
for d in _ALL_DIRS:
    d.mkdir(parents=True, exist_ok=True)

# GPU and resource limits (RTX 5090 32GB, 62GB RAM)
GPU_DEVICE = 0
VRAM_TOTAL_GB = 32.0
VRAM_SAFETY_MARGIN_GB = 1.5
RAM_TOTAL_GB = 62.0
RAM_SAFETY_MARGIN_GB = 8.0

# Ollama model names — must match what's pulled via `ollama pull`
MODELS = {
    "embedding": "nomic-embed-text",
    "primary": "llama3.1:8b",
    "secondary": "mistral:7b",
    "summarization": "llama3.1:8b",
    "topic_extraction": "llama3.1:8b",
}

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT = 300

# --- Ollama invocation policy (see shared/services/ollama_model_caller.py) ---
# Background batches with prompts at least this many chars may use the secondary model (Mistral).
OLLAMA_BATCH_PROMPT_CHARS_FOR_SECONDARY = int(
    os.environ.get("OLLAMA_BATCH_PROMPT_CHARS_FOR_SECONDARY", "12000")
)
# If true, structured extraction paths that use the caller can use Mistral (faster/cheaper VRAM).
OLLAMA_USE_SECONDARY_FOR_EXTRACTION = os.environ.get(
    "OLLAMA_USE_SECONDARY_FOR_EXTRACTION", "false"
).lower() in ("1", "true", "yes")

# Extra tags for `refresh_ollama_models.py` only (optional large models, not in MODELS routing).
# Example: export OLLAMA_EXTRA_PULL_MODELS=llama3.1:70b
OLLAMA_EXTRA_PULL_MODELS: tuple[str, ...] = tuple(
    m.strip()
    for m in os.environ.get("OLLAMA_EXTRA_PULL_MODELS", "").split(",")
    if m.strip()
)

# Narrative finisher (~70B): final editorial pass on storylines (see docs/STORYLINE_70B_NARRATIVE_FINISHER.md).
NARRATIVE_FINISHER_MODEL = os.environ.get(
    "OLLAMA_NARRATIVE_FINISHER_MODEL",
    os.environ.get("OLLAMA_OPTIONAL_QUALITY_MODEL", "llama3.1:70b"),
)
# Backward compat for docs / env that used OLLAMA_OPTIONAL_QUALITY_MODEL only
OLLAMA_OPTIONAL_QUALITY_MODEL = NARRATIVE_FINISHER_MODEL

# Include NARRATIVE_FINISHER_MODEL in refresh_ollama_models.py (large download — default off).
OLLAMA_PULL_NARRATIVE_FINISHER = os.environ.get(
    "OLLAMA_PULL_NARRATIVE_FINISHER", "false"
).lower() in ("1", "true", "yes")


def ollama_pull_model_names() -> tuple[str, ...]:
    """Unique Ollama image tags to refresh with `ollama pull` (excludes non-Ollama embedders)."""
    tags: set[str] = set(MODELS.values())
    for v in FINANCE_MODELS.values():
        if not v or "/" in v:
            # HuggingFace ids (e.g. BAAI/bge-...) are not Ollama pulls
            continue
        tags.add(v)
    tags.update(OLLAMA_EXTRA_PULL_MODELS)
    if OLLAMA_PULL_NARRATIVE_FINISHER and NARRATIVE_FINISHER_MODEL:
        tags.add(NARRATIVE_FINISHER_MODEL)
    return tuple(sorted(tags))

# Database (Widow secondary; rollback: localhost:5433 + NAS tunnel)
DB_HOST = os.environ.get("DB_HOST", "192.168.93.101")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "news_intel")
DB_USER = os.environ.get("DB_USER", "newsapp")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

# In-app read-only SQL explorer (Monitor → SQL explorer). Off by default — anyone who can reach the API can read the DB when enabled.
SQL_EXPLORER_ENABLED = os.environ.get("NEWS_INTEL_SQL_EXPLORER", "").lower() in ("1", "true", "yes")

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = LOG_DIR / "pipeline.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
# LLM interaction ledger: log full prompt/response text (dev: true, prod: false)
LOG_LLM_FULL_TEXT = os.environ.get("LOG_LLM_FULL_TEXT", "false").lower() in ("1", "true", "yes")


def news_intel_is_production() -> bool:
    """True when API should use tightened CORS, hosts, OpenAPI, and error responses."""
    return os.environ.get("NEWS_INTEL_ENV", "development").strip().lower() == "production"


def news_intel_cors_allow_origins() -> list[str]:
    """
    CORS allow_origins for CORSMiddleware.
    Production: comma-separated NEWS_INTEL_CORS_ORIGINS required for browser access from those origins;
    empty means no browser origins allowed (API-only / server-to-server still works).
    Development: default ['*'] unless NEWS_INTEL_CORS_ORIGINS is set.
    """
    raw = os.environ.get("NEWS_INTEL_CORS_ORIGINS", "").strip()
    if news_intel_is_production():
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return ["*"]


def news_intel_trusted_hosts() -> list[str]:
    """
    TrustedHostMiddleware allowed_hosts.
    Production: set NEWS_INTEL_TRUSTED_HOSTS to hostnames/IPs clients use (comma-separated).
    If unset, defaults to localhost + 127.0.0.1 only.
    Development: default ['*'] unless overridden.
    """
    raw = os.environ.get("NEWS_INTEL_TRUSTED_HOSTS", "").strip()
    if news_intel_is_production():
        if not raw:
            return ["localhost", "127.0.0.1"]
        return [x.strip() for x in raw.split(",") if x.strip()]
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return ["*"]


def news_intel_api_docs_enabled() -> bool:
    """Swagger / ReDoc. Off in production unless NEWS_INTEL_ENABLE_API_DOCS=true."""
    if not news_intel_is_production():
        return True
    return os.environ.get("NEWS_INTEL_ENABLE_API_DOCS", "").lower() in ("1", "true", "yes")


def news_intel_expose_error_detail_to_client() -> bool:
    """When False, generic 500 body (detail still logged server-side)."""
    return not news_intel_is_production()


def news_intel_security_middleware_enabled() -> bool:
    """Rate limit + security headers. On in production; optional in dev via env."""
    if news_intel_is_production():
        return True
    return os.environ.get("NEWS_INTEL_SECURITY_MIDDLEWARE", "").lower() in ("1", "true", "yes")


def news_intel_rate_limit_per_minute() -> int:
    try:
        return max(1, int(os.environ.get("NEWS_INTEL_RATE_LIMIT_PER_MINUTE", "120")))
    except ValueError:
        return 120


# ============================================================
# Finance domain — external data sources
# ============================================================
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_RATE_LIMIT_PER_MINUTE = 120
# Optional FRED series IDs for commodities (registry + env; empty = skip FRED for that commodity)
# Gold default in registry; others override via FRED_{COMMODITY}_SERIES_ID (e.g. FRED_OIL_SERIES_ID, FRED_GAS_SERIES_ID)
FRED_GOLD_SERIES_ID = os.environ.get("FRED_GOLD_SERIES_ID", "IQ12260")
FRED_SILVER_SERIES_ID = os.environ.get("FRED_SILVER_SERIES_ID", "")
FRED_PLATINUM_SERIES_ID = os.environ.get("FRED_PLATINUM_SERIES_ID", "")
FRED_OIL_SERIES_ID = os.environ.get("FRED_OIL_SERIES_ID", "")
FRED_GAS_SERIES_ID = os.environ.get("FRED_GAS_SERIES_ID", "")
BIGQUERY_PROJECT_ID = os.environ.get("BIGQUERY_PROJECT_ID", "")
EDGAR_RATE_LIMIT_PER_SECOND = 10
EDGAR_USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "NewsIntelligence research@example.com")
METALS_DEV_API_KEY = os.environ.get("METALS_DEV_API_KEY", "")
# Historic context orchestrator — external APIs (optional)
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

# Finance vector store (collection name = finance_evidence_{model_suffix} — see vector_store.py)
EMBEDDING_DIMENSION = 1024  # bge-large-en-v1.5
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64

# Finance model names (Ollama)
FINANCE_MODELS = {
    "embedding": "BAAI/bge-large-en-v1.5",  # sentence-transformers
    "classification": "llama3.1:8b",
    "generation_fast": "llama3.1:8b",
    "generation_high": "mistral:7b",
}
