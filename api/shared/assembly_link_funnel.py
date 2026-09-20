"""
Assembly retrieval funnel: SQL/index prefilter → LIMIT K → cheap score.

Never full-corpus review per new storyline/event. Call sites:
continuation, storyline_automation auto-add, event coreference ranking.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from config.runtime import env_bool, env_int, env_str
from shared.assembly_link_modes import (
    DENY_SOLO_ENTITY_TYPES,
    DURABLE_ENTITY_TYPES,
    LINK_MODE_SEQUENCE,
)

logger = logging.getLogger(__name__)


def funnel_candidate_limit(*, mode: str = LINK_MODE_SEQUENCE) -> int:
    """Hard K for candidate sets (independent of corpus size)."""
    if mode == "same_event":
        return max(1, min(50, env_int("ASSEMBLY_SAME_EVENT_CANDIDATE_LIMIT", 15)))
    return max(1, min(50, env_int("ASSEMBLY_SEQUENCE_CANDIDATE_LIMIT", 10)))


def automation_auto_attach_enabled() -> bool:
    """Kill-switch: silent bag membership off by default (Event→Episode rebuild).

    STORYLINE_AUTOMATION_AUTO_ATTACH=1 re-enables legacy auto-add (not recommended).
    """
    return env_bool("STORYLINE_AUTOMATION_AUTO_ATTACH", False)


def storyline_articles_dual_write_enabled() -> bool:
    """v12: EEL is membership SSOT; dual-write to storyline_articles off by default.

    STORYLINE_ARTICLES_DUAL_WRITE=1 re-enables derived bag rows for legacy UI.
    """
    return env_bool("STORYLINE_ARTICLES_DUAL_WRITE", False)


def storyline_articles_write_allowed() -> bool:
    """True when bag membership writes are allowed.

    When episode_container_assembly is on, bag writes require dual-write.
    When episode assembly is off, legacy bag writes remain allowed.
    """
    try:
        from shared.episode_attach_gate import episode_container_assembly_enabled

        if episode_container_assembly_enabled():
            return storyline_articles_dual_write_enabled()
    except Exception:
        # Fail closed for bag writes if we cannot read the episode flag.
        return storyline_articles_dual_write_enabled()
    return True


def durable_entity_types() -> frozenset[str]:
    raw = env_str("ASSEMBLY_DURABLE_ENTITY_TYPES", "").strip()
    if not raw:
        return DURABLE_ENTITY_TYPES
    parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return frozenset(parts) if parts else DURABLE_ENTITY_TYPES


def is_durable_entity_type(entity_type: str | None) -> bool:
    et = (entity_type or "").strip().lower()
    if not et or et in DENY_SOLO_ENTITY_TYPES:
        return False
    return et in durable_entity_types()


def filter_durable_canonical_ids(
    pairs: Sequence[tuple[Any, Any]],
    *,
    exclude_hub_names: frozenset[str] | None = None,
    name_by_cid: dict[int, str] | None = None,
) -> list[int]:
    """
    From (canonical_entity_id, entity_type) pairs keep durable IDs only.

    Drop topical subjects (e.g. data breach) that bridged unrelated lawsuits.
    When exclude_hub_names + name_by_cid are provided, drop hub institution IDs
    so they never alone satisfy Mode B overlap.
    """
    hub_names = exclude_hub_names or frozenset()
    names = name_by_cid or {}
    out: list[int] = []
    seen: set[int] = set()
    for cid, etype in pairs:
        if cid is None:
            continue
        if not is_durable_entity_type(str(etype) if etype is not None else None):
            continue
        try:
            i = int(cid)
        except (TypeError, ValueError):
            continue
        if i in seen:
            continue
        if hub_names:
            ename = (names.get(i) or "").strip().lower()
            if ename and (
                ename in hub_names
                or any(len(h) >= 5 and (h in ename or ename in h) for h in hub_names)
            ):
                continue
        seen.add(i)
        out.append(i)
    return out


def _hub_name_set_for_domain(domain_key: str) -> frozenset[str]:
    try:
        import importlib.util
        import sys
        from pathlib import Path

        name = "services.domain_synthesis_config"
        mod = sys.modules.get(name)
        if mod is None:
            path = (
                Path(__file__).resolve().parents[1]
                / "services"
                / "domain_synthesis_config.py"
            )
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                return frozenset()
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        return mod.get_domain_synthesis_config(domain_key).hub_name_set()
    except Exception:
        return frozenset()


def article_durable_canonical_ids(
    conn,
    schema: str,
    article_id: int,
    *,
    domain_key: str | None = None,
    exclude_hubs: bool = False,
) -> list[int]:
    """Durable person/org(/case) canonicals on one article."""
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT canonical_entity_id, entity_type, entity_name
            FROM {schema}.article_entities
            WHERE article_id = %s AND canonical_entity_id IS NOT NULL
            """,
            (int(article_id),),
        )
        rows = cur.fetchall() or []
        name_by_cid = {
            int(r[0]): str(r[2] or "")
            for r in rows
            if r[0] is not None
        }
        pairs = [(r[0], r[1]) for r in rows]
        hubs = (
            _hub_name_set_for_domain(domain_key)
            if exclude_hubs and domain_key
            else frozenset()
        )
        return filter_durable_canonical_ids(
            pairs,
            exclude_hub_names=hubs if exclude_hubs else None,
            name_by_cid=name_by_cid if exclude_hubs else None,
        )
    except Exception as e:
        logger.debug("article_durable_canonical_ids(%s,%s): %s", schema, article_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return []
    finally:
        cur.close()


def storyline_durable_canonical_ids(
    conn,
    schema: str,
    storyline_id: int,
    *,
    domain_key: str | None = None,
    exclude_hubs: bool = False,
) -> list[int]:
    """Durable canonicals on story_entity_index (prefer typed rows)."""
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT canonical_entity_id, entity_type, entity_name
            FROM {schema}.story_entity_index
            WHERE storyline_id = %s AND canonical_entity_id IS NOT NULL
            """,
            (int(storyline_id),),
        )
        rows = cur.fetchall() or []
        name_by_cid = {
            int(r[0]): str(r[2] or "")
            for r in rows
            if r[0] is not None
        }
        pairs = [(r[0], r[1]) for r in rows]
        hubs = (
            _hub_name_set_for_domain(domain_key)
            if exclude_hubs and domain_key
            else frozenset()
        )
        return filter_durable_canonical_ids(
            pairs,
            exclude_hub_names=hubs if exclude_hubs else None,
            name_by_cid=name_by_cid if exclude_hubs else None,
        )
    except Exception as e:
        logger.debug(
            "storyline_durable_canonical_ids(%s,%s): %s", schema, storyline_id, e
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return []
    finally:
        cur.close()


def shared_durable_canonical_count(
    a: Sequence[int], b: Sequence[int]
) -> int:
    if not a or not b:
        return 0
    return len(set(int(x) for x in a) & set(int(x) for x in b))


def allow_auto_membership_sequence(
    conn,
    *,
    schema: str,
    storyline_id: int,
    article_id: int,
    min_shared: int = 1,
    domain_key: str | None = None,
    exclude_hubs: bool = True,
) -> tuple[bool, str]:
    """
    Mode B seatbelt for silent auto-attach.

    Requires ≥ min_shared durable canonical overlap between article and storyline.
    By default hub institutions (SCOTUS, Fed, …) are excluded from the count so
    genre magnets cannot alone authorize membership.
    """
    dk = (domain_key or "").strip() or None
    art = article_durable_canonical_ids(
        conn, schema, article_id, domain_key=dk, exclude_hubs=exclude_hubs
    )
    if not art:
        return False, "article_no_durable_canonical"
    sl = storyline_durable_canonical_ids(
        conn, schema, storyline_id, domain_key=dk, exclude_hubs=exclude_hubs
    )
    if not sl:
        return False, "storyline_no_durable_canonical"
    n = shared_durable_canonical_count(art, sl)
    if n < max(1, int(min_shared)):
        return False, f"durable_overlap_{n}_lt_{min_shared}"
    return True, f"durable_overlap_{n}"


def allow_storyline_membership_attach(
    conn,
    *,
    domain_key: str,
    schema: str,
    storyline_id: int,
    article_id: int,
    blend_score: float,
    link_mode: str = LINK_MODE_SEQUENCE,
    article_count: int | None = None,
) -> tuple[bool, str]:
    """
    SSOT silent-membership gate for all storyline attach paths.

    1. link_mode must allow auto membership
    2. hub-excluded durable overlap ≥ domain min_shared
    3. blend_score ≥ auto_approve_combined
    4. under attach_hard_cap
    """
    from shared.assembly_link_modes import AUTO_MEMBERSHIP_MODES
    from shared.storyline_attach_caps import storyline_at_or_over_attach_cap

    mode = (link_mode or LINK_MODE_SEQUENCE).strip()
    if mode not in AUTO_MEMBERSHIP_MODES:
        return False, f"link_mode_not_auto:{mode}"

    try:
        import importlib.util
        import sys
        from pathlib import Path

        name = "services.domain_synthesis_config"
        mod = sys.modules.get(name)
        if mod is None:
            path = (
                Path(__file__).resolve().parents[1]
                / "services"
                / "domain_synthesis_config.py"
            )
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise ImportError(name)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        cfg = mod.get_domain_synthesis_config(domain_key)
        floor = float(cfg.link_score_profile.auto_approve_combined)
        min_shared = int(cfg.membership_min_shared_non_hub())
    except Exception:
        floor = 0.75
        min_shared = 1

    try:
        score = float(blend_score)
    except (TypeError, ValueError):
        return False, "blend_score_invalid"
    if score < floor:
        return False, f"blend_{score:.3f}_lt_floor_{floor:.3f}"

    ok, reason = allow_auto_membership_sequence(
        conn,
        schema=schema,
        storyline_id=int(storyline_id),
        article_id=int(article_id),
        min_shared=min_shared,
        domain_key=domain_key,
        exclude_hubs=True,
    )
    if not ok:
        return False, reason

    count = article_count
    if count is None:
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.storyline_articles
                WHERE storyline_id = %s
                """,
                (int(storyline_id),),
            )
            row = cur.fetchone()
            count = int(row[0]) if row else 0
        except Exception as e:
            logger.debug("article_count for gate: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
            count = 0
        finally:
            cur.close()

    if storyline_at_or_over_attach_cap(domain_key, int(count or 0)):
        return False, f"attach_cap_reached:{count}"

    return True, f"ok:{reason}:blend={score:.3f}"


def prefilter_same_event_candidates(
    conn,
    *,
    event_id: int,
    durable_canonical_ids: Sequence[int],
    event_date: Any | None,
    event_type: str | None = None,
    lookback_days: int | None = None,
    limit: int | None = None,
) -> list[int]:
    """
    Mode A SQL narrow: peer chronological_events sharing durable actors + time window.

    Returns event ids only (≤K). Empty list = singleton OK — do not invent peers.
    """
    cids = [int(c) for c in durable_canonical_ids if c is not None]
    if not cids:
        return []

    k = limit if limit is not None else funnel_candidate_limit(mode="same_event")
    days = lookback_days if lookback_days is not None else env_int(
        "ASSEMBLY_SAME_EVENT_LOOKBACK_DAYS", 14
    )
    days = max(1, min(90, int(days)))

    cur = conn.cursor()
    try:
        from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

        schemas = [resolve_domain_schema(dk) for dk in get_pipeline_active_domain_keys()]
        cur.execute(
            """
            SELECT id, source_article_id
            FROM public.chronological_events
            WHERE id <> %s
              AND canonical_event_id IS NULL
              AND source_article_id IS NOT NULL
              AND (
                %s::timestamptz IS NULL
                OR actual_event_date IS NULL
                OR actual_event_date BETWEEN
                    (%s::timestamptz - (%s || ' days')::interval)
                    AND (%s::timestamptz + (%s || ' days')::interval)
              )
              AND (
                %s::text IS NULL
                OR event_type IS NULL
                OR event_type = %s
              )
            ORDER BY id DESC
            LIMIT %s
            """,
            (
                int(event_id),
                event_date,
                event_date,
                str(days),
                event_date,
                str(days),
                event_type,
                event_type,
                max(k * 20, 100),
            ),
        )
        rows = cur.fetchall() or []
        cid_set = set(cids)
        kept: list[int] = []
        for eid, art_id in rows:
            if art_id is None:
                continue
            for sch in schemas:
                if not sch:
                    continue
                try:
                    art_cids = set(article_durable_canonical_ids(conn, sch, int(art_id)))
                except Exception:
                    continue
                if art_cids & cid_set:
                    kept.append(int(eid))
                    break
            if len(kept) >= k:
                break
        return kept[:k]
    except Exception as e:
        logger.debug("prefilter_same_event_candidates(%s): %s", event_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return []
    finally:
        cur.close()


def membership_metadata(link_mode: str, **extra: Any) -> dict[str, Any]:
    """JSON-serializable metadata fragment for storyline_articles.metadata."""
    out: dict[str, Any] = {"link_mode": link_mode}
    out.update({k: v for k, v in extra.items() if v is not None})
    return out
