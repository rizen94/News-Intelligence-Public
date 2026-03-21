# Article Updates and Deduplication

## Do enhancement and RAG use original article links?

**No.** Both use **stored database content only**:

- **RAG** (`api/services/rag/domain.py`, `retrieval.py`) builds chunks from `article['content']`, `article['title']`, etc. as read from the DB. It does not re-fetch from `article.url`.
- **Enhancement** (e.g. entity extraction, topic clustering, context processor) runs on the article row in the DB. The only place we fetch from the article URL is during **initial ingestion** (e.g. `article_processing_service._fetch_article_content`, `rss_collector_tracking._extract_article_content`, `enhanced_rss_collector.extract_article_content`) when we first pull a feed or process a new item.

So if a publisher **updates an article at the same URL**, our copy stays old unless we refresh it at ingestion time.

---

## Is the deduplicator aware of “same URL, updated content”?

**No.** Current behavior:

| Location | Behavior when same URL seen again |
|----------|-----------------------------------|
| **`api/services/rss/fetching.py`** | `_is_duplicate()`: URL match → **skip** (article not saved). `_save_article()` uses `ON CONFLICT (url) DO NOTHING`, so no update. |
| **`api/collectors/rss_collector.py`** | Duplicate check: `WHERE url = %s OR (title = %s AND source_domain = %s)` → if match, **skip** (increment duplicates_rejected, continue). No UPDATE. |
| **`api/services/rss/processing.py`** | When URL exists: **UPDATE** (title, content, content_hash, updated_at). This path does refresh; it may not be the one used by the main production collector. |

So in the **main RSS collection path** (rss_collector and rss/fetching): same URL is treated as a duplicate and **never updated**. The deduplicator is **not** aware of:

- Feed `updated_parsed` (article updated at source)
- Content hash change (body changed at same URL)

Result: updated versions of an article at the same URL are skipped; enhancement and RAG keep using the old stored copy.

---

## Change made: update-aware deduplication in RSS collector

The main domain-aware collector (`api/collectors/rss_collector.py`) was updated so that when an article is considered a “duplicate” by URL:

1. We fetch the existing row (id, content, published_at, updated_at if present).
2. We compute a content hash for the **new** snippet from the feed.
3. If the feed provides `updated_parsed` and it is **newer** than the existing article’s `published_at` (or `updated_at`), we treat it as an update.
4. If the content hash of the new snippet **differs** from the existing content (or existing content is empty), we treat it as an update.
5. When either condition holds, we **UPDATE** the existing row (title, content, summary, published_at, quality/bias scores, updated_at) instead of skipping. Optionally we re-queue for topic extraction and context so enhancement and RAG see the new content.

So the deduplicator is now **aware** of “same URL but updated or changed content” and will refresh the stored article when appropriate.

---

## Optional: re-fetch from article URL

For a stronger guarantee (e.g. full body changed but RSS snippet unchanged), we could:

- Add a job that periodically re-fetches **selected** articles from `article.url` (e.g. by `updated_at` or a “needs_refresh” flag).
- Or, when we decide to “update” by URL, call an existing full-page fetcher (e.g. `extract_article_content` in `enhanced_rss_collector` or `_extract_article_content` in `rss_collector_tracking`) and store that as the new content.

That would be a separate enhancement; the change above uses only the RSS entry (title/summary/updated_parsed) and content hash to decide when to update.
