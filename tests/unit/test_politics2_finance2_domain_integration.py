"""Integration checks for politics / finance silos (schemas politics / finance, migration 219 + YAML)."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_db_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_REPO_ROOT / "api" / ".env", override=False)
        load_dotenv(_REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    pwf = _REPO_ROOT / ".db_password_widow"
    if not os.environ.get("DB_PASSWORD") and pwf.is_file():
        try:
            os.environ.setdefault("DB_PASSWORD", pwf.read_text().strip())
        except OSError:
            pass


def _db_conn_or_skip():
    import psycopg2

    _load_db_env()
    from shared.database.connection import get_db_connection

    try:
        conn = get_db_connection()
    except psycopg2.OperationalError as exc:
        pytest.skip(f"Database unavailable: {exc}")
    if not conn:
        pytest.skip("No database connection")
    return conn

from config import settings  # noqa: E402
from services.domain_synthesis_config import get_domain_synthesis_config, reload_config  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    RESERVED_SCHEMA_NAMES,
    get_active_domain_keys,
    is_valid_domain_key,
    pipeline_url_schema_pairs,
    resolve_domain_schema,
    url_schema_pairs,
)


def test_politics2_finance2_in_active_registry():
    keys = get_active_domain_keys()
    assert "politics" in keys, "api/config/domains/politics.yaml should be is_active"
    assert "finance" in keys, "api/config/domains/finance.yaml should be is_active"


def test_politics_finance_valid_and_schema_map():
    assert is_valid_domain_key("politics")
    assert is_valid_domain_key("finance")
    assert resolve_domain_schema("politics") == "politics"
    assert resolve_domain_schema("finance") == "finance"


def test_politics_finance_in_url_schema_pairs():
    pairs = dict(url_schema_pairs())
    assert pairs.get("politics") == "politics"
    assert pairs.get("finance") == "finance"


def test_pipeline_url_schema_pairs_matches_full_when_exclude_empty(monkeypatch):
    monkeypatch.delenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", raising=False)
    assert dict(pipeline_url_schema_pairs()) == dict(url_schema_pairs())


def test_pipeline_excludes_legacy_domain_keys(monkeypatch):
    monkeypatch.delenv("PIPELINE_INCLUDE_DOMAIN_KEYS", raising=False)
    monkeypatch.setenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", "politics,finance")
    pipe = dict(pipeline_url_schema_pairs())
    assert "politics" not in pipe
    assert "finance" not in pipe
    if "politics" in dict(url_schema_pairs()):
        assert pipe.get("politics") == "politics"
    if "finance" in dict(url_schema_pairs()):
        assert pipe.get("finance") == "finance"


def test_pipeline_include_allowlist(monkeypatch):
    monkeypatch.delenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", raising=False)
    monkeypatch.setenv("PIPELINE_INCLUDE_DOMAIN_KEYS", "legal,medicine")
    pipe = dict(pipeline_url_schema_pairs())
    for dk in pipe:
        assert dk in ("legal", "medicine")


def test_pipeline_excludes_domain_via_env(monkeypatch):
    monkeypatch.delenv("PIPELINE_INCLUDE_DOMAIN_KEYS", raising=False)
    monkeypatch.setenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", "artificial-intelligence")
    pipe = dict(pipeline_url_schema_pairs())
    if "artificial-intelligence" in dict(url_schema_pairs()):
        assert "artificial-intelligence" not in pipe


def test_nightly_unified_pipeline_disabled(monkeypatch):
    monkeypatch.setenv("NIGHTLY_UNIFIED_PIPELINE_ENABLED", "false")
    monkeypatch.delenv("NIGHTLY_PIPELINE_ALL_DAY", raising=False)
    from services.nightly_ingest_window_service import (
        in_nightly_enrichment_context_window_est,
        in_nightly_pipeline_window_est,
    )

    assert in_nightly_pipeline_window_est() is False
    assert in_nightly_enrichment_context_window_est() is False


def test_legislative_scan_domain_keys_env(monkeypatch):
    from services.legislative_reference_service import legislative_scan_domain_keys

    monkeypatch.delenv("LEGISLATIVE_SCAN_DOMAIN_KEYS", raising=False)
    assert legislative_scan_domain_keys() == ("politics", "legal")

    monkeypatch.setenv("LEGISLATIVE_SCAN_DOMAIN_KEYS", "politics, legal")
    assert legislative_scan_domain_keys() == ("politics", "legal")


def test_reserved_schema_names_include_core_builtins():
    assert "politics" in RESERVED_SCHEMA_NAMES
    assert "finance" in RESERVED_SCHEMA_NAMES
    assert "politics_2" not in RESERVED_SCHEMA_NAMES
    assert "finance_2" not in RESERVED_SCHEMA_NAMES


def test_rss_ingest_exclude_env_parsing(monkeypatch):
    monkeypatch.delenv("RSS_INGEST_EXCLUDE_DOMAIN_KEYS", raising=False)
    assert settings.get_rss_ingest_excluded_domain_keys() == frozenset()

    monkeypatch.setenv("RSS_INGEST_EXCLUDE_DOMAIN_KEYS", "politics, finance ")
    assert settings.get_rss_ingest_excluded_domain_keys() == frozenset({"politics", "finance"})


def test_finance_content_domain_key_defaults(monkeypatch):
    monkeypatch.delenv("FINANCE_PG_CONTENT_DOMAIN_KEY", raising=False)
    monkeypatch.delenv("FINANCE_CONTEXT_DOMAIN_KEY", raising=False)
    assert settings.finance_postgres_content_domain_key() == "finance"
    assert settings.finance_intelligence_context_domain_key() == "finance"

    monkeypatch.setenv("FINANCE_PG_CONTENT_DOMAIN_KEY", "finance-2")
    monkeypatch.delenv("FINANCE_CONTEXT_DOMAIN_KEY", raising=False)
    assert settings.finance_postgres_content_domain_key() == "finance-2"
    assert settings.finance_intelligence_context_domain_key() == "finance-2"

    monkeypatch.setenv("FINANCE_CONTEXT_DOMAIN_KEY", "finance")
    assert settings.finance_intelligence_context_domain_key() == "finance"


def test_politics_content_domain_key_default(monkeypatch):
    monkeypatch.delenv("POLITICS_PG_CONTENT_DOMAIN_KEY", raising=False)
    assert settings.politics_postgres_content_domain_key() == "politics"
    monkeypatch.setenv("POLITICS_PG_CONTENT_DOMAIN_KEY", "politics-2")
    assert settings.politics_postgres_content_domain_key() == "politics-2"


def test_synthesis_config_politics_finance_anchors():
    reload_config()
    p = get_domain_synthesis_config("politics")
    assert p.focus_areas
    f = get_domain_synthesis_config("finance")
    assert "commodities" in " ".join(f.focus_areas).lower()


@pytest.mark.requires_db
def test_db_schemas_politics_finance_exist():
    """Requires DB + migrations 201+ (219 unifies schema names to politics/finance)."""
    conn = _db_conn_or_skip()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema FROM information_schema.tables
                WHERE table_name = 'articles'
                  AND table_schema IN ('politics', 'finance', 'politics_2', 'finance_2')
                ORDER BY 1
                """
            )
            rows = {r[0] for r in cur.fetchall()}
        if rows == {"politics", "finance"}:
            return
        if rows == {"politics_2", "finance_2"}:
            pytest.skip("Apply migration 219 (run_migration_219.py) to unify schema names")
        pytest.fail(
            f"Expected politics+finance or politics_2+finance_2 articles tables; got {rows!r}"
        )
    finally:
        conn.close()


