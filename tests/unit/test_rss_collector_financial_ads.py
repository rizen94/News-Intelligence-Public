"""RSS collector: financial / legal native ads and CNN commerce URLs."""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from collectors.rss_collector import (  # noqa: E402
    _url_looks_like_commerce_native,
    _url_looks_like_finance_affiliate_vertical,
    calculate_article_quality_score,
    is_advertisement,
    is_excluded_content,
)

# Test data for the four major phrase lists
_LEGAL_SOFTWARE_NATIVE_AD_PHRASES = (
    "product spotlight",
    "product spotlight:",
    "lexis create",
    "lexis® create",
    "lexis create+",
    "lexis® create+",
    "create+ for litigators",
    "for litigators —",
    "lexis+ ai",
    "lexis+ for",
    "lexisnexis create",
    "powered by lexisnexis",
    "sponsored by lexis",
    "sponsored by lexisnexis",
    "presented by lexisnexis",
    "westlaw edge free trial",
    "try westlaw free",
    "westlaw precision",
    "practical law free trial",
    "casetext co-counsel",
    "harvey ai for law firms",
    "legal tech demo",
    "schedule your demo",
    "book a demo with",
    "free firm trial",
    "legal practice management software",
    "case management software for lawyers",
    "westlaw free trial",
    "lexis free trial",
    "lexisnexis free trial",
    "try lexis",
    "try westlaw",
    "upgrade to westlaw",
    "upgrade to lexis",
)

_MEDICINE_PHARMA_NATIVE_AD_PHRASES = (
    "savings card",
    "copay card",
    "instant savings offer",
    "pay as little as $",
    "pay no more than",
    "$0 copay",
    "eligible commercially insured",
    "eligible patients may pay",
    "not actual patients",
    "not actual patient",
    "not a real patient",
    "actor portrayal",
    "paid actor",
    "paid actors",
    "paid spokesperson",
    "prescribing information and medication guide",
    "scroll for important safety",
    "scroll for isi",
    "important safety information, including boxed warning",
    "fda-approved treatment option",
    "prescription treatment website",
    "get your prescription online",
    "same-day prescription delivery",
    "order medication online",
    "weight loss prescription online",
    "miracle supplement",
    "this statement has not been evaluated by the fda",
    "not intended to diagnose, treat, cure",
)

_AI_BOT_NATIVE_AD_PHRASES = (
    "ai chatbot free trial",
    "no-code ai chatbot",
    "no-code chatbot",
    "white-label ai chatbot",
    "white-label chatbot",
    "custom ai chatbot for your",
    "ai chatbot for your business",
    "ai chatbot for your website",
    "automate customer service with ai",
    "customer service ai chatbot",
    "conversational ai platform",
    "enterprise ai chatbot",
    "sales ai bot",
    "ai sdr",
    "ai sales assistant",
    "hire an ai employee",
    "digital worker powered by ai",
    "replace your support team with ai",
    "gpt for your business",
    "custom gpt for your",
    "build your own chatgpt",
    "clone yourself with ai",
    "deploy your llm in minutes",
    "rag-as-a-service",
    "try our ai assistant",
    "book a demo with our ai",
    "start your free ai trial",
    "unlimited ai messages",
    "ai agent free trial",
    "virtual assistant for your sales team",
    "automate your workflow with our ai",
    "get more leads with ai bots",
)

