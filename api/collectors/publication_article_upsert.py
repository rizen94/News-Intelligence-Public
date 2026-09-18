"""
Shared upsert helpers for literature collectors (Europe PMC / PubMed).

Publication identity (doi / pmid / pmcid) when columns exist; else URL dedup.
Also upserts intelligence.processed_documents with citations when full text /
references are available.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any

import psycopg2.errors

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)


def _resolve_schema(domain_key: str) -> str:
    from shared.domain_registry import resolve_domain_schema

    return resolve_domain_schema(domain_key)


@lru_cache(maxsize=64)
def article_columns(schema: str) -> frozenset[str]:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = 'articles'
                    """,
                    (schema,),
                )
                return frozenset(str(r[0]) for r in cur.fetchall() or [])
    except Exception as e:
        logger.debug("article_columns(%s) failed: %s", schema, e)
        return frozenset()


def schema_exists(schema: str) -> bool:
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = %s LIMIT 1
                    """,
                    (schema,),
                )
                return bool(cur.fetchone())
    except Exception:
        return False


def clear_article_column_cache() -> None:
    article_columns.cache_clear()


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if len(s) >= 10:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = str(doi).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.lower().startswith(prefix):
            d = d[len(prefix) :]
            break
    d = d.strip()
    return d or None


def find_existing_article_id(
    cur,
    schema: str,
    *,
    doi: str | None = None,
    pmid: str | None = None,
    pmcid: str | None = None,
    url: str | None = None,
) -> int | None:
    cols = article_columns(schema)
    doi_n = _normalize_doi(doi)
    if doi_n and "doi" in cols:
        cur.execute(f"SELECT id FROM {schema}.articles WHERE doi = %s LIMIT 1", (doi_n,))
        row = cur.fetchone()
        if row:
            return int(row[0])
    if pmid and "pmid" in cols:
        cur.execute(f"SELECT id FROM {schema}.articles WHERE pmid = %s LIMIT 1", (str(pmid),))
        row = cur.fetchone()
        if row:
            return int(row[0])
    if pmcid and "pmcid" in cols:
        cur.execute(
            f"SELECT id FROM {schema}.articles WHERE pmcid = %s LIMIT 1",
            (str(pmcid),),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])
    if url:
        cur.execute(f"SELECT id FROM {schema}.articles WHERE url = %s LIMIT 1", (url,))
        row = cur.fetchone()
        if row:
            return int(row[0])
        if "canonical_url" in cols:
            cur.execute(
                f"SELECT id FROM {schema}.articles WHERE canonical_url = %s LIMIT 1",
                (url,),
            )
            row = cur.fetchone()
            if row:
                return int(row[0])
    return None


def upsert_publication_article(
    *,
    domain_key: str,
    title: str,
    url: str,
    content: str | None = None,
    summary: str | None = None,
    published_at: Any = None,
    source_domain: str = "europepmc.org",
    doi: str | None = None,
    pmid: str | None = None,
    pmcid: str | None = None,
    abstract_only: bool = True,
    authors: list[str] | None = None,
    metadata_extra: dict[str, Any] | None = None,
    study_design: str | None = None,
) -> int | None:
    """
    Insert or update one literature article. Returns article id or None.
    """
    title_clean = (title or "").strip()
    url_clean = (url or "").strip()
    if not title_clean or not url_clean:
        return None

    schema = _resolve_schema(domain_key)
    if not schema_exists(schema):
        logger.warning(
            "literature upsert: schema %s missing for domain_key=%s — skip",
            schema,
            domain_key,
        )
        return None

    cols = article_columns(schema)
    doi_n = _normalize_doi(doi)
    pub_date = _as_date(published_at)
    now = datetime.now(timezone.utc)
    body = (content or summary or title_clean)[:500_000]
    summary_text = (summary or body[:2000])[:8000]
    meta: dict[str, Any] = {
        "literature": True,
        "domain_key": domain_key,
        "doi": doi_n,
        "pmid": str(pmid) if pmid else None,
        "pmcid": str(pmcid) if pmcid else None,
        "abstract_only": bool(abstract_only),
        "authors": list(authors or [])[:40],
    }
    if study_design:
        meta["study_design"] = study_design
    if metadata_extra:
        meta.update(metadata_extra)

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                existing = find_existing_article_id(
                    cur,
                    schema,
                    doi=doi_n,
                    pmid=pmid,
                    pmcid=pmcid,
                    url=url_clean,
                )
                if existing:
                    sets = [
                        "title = %s",
                        "content = COALESCE(NULLIF(%s, ''), content)",
                        "summary = COALESCE(NULLIF(%s, ''), summary)",
                        "updated_at = NOW()",
                    ]
                    params: list[Any] = [title_clean[:500], body, summary_text]
                    if "metadata" in cols:
                        sets.append("metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb")
                        params.append(json.dumps(meta))
                    if "doi" in cols and doi_n:
                        sets.append("doi = COALESCE(doi, %s)")
                        params.append(doi_n)
                    if "pmid" in cols and pmid:
                        sets.append("pmid = COALESCE(pmid, %s)")
                        params.append(str(pmid))
                    if "pmcid" in cols and pmcid:
                        sets.append("pmcid = COALESCE(pmcid, %s)")
                        params.append(str(pmcid))
                    if "abstract_only" in cols:
                        sets.append("abstract_only = %s")
                        params.append(bool(abstract_only))
                    params.append(existing)
                    cur.execute(
                        f"UPDATE {schema}.articles SET {', '.join(sets)} WHERE id = %s",
                        params,
                    )
                    conn.commit()
                    return existing

                # Dynamic insert
                col_list = ["title", "url", "content", "summary", "created_at"]
                val_list: list[Any] = [
                    title_clean[:500],
                    url_clean,
                    body,
                    summary_text,
                    now,
                ]
                if "published_at" in cols and pub_date:
                    col_list.append("published_at")
                    val_list.append(datetime.combine(pub_date, datetime.min.time()).replace(
                        tzinfo=timezone.utc
                    ))
                if "source_domain" in cols:
                    col_list.append("source_domain")
                    val_list.append(source_domain[:255])
                if "enrichment_status" in cols:
                    col_list.append("enrichment_status")
                    val_list.append("pending")
                if "enrichment_attempts" in cols:
                    col_list.append("enrichment_attempts")
                    val_list.append(0)
                if "quality_score" in cols:
                    col_list.append("quality_score")
                    val_list.append(0.7)
                if "bias_score" in cols:
                    col_list.append("bias_score")
                    val_list.append(0.0)
                if "doi" in cols and doi_n:
                    col_list.append("doi")
                    val_list.append(doi_n)
                if "pmid" in cols and pmid:
                    col_list.append("pmid")
                    val_list.append(str(pmid))
                if "pmcid" in cols and pmcid:
                    col_list.append("pmcid")
                    val_list.append(str(pmcid))
                if "abstract_only" in cols:
                    col_list.append("abstract_only")
                    val_list.append(bool(abstract_only))
                if "metadata" in cols:
                    col_list.append("metadata")
                    val_list.append(json.dumps(meta))
                if "event_date" in cols and pub_date:
                    col_list.append("event_date")
                    val_list.append(
                        datetime.combine(pub_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                    )
                if "ingestion_date" in cols:
                    col_list.append("ingestion_date")
                    val_list.append(now)
                if "author" in cols and authors:
                    col_list.append("author")
                    val_list.append(", ".join(authors[:8])[:500])

                cols_sql = list(col_list)
                cast_ph = ["%s::jsonb" if c == "metadata" else "%s" for c in col_list]
                try:
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.articles ({', '.join(cols_sql)})
                        VALUES ({', '.join(cast_ph)})
                        RETURNING id
                        """,
                        val_list,
                    )
                except psycopg2.errors.UndefinedColumn:
                    conn.rollback()
                    clear_article_column_cache()
                    # Minimal fallback
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.articles (title, url, content, summary, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (title_clean[:500], url_clean, body, summary_text, now),
                    )
                row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else None
    except Exception as e:
        logger.warning("publication article upsert failed url=%s: %s", url_clean[:120], e)
        return None


