"""
Document acquisition — T3.1.
Ingest document metadata + URL from config (document_sources.ingest_urls) or from explicit
payload; insert into intelligence.processed_documents. No heavy PDF fetch/parse yet.
See docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md, V6_QUALITY_FIRST_TODO.md Tier 3.
"""

import json
import logging
from datetime import date
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


def ingest_from_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Read document_sources.ingest_urls from config; for each entry (url or {url, title, ...}),
    insert a row into processed_documents (metadata only). Returns { inserted: int, errors: [] }.
    """
    if config is None:
        try:
            from config.orchestrator_governance import get_orchestrator_governance_config

            config = get_orchestrator_governance_config()
        except Exception as e:
            logger.warning("document_acquisition: config load failed: %s", e)
            return {"inserted": 0, "errors": ["Config unavailable"]}

    doc_sources = config.get("document_sources") or {}
    urls = doc_sources.get("ingest_urls") or []
    if not urls:
        return {"inserted": 0, "errors": []}

    conn = get_db_connection()
    if not conn:
        return {"inserted": 0, "errors": ["Database unavailable"]}

    inserted = 0
    errors: list[str] = []
    try:
        with conn.cursor() as cur:
            for entry in urls:
                if isinstance(entry, str):
                    row = {"source_url": entry, "title": None, "source_type": None}
                elif isinstance(entry, dict):
                    row = {
                        "source_url": entry.get("url") or entry.get("source_url"),
                        "title": entry.get("title"),
                        "source_type": entry.get("source_type"),
                        "source_name": entry.get("source_name"),
                        "document_type": entry.get("document_type"),
                        "publication_date": entry.get("publication_date"),
                    }
                else:
                    errors.append("Invalid ingest entry (not string or dict)")
                    continue
                url = row.get("source_url")
                if not url:
                    errors.append("Missing url in ingest entry")
                    continue
                pub = row.get("publication_date")
                if isinstance(pub, str):
                    try:
                        from datetime import datetime

                        pub = datetime.fromisoformat(pub.replace("Z", "+00:00")).date()
                    except (ValueError, TypeError):
                        pub = None
                elif not isinstance(pub, date):
                    pub = None
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.processed_documents
                        (source_type, source_name, source_url, title, document_type, publication_date)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            row.get("source_type"),
                            row.get("source_name"),
                            url,
                            row.get("title"),
                            row.get("document_type"),
                            pub,
                        ),
                    )
                    inserted += 1
                except Exception as e:
                    errors.append(f"{url}: {e}")
        conn.commit()
    except Exception as e:
        logger.exception("ingest_from_config: %s", e)
        errors.append(str(e))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {"inserted": inserted, "errors": errors}


def create_document(
    source_url: str,
    title: str | None = None,
    source_type: str | None = None,
    source_name: str | None = None,
    document_type: str | None = None,
    publication_date: date | None = None,
    authors: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    publication_date_str: str | None = None,
) -> dict[str, Any]:
    """
    Insert one processed_document from given metadata. Returns { success, document_id, error }.
    publication_date can be date or ISO date string via publication_date_str.
    """
    if publication_date is None and publication_date_str:
        try:
            from datetime import datetime

            publication_date = datetime.fromisoformat(
                publication_date_str.replace("Z", "+00:00")
            ).date()
        except (ValueError, TypeError):
            pass
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database unavailable"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.processed_documents
                (source_type, source_name, source_url, title, document_type, publication_date, authors, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    source_type,
                    source_name,
                    source_url,
                    title,
                    document_type,
                    publication_date,
                    authors or [],
                    json.dumps(metadata or {}),
                ),
            )
            doc_id = cur.fetchone()[0]
        conn.commit()
        return {"success": True, "document_id": doc_id}
    except Exception as e:
        logger.exception("create_document: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
    finally:
        try:
            conn.close()
        except Exception:
            pass
