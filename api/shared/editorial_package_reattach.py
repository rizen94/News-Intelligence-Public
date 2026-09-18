"""Sticky uncouple / reattach policy for editorial package members.

Reduction (and operators) can uncouple members from a package. Those rows must
not be silently revived by story_continuation, research attach, or seed refresh
via ``add_member`` UPSERT → ``status='active'``.

Flags that imply a durable suppress stamp (must clear via allow_reattach):
unrelated, geo_mismatch, theme_mismatch, entity_mismatch.
"""

from __future__ import annotations

from typing import Any

# Deterministic reduction flags that should survive continuation re-seeds.
SUPPRESS_REATTACH_FLAGS: frozenset[str] = frozenset(
    {"unrelated", "geo_mismatch", "theme_mismatch", "entity_mismatch"}
)

_BLOCKED_STATUSES: frozenset[str] = frozenset({"removed", "quarantined"})


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def member_status_blocks_reattach(status: str | None) -> bool:
    return str(status or "").strip().lower() in _BLOCKED_STATUSES


def member_has_suppress_reattach(member_or_meta: dict[str, Any] | None) -> bool:
    """True when metadata.suppress_reattach is set (member row or metadata alone)."""
    if not member_or_meta:
        return False
    meta = member_or_meta
    if "suppress_reattach" not in meta and (
        "metadata" in meta or "status" in meta or "member_type" in meta
    ):
        meta = _as_dict(member_or_meta.get("metadata"))
    return bool(meta.get("suppress_reattach"))


def flags_warrant_suppress(flags: list[str] | None = None, rationale: str | None = None) -> bool:
    flag_set = {str(f).strip().lower() for f in (flags or []) if f}
    if flag_set & SUPPRESS_REATTACH_FLAGS:
        return True
    text = (rationale or "").lower()
    return any(f in text for f in SUPPRESS_REATTACH_FLAGS)


def build_suppress_metadata(
    *,
    flags: list[str] | None = None,
    rationale: str | None = None,
    actor: str = "reduction",
    modal: str = "reduction",
) -> dict[str, Any]:
    clean_flags = sorted(
        {str(f).strip().lower() for f in (flags or []) if f} & SUPPRESS_REATTACH_FLAGS
    )
    if not clean_flags and rationale:
        clean_flags = sorted(f for f in SUPPRESS_REATTACH_FLAGS if f in rationale.lower())
    reason = (rationale or "").strip()
    if not reason and clean_flags:
        reason = f"deterministic:{','.join(clean_flags)}"
    return {
        "suppress_reattach": True,
        "suppress_reason": reason[:500] or "uncoupled",
        "suppress_flags": clean_flags,
        "suppress_by": actor,
        "suppress_modal": modal,
    }


def clear_suppress_from_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    meta = dict(_as_dict(metadata))
    for key in (
        "suppress_reattach",
        "suppress_reason",
        "suppress_flags",
        "suppress_by",
        "suppress_modal",
        "suppress_at",
    ):
        meta.pop(key, None)
    return meta


def member_excluded_from_compose(member: dict[str, Any] | None) -> bool:
    """Belt-and-suspenders: never cite/compose members stamped suppress_reattach."""
    return member_has_suppress_reattach(member)
