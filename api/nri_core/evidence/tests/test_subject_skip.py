from types import SimpleNamespace

from nri_core.evidence.mention_resolver import NON_ENTITY_TYPES, _should_skip_mention


def test_subject_type_skipped_by_default(monkeypatch):
    monkeypatch.setattr(
        "nri_core.evidence.mention_resolver.get_config",
        lambda: SimpleNamespace(skip_subject_mentions=True),
    )
    assert _should_skip_mention({"entity_type": "subject"})


def test_person_not_skipped(monkeypatch):
    monkeypatch.setattr(
        "nri_core.evidence.mention_resolver.get_config",
        lambda: SimpleNamespace(skip_subject_mentions=True),
    )
    assert not _should_skip_mention({"entity_type": "person"})


def test_non_entity_types_includes_subject():
    assert "subject" in NON_ENTITY_TYPES
