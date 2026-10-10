"""Unit tests for expected-date extraction and news dek heuristics."""

from datetime import date, datetime, timezone

from domains.reader.services.expected_dates import extract_expected_dates
from domains.reader.services.home_feed import classify_and_build_feeds


def test_iso_expected_date():
    out = extract_expected_dates("Launch scheduled for 2026-07-15", reference=date(2026, 3, 1))
    assert out["expected_on"] == "2026-07-15"
    assert out["date_precision"] == "day"


def test_month_phrase_to_first():
    out = extract_expected_dates("Paper expected this July", reference=date(2026, 3, 20))
    assert out["expected_on"] == "2026-07-01"
    assert out["date_precision"] == "month"


def test_mdy_concrete():
    out = extract_expected_dates("Announced March 15, 2026; hearing April 2, 2026")
    assert out["announced_on"] == "2026-03-15"
    assert out["expected_on"] == "2026-04-02"


def test_news_requires_dek_and_material_update():
    now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "id": 1,
            "title": "Budget fight intensifies",
            "description": "Lawmakers clash over spending.",
            "editorial_document": {"lede": "Senate leaders reopen talks on the continuing resolution."},
            "updated_at": datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            "last_refinement": None,
            "article_count": 4,
            "parent_storyline_id": None,
            "is_mega_storyline": False,
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "articles_21d": 2,
            "domain": "politics",
            "last_article_added_at": datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc),
        },
        {
            # Membership-only bump: last_article_added_at recent but no material update / empty dek
            "id": 2,
            "title": "Quiet membership bump",
            "description": "",
            "editorial_document": {},
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "last_refinement": None,
            "article_count": 3,
            "parent_storyline_id": None,
            "is_mega_storyline": False,
            "created_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
            "articles_21d": 1,
            "domain": "politics",
            "last_article_added_at": datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc),
        },
    ]
    feeds = classify_and_build_feeds(rows, now=now)
    news_ids = {n["storyline_id"] for n in feeds["news"]}
    assert 1 in news_ids
    assert 2 not in news_ids


def test_ai_thin_cluster_is_one_off_not_news():
    now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "id": 10,
            "title": "Structured Driving-State Narratives for GNSS Spoofing",
            "description": "arXiv paper on SLM-based spoofing detection.",
            "editorial_document": {
                "lede": "A Clemson team frames GNSS spoofing as a small-language-model classification task."
            },
            "updated_at": datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            "last_refinement": datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            "article_count": 1,
            "parent_storyline_id": None,
            "is_mega_storyline": False,
            "created_at": datetime(2026, 9, 18, tzinfo=timezone.utc),
            "articles_21d": 1,
            "domain": "artificial-intelligence",
            "last_article_added_at": datetime(2026, 9, 18, tzinfo=timezone.utc),
        },
        {
            "id": 11,
            "title": "Open-weight models under EU scrutiny",
            "description": "Multiple papers and regulator actions over weeks.",
            "editorial_document": {
                "lede": "Regulators and labs trade claims as open-weight releases accelerate."
            },
            "updated_at": datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc),
            "last_refinement": datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc),
            "article_count": 5,
            "parent_storyline_id": None,
            "is_mega_storyline": False,
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "articles_21d": 4,
            "domain": "artificial-intelligence",
            "last_article_added_at": datetime(2026, 9, 19, tzinfo=timezone.utc),
        },
    ]
    feeds = classify_and_build_feeds(rows, now=now)
    news_ids = {n["storyline_id"] for n in feeds["news"]}
    one_off_ids = {n["storyline_id"] for n in feeds["one_offs"]}
    assert 10 in one_off_ids
    assert 10 not in news_ids
    assert 11 in news_ids
    assert 11 not in one_off_ids
    paper = next(x for x in feeds["one_offs"] if x["storyline_id"] == 10)
    assert "Paper" in paper["badges"]
    assert paper["announced_on"] == "2026-09-18"
