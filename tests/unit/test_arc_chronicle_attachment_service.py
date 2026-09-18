"""Arc entity name resolution + chronicle soft-match fallback."""

from __future__ import annotations

from services.arc_entity_resolution import resolve_arc_entity_names


def test_resolve_arc_entity_names_from_qids():
    names = resolve_arc_entity_names(
        {"primary_entity_qids": ["Q30", "Q159"], "metadata": {}}
    )
    assert "united states" in names
    assert "russia" in names
    assert "us" in names


def test_resolve_arc_entity_names_merges_yaml_and_metadata():
    names = resolve_arc_entity_names(
        {
            "primary_entity_qids": ["Q796"],
            "primary_entity_names": ["OPEC"],
            "metadata": {
                "primary_entity_names": ["Saudi Arabia"],
                "primary_entity_aliases": ["OPEC+"],
            },
        }
    )
    assert "opec" in names
    assert "opec+" in names
    assert "saudi arabia" in names


def test_resolve_arc_entity_names_empty():
    assert resolve_arc_entity_names(None) == []
    assert resolve_arc_entity_names({}) == []


def test_load_linear_proteins_accepts_names_without_qids(monkeypatch):
    from services import arc_chronicle_attachment_service as mod

    class FakeCur:
        def __init__(self):
            self.last_params = None

        def execute(self, sql, params=None):
            self.last_params = params

        def fetchall(self):
            # Simulate name-match hit even when QIDs empty in DB
            return [(11, "US-China trade", "active", None, 5)]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    cur = FakeCur()

    class FakeConn:
        def cursor(self):
            return cur

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    class FakeCtx:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, *a):
            pass

    class Cfg:
        story_kind = "event_narrative"

        def is_chemistry_kind(self):
            return False

    monkeypatch.setattr(mod, "get_ui_db_connection_context", lambda: FakeCtx())
    monkeypatch.setattr(mod, "get_pipeline_active_domain_keys", lambda: ["politics"])
    monkeypatch.setattr(mod, "resolve_domain_schema", lambda dk: "politics")
    monkeypatch.setattr(mod, "get_domain_synthesis_config", lambda dk: Cfg())

    rows = mod._load_linear_proteins([], ["united states", "china"], limit=10)
    assert len(rows) == 1
    assert rows[0]["storyline_id"] == 11
    # names list present in params (repeated for SQL placeholders)
    assert cur.last_params is not None
    assert ["united states", "china"] in [
        p for p in cur.last_params if isinstance(p, list)
    ]


def test_load_linear_proteins_empty_without_qids_or_names():
    from services import arc_chronicle_attachment_service as mod

    assert mod._load_linear_proteins([], [], limit=10) == []
