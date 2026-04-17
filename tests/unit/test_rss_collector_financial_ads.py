"""RSS collector: financial / legal native ads and CNN commerce URLs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from collectors.rss_collector import (  # noqa: E402
    _url_looks_like_commerce_native,
    _url_looks_like_finance_affiliate_vertical,
    calculate_article_quality_score,
    is_advertisement,
    is_excluded_content,
)


def test_url_commerce_native_cnn_underscored():
    assert _url_looks_like_commerce_native(
        "https://www.cnn.com/cnn-underscored/money/best-credit-cards"
    )
    assert not _url_looks_like_commerce_native(
        "https://www.cnn.com/2024/01/01/politics/example"
    )


def test_is_advertisement_financial_phrases():
    assert is_advertisement(
        "Great rewards",
        "Apply today. Subject to credit approval. Member FDIC.",
        "https://example.com/x",
    )
    assert is_advertisement(
        "Best cards",
        "See rates and fees. Variable APR applies.",
        "https://example.com/y",
    )


def test_is_advertisement_legal_vendor_product_spotlight():
    title = "Product Spotlight: Lexis® Create+ For Litigators"
    body = "Streamline drafting with AI-assisted workflows. Terms apply."
    assert is_advertisement(title, body, "https://www.abajournal.com/ad/example")


def test_is_advertisement_legal_westlaw_trial_phrase():
    assert is_advertisement(
        "Westlaw Edge",
        "Start your Westlaw Edge free trial today.",
        "https://example.com/promo",
    )


def test_is_advertisement_pharma_savings_card():
    assert is_advertisement(
        "Treatment option",
        "Eligible commercially insured patients may pay as little as $10 with savings card.",
        "https://example.com/drug-promo",
    )


def test_is_advertisement_ai_chatbot_saas():
    assert is_advertisement(
        "Scale support",
        "Deploy our no-code AI chatbot for your website. Start your free AI trial.",
        "https://vendor.example/saas",
    )


def test_native_vertical_promo_does_not_match_plain_health_news():
    assert not is_advertisement(
        "Study finds modest benefit in older adults",
        "Researchers reported outcomes in a randomized trial. Discuss screening with your clinician.",
        "https://nejm.org/doi/example",
    )


def test_quality_score_caps_legal_native_ad_below_ingest():
    q = calculate_article_quality_score(
        "Product Spotlight: Lexis® Create+ For Litigators",
        "Long " * 200,
        "ABA Journal",
        "https://example.com/legal-tools",
    )
    assert q < 0.3


def test_url_finance_affiliate_vertical():
    assert _url_looks_like_finance_affiliate_vertical(
        "https://www.nerdwallet.com/article/credit-cards/best-cards"
    )
    assert not _url_looks_like_finance_affiliate_vertical(
        "https://www.reuters.com/world/us/congress-2025-01-01/"
    )


def test_is_advertisement_title_only_credit_card_roundup():
    assert is_advertisement(
        "Compare the best credit cards for dining rewards",
        "",
        "https://example.com/article",
    )
    assert is_advertisement(
        "Top 6 credit cards for travel in 2026",
        "",
        "https://example.com/article",
    )
    assert not is_advertisement(
        "Senate panel holds hearing on credit card fee cap bill",
        "Lawmakers discussed interchange fees.",
        "https://example.com/politics/1",
    )


def test_is_excluded_content_politics_merged_defaults_best_credit_cards():
    assert is_excluded_content(
        "Our picks",
        "Best credit cards for groceries and gas this year.",
        "Wirecutter",
        "",
        domain="politics",
    )


def test_quality_score_caps_cnn_commerce_and_skips_reputable_boost():
    # Commerce URL: no +0.15 for "cnn" in source, and capped below 0.3 ingest threshold
    q = calculate_article_quality_score(
        "The best travel cards",
        "Long " * 200 + " body text for length boost",
        "CNN Politics",
        "https://www.cnn.com/cnn-underscored/money/credit-cards",
    )
    assert q < 0.3

    # Same title/body with a normal politics path still gets CNN boost (high)
    q_news = calculate_article_quality_score(
        "House vote scheduled",
        "Officials said " * 80,
        "CNN Politics",
        "https://www.cnn.com/2025/01/01/politics/congress",
    )
    assert q_news >= 0.5
