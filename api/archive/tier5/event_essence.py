"""
Event essence text for Mode A ranking (same-event corroboration).

Built from chronological_events fields only — not article body soup.
Use after SQL prefilter; never as a full-corpus scan key alone.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _actor_names(key_actors: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(key_actors, (list, tuple)):
        return names
    for item in key_actors:
        if isinstance(item, dict):
            n = (item.get("name") or "").strip()
            if n:
                names.append(n)
        elif item:
            names.append(str(item).strip())
    return names


def event_essence_text(
    event: Mapping[str, Any] | None,
    *,
    max_chars: int = 800,
) -> str:
    """
    Compact who/what/when/where/outcome string for embedding or cheap compare.

    Accepts a chronological_events-shaped dict (title, key_actors, location,
    actual_event_date / event_date, description / outcome, event_type).
    """
    if not event:
        return ""

    title = (
        event.get("title")
        or event.get("event_title")
        or ""
    )
    title = str(title).strip()

    etype = str(event.get("event_type") or "").strip()
    location = str(event.get("location") or "").strip()
    date_val = event.get("actual_event_date") or event.get("event_date") or ""
    if hasattr(date_val, "isoformat"):
        date_s = date_val.isoformat()[:10]
    else:
        date_s = str(date_val).strip()[:32] if date_val else ""

    actors = _actor_names(event.get("key_actors") or event.get("entities"))
    outcome = str(
        event.get("outcome") or event.get("description") or ""
    ).strip()

    parts: list[str] = []
    if title:
        parts.append(title)
    meta_bits: list[str] = []
    if etype:
        meta_bits.append(f"type={etype}")
    if date_s:
        meta_bits.append(f"when={date_s}")
    if location:
        meta_bits.append(f"where={location}")
    if meta_bits:
        parts.append("; ".join(meta_bits))
    if actors:
        parts.append("Actors: " + ", ".join(actors[:12]))
    if outcome:
        parts.append("Outcome: " + outcome[:400])

    text = ". ".join(parts)
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def event_essence_from_row(
    *,
    title: str | None = None,
    event_type: str | None = None,
    location: str | None = None,
    actual_event_date: Any = None,
    key_actors: Sequence[Any] | None = None,
    description: str | None = None,
    outcome: str | None = None,
) -> str:
    """Positional-friendly wrapper for DB row unpacking."""
    return event_essence_text(
        {
            "title": title,
            "event_type": event_type,
            "location": location,
            "actual_event_date": actual_event_date,
            "key_actors": list(key_actors or []),
            "description": description,
            "outcome": outcome,
        }
    )
