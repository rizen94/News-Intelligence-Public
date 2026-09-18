"""Unit tests: CourtListener + Federal Register collectors (mocked HTTP)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))


@pytest.fixture(autouse=True)
def _enable_collectors(monkeypatch):
    monkeypatch.setenv("COURTLISTENER_COLLECTOR_ENABLED", "true")
    monkeypatch.setenv("FEDERAL_REGISTER_COLLECTOR_ENABLED", "true")
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "test-token")
    monkeypatch.setenv("PUBLIC_DATA_SENTINEL_ARTICLE_ID", "0")
    # Bypass feature registry YAML default false
    monkeypatch.setattr(
        "collectors.public_event_upsert.is_feature_enabled",
        lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "collectors.courtlistener_collector.collector_enabled",
        lambda *a, **k: True,
    )
    monkeypatch.setattr(
        "collectors.federal_register_collector.collector_enabled",
        lambda *a, **k: True,
    )


def test_courtlistener_maps_and_upserts(monkeypatch):
    from collectors import courtlistener_collector as cl

    sample = {
        "results": [
            {
                "cluster_id": 12345,
                "caseName": "Example v. United States",
                "dateFiled": "2026-07-01",
                "court": "scotus",
                "snippet": "Held that…",
                "absolute_url": "/opinion/12345/example/",
            }
        ],
        "next": None,
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = sample

    upserts: list[dict] = []

    def _capture(**kwargs):
        upserts.append(kwargs)
        return True

    monkeypatch.setattr(cl.requests, "get", lambda *a, **k: mock_resp)
    monkeypatch.setattr(cl, "upsert_chronological_event", _capture)
    monkeypatch.setattr(cl, "rate_limit_sleep", lambda *a, **k: None)

    out = cl.collect_courtlistener(page_size=5, pages=1)
    assert out["skipped"] is False
    assert out["fetched"] == 1
    assert out["inserted"] == 1
    assert upserts[0]["extraction_method"] == "courtlistener"
    assert upserts[0]["domain_key"] == "legal"
    assert upserts[0]["event_type"] == "court_ruling"
    assert "courtlistener:12345" in upserts[0]["event_id"]


def test_courtlistener_skips_without_token(monkeypatch):
    from collectors import courtlistener_collector as cl

    monkeypatch.setattr(cl, "_token", lambda: "")
    out = cl.collect_courtlistener()
    assert out["skipped"] is True
    assert out["inserted"] == 0


def test_federal_register_maps_and_upserts(monkeypatch):
    from collectors import federal_register_collector as fr

    sample = {
        "results": [
            {
                "document_number": "2026-12345",
                "title": "Energy Conservation Standards",
                "type": "Rule",
                "publication_date": "2026-07-15",
                "abstract": "DOE amends…",
                "html_url": "https://www.federalregister.gov/documents/2026/07/15/2026-12345",
                "agencies": [{"name": "Energy Department"}],
                "significant": True,
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = sample

    upserts: list[dict] = []

    def _capture(**kwargs):
        upserts.append(kwargs)
        return True

    monkeypatch.setattr(fr.requests, "get", lambda *a, **k: mock_resp)
    monkeypatch.setattr(fr, "upsert_chronological_event", _capture)
    monkeypatch.setattr(fr, "rate_limit_sleep", lambda *a, **k: None)

    out = fr.collect_federal_register(per_page=10)
    assert out["skipped"] is False
    assert out["fetched"] == 1
    assert out["inserted"] == 1
    assert upserts[0]["extraction_method"] == "federal_register"
    assert upserts[0]["domain_key"] == "legal"
    assert "federal_register:2026-12345" in upserts[0]["event_id"]
    assert upserts[0]["importance_score"] == 0.65


def test_federal_register_handles_http_error(monkeypatch):
    from collectors import federal_register_collector as fr

    def _boom(*a, **k):
        raise fr.requests.RequestException("down")

    monkeypatch.setattr(fr.requests, "get", _boom)
    monkeypatch.setattr(fr, "rate_limit_sleep", lambda *a, **k: None)
    docs = fr.fetch_documents(per_page=5)
    assert docs == []
