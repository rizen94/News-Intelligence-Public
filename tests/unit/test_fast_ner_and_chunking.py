"""Unit tests for fast NER merge and context chunking helpers."""

from __future__ import annotations

from shared.context_chunking import split_article_into_context_chunks
from shared.fast_ner_lane import merge_entity_dicts


def test_merge_entity_dicts_dedupes_by_name():
    base = {"people": [{"name": "Jane Doe", "confidence": 0.7, "in_headline": False}]}
    extra = {"people": [{"name": "jane doe", "confidence": 0.9, "in_headline": True}]}
    merged = merge_entity_dicts(base, extra)
    assert len(merged["people"]) == 1
    assert merged["people"][0]["confidence"] == 0.9


def test_merge_entity_dicts_coerces_string_items():
    base = {"people": ["Jane Doe", {"name": "ACME Corp", "confidence": 0.9}]}
    extra = {"organizations": [{"name": "ACME Corp", "confidence": 0.95, "fast_ner_source": "spacy"}]}
    merged = merge_entity_dicts(base, extra)
    assert merged["people"][0]["name"] == "Jane Doe"
    assert merged["people"][0]["confidence"] == 0.8
    assert len(merged["organizations"]) == 1


def test_split_short_article_single_chunk():
    chunks = split_article_into_context_chunks("Title", "Short body text.")
    assert len(chunks) == 1
    assert chunks[0][0] == "Title"


def test_split_long_article_multiple_chunks(monkeypatch):
    monkeypatch.setenv("CONTEXT_CHUNKING_ENABLED", "true")
    monkeypatch.setenv("CONTEXT_CHUNK_MIN_CHARS", "100")
    monkeypatch.setenv("CONTEXT_CHUNK_SIZE_TOKENS", "50")
    monkeypatch.setenv("CONTEXT_CHUNK_MAX_CHUNKS", "3")
    body = "Word " * 500
    chunks = split_article_into_context_chunks("Long piece", body)
    assert 1 <= len(chunks) <= 3
    assert all(c[1] for c in chunks)
