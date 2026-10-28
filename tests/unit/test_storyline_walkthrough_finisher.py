"""Unit tests for storyline editorial walkthrough finisher."""

from __future__ import annotations

from services.storyline_narrative_finisher_service import (
    PROMPT_VERSION,
    StorylineFinisherBundle,
    _load_walkthrough_prompt,
    build_finisher_prompt,
    parse_finisher_response,
    persist_narrative_finish_to_db,
)


def test_walkthrough_prompt_loads_required_sections():
    text = _load_walkthrough_prompt()
    assert "Competing explanations" in text or "competing" in text.lower()
    assert "Background" in text
    assert "---JSON---" in text or "JSON" in text


def test_build_finisher_prompt_includes_rag_and_bones():
    bundle = StorylineFinisherBundle(
        domain_key="politics",
        schema_name="politics",
        storyline_id=8267,
        storyline_title="Netanyahu Rejects Trump's Gaza Disarmament Plan",
        analysis_bones="Description:\nNetanyahu rejected the plan.",
        rag_context_rendered="Wikipedia:\n- Gaza: contested territory…",
        article_summaries=[{"id": 1, "title": "Netanyahu rejects plan", "summary": "…"}],
    )
    prompt = build_finisher_prompt(bundle)
    assert PROMPT_VERSION in prompt
    assert "Wikipedia:" in prompt
    assert "Netanyahu rejected the plan" in prompt
    assert "8267" in prompt


def test_parse_finisher_response_accepts_competing_theories():
    raw = """
Some preamble.

---JSON---
{
  "canonical_narrative": "## Lede\\n\\nSomething happened.\\n\\n## Competing explanations\\n\\nTwo views.",
  "competing_theories": [
    {"label": "Security first", "claim": "Disarmament precondition", "support": ["speech"], "counter": ["allies pushed"]}
  ],
  "open_questions": ["What are the 15 points?"],
  "suggested_new_entities": [],
  "suggested_new_context_hooks": [],
  "sections_to_deprecate_or_trim": [],
  "insufficient_evidence": false,
  "gaps": []
}
"""
    parsed, err = parse_finisher_response(raw)
    assert err is None
    assert isinstance(parsed, dict)
    assert "## Lede" in parsed["canonical_narrative"]
    assert parsed["competing_theories"][0]["label"] == "Security first"
    assert parsed["insufficient_evidence"] is False


def test_persist_meta_shape_includes_competing_theories(monkeypatch):
    """Ensure persist builds meta with competing_theories without requiring DB."""
    captured: dict = {}

    class _Cur:
        def execute(self, sql, params=None):
            captured["sql"] = sql
            captured["params"] = params

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Conn:
        def cursor(self):
            return _Cur()

        def commit(self):
            captured["committed"] = True

    class _Ctx:
        def __enter__(self):
            return _Conn()

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        "services.storyline_narrative_finisher_service.get_ephemeral_db_connection_context",
        lambda: _Ctx(),
    )
    monkeypatch.setattr(
        "services.storyline_narrative_finisher_service._schema_name",
        lambda _d: "politics",
    )

    ok = persist_narrative_finish_to_db(
        "politics",
        8267,
        {
            "parsed": {
                "canonical_narrative": "## Lede\n\nHello walkthrough.\n\n## Background\n\nHistory.",
                "competing_theories": [{"label": "A", "claim": "c", "support": [], "counter": []}],
                "gaps": ["thin plan text"],
                "insufficient_evidence": False,
                "open_questions": ["q1"],
            },
            "model": "test-model",
            "prompt_version": PROMPT_VERSION,
            "parse_error": None,
        },
    )
    assert ok is True
    assert captured.get("committed") is True
    import json

    meta = json.loads(captured["params"][1])
    assert meta["competing_theories"][0]["label"] == "A"
    assert meta["gaps"] == ["thin plan text"]
    assert meta["prompt_version"] == PROMPT_VERSION
