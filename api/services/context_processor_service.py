"""
Context processor service — Phase 1.2 context-centric pipeline.
Creates intelligence.contexts and article_to_context from domain articles.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Domain key -> schema name (same as rss_collector)
DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}


def _schema_for_domain(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


def ensure_context_for_article(domain_key: str, article_id: int) -> Optional[int]:
    """
    Ensure a context exists for the given domain article. Creates one if missing.
    Returns context_id if created or already present, else None on error.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.warning("Context processor: no DB connection")
        return None

    schema_name = _schema_for_domain(domain_key)
    try:
        with conn.cursor() as cur:
            # Already linked?
            cur.execute(
                """
                SELECT context_id FROM intelligence.article_to_context
                WHERE domain_key = %s AND article_id = %s
                """,
                (domain_key, article_id),
            )
            row = cur.fetchone()
            if row:
                conn.close()
                return row[0]

            # Fetch article
            cur.execute(
                f"""
                SELECT title, content, url, published_at, created_at
                FROM {schema_name}.articles WHERE id = %s
                """,
                (article_id,),
            )
            art = cur.fetchone()
            if not art:
                logger.debug(f"Article {domain_key}/{article_id} not found")
                conn.close()
                return None

            title, content, url, published_at, created_at = art
            title = (title or "")[:2000]
            content = (content or "")[:500000]
            raw_content = content

            # Insert context
            cur.execute(
                """
                INSERT INTO intelligence.contexts
                (source_type, domain_key, title, content, raw_content, metadata, created_at, updated_at)
                VALUES ('article', %s, %s, %s, %s, %s, COALESCE(%s, NOW()), NOW())
                RETURNING id
                """,
                (
                    domain_key,
                    title,
                    content,
                    raw_content,
                    json.dumps({"url": url, "published_at": str(published_at) if published_at else None}),
                    created_at,
                ),
            )
            context_id = cur.fetchone()[0]

            # Link article -> context
            cur.execute(
                """
                INSERT INTO intelligence.article_to_context (context_id, domain_key, article_id)
                VALUES (%s, %s, %s)
                """,
                (context_id, domain_key, article_id),
            )
            conn.commit()
            logger.debug(f"Context {context_id} created for {domain_key}.articles.{article_id}")
            conn.close()
            # Link context to entity_profiles via article_entities (Phase 1.3); non-fatal
            try:
                link_context_to_article_entities(context_id, domain_key, article_id)
            except Exception:
                pass
            return context_id
    except Exception as e:
        logger.warning(f"Context processor: ensure_context_for_article failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return None


def link_context_to_article_entities(context_id: int, domain_key: str, article_id: int) -> int:
    """
    Link a context to entity_profiles using article_entities (canonical_entity_id) and old_entity_to_new.
    Returns number of context_entity_mentions inserted. No-op if table 145 not applied or no entities.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return 0

    schema_name = _schema_for_domain(domain_key)
    linked = 0
    try:
        with conn.cursor() as cur:
            # article_entities with canonical_entity_id for this article
            cur.execute(
                f"""
                SELECT ae.canonical_entity_id, ae.confidence, ae.source_text_snippet
                FROM {schema_name}.article_entities ae
                WHERE ae.article_id = %s AND ae.canonical_entity_id IS NOT NULL
                """,
                (article_id,),
            )
            rows = cur.fetchall()
            for old_entity_id, confidence, snippet in rows:
                cur.execute(
                    """
                    SELECT entity_profile_id FROM intelligence.old_entity_to_new
                    WHERE domain_key = %s AND old_entity_id = %s
                    """,
                    (domain_key, old_entity_id),
                )
                profile_row = cur.fetchone()
                if not profile_row:
                    continue
                entity_profile_id = profile_row[0]
                conf = float(confidence) if confidence is not None else 0.8
                snippet_str = (snippet or "")[:1000]
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.context_entity_mentions
                        (context_id, entity_profile_id, confidence, source_snippet)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (context_id, entity_profile_id) DO UPDATE SET
                            confidence = EXCLUDED.confidence,
                            source_snippet = COALESCE(EXCLUDED.source_snippet, context_entity_mentions.source_snippet)
                        """,
                        (context_id, entity_profile_id, conf, snippet_str or None),
                    )
                    linked += 1
                except Exception as e:
                    if "does not exist" in str(e).lower():
                        break  # table 145 not applied
                    logger.debug(f"Context entity mention skip: {e}")
            conn.commit()
        conn.close()
        return linked
    except Exception as e:
        if "does not exist" in str(e).lower():
            pass
        else:
            logger.debug(f"link_context_to_article_entities: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return 0


def sync_domain_articles_to_contexts(domain_key: str, limit: int = 500) -> int:
    """
    Backfill: create contexts for articles in this domain that don't have one.
    Returns number of new contexts created.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.warning("Context processor: no DB connection for sync")
        return 0

    schema_name = _schema_for_domain(domain_key)
    created = 0
    try:
        with conn.cursor() as cur:
            # Articles without a context (not in article_to_context)
            cur.execute(
                f"""
                SELECT a.id, a.title, a.content, a.url, a.published_at, a.created_at
                FROM {schema_name}.articles a
                LEFT JOIN intelligence.article_to_context atc
                  ON atc.domain_key = %s AND atc.article_id = a.id
                WHERE atc.context_id IS NULL
                ORDER BY a.created_at DESC
                LIMIT %s
                """,
                (domain_key, limit),
            )
            rows = cur.fetchall()
            if not rows:
                conn.close()
                return 0

            for row in rows:
                article_id, title, content, url, published_at, created_at = row
                title = (title or "")[:2000]
                content = (content or "")[:500000]
                raw_content = content
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.contexts
                        (source_type, domain_key, title, content, raw_content, metadata, created_at, updated_at)
                        VALUES ('article', %s, %s, %s, %s, %s, COALESCE(%s, NOW()), NOW())
                        RETURNING id
                        """,
                        (
                            domain_key,
                            title,
                            content,
                            raw_content,
                            json.dumps({"url": url, "published_at": str(published_at) if published_at else None}),
                            created_at,
                        ),
                    )
                    context_id = cur.fetchone()[0]
                    cur.execute(
                        """
                        INSERT INTO intelligence.article_to_context (context_id, domain_key, article_id)
                        VALUES (%s, %s, %s)
                        """,
                        (context_id, domain_key, article_id),
                    )
                    created += 1
                    link_context_to_article_entities(context_id, domain_key, article_id)
                except Exception as e:
                    logger.debug(f"Context sync skip article {article_id}: {e}")
                    continue

            conn.commit()
        conn.close()
        if created > 0:
            logger.info(f"Context sync {domain_key}: {created} new contexts created")
        return created
    except Exception as e:
        logger.warning(f"Context processor: sync_domain failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return 0


def backfill_context_entity_mentions_for_domain(domain_key: str, limit: int = 500) -> int:
    """
    For existing article_to_context rows in this domain, (re)run link_context_to_article_entities
    so context_entity_mentions is populated after entity extraction / entity_profile_sync.
    Call after entity_profile_sync so old_entity_to_new is up to date.
    Returns number of contexts that got at least one new mention.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return 0
    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT context_id, article_id FROM intelligence.article_to_context
                WHERE domain_key = %s ORDER BY context_id DESC LIMIT %s
                """,
                (domain_key, limit),
            )
            rows = cur.fetchall()
        conn.close()
        for context_id, article_id in rows:
            n = link_context_to_article_entities(context_id, domain_key, article_id)
            if n > 0:
                updated += 1
        if updated > 0:
            logger.info(f"Context processor: backfill {domain_key} — {updated} contexts got entity mentions")
        return updated
    except Exception as e:
        logger.debug(f"Context processor backfill_context_entity_mentions: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return 0
