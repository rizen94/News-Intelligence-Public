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

# Database (Widow secondary; rollback: localhost:5433 + NAS tunnel)
DB_HOST = os.environ.get("DB_HOST", "192.168.93.101")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
DB_NAME = os.environ.get("DB_NAME", "news_intel")
DB_USER = os.environ.get("DB_USER", "newsapp")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = LOG_DIR / "pipeline.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
# LLM interaction ledger: log full prompt/response text (dev: true, prod: false)
LOG_LLM_FULL_TEXT = os.environ.get("LOG_LLM_FULL_TEXT", "false").lower() in ("1", "true", "yes")

# ============================================================
# Finance domain — external data sources
# ============================================================
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_RATE_LIMIT_PER_MINUTE = 120
BIGQUERY_PROJECT_ID = os.environ.get("BIGQUERY_PROJECT_ID", "")
EDGAR_RATE_LIMIT_PER_SECOND = 10
EDGAR_USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "NewsIntelligence research@example.com")
METALS_DEV_API_KEY = os.environ.get("METALS_DEV_API_KEY", "")

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
