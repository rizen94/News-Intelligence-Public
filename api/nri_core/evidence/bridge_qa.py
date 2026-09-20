"""Bridge QA gate for mention resolver auto-link downgrade."""

from __future__ import annotations

from nri_core.services.bridge_qa import assess_bridge_qa
from nri_core.spine.api.lookup import get_entity


def validate_bridge_link(
    *,
    mention_text: str,
    ni_canonical_name: str | None,
    ni_entity_type: str | None,
    ftm_id: str,
    match_score: float,
    match_tier: int,
) -> tuple[bool, str]:
    entity = get_entity(ftm_id)
    if entity is None:
        return False, "ftm_entity_not_found"

    qa = assess_bridge_qa(
        ni_canonical_name=ni_canonical_name,
        ftm_caption=entity.caption,
        ni_entity_type=ni_entity_type,
        ftm_schema_name=entity.schema_name,
        ftm_dataset=entity.dataset,
        mention_text=mention_text,
        anchors=entity.anchors,
    )
    status = str(qa.get("qa_status") or "unknown")
    if status == "ok":
        return True, ""
    flags = qa.get("qa_flags") or []
    reason = f"bridge_qa_{status}"
    if flags:
        reason = f"{reason}:{flags[0]}"
    return False, reason
