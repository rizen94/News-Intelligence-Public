"""Proactive detection outbreak fast-path."""

from domains.storyline_management.services.proactive_detection_service import (
    ProactiveDetectionService,
)


def test_outbreak_articles_link_despite_low_keyword_jaccard():
    svc = ProactiveDetectionService(domain="medicine")
    a = {
        "id": 297850,
        "title": "Message by the WHO Director-General to the people of Tenerife regarding the hantavirus response",
        "summary": "",
        "source_domain": "who.int — rss-feeds",
    }
    b = {
        "id": 297851,
        "title": "WHO’s response to hantavirus cases linked to a cruise ship",
        "summary": "",
        "source_domain": "who.int — rss-feeds",
    }
    kw_a = svc._extract_keywords(a["title"])
    kw_b = svc._extract_keywords(b["title"])
    sim = svc._calculate_keyword_similarity(kw_a, kw_b)
    assert sim < svc.keyword_similarity_threshold
    assert svc._articles_link_for_clustering(a, b, sim) is True


def test_outbreak_signal_two_who_articles():
    svc = ProactiveDetectionService(domain="medicine")
    articles = [
        {
            "id": 1,
            "title": "Hantavirus cases rise in region",
            "summary": "WHO alert issued",
            "source_domain": "www.who.int",
        },
        {
            "id": 2,
            "title": "Public health response to hantavirus outbreak",
            "summary": "Surveillance expanded",
            "source_domain": "www.who.int",
        },
    ]
    assert svc._cluster_outbreak_signal(articles) is True


def test_outbreak_cluster_gets_confidence_floor():
    svc = ProactiveDetectionService(domain="medicine")
    articles = [
        {
            "id": 1,
            "title": "Hantavirus outbreak alert",
            "summary": "",
            "source_domain": "who.int",
            "published_at": None,
        },
        {
            "id": 2,
            "title": "WHO hantavirus response",
            "summary": "",
            "source_domain": "who.int",
            "published_at": None,
        },
    ]
    import asyncio

    emerging = asyncio.run(svc._create_emerging_storyline({"articles": articles}))
    assert emerging is not None
    assert emerging["confidence_score"] >= svc.promote_min_confidence
    assert svc._should_promote_to_storyline(emerging) is True


def test_politics_no_outbreak_pair_promote():
    svc = ProactiveDetectionService(domain="politics")
    emerging = {
        "article_ids": [1, 2],
        "confidence_score": 0.9,
        "outbreak_signal": False,
    }
    assert svc._should_promote_to_storyline(emerging) is False
