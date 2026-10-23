"""
Fulltext pull gate — decide whether thin/title-link RSS items deserve a body fetch.

ClinicalTrials.gov (and similar) feeds often ship titles + a link; the RSS body is
boilerplate. Most trials are not worth a full pull; a minority should use the
registry API / deeper fetch. Deferred rows stay as titles and phase out of
downstream LLM work via enrichment_status=pull_deferred.
"""

from __future__ import annotations

import logging
import re
import time
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from config.runtime import env_bool, env_int, env_str

logger = logging.getLogger(__name__)

# Terminal: intentionally not pulling full body (leave for eventual phase-out).
STATUS_PULL_DEFERRED = "pull_deferred"
# Re-open for enrichment fetch after title triage.
STATUS_PENDING = "pending"

_CTGOV_BOILERPLATE_NEEDLES = (
    "study record managers: refer to the data element definitions",
    "data element definitions if submitting registration",
)

_DEFAULT_THIN_HOSTS = (
    "clinicaltrials.gov",
    "www.clinicaltrials.gov",
)

_DEFAULT_INTEREST_KEYWORDS = (
    "autism",
    "alzheimer",
    "parkinson",
    "vaccine",
    "mrna",
    "oncology",
    "immunotherapy",
    "gene therapy",
    "crispr",
    "pandemic",
    "outbreak",
    "epidemic",
    "phase 3",
    "phase iii",
    "phase 2",
    "phase ii",
    "fda",
    "ema approval",
    "breakthrough",
)

_ENTITY_CACHE: dict[str, tuple[float, list[str]]] = {}


def fulltext_pull_gate_enabled() -> bool:
    return env_bool("FULLTEXT_PULL_GATE_ENABLED", True)


def thin_link_hosts() -> frozenset[str]:
    raw = env_str(
        "FULLTEXT_PULL_THIN_HOSTS",
        ",".join(_DEFAULT_THIN_HOSTS),
    )
    hosts = {h.strip().lower() for h in raw.split(",") if h.strip()}
    return frozenset(hosts)


def interest_keywords() -> tuple[str, ...]:
    raw = env_str("FULLTEXT_PULL_INTEREST_KEYWORDS", "")
    if raw.strip():
        return tuple(k.strip().lower() for k in raw.split(",") if k.strip())
    return _DEFAULT_INTEREST_KEYWORDS


def host_from_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        return (urlparse(str(url).strip()).netloc or "").lower()
    except Exception:
        return ""


def is_thin_link_host(url: str | None) -> bool:
    host = host_from_url(url)
    if not host:
        return False
    for h in thin_link_hosts():
        if host == h or host.endswith("." + h):
            return True
    return False


def is_clinicaltrials_boilerplate(content: str | None) -> bool:
    low = (content or "").strip().lower()
    if not low:
        return False
    return any(n in low for n in _CTGOV_BOILERPLATE_NEEDLES)


def looks_like_false_enriched_thin(
    url: str | None,
    content: str | None,
    *,
    enrichment_status: str | None = None,
) -> bool:
    """
    True when a row was marked enriched but only has title-link junk
    (classic ClinicalTrials.gov trafilatura capture).
    """
    if not is_thin_link_host(url):
        return False
    body = (content or "").strip()
    if len(body) >= 400 and not is_clinicaltrials_boilerplate(body):
        return False
    es = (enrichment_status or "").strip().lower()
    if es and es not in ("enriched", "pending", "failed", ""):
        return False
    return len(body) < 400 or is_clinicaltrials_boilerplate(body)


def extract_nct_id(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"(NCT\d{8})", str(url), re.I)
    return m.group(1).upper() if m else None


def _load_subject_entity_names(schema: str, *, limit: int = 80) -> list[str]:
    now = time.time()
    cached = _ENTITY_CACHE.get(schema)
    if cached and now - cached[0] < 600:
        return cached[1]
    names: list[str] = []
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT canonical_name
                    FROM {schema}.entity_canonical
                    WHERE entity_type IN ('subject', 'condition', 'disease', 'concept')
                      AND LENGTH(TRIM(canonical_name)) >= 4
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall() or []
                names = [str(r[0]).strip() for r in rows if r and r[0]]
    except Exception as e:
        logger.debug("fulltext_pull_gate entity names %s: %s", schema, e)
    _ENTITY_CACHE[schema] = (now, names)
    return names