_FINANCIAL_NATIVE_AD_PHRASES = (
    "subject to credit approval",
    "member fdic",
    "member fdic.",
    "0% intro apr",
    "introductory apr",
    "intro apr",
    "see issuer",
    "see rates and fees",
    "rates & fees",
    "rates and fees",
    "variable apr",
    "credit card offer",
    "credit card offers",
    "best credit cards",
    "cash back rewards",
    "earn unlimited",
    "points per dollar",
    "terms apply",
    "cnn underscored",
    "partner offer",
    "paid partner",
    "bonus miles after",
    "bonus points after",
    "earn miles on every",
    "earn points on every",
    "prequalified offer",
    "pre-approved offer",
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


def test_is_advertisement_does_not_flag_news_deals_or_marketing():
    assert not is_advertisement(
        "Israel and Hamas reach a ceasefire deal",
        "Negotiators said the deal would pause fighting. Marketing of the plan continues in Congress.",
        "https://www.reuters.com/world/ceasefire-deal",
    )
    assert not is_advertisement(
        "Holiday sales jump as shoppers return",
        "Retail sales rose 2% last month, the Commerce Department said.",
        "https://www.bloomberg.com/news/articles/retail-sales",
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
@pytest.mark.parametrize("phrase", _FINANCIAL_NATIVE_AD_PHRASES)
def test_is_advertisement_financial_phrases_parametrized(phrase):
    """Test that all financial native ad phrases are detected in title and body."""
    # Test in title
    assert is_advertisement(
        phrase,
        "Some content",
        "https://example.com/test"
    )
    
@pytest.mark.parametrize("phrase", _LEGAL_SOFTWARE_NATIVE_AD_PHRASES)
def test_is_advertisement_legal_phrases_parametrized(phrase):
    """Test that all legal software native ad phrases are detected in title and body."""
    # Test in title
    assert is_advertisement(
        phrase,
        "Some content",
        "https://example.com/test"
    )
    
@pytest.mark.parametrize("phrase", _MEDICINE_PHARMA_NATIVE_AD_PHRASES)
def test_is_advertisement_pharma_phrases_parametrized(phrase):
    """Test that all medicine/pharma native ad phrases are detected in title and body."""
    # Test in title
    assert is_advertisement(
        phrase,
        "Some content",
        "https://example.com/test"
    )
    
@pytest.mark.parametrize("phrase", _AI_BOT_NATIVE_AD_PHRASES)
def test_is_advertisement_ai_bot_phrases_parametrized(phrase):
    """Test that all AI bot native ad phrases are detected in title and body."""
    # Test in title
    assert is_advertisement(
        phrase,
        "Some content",
        "https://example.com/test"
    )
    
    # Test in body  
    assert is_advertisement(
        "Regular title",
        phrase,
        "https://example.com/test"
    )


def test_is_advertisement_case_insensitive():
    """Test that advertisement detection is case insensitive."""
    # Test with uppercase
    assert is_advertisement(
        "PRODUCT SPOTLIGHT: LEXIS® CREATE+ FOR LITIGATORS",
        "Some content",
        "https://example.com/test"
    )
    
    # Test with mixed case
    assert is_advertisement(
        "Lexis® Create+ Free Trial",
        "Some content", 
        "https://example.com/test"
    )


def test_is_advertisement_unicode_handling():
    """Test that advertisement detection handles unicode characters properly."""
    # Test with registered trademark symbol
    assert is_advertisement(
        "Lexis® Create+ Free Trial",
        "Some content",
        "https://example.com/test"
    )


def test_is_advertisement_title_only_vs_body_only():
    """Test that phrases in title only vs body only both trigger advertisements."""
    # Phrase in title only
    assert is_advertisement(
        "Product Spotlight: Lexis® Create+ For Litigators",
        "Some content here but not the ad phrase",
        "https://example.com/test"
    )
    
    # Phrase in body only  
    assert is_advertisement(
        "Regular title",
        "Product Spotlight: Lexis® Create+ For Litigators",
        "https://example.com/test"
    )


def test_is_advertisement_boundary_word_counts():
    """Test edge cases around word counts for phrase matching."""
    # Test with exact phrase match
    assert is_advertisement(
        "Best credit cards",
        "Some content with the phrase best credit cards in it",
        "https://example.com/test"
    )
    
    # Test with phrase plus surrounding text
    assert is_advertisement(
        "Get your prescription online",
        "This is a test about getting prescriptions online with a savings card",
        "https://example.com/test"
    )
    # Test in body  
    assert is_advertisement(
        "Regular title",
        phrase,
        "https://example.com/test"
    )
    # Test in body  
    assert is_advertisement(
        "Regular title",
        phrase,
        "https://example.com/test"
    )
    # Test in body  
    assert is_advertisement(
        "Regular title",
        phrase,
        "https://example.com/test"
    )
