"""Unit tests for multi-context claim LLM JSON parsing."""


def test_parse_batched_claims_response_object_keys():
    from services.claim_extraction_service import _parse_batched_claims_response
    raw = """{
        "101": [{"subject": "Japan", "predicate": "raised rates", "object": "0.5%", "confidence": 0.9}],
        "102": []
    }"""
    got = _parse_batched_claims_response(raw, [101, 102, 103])
    assert len(got[101]) == 1
    assert got[101][0][0] == "Japan"
    assert got[102] == []
    assert got[103] == []


def test_parse_batched_claims_response_contexts_wrapper():
    from services.claim_extraction_service import _parse_batched_claims_response

    raw = """{"contexts": {"55": [{"subject": "ACME", "predicate": "filed", "confidence": 0.8}]}}"""
    got = _parse_batched_claims_response(raw, [55])
    assert len(got[55]) == 1
    assert got[55][0][1] == "filed"