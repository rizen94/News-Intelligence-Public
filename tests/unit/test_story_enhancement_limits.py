"""Shared story_enhancement batch resolver / facts-only policy."""


def test_run_limits_facts_only_defaults(monkeypatch):
    from shared import pipeline_resource_policy as prp

    monkeypatch.delenv("STORY_ENHANCEMENT_FACT_BATCH", raising=False)
    monkeypatch.delenv("STORY_ENHANCEMENT_QUEUE_BATCH", raising=False)
    monkeypatch.delenv("STORY_ENHANCEMENT_ENRICH_LIMIT", raising=False)
    monkeypatch.delenv("STORY_ENHANCEMENT_BUILD_LIMIT", raising=False)

    limits = prp.story_enhancement_run_limits(facts_only=True)
    assert limits["enrich_limit"] == 0
    assert limits["build_limit"] == 0
    assert limits["fact_batch"] == 1000
    assert limits["queue_batch"] == 200


def test_run_limits_full_cycle_defaults(monkeypatch):
    from shared import pipeline_resource_policy as prp

    monkeypatch.delenv("STORY_ENHANCEMENT_FACT_BATCH", raising=False)
    monkeypatch.delenv("STORY_ENHANCEMENT_QUEUE_BATCH", raising=False)
    monkeypatch.delenv("STORY_ENHANCEMENT_ENRICH_LIMIT", raising=False)
    monkeypatch.delenv("STORY_ENHANCEMENT_BUILD_LIMIT", raising=False)

    limits = prp.story_enhancement_run_limits(facts_only=False)
    assert limits["enrich_limit"] == 10
    assert limits["build_limit"] == 10
    assert limits["fact_batch"] == 100
    assert limits["queue_batch"] == 10


def test_run_limits_env_overrides(monkeypatch):
    from shared import pipeline_resource_policy as prp

    monkeypatch.setenv("STORY_ENHANCEMENT_FACT_BATCH", "1500")
    monkeypatch.setenv("STORY_ENHANCEMENT_QUEUE_BATCH", "250")
    monkeypatch.setenv("STORY_ENHANCEMENT_ENRICH_LIMIT", "25")
    monkeypatch.setenv("STORY_ENHANCEMENT_BUILD_LIMIT", "15")

    facts = prp.story_enhancement_run_limits(facts_only=True)
    assert facts["fact_batch"] == 1500
    assert facts["queue_batch"] == 250
    assert facts["enrich_limit"] == 0
    assert facts["build_limit"] == 0

    full = prp.story_enhancement_run_limits(facts_only=False)
    assert full["fact_batch"] == 1500
    assert full["queue_batch"] == 250
    assert full["enrich_limit"] == 25
    assert full["build_limit"] == 15


def test_run_limits_follows_facts_only_helper(monkeypatch):
    from shared import pipeline_resource_policy as prp

    monkeypatch.setattr(prp, "story_enhancement_facts_only", lambda: True)
    limits = prp.story_enhancement_run_limits()
    assert limits["enrich_limit"] == 0

    monkeypatch.setattr(prp, "story_enhancement_facts_only", lambda: False)
    limits = prp.story_enhancement_run_limits()
    assert limits["enrich_limit"] == 10


def test_facts_only_env_true_false(monkeypatch):
    from shared import pipeline_resource_policy as prp

    monkeypatch.setenv("STORY_ENHANCEMENT_FACTS_ONLY", "true")
    assert prp.story_enhancement_facts_only() is True
    monkeypatch.setenv("STORY_ENHANCEMENT_FACTS_ONLY", "false")
    assert prp.story_enhancement_facts_only() is False
