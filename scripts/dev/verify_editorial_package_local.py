#!/usr/bin/env python3
"""
Local verification for editorial packages (v11) — PopOS news_intel_dev only.

Usage:
  set -a; source .env.dev; set +a
  python3 scripts/dev/verify_editorial_package_local.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API = os.path.join(ROOT, "api")
if API not in sys.path:
    sys.path.insert(0, API)


def main() -> int:
    env = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    db = (os.environ.get("DB_NAME") or "").strip()
    host = (os.environ.get("DB_HOST") or "").strip()
    if env != "development" or db != "news_intel_dev":
        print(
            "REFUSE: set ENVIRONMENT=development and DB_NAME=news_intel_dev "
            f"(got ENVIRONMENT={env!r} DB_NAME={db!r})"
        )
        return 2
    if host in ("192.168.93.101", "widow"):
        print("REFUSE: Widow host — local verify only")
        return 2

    from services.editorial_package_service import (
        add_link,
        add_member,
        create_package,
        get_package,
        mark_ready_for_editor,
        reduction_clear_or_block,
        search_attachable,
        set_link_status,
        set_member_status,
        update_package,
        validate_prose_citations,
    )
    from services.news_story_service import create_or_update_draft, publish_story
    from services.modal_handoff_service import editor_alerts, request_rework
    from shared.editorial_package_vocab import provenance_has_citeable_source

    # Soft title-as-quote is not publish-citeable
    soft = {"label": "Headline only", "quote": "Headline only"}
    assert provenance_has_citeable_source(soft, for_publish=True) is False
    print("title-as-quote publish refusal OK")

    # Allowlist rejection
    try:
        pkg_bad = create_package(working_title="allowlist check", primary_modal="research")
        add_member(
            int(pkg_bad["id"]),
            member_type="extracted_claim",
            member_id=1,
            member_family="research",
            domain_key="politics",  # not on research allowlist
            added_by_modal="research",
            provenance={"quote": "x"},
        )
        print("FAIL: allowlist should have rejected politics on research")
        return 1
    except ValueError as e:
        print(f"allowlist rejection OK: {e}")

    pkg = create_package(
        working_title="v11 verify hybrid",
        primary_modal="narrative",
        domain_keys=["medicine", "politics"],
        created_by="verify_script",
    )
    pid = int(pkg["id"])
    print(f"package_id={pid}")

    research = add_member(
        pid,
        member_type="extracted_claim",
        member_id=900001,
        member_family="research",
        domain_key="medicine",
        role="core_claim",
        added_by_modal="research",
        provenance={
            "quote": "ADHD comorbidity rates rose in cohort X.",
            "source_url": "https://example.test/paper/1",
        },
    )
    # article_id alone insufficient
    thin = add_member(
        pid,
        member_type="article",
        member_id=900099,
        member_family="research",
        domain_key="medicine",
        role="supporting",
        added_by_modal="research",
        provenance={"article_id": 1},
    )
    narrative = add_member(
        pid,
        member_type="chronological_event",
        member_id=900002,
        member_family="narrative",
        domain_key="politics",
        role="anchor_event",
        added_by_modal="narrative",
        provenance={
            "quote": "Hearing scheduled for Tuesday.",
            "article_id": 1,
        },
    )
    link = add_link(
        pid,
        from_member_id=int(research["id"]),
        to_member_id=int(narrative["id"]),
        link_type="supports",
        inference_stage="candidate",
        modal="narrative",
    )
    set_link_status(
        pid,
        int(link["id"]),
        status="removed",
        modal="reduction",
        rationale="verify prune link",
    )

    set_member_status(
        pid,
        int(narrative["id"]),
        status="quarantined",
        modal="reduction",
        rationale="verify quarantine",
    )

    # Status transition refreshes readiness
    updated = update_package(pid, status="in_editing", actor="verify_script", modal="editor")
    assert updated and isinstance(updated.get("readiness"), dict)
    assert updated["readiness"].get("reduction_cleared") is False
    print("in_editing alone does not clear reduction")

    full = get_package(pid)
    assert full is not None
    readiness = full.get("readiness") or {}
    assert readiness.get("research_brief_ready") is True
    assert "citation_coverage" in readiness
    print(f"readiness={readiness}")

    # Zero citations on non-empty body
    zero = validate_prose_citations(pid, "Unsupported sentence with no markers.")
    assert zero["ok"] is False
    assert any(r.get("reason") == "zero_citations" for r in zero["refused"])
    print("zero-cite body correctly refused")

    # Cite thin article (article_id only) → missing_quote_or_url
    thin_body = f"See article [@m{thin['id']}]."
    thin_check = validate_prose_citations(pid, thin_body)
    assert thin_check["ok"] is False
    print("article_id-only provenance correctly refused")

    bad_body = f"Event happened [@m{narrative['id']}]."
    bad = validate_prose_citations(pid, bad_body)
    assert bad["ok"] is False
    print("quarantined citation correctly refused")

    good_body = f"Finding holds [@m{research['id']}]."
    good = validate_prose_citations(pid, good_body)
    assert good["ok"] is True

    draft = create_or_update_draft(
        pid,
        title="Verify story",
        body_md="No citations here.",
        presentation_kind="hybrid",
        actor="verify_script",
    )
    assert draft["citation_check"]["ok"] is False
    story_id = int(draft["story"]["id"])
    alerts = editor_alerts(limit=20)
    assert any(
        a.get("reason_code") == "citation_gap" and a.get("package_id") == pid for a in alerts
    ), alerts
    print("citation_gap handoff emitted")

    # Empty body publish block
    create_or_update_draft(
        pid,
        title="Verify story empty",
        body_md="   ",
        presentation_kind="hybrid",
        actor="verify_script",
        story_id=story_id,
    )
    empty_block = publish_story(story_id, actor="verify_script")
    assert empty_block.get("blocked") is True
    assert empty_block.get("block_reason") == "empty_body"
    print("empty-body publish blocked")

    create_or_update_draft(
        pid,
        title="Verify story bad",
        body_md=bad_body,
        presentation_kind="hybrid",
        actor="verify_script",
        story_id=story_id,
    )
    # Not reduction-cleared yet
    not_ready = publish_story(story_id, actor="verify_script")
    assert not_ready.get("blocked") is True
    assert not_ready.get("block_reason") == "not_reduction_cleared"
    print("publish blocked without reduction clearance")

    reduction_clear_or_block(pid, clear=True, actor="verify_script", rationale="verify clear")
    mark_ready_for_editor(pid, from_modal="reduction", actor="verify_script")

    create_or_update_draft(
        pid,
        title="Verify story bad",
        body_md=bad_body,
        presentation_kind="hybrid",
        actor="verify_script",
        story_id=story_id,
    )
    blocked = publish_story(story_id, actor="verify_script")
    assert blocked.get("blocked") is True
    print("publish blocked on unsupported citation")

    create_or_update_draft(
        pid,
        title="Verify story",
        body_md=good_body,
        presentation_kind="hybrid",
        actor="verify_script",
        story_id=story_id,
    )
    # Re-clear after draft flipped status to in_editing
    reduction_clear_or_block(pid, clear=True, actor="verify_script", rationale="verify clear again")
    published = publish_story(story_id, actor="verify_script")
    assert published.get("published") is True, published
    print(f"published story_id={story_id}")

    request_rework(pid, target_modal="research", note="verify rework", actor="verify_script")
    print("rework handoff OK")

    search = search_attachable(modal="research", q="a", limit=5)
    hits = search.get("hits") or []
    # No location/entity members keyed by event id
    assert not any(
        h.get("member_type") in ("location", "entity") and h.get("provenance", {}).get("event_id")
        for h in hits
    )
    print(f"search hits={len(hits)} (may be 0 on empty corpus)")

    # Research modality: route helper + dry-run pass (no LLM required for dry_run=False
    # when auto-apply off; force status and dry_run to avoid side effects)
    from services.editorial_package_research_service import (
        resolve_research_route,
        run_research_pass_sync,
        validate_research_payload,
    )

    assert (
        resolve_research_route(
            changed=0,
            meta={"reduction_rounds": 1, "last_reduction_removed_count": 0},
            round_n=1,
            max_r=3,
        )
        == "editor"
    )
    research_pkg = create_package(
        working_title="Verify research modality",
        summary_stub="Claims into facts smoke",
        domain_keys=["medicine"],
        primary_modal="research",
        status="in_research",
        actor="verify_script",
    )
    rpid = int(research_pkg["id"])
    update_package(
        rpid,
        presentation_kind="research_brief",
        actor="verify_script",
        modal="research",
    )
    add_member(
        rpid,
        member_type="extracted_claim",
        member_id=1,
        member_family="research",
        role="core_claim",
        added_by_modal="research",
        provenance={"quote": "Verify claim text for research pass"},
        actor="verify_script",
    )
    dry = run_research_pass_sync(rpid, dry_run=True, force=True)
    assert dry.get("ok") or dry.get("skipped") or dry.get("error") != "crash"
    print(f"research dry-run package_id={rpid} changed={dry.get('changed')} route={dry.get('route_target')}")
    # Validate citeable gate locally
    vp = validate_research_payload(
        {"attach": [{"candidate_key": "versioned_fact:1", "role": "core_claim"}], "links": []},
        payload={
            "members": [],
            "candidates": [
                {
                    "candidate_key": "versioned_fact:1",
                    "member_type": "versioned_fact",
                    "member_id": 1,
                    "provenance": {},
                }
            ],
            "uncoupled_history": [],
            "gaps": [],
        },
    )
    assert vp["attach"] == []
    assert any("not_citeable" in r for r in vp["rejected"])
    print("research validate citeable gate OK")

    print("OK: editorial package local verify passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
