"""Sanity checks for report route domain-key helpers (no DB)."""

from domains.intelligence_hub.routes import report as report_mod


def test_domain_keys_matching_path_science_tech():
    keys = report_mod._domain_keys_matching_path("science-tech")
    assert "science-tech" in keys
    assert "science_tech" in keys


def test_path_segment_for_db_domain_key():
    assert report_mod._path_segment_for_db_domain_key("science_tech") == "science-tech"
    assert report_mod._path_segment_for_db_domain_key("politics") == "politics"
