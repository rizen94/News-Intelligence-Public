"""RSS collector: financial native ads and CNN commerce URLs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from collectors.rss_collector import (  # noqa: E402
    _url_looks_like_commerce_native,
    calculate_article_quality_score,
    is_advertisement,
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
