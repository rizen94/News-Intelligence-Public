"""
Story Continuation Service for News Intelligence v5.0 (Phase 3)

When new events are extracted, this service matches them to existing
long-running storylines -- even if the last related article was months ago.

Matching strategy:
1. Entity lookup in story_entity_index (no time window)
2. Event type compatibility filter
3. LLM context verification for top candidates
4. Automatic or flagged linking based on confidence

Also manages storyline lifecycle transitions:
  active -> dormant -> watching -> concluded -> archived

Integration Point: Processes events from `chronological_events` table and links them
to existing storylines in the database. Updates `storyline_id` field for downstream
processing by other phases.

Error Handling:
- Database connection issues trigger retry mechanisms
- LLM context verification failures are logged and skipped
- Invalid storyline data is logged and skipped
- Entity lookup failures are logged and events proceed to next phase

Monitoring:
- Storyline linking accuracy
- LLM verification confidence scores
- Processing time per event
- Storyline transition rates
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from config.runtime import env_int
from shared.pg_savepoint import execute_with_savepoint
from shared.services.llm_service import LLMService, ModelType
from shared.story_entity_index import map_entity_type_for_sei

logger = logging.getLogger(__name__)

EVENT_TYPE_COMPATIBILITY = {
    "legal_action": {"court_ruling", "arrest", "investigation", "legal_action", "legislation"},
    "court_ruling": {"legal_action", "arrest", "investigation", "court_ruling"},
    "arrest": {"legal_action", "court_ruling", "investigation", "arrest"},
    "investigation": {"legal_action", "court_ruling", "arrest", "investigation", "report_release"},
    "policy_decision": {"legislation", "policy_decision", "public_statement", "meeting"},
    "legislation": {"policy_decision", "legislation", "public_statement", "meeting"},
    "election": {"election", "appointment", "resignation", "public_statement"},
        "conflict": {
            "conflict",
            "military_action",
            "agreement",
            "protest",
            "public_statement",
            "death",
            "diplomatic",
        },
        "military_action": {"conflict", "military_action", "diplomatic", "protest"},
        "diplomatic": {"diplomatic", "conflict", "agreement", "meeting", "policy_decision"},
    "protest": {"protest", "conflict", "public_statement", "arrest"},
    "agreement": {"agreement", "conflict", "meeting", "policy_decision"},
    "economic_event": {"economic_event", "policy_decision", "report_release"},
    "appointment": {"appointment", "resignation", "election"},
    "resignation": {"resignation", "appointment", "investigation"},
}

STORY_VERIFICATION_PROMPT = """You are a senior news analyst. Determine whether a new event belongs to an existing storyline.

Existing storyline: "{storyline_title}"
Summary: {storyline_summary}

Recent events in this storyline (chronological):
{recent_events}

Core entities: {core_entities}

---

New event: "{event_title}" on {event_date}
Key actors: {event_actors}
Description: {event_description}

---