def upsert_processed_document(
    *,
    source_url: str,
    title: str,
    source_type: str = "europepmc",
    source_name: str = "Europe PMC",
    document_type: str = "research_paper",
    publication_date: Any = None,
    authors: list[str] | None = None,
    citations: list[Any] | None = None,
    extracted_sections: list[Any] | None = None,
    abstract_only: bool = False,
    metadata_extra: dict[str, Any] | None = None,
    full_text: str | None = None,
) -> int | None:
    """Upsert intelligence.processed_documents by source_url; set citations when provided."""
    url = (source_url or "").strip()
    if not url:
        return None
    pub = _as_date(publication_date)
    meta: dict[str, Any] = {
        "abstract_only": bool(abstract_only),
        "literature": True,
    }
    if metadata_extra:
        meta.update(metadata_extra)
    sections = list(extracted_sections or [])
    if full_text and not sections:
        sections = [{"heading": "full_text", "content": full_text[:200_000]}]
    citations_json = json.dumps(citations or [])
    sections_json = json.dumps(sections)
    authors_arr = list(authors or [])[:50]

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM intelligence.processed_documents
                    WHERE source_url = %s LIMIT 1
                    """,
                    (url,),
                )
                row = cur.fetchone()
                if row:
                    doc_id = int(row[0])
                    cur.execute(
                        """
                        UPDATE intelligence.processed_documents SET
                            title = COALESCE(NULLIF(%s, ''), title),
                            publication_date = COALESCE(%s, publication_date),
                            authors = CASE WHEN %s::text[] = '{}'::text[] THEN authors ELSE %s::text[] END,
                            citations = CASE
                                WHEN %s::jsonb = '[]'::jsonb THEN citations
                                ELSE %s::jsonb
                            END,
                            extracted_sections = CASE
                                WHEN %s::jsonb = '[]'::jsonb THEN extracted_sections
                                ELSE %s::jsonb
                            END,
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            (title or "")[:2000],
                            pub,
                            authors_arr,
                            authors_arr,
                            citations_json,
                            citations_json,
                            sections_json,
                            sections_json,
                            json.dumps(meta),
                            doc_id,
                        ),
                    )
                    conn.commit()
                    return doc_id
                cur.execute(
                    """
                    INSERT INTO intelligence.processed_documents (
                        source_type, source_name, source_url, title, publication_date,
                        authors, document_type, extracted_sections, citations, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s::text[], %s, %s::jsonb, %s::jsonb, %s::jsonb
                    )
                    RETURNING id
                    """,
                    (
                        source_type[:50],
                        source_name[:255],
                        url,
                        (title or "")[:2000],
                        pub,
                        authors_arr,
                        document_type[:50],
                        sections_json,
                        citations_json,
                        json.dumps(meta),
                    ),
                )
                new_row = cur.fetchone()
            conn.commit()
            return int(new_row[0]) if new_row else None
    except Exception as e:
        logger.warning("processed_documents upsert failed url=%s: %s", url[:120], e)
        return None