@pytest.mark.requires_db
def test_finance_extension_tables_after_migration_206():
    """Requires DB + migrations 201/206/219 (finance extension tables)."""
    conn = _db_conn_or_skip()
    expected = frozenset(
        {
            "research_topics",
            "topic_extraction_queue",
            "market_patterns",
            "corporate_announcements",
            "financial_indicators",
        }
    )
    try:
        names = sorted(expected)
        placeholders = ",".join(["%s"] * len(names))
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema IN ('finance', 'finance_2') AND table_name IN ({placeholders})
                """,
                names,
            )
            found = {r[0] for r in cur.fetchall()}
        if not found:
            pytest.skip(
                "finance silo has no extension tables yet; apply migration 206 "
                "(PYTHONPATH=api uv run python api/scripts/run_migration_206.py)"
            )
        missing = expected - found
        if missing:
            pytest.fail(
                "finance extension incomplete (partial 206?): missing "
                f"{sorted(missing)} (found {sorted(found)})"
            )
    finally:
        conn.close()


@pytest.mark.requires_db
def test_public_domains_rows_politics_finance_schemas():
    conn = _db_conn_or_skip()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, schema_name FROM public.domains
                WHERE schema_name IN ('politics', 'finance', 'politics_2', 'finance_2')
                ORDER BY schema_name
                """
            )
            rows = cur.fetchall()
        by_schema = {r[1]: r[0] for r in rows}
        pol_schema = by_schema.get("politics") or by_schema.get("politics_2")
        fin_schema = by_schema.get("finance") or by_schema.get("finance_2")
        assert pol_schema == "politics", f"politics catalog mismatch: {by_schema!r}"
        assert fin_schema == "finance", f"finance catalog mismatch: {by_schema!r}"
    finally:
        conn.close()
