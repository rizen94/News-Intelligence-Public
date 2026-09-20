from nri_core.spine.ingest.mappers.edgar import (
    EdgarCompany,
    dedupe_by_cik,
    is_instrument_tail,
    load_deduped_companies,
)


def test_instrument_tail_detects_warrant():
    assert is_instrument_tail(EdgarCompany("0000320193", "AAPLW", "Apple Inc. Warrant"))


def test_instrument_tail_keeps_operating_company():
    assert not is_instrument_tail(EdgarCompany("0000320193", "AAPL", "Apple Inc."))


def test_dedupe_by_cik_keeps_one_per_cik():
    companies = [
        EdgarCompany("0000320193", "AAPL", "Apple Inc."),
        EdgarCompany("0000320193", "AAPLW", "Apple Inc. Warrant"),
    ]
    deduped = dedupe_by_cik(companies)
    assert len(deduped) == 1
    assert deduped[0].ticker == "AAPL"


def test_load_deduped_filters_instruments(monkeypatch):
    def fake_fetch():
        return [
            EdgarCompany("0000789019", "MSFT", "Microsoft Corp"),
            EdgarCompany("0000789019", "MSFTW", "Microsoft Corp Warrant"),
        ]

    monkeypatch.setattr(
        "spine.ingest.mappers.edgar.fetch_company_tickers",
        fake_fetch,
    )
    result = load_deduped_companies()
    assert len(result) == 1
    assert result[0].ticker == "MSFT"
