from nri_core.spine.ingest.mappers.edgar import EdgarCompany, company_to_ftm_entity


def test_known_cik_maps_to_ftm_entity():
    company = EdgarCompany(cik="0000320193", ticker="AAPL", title="Apple Inc.")
    entity = company_to_ftm_entity(company)
    assert entity["schema_name"] == "Company"
    assert any(s["prop"] == "cik" and s["value"] == "0000320193" for s in entity["statements"])
    assert any(a["type"] == "cik" for a in entity["anchors"])
