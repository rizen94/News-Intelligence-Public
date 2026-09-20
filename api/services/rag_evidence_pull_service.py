"""
Selective RAG evidence pull — chemistry stimulus when a bond needs more source text.

Supports arXiv PDF plus feature-flagged court PDF, Federal Register, and WHO/CDC
bulletin URL fetchers (Phase 5 generalization).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.runtime import env_bool, env_int, env_str
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

_ARXIV_ID_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)(\d{4}\.\d{4,5})(?:v\d+)?",
    re.I,
)
_COURT_PDF_RE = re.compile(
    r"(?:courtlistener\.com|govinfo\.gov|supremecourt\.gov|cafc\.uscourts\.gov).*\.pdf",
    re.I,
)
_FEDREG_RE = re.compile(
    r"federalregister\.gov/(?:documents|d)/|govinfo\.gov/content/pkg/FR-",
    re.I,
)
_WHO_CDC_RE = re.compile(
    r"(?:who\.int|cdc\.gov)/(?:.*(?:bulletin|mmwr|disease|outbreak|news))",
    re.I,
)

_SOURCE_TYPES = frozenset(
    {"arxiv", "court_pdf", "federal_register", "who_cdc", "url_fetch", "other"}
)
_FETCH_TIMEOUT = 15


def rag_evidence_pull_enabled() -> bool:
    from shared.chemistry_beaker import stimulus_rag_enabled

    return stimulus_rag_enabled()


def source_type_enabled(source_type: str) -> bool:
    """Feature-flag new source types; arxiv always allowed when stimulus_rag on."""
    st = (source_type or "arxiv").lower()
    if st == "arxiv":
        return True
    flags = {
        "court_pdf": "RAG_EVIDENCE_PULL_COURT_PDF_ENABLED",
        "federal_register": "RAG_EVIDENCE_PULL_FEDERAL_REGISTER_ENABLED",
        "who_cdc": "RAG_EVIDENCE_PULL_WHO_CDC_ENABLED",
        "url_fetch": "RAG_EVIDENCE_PULL_URL_FETCH_ENABLED",
        "other": "RAG_EVIDENCE_PULL_URL_FETCH_ENABLED",
    }
    env_name = flags.get(st)
    if not env_name:
        return False
    try:
        from config.feature_registry import is_feature_enabled

        key_map = {
            "court_pdf": "stimulus_rag_court_pdf",
            "federal_register": "stimulus_rag_federal_register",
            "who_cdc": "stimulus_rag_who_cdc",
            "url_fetch": "stimulus_rag_url_fetch",
            "other": "stimulus_rag_url_fetch",
        }
        fk = key_map.get(st)
        if fk and is_feature_enabled(fk, default=False):
            return True
    except Exception:
        pass
    return env_bool(env_name, False)


def daily_auto_cap() -> int:
    return max(0, env_int("RAG_EVIDENCE_PULL_DAILY_AUTO_CAP", 8))


def parse_arxiv_id(url_or_text: str | None) -> str | None:
    if not url_or_text:
        return None
    m = _ARXIV_ID_RE.search(str(url_or_text))
    return m.group(1) if m else None


def detect_source_type(url_or_text: str | None) -> str:
    """Heuristic source_type from URL/text."""
    s = str(url_or_text or "")
    if parse_arxiv_id(s):
        return "arxiv"
    if _COURT_PDF_RE.search(s) or (".pdf" in s.lower() and "court" in s.lower()):
        return "court_pdf"
    if _FEDREG_RE.search(s):
        return "federal_register"
    if _WHO_CDC_RE.search(s):
        return "who_cdc"
    if s.startswith("http"):
        return "url_fetch"
    return "other"


def fetch_url_text(url: str, *, max_chars: int = 50_000) -> tuple[str, bool]:
    """
    Lightweight URL body fetch (plain text / HTML strip), patterned after
    clinicaltrials_study_fetch (urllib + User-Agent, no heavy scraper).
    """
    if not url or not url.startswith("http"):
        return "", False
    try:
        req = Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain,*/*",
                "User-Agent": "NewsIntelligence/1.0 stimulus-rag",
            },
        )
        with urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read(max_chars + 1024)
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            return f"[pdf_bytes:{len(raw)} url={url}]", True
        text = raw.decode("utf-8", errors="replace")
        text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
        text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 80:
            return text, False
        return text[:max_chars], True
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        logger.debug("fetch_url_text %s: %s", url[:120], e)
        return "", False
    except Exception as e:
        logger.warning("fetch_url_text unexpected %s: %s", url[:80], e)
        return "", False


def fetch_court_pdf_body(url: str) -> tuple[str, bool]:
    if not source_type_enabled("court_pdf"):
        return "", False
    return fetch_url_text(url)


def fetch_federal_register_body(url: str) -> tuple[str, bool]:
    if not source_type_enabled("federal_register"):
        return "", False
    return fetch_url_text(url)


def fetch_who_cdc_bulletin_body(url: str) -> tuple[str, bool]:
    if not source_type_enabled("who_cdc"):
        return "", False
    return fetch_url_text(url)


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
    source_type: str | None = None,
) -> dict[str, Any]:
    if not rag_evidence_pull_enabled() and not auto_queue:
        # Still allow explicit enqueue when flag off for operator tools
        pass
    st = (source_type or detect_source_type(pdf_url or arxiv_id or "")).lower()
    if st not in _SOURCE_TYPES:
        st = "other"
    if st != "arxiv" and not source_type_enabled(st) and not auto_queue:
        return {"ok": False, "error": f"source_type_disabled:{st}"}
    if arxiv_id and not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        st = "arxiv"
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
                    interest_score, selection_reason, status, source_type
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                    st,
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return {"ok": True, "id": int(row[0]), "status": row[1], "source_type": st}
    except Exception as e:
        err = str(e)
        try:
            conn.rollback()
        except Exception:
            pass
        if "source_type" in err.lower():
            return _enqueue_without_source_type(
                domain_key=domain_key,
                article_id=article_id,
                arxiv_id=arxiv_id,
                pdf_url=pdf_url,
                proposal_id=proposal_id,
                storyline_id=storyline_id,
                interest_score=interest_score,
                selection_reason=selection_reason,
                status=status,
            )
        if "unique" in err.lower() or "duplicate" in err.lower():
            return {"ok": True, "duplicate": True}
        logger.warning("enqueue_evidence_pull: %s", e)
        return {"ok": False, "error": err[:300]}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _enqueue_without_source_type(
    *,
    domain_key: str,
    article_id: int | None,
    arxiv_id: str | None,
    pdf_url: str | None,
    proposal_id: int | None,
    storyline_id: int | None,
    interest_score: float | None,
    selection_reason: str | None,
    status: str,
) -> dict[str, Any]:
    """Pre-migration 279 fallback (no source_type column)."""
    conn = get_db_connection()
    if not conn:
        return {"ok": False, "error": "no_db"}
    try:
        with conn.cursor() as cur:
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
        return {"ok": True, "id": int(row[0]), "status": row[1], "legacy": True}
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return {"ok": True, "duplicate": True}
        return {"ok": False, "error": str(e)[:300]}
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
            try:
                cur.execute(
                    """
                    SELECT id, domain_key, article_id, arxiv_id, pdf_url, selection_reason,
                           COALESCE(source_type, 'arxiv') AS source_type
                    FROM intelligence.rag_evidence_pull_queue
                    WHERE status = 'queued'
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (limit,),
                )
            except Exception:
                conn.rollback()
                cur.execute(
                    """
                    SELECT id, domain_key, article_id, arxiv_id, pdf_url, selection_reason,
                           'arxiv' AS source_type
                    FROM intelligence.rag_evidence_pull_queue
                    WHERE status = 'queued'
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (limit,),
                )
            rows = list(cur.fetchall())
        for qid, domain_key, article_id, arxiv_id, pdf_url, reason, source_type in rows:
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
                    url = pdf_url or (
                        f"http://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None
                    )
                    if not url:
                        raise ValueError("missing pdf_url/arxiv_id")
                    st = str(source_type or "arxiv")
                    doc_type = {
                        "arxiv": "paper",
                        "court_pdf": "court_filing",
                        "federal_register": "regulation",
                        "who_cdc": "bulletin",
                    }.get(st, "document")
                    source_name = {
                        "arxiv": "arXiv",
                        "court_pdf": "Court PDF",
                        "federal_register": "Federal Register",
                        "who_cdc": "WHO/CDC",
                    }.get(st, st)
                    meta: dict[str, Any] = {
                        "domain_key": domain_key,
                        "article_id": article_id,
                        "arxiv_id": arxiv_id,
                        "rag_evidence_pull_id": qid,
                        "require_evidence_ticket": True,
                        "source_type": st,
                    }
                    if st in ("federal_register", "who_cdc", "url_fetch"):
                        body, ok = fetch_url_text(url)
                        if ok and body and not body.startswith("[pdf_bytes:"):
                            meta["fetched_chars"] = len(body)
                            meta["inline_fetch"] = True
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
                            VALUES (%s, %s, %s, %s, %s::jsonb)
                            RETURNING id
                            """,
                            (
                                url,
                                f"{source_name}:{arxiv_id or qid}",
                                source_name,
                                doc_type,
                                json.dumps(meta),
                            ),
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
