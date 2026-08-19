"""Unit tests for ClinicalTrials.gov / thin-link fulltext pull gate."""

from __future__ import annotations

from shared.article_processing_gates import finalize_rss_enrichment_after_inline
from shared.fulltext_pull_gate import (
    STATUS_PULL_DEFERRED,
    evaluate_fulltext_pull,
    extract_nct_id,
    is_clinicaltrials_boilerplate,
    is_thin_link_host,
)
from services.clinicaltrials_study_fetch import _study_json_to_text


def test_is_thin_link_host_clinicaltrials():
    assert is_thin_link_host("https://clinicaltrials.gov/study/NCT07717723")
    assert is_thin_link_host("https://www.clinicaltrials.gov/ct2/show/NCT07717723")
    assert not is_thin_link_host("https://www.nejm.org/doi/full/10.1056/NEJMoa123")


def test_boilerplate_detection():
    junk = (
        "Study record managers: refer to the Data Element Definitions if submitting "
        "registration or results information."
    )
    assert is_clinicaltrials_boilerplate(junk)
    assert not is_clinicaltrials_boilerplate("A real brief summary of a Phase 3 vaccine trial.")


def test_extract_nct_id():
    assert extract_nct_id("https://clinicaltrials.gov/study/NCT07717723") == "NCT07717723"
    assert extract_nct_id("https://example.com/nope") is None


def test_evaluate_defer_generic_title():
    v = evaluate_fulltext_pull(
        title="Breast Lump Clipping Methods Comparison",
        url="https://clinicaltrials.gov/study/NCT07716644",
        content="Study record managers: refer to the Data Element Definitions if submitting registration or results information.",
        domain_key="medicine",
    )
    assert v["decision"] == "defer"


def test_evaluate_pull_interesting_title():
    v = evaluate_fulltext_pull(
        title="Phase 3 mRNA Vaccine Trial for Alzheimer's Disease",
        url="https://clinicaltrials.gov/study/NCT09999999",
        content="",
        domain_key="medicine",
    )
    assert v["decision"] == "pull"
    assert "keyword" in (v.get("reason") or "") or "phase" in (v.get("reason") or "")


def test_rss_finalize_thin_link_stays_pending():
    from datetime import datetime, timezone

    status, attempts = finalize_rss_enrichment_after_inline(
        "Study record managers: refer to the Data Element Definitions if submitting registration or results information.",
        created_at=datetime.now(timezone.utc),
        url="https://clinicaltrials.gov/study/NCT07717723",
        trafilatura_attempted=False,
        trafilatura_ok=False,
    )
    assert status == "pending"
    assert attempts == 0


def test_study_json_to_text_includes_summary():
    data = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT07717723",
                "briefTitle": "Caregiver Stress Study",
            },
            "descriptionModule": {
                "briefSummary": "Evaluate Confident Caregiver intervention among family caregivers."
            },
            "conditionsModule": {"conditions": ["Caregiver Burden", "Stress"]},
            "designModule": {"studyType": "INTERVENTIONAL", "phases": ["NA"]},
            "statusModule": {"overallStatus": "RECRUITING"},
            "armsInterventionsModule": {
                "interventions": [{"name": "Confident Caregiver Intervention"}]
            },
        }
    }
    text = _study_json_to_text(data, nct="NCT07717723")
    assert "NCT07717723" in text
    assert "Confident Caregiver" in text
    assert "Caregiver Burden" in text
    assert STATUS_PULL_DEFERRED == "pull_deferred"
