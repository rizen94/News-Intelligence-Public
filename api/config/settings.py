"""
Central configuration for News Intelligence system.
Paths from config.paths; resource limits, model names, API settings here.
"""

import os
from pathlib import Path

from config.paths import (
    CHROMA_DIR,
    DATA_DIR,
    FINANCE_CACHE_DB,
    FINANCE_CHROMA_DIR,
    FINANCE_DATA_DIR,
    FINANCE_MANIFESTS_DIR,
    FINANCE_MARKET_DB,
    FINANCE_REPORTS_DIR,
    LOG_DIR,
    MANIFESTS_DIR,
    REPORTS_OUTPUT_DIR,
)

# Archive storage — large files, raw downloads, model backups
ARCHIVE_DIR = Path(
    os.environ.get("NEWS_INTEL_ARCHIVE_DIR", "")
)

# Ensure directories exist
_ALL_DIRS = [
    DATA_DIR,
    REPORTS_OUTPUT_DIR,
    MANIFESTS_DIR,
    CHROMA_DIR,
    LOG_DIR,
    FINANCE_DATA_DIR,
    FINANCE_MANIFESTS_DIR,
    FINANCE_REPORTS_DIR,
    FINANCE_CHROMA_DIR,
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
OLLAMA_MODEL_PRIMARY = os.environ.get("OLLAMA_MODEL_PRIMARY", "llama3.1:8b")
OLLAMA_MODEL_SECONDARY = os.environ.get("OLLAMA_MODEL_SECONDARY", "mistral-nemo:12b")
OLLAMA_MODEL_PHI = os.environ.get("OLLAMA_MODEL_PHI", "phi3.5:latest")
OLLAMA_MODEL_EXTRACTION = os.environ.get("OLLAMA_MODEL_EXTRACTION", "qwen3.6:latest")

MODELS = {
    "embedding": os.environ.get("OLLAMA_MODEL_EMBEDDING", "nomic-embed-text"),
    "primary": OLLAMA_MODEL_PRIMARY,
    "secondary": OLLAMA_MODEL_SECONDARY,
    "summarization": OLLAMA_MODEL_PRIMARY,
    "topic_extraction": OLLAMA_MODEL_PRIMARY,
}

# Ollama hosts — canonical values from config.runtime (SSOT for host URLs)
from config.runtime import (
    ollama_dual_host_routing_enabled as OLLAMA_DUAL_HOST_ROUTING_ENABLED,
    ollama_host as _runtime_ollama_host,
    ollama_pop_os_host as _runtime_ollama_pop_os_host,
    ollama_timeout_seconds as _runtime_ollama_timeout,
)

OLLAMA_HOST = _runtime_ollama_host()
OLLAMA_POP_OS_HOST = _runtime_ollama_pop_os_host()
OLLAMA_TIMEOUT = _runtime_ollama_timeout()

# --- Ollama invocation policy (see shared/services/ollama_model_caller.py) ---
# Background batches with prompts at least this many chars may use the secondary model (e.g. Mistral-Nemo 12B).
OLLAMA_BATCH_PROMPT_CHARS_FOR_SECONDARY = int(
    os.environ.get("OLLAMA_BATCH_PROMPT_CHARS_FOR_SECONDARY", "12000")
)
# If true, structured extraction paths that use the caller can use the secondary slot (not primary 8B).
OLLAMA_USE_SECONDARY_FOR_EXTRACTION = os.environ.get(
    "OLLAMA_USE_SECONDARY_FOR_EXTRACTION", "false"
).lower() in ("1", "true", "yes")
# If true, STRUCTURED_EXTRACTION uses Qwen (OLLAMA_MODEL_EXTRACTION) instead of primary/secondary.
OLLAMA_USE_QWEN_FOR_EXTRACTION = os.environ.get(
    "OLLAMA_USE_QWEN_FOR_EXTRACTION", "false"
).lower() in ("1", "true", "yes")
# If true, fast simple local passes (e.g. readability quality LLM) use Phi (OLLAMA_MODEL_PHI).
OLLAMA_USE_PHI_FOR_FAST_SIMPLE = os.environ.get(
    "OLLAMA_USE_PHI_FOR_FAST_SIMPLE", "false"
).lower() in ("1", "true", "yes")

# Extra tags for `refresh_ollama_models.py` only (optional large models, not in MODELS routing).
# Example: export OLLAMA_EXTRA_PULL_MODELS=llama3.1:70b
OLLAMA_EXTRA_PULL_MODELS: tuple[str, ...] = tuple(
    m.strip() for m in os.environ.get("OLLAMA_EXTRA_PULL_MODELS", "").split(",") if m.strip()
)

# Narrative finisher (32B on popOS RTX5090): final editorial pass on storylines
# qwen2.5:32b-instruct is the heavy model available on popOS (192.168.93.99)
NARRATIVE_FINISHER_MODEL = os.environ.get(
    "OLLAMA_NARRATIVE_FINISHER_MODEL",
    os.environ.get("OLLAMA_OPTIONAL_QUALITY_MODEL", "qwen2.5:32b-instruct"),
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
    if OLLAMA_MODEL_PHI:
        tags.add(OLLAMA_MODEL_PHI)
    if OLLAMA_MODEL_EXTRACTION:
        tags.add(OLLAMA_MODEL_EXTRACTION)
    if OLLAMA_PULL_NARRATIVE_FINISHER and NARRATIVE_FINISHER_MODEL:
        tags.add(NARRATIVE_FINISHER_MODEL)
    return tuple(sorted(tags))


# Database (post-migration: local on Widow server)
DB_HOST = os.environ.get("DB_HOST", "localhost")
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
        return max(1, int(os.environ.get("NEWS_INTEL_RATE_LIMIT_PER_MINUTE", "300")))
    except ValueError:
        return 300


def news_intel_rate_limit_exempt_private_lan() -> bool:
    """Homelab: PopOS Caddy → Widow shares one proxy IP; exempt RFC1918/loopback from per-IP cap."""
    return os.environ.get("NEWS_INTEL_RATE_LIMIT_EXEMPT_PRIVATE_LAN", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def get_rss_ingest_excluded_domain_keys() -> frozenset[str]:
    """Domain keys skipped by ``collect_rss_feeds`` (comma-separated env). Use to exclude legacy schemas during cutover."""
    raw = os.environ.get("RSS_INGEST_EXCLUDE_DOMAIN_KEYS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())


def rss_ingest_mirror_pipeline_enabled() -> bool:
    """
    When true, RSS collection iterates ``pipeline_url_schema_pairs()`` (same silos as automation backlog),
    then still subtracts ``RSS_INGEST_EXCLUDE_DOMAIN_KEYS``. Avoids ingesting into legacy silos you excluded
    from processing without duplicating allowlists.
    """
    return os.environ.get("RSS_INGEST_MIRROR_PIPELINE", "").lower() in (
        "1",
        "true",
        "yes",
    )


def finance_postgres_content_domain_key() -> str:
    """ArticleService / finance helpers: which ``domain_key`` owns finance RSS articles (default ``finance``)."""
    return (os.environ.get("FINANCE_PG_CONTENT_DOMAIN_KEY") or "finance").strip()


def finance_intelligence_context_domain_key() -> str:
    """``intelligence.contexts.domain_key`` filter for finance-side orchestration (defaults to finance_postgres_content_domain_key)."""
    raw = os.environ.get("FINANCE_CONTEXT_DOMAIN_KEY", "").strip()
    return raw if raw else finance_postgres_content_domain_key()


def politics_postgres_content_domain_key() -> str:
    """Background jobs that read politics articles by silo (default ``politics``)."""
    return (os.environ.get("POLITICS_PG_CONTENT_DOMAIN_KEY") or "politics").strip()


def event_tracking_max_age_days() -> int:
    """
    Context age window for event discovery candidates.
    Older contexts are skipped to keep event_tracking focused on current developments.
    """
    try:
        n = int(os.environ.get("EVENT_TRACKING_MAX_AGE_DAYS", "14"))
    except ValueError:
        n = 14
    return max(1, min(180, n))


def event_tracking_min_content_len() -> int:
    """
    Minimum context content length for event discovery candidates.
    Very short contexts are typically too low-signal for reliable event grouping.
    """
    try:
        n = int(os.environ.get("EVENT_TRACKING_MIN_CONTENT_LEN", "180"))
    except ValueError:
        n = 180
    return max(0, min(5000, n))


def event_tracking_min_articles_per_event() -> int:
    """
    Minimum distinct contexts required to create a tracked event.
    Raised default (4) reduces phantom one-off / weakly related groupings.
    """
    try:
        n = int(os.environ.get("EVENT_TRACKING_MIN_ARTICLES_PER_EVENT", "4"))
    except ValueError:
        n = 4
    return max(2, min(50, n))


def event_tracking_storyline_min_entity_overlap() -> int:
    """
    Minimum distinct canonical entities shared with a storyline before linking.
    Overlap of 1 previously attached Fed/Treasury noise to unrelated mega-storylines.
    """
    try:
        n = int(os.environ.get("EVENT_TRACKING_STORYLINE_MIN_ENTITY_OVERLAP", "3"))
    except ValueError:
        n = 3
    return max(1, min(50, n))


def topic_clustering_graduation_confidence() -> float:
    """
    Average article-topic confidence at/above which an article is considered clustered.
    Lowering this can reduce topic_clustering churn and backlog.
    """
    try:
        n = float(os.environ.get("TOPIC_CLUSTERING_GRADUATION_CONFIDENCE", "0.88"))
    except ValueError:
        n = 0.88
    return min(0.99, max(0.50, n))


def topic_clustering_backlog_uses_pass_marker() -> bool:
    """
    When true (default), Monitor/automation ``queue_depth`` for topic_clustering counts only
    articles that have never completed a clustering pass (``last_pass_at`` empty) — same
    first-pass-only predicate as ``TopicClusteringService.select_pending_article_ids`` /
    PopOS idle gate. Retry/failed rows appear in ``retry_depth`` via phase_work_queue_metrics,
    not in ``queue_depth``.
    Legacy low-confidence re-refinement backlog when false (and iterative refinement on).
    """
    return os.environ.get("TOPIC_CLUSTERING_BACKLOG_USE_PASS_MARKER", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def topic_clustering_iterative_refinement_enabled() -> bool:
    """
    When true, topic_clustering selects articles below graduation confidence for repeat passes
    (legacy churn). When false (default), each article is only queued until the first successful pass
    records ``last_pass_at`` — aligned with ``topic_clustering_backlog_uses_pass_marker``.
    """
    return os.environ.get("TOPIC_CLUSTERING_ITERATIVE_REFINEMENT", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def topic_clustering_batch_size() -> int:
    try:
        n = int(os.environ.get("TOPIC_CLUSTERING_BATCH_SIZE", "20"))
    except ValueError:
        n = 20
    # No artificial ceiling — adaptive bounds + host headroom own the limit.
    default = max(5, n)
    try:
        from shared.adaptive_batch_policy import get_persisted_adaptive_batch, resolve_adaptive_batch

        # Prefer live tune when adaptive is on; otherwise last persisted value for Monitor/ETA callers.
        from shared.adaptive_batch_policy import adaptive_batch_enabled

        if adaptive_batch_enabled():
            tuned, _meta = resolve_adaptive_batch("topic_clustering", default)
            return max(5, int(tuned))
        adaptive = get_persisted_adaptive_batch("topic_clustering")
        if adaptive is not None:
            return max(5, int(adaptive))
    except Exception:
        pass
    return default


def topic_clustering_concurrency() -> int:
    try:
        n = int(os.environ.get("TOPIC_CLUSTERING_CONCURRENCY", "5"))
    except ValueError:
        n = 5
    return max(1, min(20, n))


def topic_fast_match_min_score() -> float:
    try:
        n = float(os.environ.get("TOPIC_FAST_MATCH_MIN_SCORE", "0.62"))
    except ValueError:
        n = 0.62
    return min(0.99, max(0.35, n))


def unified_intake_extraction_enabled() -> bool:
    """When true, unified intake is the only scheduled intake extract path."""
    raw = os.environ.get("UNIFIED_INTAKE_EXTRACTION_ENABLED", "true").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    return True


def legacy_intake_extraction_enabled() -> bool:
    """Explicit rollback: run legacy per-phase intake instead of unified."""
    return os.environ.get("LEGACY_INTAKE_EXTRACTION_ENABLED", "").lower() in ("1", "true", "yes")


def unified_intake_legacy_aware_backlog_enabled() -> bool:
    """Skip LLM for articles already satisfied by legacy intake; backfill pass marker only."""
    raw = os.environ.get("UNIFIED_INTAKE_LEGACY_AWARE_BACKLOG", "true").strip().lower()
    return raw not in ("0", "false", "no")


def fast_ner_enabled() -> bool:
    return os.environ.get("FAST_NER_ENABLED", "true").lower() in ("1", "true", "yes")


def fast_ner_backend() -> str:
    """spacy | gliner | both | auto (spacy then gliner if available)."""
    raw = (os.environ.get("FAST_NER_BACKEND", "spacy") or "spacy").strip().lower()
    if raw in ("spacy", "gliner", "both", "auto"):
        return raw
    return "spacy"


def fast_ner_max_chars() -> int:
    try:
        return max(2000, min(100_000, int(os.environ.get("FAST_NER_MAX_CHARS", "24000"))))
    except ValueError:
        return 24000


def unified_intake_max_article_chars() -> int:
    """
    Per-article body budget in the unified intake LLM prompt.

    Default matches FAST_NER_MAX_CHARS (24000) so entity/event extraction sees
    the same long-form body as the NER pre-pass. Override:
    UNIFIED_INTAKE_MAX_ARTICLE_CHARS.
    """
    raw = os.environ.get("UNIFIED_INTAKE_MAX_ARTICLE_CHARS", "").strip()
    if raw:
        try:
            return max(4000, min(100_000, int(raw)))
        except ValueError:
            pass
    return fast_ner_max_chars()


def fast_ner_gliner_labels() -> list[str]:
    raw = os.environ.get(
        "FAST_NER_GLINER_LABELS",
        "person,organization,company,location,country,event,law,product",
    )
    return [x.strip() for x in raw.split(",") if x.strip()]


def context_chunking_enabled() -> bool:
    # Off by default: one context per article with full body (articles/contexts
    # already use unbounded text). Opt in with CONTEXT_CHUNKING_ENABLED=true.
    return os.environ.get("CONTEXT_CHUNKING_ENABLED", "false").lower() in ("1", "true", "yes")


def context_chunk_min_chars() -> int:
    try:
        return max(4000, int(os.environ.get("CONTEXT_CHUNK_MIN_CHARS", "12000")))
    except ValueError:
        return 12000


def context_chunk_size_tokens() -> int:
    try:
        return max(256, min(4096, int(os.environ.get("CONTEXT_CHUNK_SIZE_TOKENS", "1024"))))
    except ValueError:
        return 1024


def context_chunk_overlap_tokens() -> int:
    try:
        return max(0, min(512, int(os.environ.get("CONTEXT_CHUNK_OVERLAP_TOKENS", "128"))))
    except ValueError:
        return 128


def context_chunk_max_chunks() -> int:
    try:
        return max(1, min(12, int(os.environ.get("CONTEXT_CHUNK_MAX_CHUNKS", "4"))))
    except ValueError:
        return 4


def news_intel_public_web_auth_enabled() -> bool:
    """When true, enforce guest vs admin for browser-facing API traffic (see docs/PUBLIC_DEPLOYMENT.md)."""
    return os.environ.get("NEWS_INTEL_PUBLIC_WEB_AUTH", "").lower() in ("1", "true", "yes")


def news_intel_allow_anonymous_guest() -> bool:
    """
    When public web auth is on, unauthenticated requests default to guest role if true (public demo).
    If false, callers must log in (guest or admin account).
    """
    return os.environ.get("NEWS_INTEL_ALLOW_ANONYMOUS_GUEST", "true").lower() in ("1", "true", "yes")


def news_intel_auth_jwt_secret() -> str:
    """HS256 secret for HTTP-only session cookie. Prefer NEWS_INTEL_JWT_SECRET; falls back to JWT_SECRET."""
    return (
        os.environ.get("NEWS_INTEL_JWT_SECRET", "").strip()
        or os.environ.get("JWT_SECRET", "").strip()
    )


def news_intel_auth_cookie_name() -> str:
    return os.environ.get("NEWS_INTEL_AUTH_COOKIE_NAME", "ni_session").strip() or "ni_session"


def news_intel_auth_cookie_max_age_seconds() -> int:
    try:
        return max(60, int(os.environ.get("NEWS_INTEL_AUTH_COOKIE_MAX_AGE_SECONDS", str(7 * 24 * 3600))))
    except ValueError:
        return 7 * 24 * 3600


def news_intel_auth_cookie_secure() -> bool:
    """Default Secure cookies in production (HTTPS)."""
    if news_intel_is_production():
        return os.environ.get("NEWS_INTEL_AUTH_COOKIE_SECURE", "true").lower() in ("1", "true", "yes")
    return os.environ.get("NEWS_INTEL_AUTH_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")


def news_intel_auth_cookie_samesite() -> str:
    raw = os.environ.get("NEWS_INTEL_AUTH_COOKIE_SAMESITE", "lax").strip().lower()
    return raw if raw in ("lax", "strict", "none") else "lax"


# ============================================================
# Finance domain — external data sources
# ============================================================
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_RATE_LIMIT_PER_MINUTE = 120
# Optional FRED series ID overrides for commodities (registry holds defaults; env wins when set)
# Gold default in registry; oil/gas defaults: DCOILWTICO, DHHNGSP in commodity_registry.yaml
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
# Politics — Congress.gov API v3 (bill metadata, summaries, text versions; see api/config/government_sources.yaml)
CONGRESS_GOV_API_KEY = os.environ.get("CONGRESS_GOV_API_KEY", "")

# Finance vector store (collection name = finance_evidence_{model_suffix} — see vector_store.py)
EMBEDDING_DIMENSION = 1024  # bge-large-en-v1.5
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64

# Finance model names (Ollama)
FINANCE_MODELS = {
    "embedding": "BAAI/bge-large-en-v1.5",  # sentence-transformers
    "classification": OLLAMA_MODEL_PRIMARY,
    "generation_fast": OLLAMA_MODEL_PRIMARY,
    "generation_high": os.environ.get("FINANCE_OLLAMA_GENERATION_HIGH", OLLAMA_MODEL_SECONDARY),
}
