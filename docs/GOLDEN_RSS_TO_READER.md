# Golden trace: RSS → readable material

**Authority for product/pipeline “done”.** Agents: skill **`ni-golden-trace`**. Complements `RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2 (ops health), not a substitute.

## When this applies

Any work on **reader feed**, **briefs**, **RSS intake → user-visible story**, **pipeline “not processing”** (not pure Grafana/infra-only tickets).

## Definition of done

A fix is **not** complete until **one golden `article_id`** (named in chat) has been traced on **Widow `news_intel`**:

| Stage | What to prove |
|-------|----------------|
| 1 Intake | Row in `{schema}.articles` (title, `created_at`) |
| 2 Enrichment | `summary` or body signals usable for dek (length/gate per `home_feed._dek_from_row`) |
| 3 Storyline | Optional for raw fallback; required for arc UX: `storyline_articles` + `storylines` |
| 4 Editorial | `editorial_document` / refinement timestamps when storyline path |
| 5 Reader | `GET /api/reader/home` (same host as SPA) shows item in intended section **or** explicit “blocked at stage N” with journal excerpt |

**Ops-only changes** (Grafana, run history schema, unrelated refactors) do **not** satisfy this checklist unless the ticket was ops-only.

## Pick the golden article

```sql
-- Latest politics intake (adjust schema)
SELECT id, title, created_at, length(COALESCE(summary,'')) AS summary_len
FROM politics.articles
ORDER BY created_at DESC
LIMIT 5;
```

Record `golden_article_id` in the handoff / first chat proof block.

**Current golden (politics, 2026-11-11):** **`401605`** — title starts “OpenAI president Greg Brockman…”; `content` populated, `summary` empty, not in `storyline_articles`. Re-pick if this id is gone.

## Stage SQL (template — `politics` / `:id`)

```sql
-- 1 Intake
SELECT id, title, created_at, published_at FROM politics.articles WHERE id = :id;

-- 2 Enrichment
SELECT id, length(COALESCE(summary,'')) AS summary_len,
       length(COALESCE(content,'')) AS content_len
FROM politics.articles WHERE id = :id;

-- 3 Storyline bridge
SELECT sa.storyline_id, sa.added_at
FROM politics.storyline_articles sa WHERE sa.article_id = :id;

SELECT s.id, s.title, s.updated_at, s.last_refinement,
       left(s.editorial_document::text, 200) AS editorial_snippet
FROM politics.storylines s
JOIN politics.storyline_articles sa ON sa.storyline_id = s.id
WHERE sa.article_id = :id;

-- 5 Reader contract (run on Widow or public URL)
curl -sS "http://127.0.0.1:8000/api/reader/home?domain=politics&section=news&page_size=50" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('news',[])), d.get('news',[])[:2])"
```

Reader rules: `api/domains/reader/services/home_feed.py` — News needs recent `material_at`, non-empty **dek**, not membership-only bumps.

## Root cause discipline

1. **Find the first failing stage** for the golden row (do not patch downstream).
2. **One primary hypothesis** per Act session; falsify with one command each.
3. **Forbidden as “fixed”:** scheduling-only, monitoring-only, COUNT(\*) without golden row, handoff without deploy + stage movement.
4. **Widow runtime:** product claims need deploy (`ni-ship-widow`) + re-run stage SQL on the **same** `article_id`.

## Related docs

- `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` — services, heartbeats, run history
- `docs/PIPELINE_AND_AUTOMATION.md` — phase behavior
- `docs/MONITOR_REPORTING_AND_METRICS.md` — what Grafana vs reader own
