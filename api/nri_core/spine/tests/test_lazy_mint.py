from nri_core.spine.resolution.lazy_mint import search_wikidata


def test_wikidata_search_returns_list_or_empty():
    # Live API — may return hits for well-known name
    hits = search_wikidata("Donald Trump", limit=1)
    assert isinstance(hits, list)
