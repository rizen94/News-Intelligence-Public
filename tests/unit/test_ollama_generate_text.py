"""Unit tests for Ollama generate text extraction (qwen3 thinking fallback)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from shared.services.llm_service import _ollama_generate_text  # noqa: E402


def test_prefers_response_over_thinking():
    assert _ollama_generate_text({"response": " {\"a\":1} ", "thinking": "{\"b\":2}"}) == '{"a":1}'


def test_falls_back_to_thinking_when_response_empty():
    assert _ollama_generate_text({"response": "", "thinking": ' {"ok": true} '}) == '{"ok": true}'


def test_empty_when_neither():
    assert _ollama_generate_text({}) == ""
    assert _ollama_generate_text(None) == ""
