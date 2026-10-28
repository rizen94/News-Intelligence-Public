"""
Vault cluster discovery — form topic hubs from shared entities/tags/events.

Does NOT merge storyline_articles. Hubs are Obsidian index pages + registry metadata.
Hub-facet people alone never define a cluster (need durable non-hub glue).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.vault_note_contract import slugify_entity_name

logger = logging.getLogger(__name__)

# Minimum durable (non-hub) entity overlap to edge two episodes
ENTITY_JACCARD_MIN = 0.22
ENTITY_INTERSECTION_MIN = 2
# Soft boosts
TAG_BOOST = 0.12
EVENT_BOOST = 0.18
TOPIC_BOOST = 0.10
EDGE_SCORE_MIN = 0.28
MIN_CLUSTER_SIZE = 3
MAX_EPISODES = 400
MAX_HUBS_PER_PASS = 12
# Prefer geo/org/topic glue; person-only pairs are weak Situations
PREFERRED_ENTITY_TYPES = frozenset(
    {
        "location",
        "place",
        "geo",
        "country",
        "city",
        "region",
        "organization",
        "org",
        "institution",
        "company",
        "gpe",
        "facility",
        "event",
        "topic",
    }
)
PERSON_ENTITY_TYPES = frozenset(
    {"person", "per", "people", "politician", "individual"}
)


def _hub_name_set(domain_key: str) -> set[str]:
    names: set[str] = set()
    try:
        from services.domain_synthesis_config import get_domain_hub_facets

        for f in get_domain_hub_facets(domain_key):
            for n in f.names or []:
                if n:
                    names.add(str(n).strip().lower())
    except Exception:
        pass
    return names


def _jaccard(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / float(len(a | b))


def _load_episode_entity_sets(
    cur,
    schema: str,
    domain_key: str,
    *,
    limit: int = MAX_EPISODES,
) -> dict[int, dict[str, Any]]:
    """storyline_id → {durable_ids, all_ids, title, article_count}."""
    hub_names = _hub_name_set(domain_key)
    cur.execute(
        f"""
        SELECT s.id, COALESCE(s.title, ''), COALESCE(s.article_count, 0)::int
        FROM {schema}.storylines s
        WHERE s.status = 'active'
          AND COALESCE(s.article_count, 0) >= 2
        ORDER BY COALESCE(s.updated_at, s.created_at) DESC NULLS LAST
        LIMIT %s
        """,
        (int(limit),),
    )
    episodes = {
        int(r[0]): {
            "title": r[1] or "",
            "article_count": int(r[2] or 0),
            "durable_ids": set(),
            "all_ids": set(),
            "entity_names": {},
        }
        for r in (cur.fetchall() or [])
    }
    if not episodes:
        return {}

    ids = list(episodes.keys())
    # Prefer SEI when present
    try:
        cur.execute(
            f"""
            SELECT storyline_id, entity_id, COALESCE(entity_name, ''),
                   COALESCE(mention_count, 1)::int
            FROM {schema}.story_entity_index
            WHERE storyline_id = ANY(%s)
              AND entity_id IS NOT NULL
            """,
            (ids,),
        )
        sei_rows = cur.fetchall() or []
    except Exception:
        sei_rows = []
        try:
            cur.connection.rollback()
        except Exception:
            pass

    if sei_rows:
        for sid, eid, ename, _mc in sei_rows:
            sid_i, eid_i = int(sid), int(eid)
            if sid_i not in episodes:
                continue
            episodes[sid_i]["all_ids"].add(eid_i)
            episodes[sid_i]["entity_names"][eid_i] = ename or ""
            if (ename or "").strip().lower() not in hub_names:
                episodes[sid_i]["durable_ids"].add(eid_i)
    else:
        cur.execute(
            f"""
            SELECT sa.storyline_id, ae.canonical_entity_id,
                   COALESCE(ae.entity_name, ''), COUNT(*)::int
            FROM {schema}.storyline_articles sa
            JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
            WHERE sa.storyline_id = ANY(%s)
              AND ae.canonical_entity_id IS NOT NULL
            GROUP BY sa.storyline_id, ae.canonical_entity_id, ae.entity_name
            """,
            (ids,),
        )
        for sid, eid, ename, _c in cur.fetchall() or []:
            sid_i, eid_i = int(sid), int(eid)
            if sid_i not in episodes:
                continue
            episodes[sid_i]["all_ids"].add(eid_i)
            episodes[sid_i]["entity_names"][eid_i] = ename or ""
            if (ename or "").strip().lower() not in hub_names:
                episodes[sid_i]["durable_ids"].add(eid_i)

    # Annotate entity types for seed preference / person-pair rejection
    all_eids: set[int] = set()
    for ep in episodes.values():
        all_eids |= set(ep.get("durable_ids") or set())
    type_map: dict[int, str] = {}
    if all_eids:
        try:
            cur.execute(
                f"""
                SELECT id, lower(COALESCE(entity_type, ''))
                FROM {schema}.entity_canonical
                WHERE id = ANY(%s)
                """,
                (list(all_eids),),
            )
            type_map = {int(r[0]): (r[1] or "") for r in (cur.fetchall() or [])}
        except Exception:
            try:
                cur.connection.rollback()
            except Exception:
                pass
    for ep in episodes.values():
        ep["entity_types"] = {
            eid: type_map.get(eid, "") for eid in (ep.get("durable_ids") or set())
        }
        ep["preferred_ids"] = {
            eid
            for eid, t in (ep.get("entity_types") or {}).items()
            if t in PREFERRED_ENTITY_TYPES
        }

    return episodes


def _vault_tag_overlap(
    cur,
    domain_key: str,
    storyline_ids: list[int],
) -> dict[tuple[int, int], float]:
    """Pairs that share non-structural vault tags via storyline notes."""
    if len(storyline_ids) < 2:
        return {}
    try:
        cur.execute(
            """
            SELECT object_id, tags
            FROM intelligence.vault_notes
            WHERE domain_key = %s
              AND note_type = 'storyline'
              AND object_id = ANY(%s)
            """,
            (domain_key, storyline_ids),
        )
    except Exception:
        return {}
    tag_map: dict[int, set[str]] = {}
    for oid, tags in cur.fetchall() or []:
        clean = {
            str(t).lower()
            for t in (tags or [])
            if t
            and not str(t).startswith("domain/")
            and str(t) not in ("storyline", "entity", "preseed", "seed", "cluster")
        }
        if clean:
            tag_map[int(oid)] = clean
    boosts: dict[tuple[int, int], float] = {}
    keys = list(tag_map.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            inter = tag_map[a] & tag_map[b]
            if len(inter) >= 1:
                boosts[(min(a, b), max(a, b))] = TAG_BOOST * min(2.0, float(len(inter)))
    return boosts


def _shared_event_boost(
    cur,
    schema: str,
    storyline_ids: list[int],
) -> dict[tuple[int, int], float]:
    """Episodes sharing the same chronological event fingerprint."""
    boosts: dict[tuple[int, int], float] = {}
    sid_set = set(int(x) for x in storyline_ids)
    sid_strs = [str(x) for x in storyline_ids]
    try:
        cur.execute(
            """
            SELECT event_fingerprint, array_agg(DISTINCT storyline_id)
            FROM public.chronological_events
            WHERE storyline_id = ANY(%s)
              AND event_fingerprint IS NOT NULL
              AND length(event_fingerprint) > 8
            GROUP BY event_fingerprint
            HAVING COUNT(DISTINCT storyline_id) >= 2
            LIMIT 300
            """,
            (sid_strs,),
        )
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return boosts

    for _fp, arr in cur.fetchall() or []:
        members = []
        for raw in arr or []:
            try:
                sid = int(str(raw).strip())
            except (TypeError, ValueError):
                continue
            if sid in sid_set:
                members.append(sid)
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                key = (min(members[i], members[j]), max(members[i], members[j]))
                boosts[key] = max(boosts.get(key, 0.0), EVENT_BOOST)
    return boosts


def _topic_overlap_boost(
    cur,
    schema: str,
    storyline_ids: list[int],
) -> dict[tuple[int, int], float]:
    boosts: dict[tuple[int, int], float] = {}
    try:
        cur.execute(
            f"""
            SELECT sa.storyline_id, atc.cluster_id
            FROM {schema}.storyline_articles sa
            JOIN {schema}.article_topic_clusters atc ON atc.article_id = sa.article_id
            WHERE sa.storyline_id = ANY(%s)
            """,
            (storyline_ids,),
        )
    except Exception:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return boosts
    by_cluster: dict[Any, set[int]] = defaultdict(set)
    for sid, cid in cur.fetchall() or []:
        by_cluster[cid].add(int(sid))
    for members in by_cluster.values():
        mlist = list(members)
        if len(mlist) < 2:
            continue
        for i in range(len(mlist)):
            for j in range(i + 1, len(mlist)):
                key = (min(mlist[i], mlist[j]), max(mlist[i], mlist[j]))
                boosts[key] = max(boosts.get(key, 0.0), TOPIC_BOOST)
    return boosts


def _union_find_components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in edges:
        union(a, b)
    buckets: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        buckets[find(i)].append(i)
    return list(buckets.values())


def _title_from_entities(
    episodes: dict[int, dict[str, Any]],
    member_ids: list[int],
) -> tuple[str, str, list[int]]:
    counts: dict[int, int] = defaultdict(int)
    preferred_counts: dict[int, int] = defaultdict(int)
    names: dict[int, str] = {}
    types: dict[int, str] = {}
    for sid in member_ids:
        ep = episodes.get(sid) or {}
        for eid in ep.get("durable_ids") or set():
            counts[eid] += 1
            names[eid] = (ep.get("entity_names") or {}).get(eid) or names.get(eid) or f"e{eid}"
            et = (ep.get("entity_types") or {}).get(eid) or types.get(eid) or ""
            types[eid] = et
            if eid in (ep.get("preferred_ids") or set()) or et in PREFERRED_ENTITY_TYPES:
                preferred_counts[eid] += 1
    # Prefer geo/org seeds for title; fall back to durable counts
    rank_src = preferred_counts if preferred_counts else counts
    top = sorted(rank_src.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    if len(top) < 2 and counts:
        for eid, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            if eid not in {t[0] for t in top}:
                top.append((eid, c))
            if len(top) >= 2:
                break
    seed_ids = [eid for eid, _ in top]
    label_parts = [names[eid] for eid in seed_ids if names.get(eid)]
    if not label_parts:
        label_parts = [f"Cluster {member_ids[0]}"]
    title = " / ".join(label_parts[:2]) + " (situation)"
    key = slugify_entity_name("_".join(label_parts[:2]) or f"cluster-{member_ids[0]}")
    return title, key, seed_ids


def _is_person_only_seeds(
    episodes: dict[int, dict[str, Any]],
    seed_ids: list[int],
    member_ids: list[int],
) -> bool:
    """True when top seeds are all people and no preferred durable glue in members."""
    if not seed_ids:
        return True
    types: dict[int, str] = {}
    preferred: set[int] = set()
    for sid in member_ids:
        ep = episodes.get(sid) or {}
        types.update(ep.get("entity_types") or {})
        preferred |= set(ep.get("preferred_ids") or set())
    if preferred:
        return False
    seed_types = [types.get(eid, "") for eid in seed_ids]
    if not seed_types:
        return True
    return all(t in PERSON_ENTITY_TYPES or t == "" for t in seed_types) and any(
        t in PERSON_ENTITY_TYPES for t in seed_types
    )


def discover_and_upsert_cluster_hubs(
    *,
    domain_key: str,
    force: bool = False,
    dry_run: bool = False,
    max_episodes: int = MAX_EPISODES,
) -> dict[str, Any]:
    from services.vault_cluster_hub_service import (
        list_cluster_hubs,
        vault_cluster_hubs_enabled,
        write_cluster_hub,
    )

    if not vault_cluster_hubs_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled"}

    schema = resolve_domain_schema(domain_key)
    stats: dict[str, Any] = {
        "ok": True,
        "domain_key": domain_key,
        "episodes": 0,
        "edges": 0,
        "candidates": 0,
        "upserted": [],
        "merged_into": [],
    }

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            episodes = _load_episode_entity_sets(
                cur, schema, domain_key, limit=max_episodes
            )
            stats["episodes"] = len(episodes)
            if len(episodes) < MIN_CLUSTER_SIZE:
                return stats

            sid_list = list(episodes.keys())
            index = {sid: i for i, sid in enumerate(sid_list)}
            tag_boosts = _vault_tag_overlap(cur, domain_key, sid_list)
            event_boosts = _shared_event_boost(cur, schema, sid_list)
            topic_boosts = _topic_overlap_boost(cur, schema, sid_list)

            edges: list[tuple[int, int]] = []
            for i in range(len(sid_list)):
                a = sid_list[i]
                da = episodes[a]["durable_ids"]
                if len(da) < ENTITY_INTERSECTION_MIN:
                    continue
                for j in range(i + 1, len(sid_list)):
                    b = sid_list[j]
                    db = episodes[b]["durable_ids"]
                    inter = len(da & db)
                    if inter < ENTITY_INTERSECTION_MIN:
                        continue
                    jac = _jaccard(da, db)
                    if jac < ENTITY_JACCARD_MIN and inter < 4:
                        continue
                    pair = (min(a, b), max(a, b))
                    score = jac + tag_boosts.get(pair, 0.0)
                    score += event_boosts.get(pair, 0.0)
                    score += topic_boosts.get(pair, 0.0)
                    if score >= EDGE_SCORE_MIN or inter >= 4:
                        edges.append((index[a], index[b]))
            stats["edges"] = len(edges)
            components = _union_find_components(len(sid_list), edges)

    # Rank components by size × durable density (+ preferred seed boost)
    scored_components: list[tuple[float, list[int]]] = []
    for comp in components:
        if len(comp) < MIN_CLUSTER_SIZE:
            continue
        members = [sid_list[i] for i in comp]
        durable_union: set[int] = set()
        preferred_union: set[int] = set()
        for sid in members:
            durable_union |= episodes[sid]["durable_ids"]
            preferred_union |= set(episodes[sid].get("preferred_ids") or set())
        if len(durable_union) < ENTITY_INTERSECTION_MIN:
            continue
        # Event-linked pairs among members
        event_hits = 0
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                pair = (min(members[i], members[j]), max(members[i], members[j]))
                if event_boosts.get(pair):
                    event_hits += 1
        score = float(len(members)) * (1.0 + 0.1 * len(durable_union))
        score += 2.0 * len(preferred_union)
        score += 1.5 * event_hits
        scored_components.append((score, members))
    scored_components.sort(key=lambda x: -x[0])
    stats["candidates"] = len(scored_components)

    existing = list_cluster_hubs(domain_key=domain_key, limit=100)

    for _, members in scored_components[:MAX_HUBS_PER_PASS]:
        title, cluster_key, seed_ids = _title_from_entities(episodes, members)
        from services.vault_quality_gates import is_junk_title

        if is_junk_title(title):
            stats.setdefault("skipped_junk_title", 0)
            stats["skipped_junk_title"] += 1
            continue
        # Merge into existing hub if high seed/member overlap
        merge_hub = None
        member_set = set(members)
        for h in existing:
            exist_members = set(int(x) for x in (h.get("member_storyline_ids") or []))
            exist_seeds = set(int(x) for x in (h.get("seed_entity_ids") or []))
            mem_overlap = len(member_set & exist_members) / max(
                1.0, float(min(len(member_set), len(exist_members) or 1))
            )
            seed_overlap = (
                len(set(seed_ids) & exist_seeds) / max(1.0, float(len(seed_ids)))
                if seed_ids
                else 0.0
            )
            # Prefer merge into existing Situations (slightly looser than before)
            if mem_overlap >= 0.3 or seed_overlap >= 0.4:
                merge_hub = h
                break

        if merge_hub is None and _is_person_only_seeds(episodes, seed_ids, members):
            # Skip noisy person-pair Situations unless event-glued
            event_glued = False
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    pair = (min(members[i], members[j]), max(members[i], members[j]))
                    if event_boosts.get(pair):
                        event_glued = True
                        break
                if event_glued:
                    break
            if not event_glued:
                stats.setdefault("skipped_person_only", 0)
                stats["skipped_person_only"] = int(stats["skipped_person_only"]) + 1
                continue

        if merge_hub:
            merged_members = sorted(
                set(int(x) for x in (merge_hub.get("member_storyline_ids") or []))
                | member_set
            )
            merged_seeds = sorted(
                set(int(x) for x in (merge_hub.get("seed_entity_ids") or []))
                | set(seed_ids)
            )
            cluster_key = str(
                (merge_hub.get("metadata") or {}).get("cluster_key")
                or merge_hub.get("cluster_key")
                or cluster_key
            )
            title = merge_hub.get("title") or title
            vault_path = merge_hub.get("vault_path")
            stats["merged_into"].append(cluster_key)
        else:
            merged_members = sorted(members)
            merged_seeds = seed_ids
            vault_path = None

        if dry_run:
            stats["upserted"].append(
                {
                    "dry_run": True,
                    "cluster_key": cluster_key,
                    "title": title,
                    "member_count": len(merged_members),
                }
            )
            continue

        try:
            r = write_cluster_hub(
                domain_key=domain_key,
                cluster_key=cluster_key,
                title=title,
                member_storyline_ids=merged_members,
                seed_entity_ids=merged_seeds,
                vault_path=vault_path,
                force=force,
            )
            stats["upserted"].append(r)
        except Exception as e:
            logger.warning("cluster hub upsert %s: %s", cluster_key, e)

    return stats


def run_cluster_hub_discovery_cycle(
    *,
    domain_keys: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    from shared.domain_registry import get_pipeline_active_domain_keys

    domains = domain_keys or list(get_pipeline_active_domain_keys())
    out: dict[str, Any] = {"ok": True, "domains": {}}
    for dk in domains:
        try:
            out["domains"][dk] = discover_and_upsert_cluster_hubs(domain_key=dk, force=force)
        except Exception as e:
            logger.warning("cluster discovery %s: %s", dk, e)
            out["domains"][dk] = {"ok": False, "error": str(e)}
    # Always refresh known hubs (timeline rebuild)
    try:
        from services.vault_cluster_hub_service import refresh_all_cluster_hubs

        out["refresh"] = refresh_all_cluster_hubs(force=force)
    except Exception as e:
        out["refresh"] = {"ok": False, "error": str(e)}
    # Situation briefs for hubs whose evidence fingerprint drifted
    try:
        from services.vault_hub_brief_service import refresh_stale_hub_briefs

        out["briefs"] = refresh_stale_hub_briefs(force=force)
    except Exception as e:
        out["briefs"] = {"ok": False, "error": str(e)}
    return out
