"""
Selective RAG evidence pull — chemistry stimulus when a bond needs more source text.

Primarily arXiv abstract → PDF download via document_processing, gated by queue ticket.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_int, env_str
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

_ARXIV_ID_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)(\d{4}\.\d{4,5})(?:v\d+)?",
    re.I,
)


def rag_evidence_pull_enabled() -> bool:
    from shared.chemistry_beaker import stimulus_rag_enabled

    return stimulus_rag_enabled()


def daily_auto_cap() -> int:
    return max(0, env_int("RAG_EVIDENCE_PULL_DAILY_AUTO_CAP", 8))


def parse_arxiv_id(url_or_text: str | None) -> str | None:
    if not url_or_text:
        return None
    m = _ARXIV_ID_RE.search(str(url_or_text))
    return m.group(1) if m else None


def enqueue_evidence_pull(
    *,
    domain_key: str,
    article_id: int | None = None,
    arxiv_id: str | None = None,
    pdf_url: str | None = None,
    proposal_id: int | None = None,
    storyline_id: int | None = None,
    interest_score: float | None = None,
    selection_reason: str | None = None,
    auto_queue: bool = False,
) -> dict[str, Any]:
    if not rag_evidence_pull_enabled() and not auto_queue:
        # Still allow explicit enqueue when flag off for operator tools
        pass
    if arxiv_id and not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    status = "queued" if auto_queue else "pending_approval"
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "no_db"}
    try:
        with conn.cursor() as cur:
            if auto_queue and daily_auto_cap() > 0:
                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM intelligence.rag_evidence_pull_queue
                    WHERE created_at::date = CURRENT_DATE
                      AND status IN ('queued', 'downloading', 'processing', 'complete')
                    """
                )
                if int(cur.fetchone()[0] or 0) >= daily_auto_cap():
                    status = "pending_approval"
            cur.execute(
                """
                INSERT INTO intelligence.rag_evidence_pull_queue (
                    domain_key, article_id, arxiv_id, pdf_url, proposal_id, storyline_id,
                    interest_score, selection_reason, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id, status
                """,
                (
                    domain_key,
                    article_id,
                    arxiv_id,
                    pdf_url,
                    proposal_id,
                    storyline_id,
                    interest_score,
                    (selection_reason or "")[:2000],
                    status,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return {"ok": True, "id": int(row[0]), "status": row[1]}
    except Exception as e:
        err = str(e)
        try:
            conn.rollback()
        except Exception:
            pass
        if "unique" in err.lower() or "duplicate" in err.lower():
            return {"ok": True, "duplicate": True}
        logger.warning("enqueue_evidence_pull: %s", e)
        return {"ok": False, "error": err[:300]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def screen_ai_arxiv_for_evidence_pull(*, limit: int = 20) -> dict[str, Any]:
    """
    Layer-1: find recent AI arXiv abstract articles not yet ticketed; enqueue mid/high.
    High score → auto queued (cap); mid → pending_approval.
    """
    if not rag_evidence_pull_enabled():
        return {"enabled": False, "enqueued": 0}
    from shared.domain_registry import resolve_domain_schema

    domain_key = "artificial-intelligence"
    schema = resolve_domain_schema(domain_key)
    high = float(env_str("RAG_EVIDENCE_PULL_HIGH_THRESHOLD", "0.72") or 0.72)
    mid = float(env_str("RAG_EVIDENCE_PULL_MID_THRESHOLD", "0.45") or 0.45)
    conn = get_db_connection()
    if not conn:
        return {"enqueued": 0, "error": "no_db"}
    stats = {"enqueued": 0, "pending_approval": 0, "queued": 0, "skipped": 0}
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id, a.title, a.url, a.summary, a.content
                FROM {schema}.articles a
                WHERE a.url ILIKE '%%arxiv.org%%'
                  AND COALESCE(a.created_at, a.published_at) > NOW() - INTERVAL '14 days'
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.rag_evidence_pull_queue q
                    WHERE q.domain_key = %s AND q.article_id = a.id
                  )
                ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
                LIMIT %s
                """,
                (domain_key, limit),
            )
            rows = cur.fetchall()
        for aid, title, url, summary, content in rows:
            arxiv_id = parse_arxiv_id(url) or parse_arxiv_id(str(title or ""))
            if not arxiv_id:
                stats["skipped"] += 1
                continue
            text = f"{title or ''} {summary or ''} {(content or '')[:2000]}".lower()
            score = 0.2
            reason_bits = []
            for kw, boost in (
                ("policy", 0.15),
                ("safety", 0.15),
                ("benchmark", 0.2),
                ("evaluation", 0.15),
                ("alignment", 0.15),
                ("regulation", 0.15),
                ("llm", 0.1),
                ("transformer", 0.05),
            ):
                if kw in text:
                    score += boost
                    reason_bits.append(kw)
            try:
                from services.domain_synthesis_config import get_domain_synthesis_config

                cfg = get_domain_synthesis_config(domain_key)
                for area in cfg.focus_areas[:6]:
                    tok = str(area).lower().split()[:2]
                    if tok and all(t in text for t in tok if len(t) > 3):
                        score += 0.1
                        reason_bits.append("focus:" + tok[0])
            except Exception:
                pass
            score = min(1.0, score)
            if score < mid:
                stats["skipped"] += 1
                continue
            auto = score >= high
            res = enqueue_evidence_pull(
                domain_key=domain_key,
                article_id=int(aid),
                arxiv_id=arxiv_id,
                interest_score=score,
                selection_reason="keywords:" + ",".join(reason_bits[:8]),
                auto_queue=auto,
            )
            if res.get("ok") and not res.get("duplicate"):
                stats["enqueued"] += 1
                if res.get("status") == "queued":
                    stats["queued"] += 1
                else:
                    stats["pending_approval"] += 1
            else:
                stats["skipped"] += 1
        return stats
    except Exception as e:
        logger.warning("screen_ai_arxiv_for_evidence_pull: %s", e)
        return {**stats, "error": str(e)[:200]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def screen_hypothesized_bonds_for_evidence_pull(*, limit: int = 25) -> dict[str, Any]:
    """
    Bond-triggered stimulus: pending hypothesized/candidate proposals whose
    endpoints touch thin arXiv (or AI research) articles → enqueue PDF pull.
    """
    if not rag_evidence_pull_enabled():
        return {"enabled": False, "enqueued": 0}
    from shared.domain_registry import resolve_domain_schema

    domain_key = "artificial-intelligence"
    schema = resolve_domain_schema(domain_key)
    mid = float(env_str("RAG_EVIDENCE_PULL_MID_THRESHOLD", "0.45") or 0.45)
    high = float(env_str("RAG_EVIDENCE_PULL_HIGH_THRESHOLD", "0.72") or 0.72)
    conn = get_db_connection()
    if not conn:
        return {"enqueued": 0, "error": "no_db"}
    stats = {"enqueued": 0, "pending_approval": 0, "queued": 0, "skipped": 0, "scanned": 0}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, confidence, endpoints, evidence, inference_stage
                FROM intelligence.graph_connection_proposals
                WHERE status = 'pending'
                  AND COALESCE(inference_stage, 'candidate') IN ('hypothesized', 'candidate')
                  AND COALESCE(domain_key, %s) = %s
                ORDER BY COALESCE(confidence, 0) DESC, id DESC
                LIMIT %s
                """,
                (domain_key, domain_key, limit),
            )
            proposals = list(cur.fetchall())
        for pid, conf, endpoints, evidence, stage in proposals:
            stats["scanned"] += 1
            conf_f = float(conf or 0)
            if conf_f < mid:
                stats["skipped"] += 1
                continue
            ep = endpoints if isinstance(endpoints, dict) else {}
            ev = evidence if isinstance(evidence, dict) else {}
            article_ids: list[int] = []
            for key in ("article_ids", "anchors"):
                raw = ep.get(key) or (ev.get("anchors") or {}).get(key) or []
                if isinstance(raw, list):
                    for x in raw:
                        try:
                            article_ids.append(int(x))
                        except (TypeError, ValueError):
                            pass
            # Prefer explicit article_id on evidence
            for k in ("article_id",):
                if ev.get(k) is not None:
                    try:
                        article_ids.append(int(ev[k]))
                    except (TypeError, ValueError):
                        pass
            article_ids = list(dict.fromkeys(article_ids))[:5]
            if not article_ids:
                stats["skipped"] += 1
                continue
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT a.id, a.url, a.title
                    FROM {schema}.articles a
                    WHERE a.id = ANY(%s)
                      AND a.url ILIKE '%%arxiv.org%%'
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.rag_evidence_pull_queue q
                        WHERE q.domain_key = %s AND q.article_id = a.id
                      )
                    LIMIT 1
                    """,
                    (article_ids, domain_key),
                )
                row = cur.fetchone()
            if not row:
                stats["skipped"] += 1
                continue
            aid, url, title = row
            arxiv_id = parse_arxiv_id(url) or parse_arxiv_id(str(title or ""))
            if not arxiv_id:
                stats["skipped"] += 1
                continue
            auto = conf_f >= high or str(stage or "") == "candidate"
            res = enqueue_evidence_pull(
                domain_key=domain_key,
                article_id=int(aid),
                arxiv_id=arxiv_id,
                proposal_id=int(pid),
                interest_score=conf_f,
                selection_reason=f"bond_stimulus:{stage or 'candidate'}:proposal={pid}",
                auto_queue=auto,
            )
            if res.get("ok") and not res.get("duplicate"):
                stats["enqueued"] += 1
                if res.get("status") == "queued":
                    stats["queued"] += 1
                else:
                    stats["pending_approval"] += 1
            else:
                stats["skipped"] += 1
        return stats
    except Exception as e:
        logger.warning("screen_hypothesized_bonds_for_evidence_pull: %s", e)
        return {**stats, "error": str(e)[:200]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def drain_queued_evidence_pulls(*, limit: int = 3) -> dict[str, Any]:
    """Process queued tickets: insert PDF URL into processed_documents for document_processing."""
    if not rag_evidence_pull_enabled():
        return {"enabled": False, "processed": 0}
    import json

    conn = get_db_connection()
    if not conn:
        return {"processed": 0, "error": "no_db"}
    processed = 0
    errors = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, article_id, arxiv_id, pdf_url, selection_reason
                FROM intelligence.rag_evidence_pull_queue
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (limit,),
            )
            rows = list(cur.fetchall())
        for qid, domain_key, article_id, arxiv_id, pdf_url, reason in rows:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.rag_evidence_pull_queue
                        SET status = 'downloading', updated_at = NOW()
                        WHERE id = %s
                        """,
                        (qid,),
                    )
                    url = pdf_url or f"http://arxiv.org/pdf/{arxiv_id}.pdf"
                    meta = {
                        "domain_key": domain_key,
                        "article_id": article_id,
                        "arxiv_id": arxiv_id,
                        "rag_evidence_pull_id": qid,
                        "require_evidence_ticket": True,
                    }
                    cur.execute(
                        """
                        SELECT id FROM intelligence.processed_documents
                        WHERE source_url = %s LIMIT 1
                        """,
                        (url,),
                    )
                    existing = cur.fetchone()
                    if existing:
                        doc_id = int(existing[0])
                    else:
                        cur.execute(
                            """
                            INSERT INTO intelligence.processed_documents
                                (source_url, title, source_name, document_type, metadata)
                            VALUES (%s, %s, 'arXiv', 'paper', %s::jsonb)
                            RETURNING id
                            """,
                            (url, f"arXiv:{arxiv_id}", json.dumps(meta)),
                        )
                        doc_id = int(cur.fetchone()[0])
                    cur.execute(
                        """
                        UPDATE intelligence.rag_evidence_pull_queue
                        SET status = 'processing', processed_document_id = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (doc_id, qid),
                    )
                conn.commit()
                try:
                    from services.document_processing_service import (
                        process_unprocessed_documents,
                    )

                    process_unprocessed_documents(limit=2)
                except Exception as pe:
                    logger.debug("evidence pull process: %s", pe)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.rag_evidence_pull_queue
                        SET status = 'complete', resolved_at = NOW(), updated_at = NOW()
                        WHERE id = %s
                        """,
                        (qid,),
                    )
                conn.commit()
                processed += 1
                try:
                    from services.content_refinement_queue_service import (
                        enqueue_refinement_for_stimulus,
                    )

                    enqueue_refinement_for_stimulus(
                        domain_key=str(domain_key),
                        article_id=int(article_id) if article_id else None,
                        reason="rag_evidence_pull_complete",
                    )
                except Exception:
                    pass
            except Exception as e:
                errors += 1
                logger.warning("drain evidence pull %s: %s", qid, e)
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE intelligence.rag_evidence_pull_queue
                            SET status = 'failed', agent_notes = %s, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (str(e)[:500], qid),
                        )
                    conn.commit()
                except Exception:
                    pass
        return {"processed": processed, "errors": errors}
    except Exception as e:
        logger.warning("drain_queued_evidence_pulls: %s", e)
        return {"processed": processed, "errors": errors + 1, "error": str(e)[:200]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def count_evidence_pull_pending() -> int:
    conn = get_db_connection()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int FROM intelligence.rag_evidence_pull_queue
                WHERE status IN ('pending_approval', 'queued', 'downloading', 'processing')
                """
            )
            return int(cur.fetchone()[0] or 0)
    except Exception:
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
