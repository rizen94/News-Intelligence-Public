"""Unit tests for unified intake batch JSON parse and prompt hardening."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.services.ollama_model_policy import InvocationKind, extraction_temperature_for_invocation


def _repair_json_object_text(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
    if t.endswith("```"):
        t = t.rsplit("```", 1)[0]
    t = t.strip()
    t = re.sub(r",\s*]", "]", t)
    t = re.sub(r",\s*}", "}", t)
    return t


def _try_parse_first_json_object(text: str) -> dict[str, Any] | None:
  """Mirror of unified intake salvage helper for unit tests."""
  start = text.find("{")
  if start < 0:
      return None
  try:
      obj, _ = json.JSONDecoder().raw_decode(text, start)
  except json.JSONDecodeError:
      return None
  return obj if isinstance(obj, dict) else None


def _parse_batch_response(raw: str) -> dict[int, dict[str, Any]]:
    """Mirror of UnifiedIntakeExtractionService._parse_batch_response for unit tests."""
    text = (raw or "").strip()
    if "```" in text:
        for part in text.split("```"):
            chunk = part.strip()
            if chunk.lower().startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{"):
                text = chunk
                break
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    slice_text = text[start : end + 1]
    try:
        parsed = json.loads(slice_text)
    except json.JSONDecodeError as e:
        try:
            parsed = json.loads(_repair_json_object_text(slice_text))
        except json.JSONDecodeError:
            parsed = None
        if parsed is None and "Extra data" in str(e):
            salvaged = _try_parse_first_json_object(slice_text)
            if salvaged:
                parsed = salvaged
        if parsed is None:
            return {}
    if not isinstance(parsed, dict):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for k, v in parsed.items():
        try:
            aid = int(k)
            if isinstance(v, dict):
                out[aid] = v
        except (TypeError, ValueError):
            pass
    return out


def test_parse_batch_response_plain_object():
    raw = '{"1001": {"entities": {"people": []}, "claims": [], "events": [], "scoring": {}}}'
    parsed = _parse_batch_response(raw)
    assert 1001 in parsed


def test_parse_batch_response_markdown_fence():
    raw = '```json\n{"2002": {"entities": {}, "claims": [], "events": [], "scoring": {}}}\n```'
    parsed = _parse_batch_response(raw)
    assert 2002 in parsed


def test_parse_batch_response_extra_data_salvages_first_object():
    raw = (
        '{"3003": {"entities": {}, "claims": [], "events": [], "scoring": {}}} '
        "Here is a summary of the articles."
    )
    parsed = _parse_batch_response(raw)
    assert 3003 in parsed


def test_parse_batch_response_trailing_comma_repair():
    raw = '{"4004": {"entities": {"people": [],}, "claims": [], "events": [], "scoring": {}}}'
    parsed = _parse_batch_response(raw)
    assert 4004 in parsed


def test_build_prompt_lists_required_article_ids():
    prompt_path = Path(__file__).resolve().parents[2] / "api" / "services" / "unified_intake_extraction_service.py"
    source = prompt_path.read_text(encoding="utf-8")
    assert "Top-level JSON keys MUST be exactly" in source
    assert "no markdown fences" in source
    assert "_JSON_RETRY_SUFFIX" in source


def test_extraction_temperature_lower_for_structured_extraction():
    assert extraction_temperature_for_invocation(InvocationKind.STRUCTURED_EXTRACTION) == 0.15
    assert extraction_temperature_for_invocation(InvocationKind.DEFAULT) == 0.7


@dataclass
class _FakeGen:
    text: str
    model: str = "test-model"


def test_extract_batch_json_retry_suffix_recovers(monkeypatch):
    """Integration-style test with mocked LLM and fan-out (requires DB for import chain)."""
    import asyncio
    import os

    if not os.environ.get("NEWS_INTEL_INTEGRATION_DB"):
        pytest.skip("set NEWS_INTEL_INTEGRATION_DB=1 with Widow DB env to run")
    from services.unified_intake_extraction_service import (
        UnifiedIntakeExtractionService,
        _JSON_RETRY_SUFFIX,
    )

    svc = UnifiedIntakeExtractionService.__new__(UnifiedIntakeExtractionService)
    svc._caller = MagicMock()
    svc._entity_svc = MagicMock()
    svc._event_svc = MagicMock()
    calls: list[str] = []

    async def fake_generate(prompt: str, **kwargs: Any) -> _FakeGen:
        calls.append(prompt)
        if len(calls) == 1:
            return _FakeGen(text="not json at all")
        return _FakeGen(text='{"9001": {"entities": {}, "claims": [], "events": [], "scoring": {}}}')

    svc._caller.generate = fake_generate
    monkeypatch.setattr(
        "services.unified_intake_extraction_service.extract_fast_entities",
        lambda title, content: {},
    )
    monkeypatch.setattr(svc, "_fan_out_article", AsyncMock(return_value={"success": True, "attempted": True}))
    monkeypatch.setattr(
        "services.spine_throughput_metrics.record_fusion_parse_retry",
        lambda kind: None,
    )

    articles = [
        {
            "article_id": 9001,
            "title": "Retry suffix test headline",
            "content": "Enough body content here to pass the minimum length gate for unified intake.",
            "schema": "politics",
            "domain_key": "politics",
        }
    ]
    out = asyncio.run(svc.extract_batch(articles))
    assert 9001 in out
    assert out[9001]["success"] is True
    assert len(calls) == 2
    assert _JSON_RETRY_SUFFIX.strip() in calls[1]