def evaluate_fulltext_pull(
    *,
    title: str | None,
    url: str | None,
    content: str | None = None,
    domain_key: str | None = None,
    schema: str | None = None,
    quality_score: float | None = None,
) -> dict[str, Any]:
    """
    Decide pull vs defer for a thin-link / title-only item.

    Returns dict with keys: decision ('pull'|'defer'|'not_applicable'),
    reason, metadata.
    """
    if not fulltext_pull_gate_enabled():
        return {"decision": "not_applicable", "reason": "gate_disabled", "metadata": {}}

    thin = is_thin_link_host(url)
    boilerplate = is_clinicaltrials_boilerplate(content)
    body_len = len((content or "").strip())

    if not thin and not boilerplate:
        # Substantial body already present — enrichment may still fetch, but gate N/A.
        if body_len >= 500:
            return {"decision": "not_applicable", "reason": "substantial_body", "metadata": {}}
        return {"decision": "not_applicable", "reason": "not_thin_link", "metadata": {}}

    title_l = (title or "").strip().lower()
    reasons: list[str] = []
    score = 0.0

    for kw in interest_keywords():
        if kw and kw in title_l:
            score += 1.5
            reasons.append(f"keyword:{kw}")
            break

    # Phase markers are high-signal for trial registries.
    if re.search(r"\bphase\s*(2|3|ii|iii)\b", title_l):
        score += 1.0
        reasons.append("phase_2_or_3")

    if schema:
        for name in _load_subject_entity_names(schema):
            n = name.lower()
            if len(n) >= 5 and n in title_l:
                score += 2.0
                reasons.append(f"entity:{name}")
                break

    if quality_score is not None and float(quality_score) >= 0.75 and body_len < 200:
        # High quality on thin body is usually a title-length artifact — ignore.
        pass

    min_score = float(env_str("FULLTEXT_PULL_MIN_SCORE", "1.0") or "1.0")
    meta = {
        "thin_host": thin,
        "boilerplate": boilerplate,
        "score": score,
        "reasons": reasons,
        "nct_id": extract_nct_id(url),
        "domain_key": domain_key,
    }
    if score >= min_score:
        return {"decision": "pull", "reason": "+".join(reasons) or "score", "metadata": meta}
    return {
        "decision": "defer",
        "reason": "below_interest_threshold",
        "metadata": meta,
    }


def triage_thin_link_articles(
    conn,
    *,
    domain_key: str,
    schema_name: str,
    limit: int = 40,
) -> dict[str, int]:
    """
    Title-only triage for thin-link hosts already in DB (incl. false 'enriched').

    pull → enrichment_status=pending (eligible for registry/API fetch)
    defer → enrichment_status=pull_deferred (skip LLM; phase out)
    """
    if not fulltext_pull_gate_enabled() or limit <= 0:
        return {"examined": 0, "pull": 0, "deferred": 0}

    hosts = sorted(thin_link_hosts())
    if not hosts:
        return {"examined": 0, "pull": 0, "deferred": 0}

    # Match host as substring of URL (clinicaltrials.gov).
    host_clauses = " OR ".join(["url ILIKE %s"] * len(hosts))
    host_params = [f"%{h}%" for h in hosts]
    boilerplate_sql = " OR ".join(
        ["LOWER(COALESCE(content,'')) LIKE %s" for _ in _CTGOV_BOILERPLATE_NEEDLES]
    )
    bp_params = [f"%{n}%" for n in _CTGOV_BOILERPLATE_NEEDLES]

    examined = pull_n = defer_n = 0
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, title, url, content, enrichment_status, quality_score
            FROM {schema_name}.articles
            WHERE ({host_clauses})
              AND (
                enrichment_status IS NULL
                OR enrichment_status IN ('pending', 'failed', 'enriched')
              )
              AND (
                LENGTH(COALESCE(content,'')) < 400
                OR ({boilerplate_sql})
              )
              AND COALESCE(
                    (metadata #>> '{{fulltext_pull,triaged}}')::boolean,
                    false
                  ) = false
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (*host_params, *bp_params, int(limit)),
        )
        rows = cur.fetchall() or []

    for row in rows:
        article_id, title, url, content, status, quality = row
        examined += 1
        verdict = evaluate_fulltext_pull(
            title=title,
            url=url,
            content=content,
            domain_key=domain_key,
            schema=schema_name,
            quality_score=float(quality) if quality is not None else None,
        )
        decision = verdict.get("decision")
        import json

        meta_patch = {
            "fulltext_pull": {
                "triaged": True,
                "decision": decision,
                "reason": verdict.get("reason"),
                "metadata": verdict.get("metadata") or {},
            }
        }
        if decision == "pull":
            new_status = STATUS_PENDING
            pull_n += 1
        else:
            new_status = STATUS_PULL_DEFERRED
            defer_n += 1

        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {schema_name}.articles
                SET enrichment_status = %s,
                    metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (new_status, json.dumps(meta_patch), int(article_id)),
            )
    if examined:
        conn.commit()
        logger.info(
            "fulltext_pull triage %s: examined=%s pull=%s deferred=%s",
            domain_key,
            examined,
            pull_n,
            defer_n,
        )
    return {"examined": examined, "pull": pull_n, "deferred": defer_n}


@lru_cache(maxsize=1)
def _feature_registered() -> bool:
    """Soft check — feature registry is documentation; gate uses env."""
    return True
