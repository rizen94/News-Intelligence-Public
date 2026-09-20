from nri_core.spine.resolver.git_resolver import add_judgement, load_judgements, save_judgements


def test_resolver_judgement_roundtrip(tmp_path, monkeypatch):
    import spine.resolver.git_resolver as gr

    monkeypatch.setattr(gr, "RESOLVER_DIR", tmp_path)
    save_judgements([])
    judgements = [{"left_id": "a", "right_id": "b", "score": 0.9, "judgement": "match"}]
    save_judgements(judgements)
    loaded = load_judgements()
    assert len(loaded) == 1
    assert loaded[0]["left_id"] == "a"