Question: Is this new event part of the same ongoing story?
Answer with ONLY a JSON object:
{{
    "verdict": "YES" or "NO" or "MAYBE",
    "confidence": <float 0.0-1.0>,
    "reasoning": "<one sentence>"
}}"""

DORMANT_DAYS = 30
AUTO_LINK_THRESHOLD = 0.8
REVIEW_THRESHOLD = 0.5

# Cap on how many of the source article's entities feed candidate lookup.
ARTICLE_ENTITY_SIGNAL_LIMIT = 60


def _min_entity_overlap() -> int:
    return max(1, min(5, env_int("CONTINUATION_MIN_ENTITY_OVERLAP", 2)))


def _rare_entity_max_storylines() -> int:
    """A matched entity in <= this many storylines is distinctive enough to admit alone."""
    return max(0, min(10, env_int("CONTINUATION_RARE_ENTITY_MAX_STORYLINES", 2)))


def _candidate_limit() -> int:
    return max(1, min(50, env_int("CONTINUATION_CANDIDATE_LIMIT", 10)))


def _recheck_base_hours() -> float:
    """First recheck delay for an event that found no storyline; doubles per attempt."""
    return max(0.0, float(env_int("CONTINUATION_RECHECK_BASE_HOURS", 2)))


def _recheck_max_doublings() -> int:
    """Caps the backoff: base * 2**doublings (default 2h * 2**6 = ~5.3 days)."""
    return max(0, min(12, env_int("CONTINUATION_RECHECK_MAX_DOUBLINGS", 6)))


def continuation_recheck_due_sql(alias: str = "ce") -> tuple[str, tuple[float, int]]:
    """
    SQL predicate (plus params) selecting events due for another continuation attempt.

    Shared with the idle probe so "has work" and "will process" agree; otherwise the
    phase reports work every cycle and drains nothing.
    """
    sql = f"""(
        {alias}.continuation_checked_at IS NULL
        OR {alias}.continuation_checked_at < NOW() - (
            INTERVAL '1 hour' * %s::double precision
            * POWER(2, LEAST(GREATEST({alias}.continuation_attempts, 1) - 1, %s::int))
        )
    )"""
    return sql, (_recheck_base_hours(), _recheck_max_doublings())


def _hub_entity_count() -> int:
    """Storylines indexing more entities than this are 'hubs' and match almost anything.

    Overbroad storylines (catch-all clusters) otherwise absorb every new event, so
    they must clear a higher bar than a focused storyline.
    """
    return max(10, env_int("CONTINUATION_HUB_ENTITY_COUNT", 150))


class StoryContinuationService:
    """Matches new events to existing storylines across unbounded time windows."""

    def __init__(self, conn, llm: LLMService | None = None, schema: str | None = None):
        self.conn = conn
        self.llm = llm or LLMService()
        # When set (e.g. 'politics', 'finance', 'science_tech'), search_path is set and storyline_id stored as "schema:id"
        self.schema = schema

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def match_event_to_storyline(self, event_id: int) -> dict[str, Any] | None:
        """
        Attempt to match a single event to an existing storyline.

        Returns a dict with match info if found, else None.
        Prefers cluster-root events when resolving temporal/entity features.
        """
        event = self._load_event(event_id)
        if not event:
            return None

        # Prefer cluster root for scoring dates / continuity
        try:
            from services.event_coreference_service import resolve_cluster_root

            root_id = resolve_cluster_root(self.conn, int(event_id))
            if root_id != int(event_id):
                root_event = self._load_event(root_id)
                if root_event:
                    # Keep member id for linking; borrow root date/source_count cues
                    event["cluster_root_id"] = root_id
                    event["actual_event_date"] = (
                        root_event.get("actual_event_date") or event.get("actual_event_date")
                    )
        except Exception:
            pass

        actor_names = self._extract_names(event["key_actors"])
        entity_names = self._extract_names(event["entities"])
        # LLM actors are often descriptive prose ("city authorities"); the source
        # article's extracted entities are the same vocabulary story_entity_index
        # was built from, so they carry the real matching signal.
        article_names, canonical_ids = self._article_entity_signals(event.get("source_article_id"))
        all_names = list({*actor_names, *entity_names, *article_names})

        # Step 1a: Mode B signature candidacy (SSOT when episode assembly on)
        sig_candidates = self._find_candidates_by_signature(event)

        # Step 1b: entity lookup (no time constraint)
        entity_candidates = self._find_candidates_by_entities(
            all_names, event["id"], canonical_ids=canonical_ids
        )
        # Hub facets alone must not candidacy — require non-hub signal
        entity_candidates = [
            c for c in entity_candidates if self._candidate_has_non_hub_admit(c)
        ]

        # Merge: signature hits first, then entity (dedupe by storyline_id)
        by_id: dict[int, dict] = {}
        for c in sig_candidates + entity_candidates:
            sid = int(c["storyline_id"])
            if sid not in by_id:
                by_id[sid] = c
            elif c.get("signature_match") and not by_id[sid].get("signature_match"):
                by_id[sid] = c
        candidates = list(by_id.values())
        if not candidates:
            founded = self._maybe_found_new_episode(event)
            if founded:
                return founded
            return None

        # Step 2: event type compatibility
        candidates = self._filter_by_event_type(candidates, event["event_type"])
        if not candidates:
            return None

        # Step 2b: pre-LLM rank with blend_link_score (temporal + entity)
        candidates = self._rank_candidates_with_blend(candidates, event)
        # Strong Mode B identity hits must not be wiped by cold temporal proximity —
        # ranking recomputes blend_score and previously erased the candidacy floor.
        for c in candidates:
            if (
                c.get("signature_match")
                and c.get("signature_reason") == "identity_match"
                and int(c.get("entity_overlap") or len(c.get("matched_entities") or []) or 0)
                >= 2
            ):
                c["blend_score"] = max(float(c.get("blend_score") or 0.0), 0.80)
            elif c.get("signature_match") and float(c.get("blend_score") or 0.0) < 0.76:
                c["blend_score"] = max(float(c.get("blend_score") or 0.0), 0.76)

        # Real similarity floor before LLM (LLM is verify-only)
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config
            from shared.domain_registry import schema_to_primary_domain_key

            dk = schema_to_primary_domain_key(self.schema or "politics")
            floor = float(
                get_domain_synthesis_config(dk).link_score_profile.auto_approve_combined
            )
        except Exception:
            floor = 0.75
        candidates = [
            c for c in candidates if float(c.get("blend_score") or 0.0) >= floor
        ]
        if not candidates:
            return None

        # Step 3: Mode B identity auto-link — need real overlap, not one-token magnets.
        # Wide signatures (magnet risk) require ≥3 matched identity anchors.
        for cand in candidates[:5]:
            matched_n = len(cand.get("matched_entities") or [])
            sig_width = int(cand.get("index_size") or 0)
            need_n = 3 if sig_width > 6 else 2
            if (
                cand.get("signature_match")
                and cand.get("signature_reason") == "identity_match"
                and matched_n >= need_n
            ):
                best_match = {
                    **cand,
                    "auto_linked": True,
                    "confidence": float(cand.get("blend_score") or 0.85),
                    "reasoning": (
                        f"mode_b:{cand.get('signature_reason')}:n={matched_n}:need={need_n}"
                    ),
                }
                if self._link_event(event, best_match):
                    try:
                        self._maybe_causal_from_continuation(event, best_match)
                    except Exception:
                        pass
                    return best_match
                logger.info(
                    "continuation signature link rejected storyline=%s event=%s — trying next",
                    best_match.get("storyline_id"),
                    event.get("id"),
                )
                continue
            best_match = await self._verify_candidates([cand], event)
            if not best_match:
                continue
            if best_match.get("auto_linked"):
                # LLM must not auto-admit one-token / magnet-thin signature hits.
                if (
                    cand.get("signature_match")
                    and cand.get("signature_reason") == "identity_match"
                    and matched_n < need_n
                ):
                    best_match["auto_linked"] = False
                    best_match["reasoning"] = (
                        f"{best_match.get('reasoning') or ''};"
                        f"magnet_guard:matched={matched_n}<{need_n}"
                    ).strip(";")
                    logger.info(
                        "continuation magnet_guard storyline=%s event=%s matched=%s need=%s",
                        cand.get("storyline_id"),
                        event.get("id"),
                        matched_n,
                        need_n,
                    )
                elif self._link_event(event, best_match):
                    try:
                        self._maybe_causal_from_continuation(event, best_match)
                    except Exception:
                        pass
                    return best_match
                else:
                    logger.info(
                        "continuation link rejected storyline=%s event=%s — trying next",
                        best_match.get("storyline_id"),
                        event.get("id"),
                    )
                    continue
            if not best_match.get("auto_linked"):
                logger.info(
                    "continuation flagged (no membership) storyline=%s conf=%s blend=%s",
                    best_match.get("storyline_id"),
                    best_match.get("confidence"),
                    best_match.get("blend_score"),
                )
                return {**best_match, "membership_skipped": True, "reason": "llm_flagged"}

        # Step 4: founding — no matching episode, but event has identity anchors
        founded = self._maybe_found_new_episode(event)
        if founded:
            return founded
        return None

    def _maybe_found_new_episode(self, event: dict) -> dict | None:
        """Create a thin signed episode when an event has identity but no match."""
        try:
            from config.runtime import env_bool, env_int
            from shared.domain_registry import schema_to_primary_domain_key
            from shared.episode_attach_gate import (
                classify_event_anchors,
                episode_container_assembly_enabled,
                insert_event_episode_link,
                lock_episode_signature,
            )
        except Exception:
            return None
        if not episode_container_assembly_enabled():
            return None
        # Default OFF: unmatched events must stay events. Founding-as-escape-hatch
        # minted ~1 episode per orphan CE (politics: hundreds/day, almost none grew).
        if not env_bool("CONTINUATION_FOUNDING_ENABLED", False):
            return None
        if getattr(self, "_founding_paused", False):
            return None
        schema = self.schema or "public"
        dk = schema_to_primary_domain_key(schema)
        if not dk:
            return None
        anchors = classify_event_anchors(
            self.conn,
            domain_key=dk,
            schema=schema,
            event_id=int(event["id"]),
            article_id=int(event["source_article_id"])
            if event.get("source_article_id") is not None
            else None,
        )
        min_identity = max(1, env_int("CONTINUATION_FOUNDING_MIN_IDENTITY", 3))
        identity = list(anchors.get("identity") or [])[:8]
        supporting = list(anchors.get("supporting") or [])[:8]

        def _junk_identity(tok: str) -> bool:
            tl = str(tok or "").strip().lower()
            if len(tl) < 3:
                return True
            if "no mention" in tl or "full name" in tl or "unknown" == tl:
                return True
            if tl.startswith("@") and len(tl) < 12:
                return True
            return False

        identity = [t for t in identity if not _junk_identity(t)]
        if len(identity) < min_identity:
            return None
        # Prefer named (non-cid) identity — pure cid pairs spawn orphan spam.
        min_named = max(0, env_int("CONTINUATION_FOUNDING_MIN_NAMED", 2))
        named = [t for t in identity if not str(t).startswith("cid:")]
        if len(named) < min_named:
            logger.debug(
                "continuation founding skip cid-only identity event=%s identity=%s",
                event.get("id"),
                identity[:4],
            )
            return None
        title = (event.get("title") or "Untitled episode").strip()[:240]
        # Reject topic-keyword stubs ("appointment", "market rally") — need a real headline.
        title_words = [w for w in title.replace("—", " ").replace("-", " ").split() if w]
        min_title_words = max(2, env_int("CONTINUATION_FOUNDING_MIN_TITLE_WORDS", 6))
        if len(title_words) < min_title_words:
            logger.debug(
                "continuation founding skip weak title event=%s title=%s",
                event.get("id"),
                title[:60],
            )
            return None
        cursor = self.conn.cursor()
        try:
            import json as _json

            meta = _json.dumps(
                {
                    "source": "story_continuation_founding",
                    "founding_event_id": int(event["id"]),
                }
            )
            cursor.execute(
                f"""
                INSERT INTO {schema}.storylines
                (storyline_uuid, title, description, status, processing_status,
                 article_count, total_articles, metadata, created_at, updated_at,
                 episode_state, story_kind)
                VALUES (
                    gen_random_uuid(), %s, %s, 'active', 'pending',
                    0, 0, %s::jsonb, NOW(), NOW(),
                    'forming', NULL
                )
                RETURNING id
                """,
                (
                    title,
                    (event.get("description") or "")[:2000] or None,
                    meta,
                ),
            )
            sid = int((cursor.fetchone() or (None,))[0])
            if not sid:
                self.conn.rollback()
                return None
            lock_episode_signature(
                cursor,
                schema,
                sid,
                {"identity": identity, "supporting": supporting},
            )
            insert_event_episode_link(
                cursor,
                event_id=int(event["id"]),
                domain_key=dk,
                episode_id=sid,
                link_type="founding",
                matched_anchors=identity[:8],
                inference_stage="established",
                blend_rank=0.9,
                added_by="story_continuation_founding",
                metadata={"gate_reason": "founding_identity"},
            )
            cursor.execute(
                """
                UPDATE public.chronological_events
                SET storyline_id = %s::text
                WHERE id = %s
                """,
                (str(sid), int(event["id"])),
            )
            aid = event.get("source_article_id")
            if aid is not None:
                from shared.membership_store import insert_derived_bag_row

                insert_derived_bag_row(
                    cursor,
                    schema=schema,
                    storyline_id=int(sid),
                    article_id=int(aid),
                    relevance_score=0.9,
                    added_by="story_continuation",
                    metadata={"derived_from": "founding_identity"},
                )
            cursor.execute(
                f"""
                UPDATE {schema}.storylines
                SET episode_state = 'active', updated_at = NOW()
                WHERE id = %s
                """,
                (sid,),
            )
            self.conn.commit()
            logger.info(
                "continuation founded episode=%s from event=%s identity=%s",
                sid,
                event["id"],
                identity[:4],
            )
            return {
                "storyline_id": sid,
                "title": title,
                "auto_linked": True,
                "confidence": 0.9,
                "blend_score": 0.9,
                "founded": True,
                "matched_entities": identity[:8],
                "reasoning": "mode_b:founding_identity",
            }
        except Exception as e:
            logger.warning("continuation founding failed event=%s: %s", event.get("id"), e)
            try:
                self.conn.rollback()
            except Exception:
                pass
            return None
        finally:
            cursor.close()

    def _candidate_has_non_hub_admit(self, cand: dict) -> bool:
        """True when matched entities include enough non-hub names (hubs alone never admit)."""
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config
            from shared.domain_registry import schema_to_primary_domain_key

            dk = schema_to_primary_domain_key(self.schema or "politics")
            cfg = get_domain_synthesis_config(dk)
            need = max(1, int(cfg.membership_min_shared_non_hub()))
        except Exception:
            need = 2
            cfg = None
        matched = cand.get("matched_entities") or []
        if isinstance(matched, str):
            matched = [matched]
        if cfg is None:
            return len([m for m in matched if m]) >= need
        non_hub = [
            m for m in matched if m and not cfg.is_hub_entity_name(str(m))
        ]
        # Bare cid tokens without a resolved name are weak alone — need ≥2
        named_non_hub = [m for m in non_hub if not str(m).lower().startswith("cid:")]
        if len(named_non_hub) >= need:
            return True
        if len(non_hub) >= max(2, need):
            return True
        return False

    def _rank_candidates_with_blend(self, candidates: list[dict], event: dict) -> list[dict]:
        """Re-order candidates by blend_link_score before LLM gate."""
        try:
            from services.domain_synthesis_config import (
                get_domain_synthesis_config,
                temporal_proximity_score,
            )
            from services.embedding_link_candidate_service import blend_link_score, days_apart
        except Exception:
            return candidates

        domain_key = self.schema or "politics"
        try:
            half = get_domain_synthesis_config(domain_key).link_score_profile.temporal_half_life_days
        except Exception:
            half = 14.0

        event_date = event.get("actual_event_date")
        ranked: list[tuple[float, dict]] = []
        cursor = self.conn.cursor()
        try:
            for cand in candidates:
                sid = cand["storyline_id"]
                # Entity overlap as Jaccard proxy
                matched = cand.get("matched_entities") or []
                overlap_n = int(cand.get("entity_overlap") or len(matched) or 0)
                canonical_n = int(cand.get("canonical_overlap") or 0)
                # Identity-resolved matches are worth more than raw name hits.
                effective_n = overlap_n + canonical_n
                # Approximate: overlap / (overlap + 2) as soft jaccard
                ent_j = float(effective_n) / float(effective_n + 2) if effective_n else 0.0
                # Damp broad storylines: a hit inside a 400-entity index is weak evidence.
                index_size = int(cand.get("index_size") or 0)
                hub_cut = _hub_entity_count()
                if index_size > hub_cut:
                    ent_j *= (float(hub_cut) / float(index_size)) ** 0.5
                # Storyline last event date
                cursor.execute(
                    """
                    SELECT MAX(actual_event_date)
                    FROM chronological_events
                    WHERE storyline_id = %s::text AND canonical_event_id IS NULL
                    """,
                    (sid,),
                )
                row = cursor.fetchone()
                sl_date = row[0] if row else None
                gap = days_apart(event_date, sl_date)
                temp_p = temporal_proximity_score(gap, half_life_days=half)
                # Cold temporal must not erase strong multi-entity Mode B evidence
                # (long-running dockets / arcs spanning weeks).
                if effective_n >= 2 and float(temp_p) < 0.55:
                    temp_p = 0.55
                # Semantic proxy from entity overlap strength
                sem = min(1.0, 0.45 + 0.15 * effective_n)
                causal_b = 0.0
                try:
                    from services.causal_edges_service import has_causal_edge_between

                    # Prefer cluster-root event id when available for continuity cues.
                    _eid = int(event.get("cluster_root_id") or event.get("id") or 0)
                    if _eid and sid is not None:
                        if has_causal_edge_between(
                            "chronological_event",
                            _eid,
                            "storyline",
                            int(sid),
                            domain_key=domain_key,
                        ) or has_causal_edge_between(
                            "storyline",
                            int(sid),
                            "chronological_event",
                            _eid,
                            domain_key=domain_key,
                        ):
                            causal_b = 1.0
                except Exception:
                    causal_b = 0.0
                score = blend_link_score(
                    semantic=sem,
                    entity_jaccard=ent_j,
                    temporal_proximity=temp_p,
                    domain_key=domain_key,
                    causal_boost=causal_b,
                )
                cand["blend_score"] = score
                cand["temporal_proximity"] = temp_p
                cand["causal_boost"] = causal_b
                ranked.append((score, cand))
        finally:
            cursor.close()
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in ranked]

    def _maybe_causal_from_continuation(self, event: dict, match: dict) -> None:
        """Phase 3b: upsert causal edge when continuation links event to storyline with prior events."""
        from services.causal_edges_service import upsert_causal_edge

        sid = match.get("storyline_id")
        eid = int(event["id"])
        if sid is None:
            return
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id FROM chronological_events
                WHERE storyline_id = %s::text
                  AND id != %s
                  AND canonical_event_id IS NULL
                ORDER BY actual_event_date ASC NULLS LAST
                LIMIT 1
                """,
                (sid, eid),
            )
            prior = cursor.fetchone()
            if not prior:
                return
            conf = float(match.get("confidence") or match.get("blend_score") or 0.65)
            grade = "moderate" if conf >= 0.7 else "weak"
            domain_key = self.schema
            upsert_causal_edge(
                cause_kind="chronological_event",
                cause_id=int(prior[0]),
                effect_kind="chronological_event",
                effect_id=eid,
                relation="contributes_to",
                confidence=max(0.4, min(0.95, conf)),
                evidence_grade=grade,
                domain_key=domain_key,
                source="story_continuation",
                reasoning_steps=[
                    {
                        "action": "story_continuation_link",
                        "storyline_id": sid,
                        "event_id": eid,
                    }
                ],
            )
        finally:
            cursor.close()

    async def process_recent_events(self, limit: int = 30) -> dict[str, int]:
        """Batch-match unlinked events to storylines. Uses story_entity_index and storylines in current search_path."""
        # Events that found no storyline back off exponentially, so a cycle spends its
        # budget on fresh events instead of re-verifying the same unmatchable ones.
        # Hard-merged members (canonical_event_id set) inherit from the root — they are
        # not independent continuation work.
        due_sql, backoff_params = continuation_recheck_due_sql("ce")
        cursor = self.conn.cursor()
        try:
            if self.schema:
                cursor.execute("SET search_path TO %s, public", (self.schema,))
            # chronological_events is global — only take rows whose source article
            # lives in this schema, otherwise we re-check the same events once
            # per domain with the wrong story_entity_index.
            if self.schema:
                cursor.execute(
                    f"""
                    SELECT ce.id
                    FROM public.chronological_events ce
                    WHERE (ce.storyline_id = '' OR ce.storyline_id IS NULL)
                      AND ce.canonical_event_id IS NULL
                      AND ce.source_article_id IS NOT NULL
                      AND {due_sql}
                      AND EXISTS (
                            SELECT 1 FROM {self.schema}.articles a
                            WHERE a.id = ce.source_article_id
                      )
                    ORDER BY ce.continuation_checked_at ASC NULLS FIRST,
                             ce.extraction_timestamp DESC NULLS LAST, ce.id DESC
                    LIMIT %s
                    """,
                    (*backoff_params, limit),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT ce.id FROM public.chronological_events ce
                    WHERE (ce.storyline_id = '' OR ce.storyline_id IS NULL)
                      AND ce.canonical_event_id IS NULL
                      AND {due_sql}
                    ORDER BY ce.continuation_checked_at ASC NULLS FIRST,
                             ce.extraction_timestamp DESC NULLS LAST, ce.id DESC
                    LIMIT %s
                    """,
                    (*backoff_params, limit),
                )
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning(
                "Story continuation: failed to list unlinked events (check search_path / schema): %s",
                e,
            )
            cursor.close()
            return {"checked": 0, "linked": 0, "flagged": 0, "backed_off": 0, "inherited": 0}
        finally:
            cursor.close()

        inherited = self._inherit_storyline_from_roots(limit=max(limit, 50))

        try:
            from config.runtime import env_int

            founding_cap = max(0, env_int("CONTINUATION_FOUNDING_MAX_PER_BATCH", 1))
        except Exception:
            founding_cap = 1

        stats = {
            "checked": 0,
            "linked": 0,
            "flagged": 0,
            "backed_off": 0,
            "founded": 0,
            "inherited": inherited,
        }
        unmatched: list[int] = []
        founding_remaining = founding_cap

        def _flush() -> None:
            if not unmatched:
                return
            self._record_continuation_attempts(unmatched)
            stats["backed_off"] += len(unmatched)
            unmatched.clear()

        for (eid,) in rows:
            stats["checked"] += 1
            # Soft-disable founding for the rest of this batch once the cap is hit.
            if founding_remaining <= 0 and not getattr(self, "_founding_paused", False):
                self._founding_paused = True
            result = await self.match_event_to_storyline(eid)
            if result:
                if result.get("founded"):
                    stats["founded"] += 1
                    stats["linked"] += 1
                    founding_remaining = max(0, founding_remaining - 1)
                    continue
                if result.get("auto_linked"):
                    stats["linked"] += 1
                    continue
                stats["flagged"] += 1
            unmatched.append(eid)
            # Flush periodically: a batch cut short by the run budget must still
            # persist backoff, else the next cycle re-checks the same events.
            if len(unmatched) >= 25:
                _flush()
        _flush()
        if getattr(self, "_founding_paused", False):
            self._founding_paused = False
        return stats

    def _inherit_storyline_from_roots(self, limit: int = 100) -> int:
        """Copy storyline_id onto hard/soft members whose cluster root is already linked."""
        cursor = self.conn.cursor()
        inherited = 0
        try:
            cursor.execute(
                """
                WITH targets AS (
                    SELECT m.id, r.storyline_id AS sid
                    FROM public.chronological_events m
                    JOIN public.chronological_events r ON r.id = m.canonical_event_id
                    WHERE (m.storyline_id IS NULL OR m.storyline_id = '')
                      AND r.storyline_id IS NOT NULL
                      AND r.storyline_id <> ''
                    ORDER BY m.id DESC
                    LIMIT %s
                )
                UPDATE public.chronological_events m
                SET storyline_id = t.sid
                FROM targets t
                WHERE m.id = t.id
                """,
                (limit,),
            )
            inherited += cursor.rowcount or 0
            cursor.execute(
                """
                WITH targets AS (
                    SELECT m.id, r.storyline_id AS sid
                    FROM public.chronological_events m
                    JOIN public.chronological_events r ON r.id = m.event_cluster_id
                    WHERE m.canonical_event_id IS NULL
                      AND m.id <> r.id
                      AND (m.storyline_id IS NULL OR m.storyline_id = '')
                      AND r.storyline_id IS NOT NULL
                      AND r.storyline_id <> ''
                    ORDER BY m.id DESC
                    LIMIT %s
                )
                UPDATE public.chronological_events m
                SET storyline_id = t.sid
                FROM targets t
                WHERE m.id = t.id
                """,
                (limit,),
            )
            inherited += cursor.rowcount or 0
            self.conn.commit()
            if inherited:
                logger.info(
                    "Story continuation: inherited storyline on %s cluster members",
                    inherited,
                )
        except Exception as e:
            logger.warning("Story continuation: inherit from roots failed: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass
            return 0
        finally:
            cursor.close()
        return inherited

    def _record_continuation_attempts(self, event_ids: list[int]) -> None:
        """Bump the recheck counter for events that did not auto-link this round."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE public.chronological_events
                SET continuation_attempts = COALESCE(continuation_attempts, 0) + 1,
                    continuation_checked_at = NOW()
                WHERE id = ANY(%s)
                """,
                (event_ids,),
            )
            self.conn.commit()
        except Exception as e:
            logger.warning("Story continuation: failed to record recheck backoff: %s", e)
            try:
                self.conn.rollback()
            except Exception:
                pass
        finally:
            cursor.close()

    def update_entity_index(self, storyline_id: int):
        """
        Rebuild the entity index for a storyline from its linked events.
        Called after a new event is linked.
        """
        schema = self.schema or "public"
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                SELECT key_actors, entities
                FROM public.chronological_events
                WHERE storyline_id = %s::text
                  AND canonical_event_id IS NULL
            """,
                (storyline_id,),
            )
            rows = cursor.fetchall()

            entity_counts: dict[tuple[str, str], dict] = {}
            # Both lists default to `other`: event payloads carry no entity types, and
            # guessing `person` both mistypes organisations and splits one entity across
            # two rows (the unique key includes entity_type).
            for actors_json, entities_json in rows:
                for item_json, default_type in [(actors_json, "other"), (entities_json, "other")]:
                    items = self._parse_json(item_json)
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if isinstance(item, dict):
                            name = item.get("name", "").strip()
                            # `role` is free-text prose ("Investigating body") and is not a
                            # type — only entity_type may seed the CHECK-constrained column.
                            etype = map_entity_type_for_sei(
                                item.get("entity_type") or default_type
                            )
                        else:
                            name = str(item).strip()
                            etype = map_entity_type_for_sei(default_type)
                        if not name:
                            continue
                        key = (name.lower(), etype)
                        if key not in entity_counts:
                            entity_counts[key] = {
                                "name": name,
                                "type": etype,
                                "role": item.get("role", "") if isinstance(item, dict) else "",
                                "count": 0,
                            }
                        entity_counts[key]["count"] += 1

            skipped = 0
            try:
                from shared.domain_registry import schema_to_primary_domain_key
                from shared.story_entity_index import resolve_entity_role_for_sei

                dk = schema_to_primary_domain_key(schema)
            except Exception:
                dk = schema
                resolve_entity_role_for_sei = None  # type: ignore

            for idx, ((norm_name, etype), info) in enumerate(entity_counts.items()):
                is_core = info["count"] >= 3
                role = info["role"] or ""
                if resolve_entity_role_for_sei is not None:
                    erole, _hub = resolve_entity_role_for_sei(
                        domain_key=dk,
                        entity_name=info["name"],
                        entity_type=etype,
                    )
                    if erole:
                        role = erole
                ok = execute_with_savepoint(
                    cursor,
                    self.conn,
                    f"sei_upsert_{storyline_id}_{idx}",
                    f"""
                    INSERT INTO {schema}.story_entity_index
                        (storyline_id, entity_name, entity_role, entity_type,
                         mention_count, is_core_entity, last_seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (storyline_id, entity_name, entity_type)
                    DO UPDATE SET
                        mention_count = EXCLUDED.mention_count,
                        is_core_entity = EXCLUDED.is_core_entity,
                        entity_role = COALESCE(NULLIF(EXCLUDED.entity_role, ''),
                            {schema}.story_entity_index.entity_role),
                        last_seen_at = CURRENT_TIMESTAMP
                """,
                    (storyline_id, info["name"], role, etype, info["count"], is_core),
                )
                if not ok:
                    skipped += 1
            if skipped:
                logger.warning(
                    "Entity index storyline %s: %s/%s rows rejected",
                    storyline_id,
                    skipped,
                    len(entity_counts),
                )

            self.conn.commit()
        except Exception as e:
            logger.error(f"Entity index update for storyline {storyline_id} failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    def update_lifecycle_states(self):
        """Transition storylines between lifecycle states based on activity. Uses storylines in current search_path."""
        cursor = self.conn.cursor()
        try:
            if self.schema:
                cursor.execute("SET search_path TO %s, public", (self.schema,))
        except Exception as e:
            logger.warning(
                "Story continuation: failed to set search_path for lifecycle update: %s", e
            )
            cursor.close()
            return
        now = datetime.now(timezone.utc)
        try:
            cursor.execute(
                """
                UPDATE storylines
                SET status = 'dormant',
                    dormant_since = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'active'
                  AND last_event_at < %s
                  AND last_event_at IS NOT NULL
            """,
                (now - timedelta(days=DORMANT_DAYS),),
            )
            dormant_count = cursor.rowcount

            self.conn.commit()
            if dormant_count:
                logger.info(f"Transitioned {dormant_count} storylines to dormant")
        except Exception as e:
            logger.error(f"Lifecycle update failed: {e}")
            self.conn.rollback()
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_event(self, event_id: int) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, event_type, actual_event_date,
                   location, key_actors, entities, continuation_signals,
                   source_article_id
            FROM chronological_events
            WHERE id = %s
        """,
            (event_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "event_type": row[3],
            "actual_event_date": row[4],
            "location": row[5],
            "key_actors": self._parse_json(row[6]),
            "entities": self._parse_json(row[7]),
            "continuation_signals": self._parse_json(row[8]),
            "source_article_id": row[9],
        }

    def _article_entity_signals(self, article_id: Any) -> tuple[list[str], list[int]]:
        """Durable entity names + canonical ids from the event's source article.

        Topical ``subject`` / ``other`` rows are excluded so Mode B cannot admit
        on genre glue (e.g. ``data breach`` alone).
        """
        if article_id is None or not self.schema:
            return [], []
        cursor = self.conn.cursor()
        try:
            from shared.assembly_link_funnel import is_durable_entity_type

            cursor.execute(
                f"""
                SELECT DISTINCT entity_name, canonical_entity_id, entity_type
                FROM {self.schema}.article_entities
                WHERE article_id = %s AND entity_name IS NOT NULL
                LIMIT %s
                """,
                (int(article_id), ARTICLE_ENTITY_SIGNAL_LIMIT),
            )
            names: list[str] = []
            canonical_ids: list[int] = []
            for name, cid, etype in cursor.fetchall():
                if not is_durable_entity_type(etype):
                    continue
                if name and name.strip():
                    names.append(name.strip())
                if cid is not None:
                    canonical_ids.append(int(cid))
            return names, sorted(set(canonical_ids))
        except Exception as e:
            logger.debug("article entity signals article=%s: %s", article_id, e)
            return [], []
        finally:
            cursor.close()

    def _find_candidates_by_signature(self, event: dict) -> list[dict]:
        """Mode B: episodes whose locked anchor_signature matches this event."""
        try:
            from shared.domain_registry import schema_to_primary_domain_key
            from shared.episode_attach_gate import (
                classify_event_anchors,
                episode_container_assembly_enabled,
                parse_anchor_signature,
                signature_match,
            )
        except Exception:
            return []
        if not episode_container_assembly_enabled():
            return []
        schema = self.schema or "public"
        dk = schema_to_primary_domain_key(schema)
        if not dk:
            return []
        event_anchors = classify_event_anchors(
            self.conn,
            domain_key=dk,
            schema=schema,
            event_id=int(event["id"]),
            article_id=int(event["source_article_id"])
            if event.get("source_article_id") is not None
            else None,
        )
        if not (event_anchors.get("identity") or event_anchors.get("supporting")):
            return []
        cursor = self.conn.cursor()
        out: list[dict] = []
        try:
            cursor.execute(
                f"""
                SELECT id, title, summary, status, anchor_signature
                FROM {schema}.storylines
                WHERE COALESCE(story_kind, '') <> 'container_index'
                  AND COALESCE(is_mega_storyline, FALSE) = FALSE
                  AND status NOT IN ('archived', 'concluded')
                  AND anchor_signature IS NOT NULL
                  -- Thin forming bags are not Mode B magnets: need ≥2 articles
                  -- or an established non-forming state before candidacy.
                  AND NOT (
                        COALESCE(episode_state, '') = 'forming'
                    AND COALESCE(article_count, 0) < 2
                  )
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 80
                """
            )
            for sid, title, summary, status, raw_sig in cursor.fetchall() or []:
                sig = parse_anchor_signature(raw_sig)
                ok, matched, reason = signature_match(
                    sig, event_anchors, min_supporting=2, min_identity=2
                )
                if not ok:
                    continue
                out.append(
                    {
                        "storyline_id": int(sid),
                        "title": title,
                        "summary": summary,
                        "status": status,
                        "entity_overlap": len(matched),
                        "canonical_overlap": sum(
                            1 for m in matched if str(m).startswith("cid:")
                        ),
                        "core_entity_hit": reason == "identity_match",
                        "entity_rarity": 1,
                        "index_size": len(sig.get("identity") or [])
                        + len(sig.get("supporting") or []),
                        "matched_entities": list(matched)[:12],
                        "link_mode": "sequence",
                        "signature_match": True,
                        "signature_reason": reason,
                        "blend_score": 0.85 if reason == "identity_match" else 0.78,
                    }
                )
        except Exception as e:
            logger.debug("signature candidacy: %s", e)
        finally:
            cursor.close()
        return out

    def _find_candidates_by_entities(
        self,
        entity_names: list[str],
        event_id: int,
        *,
        canonical_ids: list[int] | None = None,
    ) -> list[dict]:
        """Candidate storylines by shared entities.

        Admits a storyline when any of these hold:
          - ``min_overlap`` distinct entity names match (original rule);
          - at least one canonical entity id matches (identity-resolved, high trust);
          - one name matches and that entity is rare across storylines (distinctive).
        Recall is deliberately wide — the LLM verification gate downstream decides.
        """
        cids = [int(c) for c in (canonical_ids or [])]
        if not entity_names and not cids:
            return []

        lower_names = sorted({n.lower().strip() for n in entity_names if n and n.strip()})
        schema = self.schema or "public"
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"""
                WITH sig_names AS (
                    SELECT UNNEST(%(names)s::text[]) AS nm
                ),
                sig_ids AS (
                    SELECT UNNEST(%(ids)s::int[]) AS cid
                ),
                matches AS (
                    SELECT sei.storyline_id,
                           sei.entity_name,
                           sei.canonical_entity_id,
                           COALESCE(sei.is_core_entity, FALSE) AS is_core,
                           (sei.canonical_entity_id IS NOT NULL
                            AND sei.canonical_entity_id IN (SELECT cid FROM sig_ids)) AS by_canonical
                    FROM {schema}.story_entity_index sei
                    WHERE (
                            LOWER(sei.entity_name) IN (SELECT nm FROM sig_names)
                            OR (sei.canonical_entity_id IS NOT NULL
                                AND sei.canonical_entity_id IN (SELECT cid FROM sig_ids))
                          )
                      -- Mode B: ignore topical subject/other glue as sole matches
                      AND LOWER(COALESCE(sei.entity_type, 'other')) NOT IN
                          ('subject', 'other', 'location', 'recurring_event')
                ),
                rarity AS (
                    SELECT LOWER(entity_name) AS nm, COUNT(DISTINCT storyline_id) AS story_count
                    FROM {schema}.story_entity_index
                    WHERE LOWER(entity_name) IN (SELECT nm FROM sig_names)
                      AND LOWER(COALESCE(entity_type, 'other')) NOT IN
                          ('subject', 'other', 'location', 'recurring_event')
                    GROUP BY 1
                ),
                sizes AS (
                    SELECT storyline_id, COUNT(*) AS sei_size
                    FROM {schema}.story_entity_index
                    GROUP BY 1
                )
                SELECT m.storyline_id, s.title, s.summary, s.status,
                       COUNT(DISTINCT m.entity_name) AS overlap,
                       COUNT(DISTINCT m.canonical_entity_id)
                           FILTER (WHERE m.by_canonical) AS canonical_overlap,
                       BOOL_OR(m.is_core) AS core_hit,
                       MIN(COALESCE(r.story_count, 9999)) AS min_story_count,
                       COALESCE(MAX(z.sei_size), 0) AS sei_size,
                       ARRAY_AGG(DISTINCT m.entity_name) AS matched_entities
                FROM matches m
                JOIN {schema}.storylines s ON s.id = m.storyline_id
                LEFT JOIN rarity r ON r.nm = LOWER(m.entity_name)
                LEFT JOIN sizes z ON z.storyline_id = m.storyline_id
                WHERE s.status NOT IN ('archived', 'concluded')
                  AND COALESCE(s.story_kind, '') <> 'container_index'
                  AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                GROUP BY m.storyline_id, s.title, s.summary, s.status
                HAVING
                    CASE WHEN COALESCE(MAX(z.sei_size), 0) > %(hub)s THEN
                        -- Hub storyline: only strong, identity-resolved evidence admits it.
                        COUNT(DISTINCT m.canonical_entity_id) FILTER (WHERE m.by_canonical) >= 2
                        OR COUNT(DISTINCT m.entity_name) >= %(hub_min_overlap)s
                    ELSE
                        COUNT(DISTINCT m.entity_name) >= %(min_overlap)s
                        OR COUNT(DISTINCT m.canonical_entity_id) FILTER (WHERE m.by_canonical) >= 1
                        OR (
                            COUNT(DISTINCT m.entity_name) >= 1
                            AND MIN(COALESCE(r.story_count, 9999)) <= %(rare)s
                        )
                    END
                ORDER BY canonical_overlap DESC, overlap DESC
                LIMIT %(limit)s
                """,
                {
                    "names": lower_names or [""],
                    "ids": cids or [0],
                    "hub": _hub_entity_count(),
                    "hub_min_overlap": max(4, _min_entity_overlap() * 2),
                    "min_overlap": _min_entity_overlap(),
                    "rare": _rare_entity_max_storylines(),
                    "limit": _candidate_limit(),
                },
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "storyline_id": row[0],
                        "title": row[1],
                        "summary": row[2],
                        "status": row[3],
                        "entity_overlap": row[4],
                        "canonical_overlap": row[5],
                        "core_entity_hit": bool(row[6]),
                        "entity_rarity": row[7],
                        "index_size": row[8],
                        "matched_entities": row[9],
                        "link_mode": "sequence",
                    }
                )
            return results
        except Exception as e:
            logger.error(f"Entity candidate lookup failed: {e}")
            return []
        finally:
            cursor.close()

    def _filter_by_event_type(self, candidates: list[dict], event_type: str) -> list[dict]:
        compatible = EVENT_TYPE_COMPATIBILITY.get(event_type, {event_type, "other"})
        filtered = []
        cursor = self.conn.cursor()
        for cand in candidates:
            cursor.execute(
                """
                SELECT DISTINCT event_type FROM chronological_events
                WHERE storyline_id = %s::text AND event_type IS NOT NULL
            """,
                (cand["storyline_id"],),
            )
            story_types = {r[0] for r in cursor.fetchall()}
            if story_types & compatible:
                cand["type_compatible"] = True
                filtered.append(cand)
            elif not story_types:
                cand["type_compatible"] = False
                filtered.append(cand)
        cursor.close()
        return filtered

    async def _verify_candidates(self, candidates: list[dict], event: dict) -> dict | None:
        for cand in candidates:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT title, actual_event_date
                FROM chronological_events
                WHERE storyline_id = %s::text
                ORDER BY actual_event_date DESC NULLS LAST
                LIMIT 5
            """,
                (cand["storyline_id"],),
            )
            recent = cursor.fetchall()
            cursor.close()

            events_text = (
                "\n".join(f"- {r[0]} ({r[1] or 'date unknown'})" for r in recent)
                or "(no prior events)"
            )

            actor_names = [
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in (event.get("key_actors") or [])
            ]

            prompt = STORY_VERIFICATION_PROMPT.format(
                storyline_title=cand["title"],
                storyline_summary=cand.get("summary") or "(no summary)",
                recent_events=events_text,
                core_entities=", ".join(cand.get("matched_entities") or []),
                event_title=event["title"],
                event_date=event.get("actual_event_date") or "unknown",
                event_actors=", ".join(actor_names),
                event_description=event.get("description") or "",
            )

            try:
                raw = await self.llm._call_ollama(ModelType.LLAMA_8B, prompt)
                verdict = self._parse_verdict(raw)
                if not verdict:
                    continue

                confidence = verdict.get("confidence", 0)
                if verdict["verdict"] == "YES" and confidence >= AUTO_LINK_THRESHOLD:
                    cand["confidence"] = confidence
                    cand["auto_linked"] = True
                    cand["reasoning"] = verdict.get("reasoning", "")
                    return cand
                elif verdict["verdict"] in ("YES", "MAYBE") and confidence >= REVIEW_THRESHOLD:
                    cand["confidence"] = confidence
                    cand["auto_linked"] = False
                    cand["reasoning"] = verdict.get("reasoning", "")
                    return cand
            except Exception as e:
                logger.warning(f"LLM verification failed for storyline {cand['storyline_id']}: {e}")

        return None

    def _emit_reactivation_watchlist_alert(
        self, cursor, schema: str, storyline_id: int, event: dict
    ) -> None:
        """v12 THIN: on reactivation, insert watchlist_alerts for matching watches."""
        title = None
        try:
            cursor.execute(
                f"SELECT title, reactivation_count FROM {schema}.storylines WHERE id = %s",
                (storyline_id,),
            )
            row = cursor.fetchone()
            if row:
                title = row[0]
                react_count = row[1]
            else:
                react_count = 1
        except Exception:
            react_count = 1
            title = f"Storyline {storyline_id}"

        # Prefer public.watchlist keyed by storyline_id (legacy global table).
        try:
            cursor.execute(
                """
                SELECT id FROM public.watchlist
                WHERE storyline_id = %s
                  AND COALESCE(alert_on_reactivation, TRUE) = TRUE
                """,
                (storyline_id,),
            )
            watches = cursor.fetchall() or []
        except Exception:
            watches = []

        event_id = event.get("id")
        for (wid,) in watches:
            cursor.execute(
                """
                INSERT INTO public.watchlist_alerts
                    (watchlist_id, storyline_id, event_id, alert_type, title, body)
                SELECT %s, %s, %s, 'reactivation', %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.watchlist_alerts wa
                    WHERE wa.watchlist_id = %s
                      AND wa.alert_type = 'reactivation'
                      AND wa.created_at > CURRENT_TIMESTAMP - INTERVAL '1 day'
                )
                """,
                (
                    wid,
                    storyline_id,
                    int(event_id) if event_id is not None else None,
                    f"Storyline reactivated: {title}",
                    f"New continuation event reactivated this storyline "
                    f"(reactivation #{react_count}).",
                    wid,
                ),
            )

    def _link_event(self, event: dict, match: dict) -> bool:
        """Attach event→episode (or legacy bag). Returns False if gate rejects."""
        cursor = self.conn.cursor()
        schema = self.schema or "public"
        try:
            storyline_id = match["storyline_id"]
            aid = event.get("source_article_id")
            blend = float(match.get("blend_score") or 0.0)
            llm_conf = match.get("confidence")
            try:
                llm_conf_f = float(llm_conf) if llm_conf is not None else None
            except (TypeError, ValueError):
                llm_conf_f = None

            episode_linked = False
            # Event → Episode SSOT when feature on — gate BEFORE stamping storyline_id
            try:
                from shared.domain_registry import schema_to_primary_domain_key
                from shared.episode_attach_gate import (
                    allow_event_episode_attach,
                    episode_container_assembly_enabled,
                    insert_event_episode_link,
                    lock_episode_signature,
                )

                dk = schema_to_primary_domain_key(schema)
                if episode_container_assembly_enabled() and dk:
                    ok_ep, ep_reason, ep_details = allow_event_episode_attach(
                        self.conn,
                        domain_key=dk,
                        schema=schema,
                        episode_id=int(storyline_id),
                        event_id=int(event["id"]),
                        article_id=int(aid) if aid is not None else None,
                        blend_rank=blend,
                    )
                    if not ok_ep:
                        logger.info(
                            "continuation episode attach blocked episode=%s event=%s: %s",
                            storyline_id,
                            event["id"],
                            ep_reason,
                        )
                        self.conn.rollback()
                        return False
                    seed = ep_details.get("seed_signature")
                    if seed:
                        lock_episode_signature(
                            cursor, schema, int(storyline_id), seed
                        )
                    import json as _json

                    insert_event_episode_link(
                        cursor,
                        event_id=int(event["id"]),
                        domain_key=dk,
                        episode_id=int(storyline_id),
                        link_type=str(ep_details.get("link_type") or "continuation"),
                        matched_anchors=list(ep_details.get("matched_anchors") or []),
                        inference_stage="established"
                        if match.get("auto_linked")
                        else "candidate",
                        blend_rank=blend,
                        added_by="story_continuation",
                        metadata={
                            "gate_reason": ep_reason,
                            "llm_confidence": llm_conf_f,
                            "llm_verdict": "YES" if match.get("auto_linked") else None,
                        },
                    )
                    if aid is not None:
                        from shared.membership_store import insert_derived_bag_row

                        insert_derived_bag_row(
                            cursor,
                            schema=schema,
                            storyline_id=int(storyline_id),
                            article_id=int(aid),
                            relevance_score=blend,
                            added_by="story_continuation",
                            metadata={
                                "derived_from": "event_episode_link",
                                "event_id": int(event["id"]),
                                "gate_reason": ep_reason,
                            },
                        )
                    episode_linked = True
            except Exception as e:
                logger.warning(
                    "continuation episode path error storyline=%s: %s",
                    storyline_id,
                    e,
                )
                try:
                    from shared.episode_attach_gate import episode_container_assembly_enabled

                    if episode_container_assembly_enabled():
                        self.conn.rollback()
                        return False
                except Exception:
                    self.conn.rollback()
                    return False

            cursor.execute(
                """
                UPDATE chronological_events
                SET storyline_id = %s::text
                WHERE id = %s
            """,
                (storyline_id, event["id"]),
            )

            # Legacy article→bag path when EEL attach did not link
            if aid is not None and not episode_linked:
                try:
                    from shared.domain_registry import schema_to_primary_domain_key
                    from shared.membership_store import MembershipIntent, admit as membership_admit

                    dk = schema_to_primary_domain_key(schema)
                    membership_admit(
                        self.conn,
                        domain_key=dk,
                        schema=schema,
                        episode_id=int(storyline_id),
                        article_id=int(aid),
                        intent=MembershipIntent.CONTINUATION,
                        blend_score=blend,
                        added_by="story_continuation",
                    )
                except Exception as e:
                    logger.warning(
                        "continuation article attach error storyline=%s: %s",
                        storyline_id,
                        e,
                    )

            # Reactivate dormant storylines / episodes
            reactivated = False
            try:
                cursor.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET status = 'active',
                        last_event_at = CURRENT_TIMESTAMP,
                        reactivation_count = COALESCE(reactivation_count, 0) + 1,
                        dormant_since = NULL,
                        episode_state = CASE
                            WHEN episode_state IN ('dormant', 'cooling', 'concluded', 'forming')
                            THEN 'active'
                            ELSE COALESCE(episode_state, 'active')
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND (
                        status = 'dormant'
                        OR episode_state IN ('dormant', 'cooling', 'concluded')
                    )
                """,
                    (storyline_id,),
                )
                reactivated = cursor.rowcount > 0
            except Exception:
                cursor.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET status = 'active',
                        last_event_at = CURRENT_TIMESTAMP,
                        reactivation_count = COALESCE(reactivation_count, 0) + 1,
                        dormant_since = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND status = 'dormant'
                """,
                    (storyline_id,),
                )
                reactivated = cursor.rowcount > 0

            if reactivated:
                try:
                    self._emit_reactivation_watchlist_alert(
                        cursor, schema, int(storyline_id), event
                    )
                except Exception as e:
                    logger.warning(
                        "reactivation watchlist alert failed storyline=%s: %s",
                        storyline_id,
                        e,
                    )

            cursor.execute(
                f"""
                UPDATE {schema}.storylines
                SET last_event_at = CURRENT_TIMESTAMP,
                    total_events = COALESCE(total_events, 0) + 1,
                    article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    total_articles = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """,
                (storyline_id, storyline_id, storyline_id),
            )

            self.conn.commit()
            self.update_entity_index(storyline_id)
            # Admit / refresh editorial package so Research modal can pick it up.
            try:
                from shared.domain_registry import schema_to_primary_domain_key
                from services.editorial_package_service import ensure_package_from_storyline

                dk = schema_to_primary_domain_key(schema)
                ensure_package_from_storyline(
                    domain_key=dk,
                    storyline_id=int(storyline_id),
                    actor="story_continuation",
                    refresh_members=True,
                )
            except Exception as e:
                logger.debug(
                    "continuation editorial seed storyline=%s: %s", storyline_id, e
                )
            logger.info(
                f"Linked event {event['id']} to storyline {storyline_id} "
                f"(confidence={match.get('confidence', 0):.2f}, auto={match.get('auto_linked')})"
            )
            return True
        except Exception as e:
            logger.error(f"Event linking failed: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def _parse_verdict(self, raw: str) -> dict | None:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            data = json.loads(text[start : end + 1])
            if "verdict" in data:
                return data
        except json.JSONDecodeError:
            pass
        return None

    @staticmethod
    def _extract_names(val) -> list[str]:
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return []
        if not isinstance(val, list):
            return []
        names = []
        for item in val:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
            else:
                name = str(item).strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _parse_json(val):
        if val is None:
            return []
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
