"""Integration checks for template silos politics-2 / finance-2 (migration 201 + YAML)."""

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
    assert "politics-2" in keys, "api/config/domains/politics-2.yaml should be is_active"
    assert "finance-2" in keys, "api/config/domains/finance-2.yaml should be is_active"


def test_politics2_finance2_valid_and_schema_map():
    assert is_valid_domain_key("politics-2")
    assert is_valid_domain_key("finance-2")
    assert resolve_domain_schema("politics-2") == "politics_2"
    assert resolve_domain_schema("finance-2") == "finance_2"


def test_politics2_finance2_in_url_schema_pairs():
    pairs = dict(url_schema_pairs())
    assert pairs.get("politics-2") == "politics_2"
    assert pairs.get("finance-2") == "finance_2"


def test_pipeline_url_schema_pairs_matches_full_when_exclude_empty(monkeypatch):
    monkeypatch.delenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", raising=False)
    assert dict(pipeline_url_schema_pairs()) == dict(url_schema_pairs())


def test_pipeline_excludes_legacy_domain_keys(monkeypatch):
    monkeypatch.delenv("PIPELINE_INCLUDE_DOMAIN_KEYS", raising=False)
    monkeypatch.setenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", "politics,finance")
    pipe = dict(pipeline_url_schema_pairs())
    assert "politics" not in pipe
    assert "finance" not in pipe
    if "politics-2" in dict(url_schema_pairs()):
        assert pipe.get("politics-2") == "politics_2"
    if "finance-2" in dict(url_schema_pairs()):
        assert pipe.get("finance-2") == "finance_2"


def test_pipeline_include_allowlist(monkeypatch):
    monkeypatch.delenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", raising=False)
    monkeypatch.setenv("PIPELINE_INCLUDE_DOMAIN_KEYS", "legal,medicine")
    pipe = dict(pipeline_url_schema_pairs())
    for dk in pipe:
        assert dk in ("legal", "medicine")


def test_pipeline_excludes_science_tech(monkeypatch):
    monkeypatch.delenv("PIPELINE_INCLUDE_DOMAIN_KEYS", raising=False)
    monkeypatch.setenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", "science-tech")
    pipe = dict(pipeline_url_schema_pairs())
    assert "science-tech" not in pipe


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

    monkeypatch.setenv("LEGISLATIVE_SCAN_DOMAIN_KEYS", "politics-2, legal")
    assert legislative_scan_domain_keys() == ("politics-2", "legal")


def test_reserved_schema_names_include_template_schemas():
    assert "politics_2" in RESERVED_SCHEMA_NAMES
    assert "finance_2" in RESERVED_SCHEMA_NAMES


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


def test_synthesis_config_merge_for_minus_two_silos():
    reload_config()
    p1 = get_domain_synthesis_config("politics")
    p2 = get_domain_synthesis_config("politics-2")
    assert p2.focus_areas == p1.focus_areas
    assert p2.event_type_priorities == p1.event_type_priorities

    f1 = get_domain_synthesis_config("finance")
    f2 = get_domain_synthesis_config("finance-2")
    assert f2.focus_areas == f1.focus_areas
    assert "commodities" in " ".join(f2.focus_areas).lower()


@pytest.mark.requires_db
def test_db_schemas_politics2_finance2_exist():
    """Requires DB + migration 201 applied."""
    conn = _db_conn_or_skip()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema FROM information_schema.tables
                WHERE table_name = 'articles'
                  AND table_schema IN ('politics_2', 'finance_2')
                ORDER BY 1
                """
            )
            rows = {r[0] for r in cur.fetchall()}
        assert rows == {"politics_2", "finance_2"}, (
            f"Expected politics_2 and finance_2 articles tables; got {rows!r}. "
            "Run: PYTHONPATH=api uv run python api/scripts/run_migration_201.py"
        )
    finally:
        conn.close()


@pytest.mark.requires_db
def test_public_domains_rows_for_minus_two():
    conn = _db_conn_or_skip()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, schema_name FROM public.domains
                WHERE domain_key IN ('politics-2', 'finance-2')
                ORDER BY domain_key
                """
            )
            rows = cur.fetchall()
        got = {r[0]: r[1] for r in rows}
        assert got.get("finance-2") == "finance_2"
        assert got.get("politics-2") == "politics_2"
    finally:
        conn.close()
