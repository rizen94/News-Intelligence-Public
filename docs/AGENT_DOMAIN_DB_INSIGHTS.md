# Agent domain DB insights (Postgres MCP)

Guide for **local agents** (Cursor, Continue, Open WebUI) to query **News Intelligence** per domain via **`postgres-mcp`**.

## Connection

| Item | Value |
|------|--------|
| MCP server | **`postgres-mcp`** (Cursor: `user-postgres-mcp`) |
| Database | **`news_intel`** on Widow `192.168.93.101` |
| Access | **Read-only** via Homelab `NEWS_INTEL_DATABASE_URI` |
| Not NI | Homelab local Postgres `:15432` — different database |

**Tools:** `list_schemas`, `list_objects`, `get_object_details`, `execute_sql`

Always call `list_objects` / `get_object_details` before guessing column names.

## Domain map

Resolve schema from registry — do not hardcode retired silos (`science-tech` / `science_tech` dropped).

```sql
SELECT domain_key, schema_name, name, is_active
FROM public.domains
WHERE is_active
ORDER BY display_order, domain_key;
```

| domain_key | schema_name | Typical focus |
|------------|-------------|---------------|
| `politics` | `politics` | Policy, elections, geopolitics |
| `finance` | `finance` | Markets, macro, commodities |
| `legal` | `legal` | Courts, regulation, litigation |
| `medicine` | `medicine` | Clinical research, public health |
| `artificial-intelligence` | `artificial_intelligence` | Models, policy, industry |

**Per-domain tables** (same shape in each `{schema}`):

- `articles`, `storylines`, `topic_clusters`, `article_topic_clusters`
- `rss_feeds`, `events` (legacy `topics` is read-only)

**Cross-domain / global:**

- `intelligence.entity_profiles`, `intelligence.entity_dossiers`, `intelligence.contexts`
- `intelligence.investigation_*` (FtM resolver — not `nri.*`)
- `public.automation_run_history`, `pipeline.pipeline_traces`

## Agent rules

1. **`SELECT` only** — no writes via MCP.
2. **Always `LIMIT`** (10–50 for samples, 100 max for aggregates unless user asks).
3. **Qualify schemas** — `{schema}.articles`, not bare `articles`.
4. **Time windows** — default `NOW() - INTERVAL '7 days'`; widen only when user asks.
5. **Facts vs workspace** — Postgres is canonical; Obsidian news vault is scratchpad only.
6. **No `nri.` schema** — use `intelligence.investigation_*`.

## Query 1 — Domain snapshot (all silos)

```sql
SELECT d.domain_key,
       (SELECT COUNT(*) FROM politics.articles) FILTER (WHERE d.schema_name = 'politics') AS placeholder
FROM public.domains d WHERE is_active;
-- Prefer explicit union (validated):
SELECT 'politics' AS domain_key, COUNT(*) AS articles,
       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') AS articles_7d,
       COUNT(*) FILTER (WHERE sentiment_score IS NOT NULL) AS analyzed
FROM politics.articles
UNION ALL
SELECT 'finance', COUNT(*),
       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days'),
       COUNT(*) FILTER (WHERE sentiment_score IS NOT NULL)
FROM finance.articles
UNION ALL
SELECT 'legal', COUNT(*),
       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days'),
       COUNT(*) FILTER (WHERE sentiment_score IS NOT NULL)
FROM legal.articles
UNION ALL
SELECT 'medicine', COUNT(*),
       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days'),
       COUNT(*) FILTER (WHERE sentiment_score IS NOT NULL)
FROM medicine.articles
UNION ALL
SELECT 'artificial-intelligence', COUNT(*),
       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days'),
       COUNT(*) FILTER (WHERE sentiment_score IS NOT NULL)
FROM artificial_intelligence.articles
ORDER BY 1;
```

## Query 2 — Hot storylines in one domain

Replace `{schema}` (e.g. `politics`, `finance`).

```sql
SELECT id, title, article_count, quality_score, status, updated_at,
       LEFT(COALESCE(canonical_narrative, summary, description), 300) AS narrative_preview
FROM {schema}.storylines
WHERE status = 'active'
  AND merged_into_id IS NULL
  AND updated_at >= NOW() - INTERVAL '14 days'
ORDER BY updated_at DESC, article_count DESC
LIMIT 15;
```

## Query 3 — Recent high-signal articles in one domain

```sql
SELECT id, title, source_domain, published_at, sentiment_score,
       LEFT(content, 200) AS excerpt
FROM {schema}.articles
WHERE content IS NOT NULL AND LENGTH(content) > 200
  AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY published_at DESC NULLS LAST, created_at DESC
LIMIT 20;
```

## Query 4 — Top topic clusters in one domain

```sql
SELECT tc.id, tc.cluster_name, tc.article_count, tc.confidence_score, tc.updated_at
FROM {schema}.topic_clusters tc
WHERE tc.article_count > 0
ORDER BY tc.updated_at DESC NULLS LAST, tc.article_count DESC
LIMIT 20;
```

## Query 5 — Entity profiles in one domain

```sql
SELECT ep.canonical_entity_id,
       ep.metadata->>'canonical_name' AS name,
       ep.metadata->>'entity_type' AS entity_type,
       ep.updated_at
FROM intelligence.entity_profiles ep
WHERE ep.domain_key = 'politics'   -- change per domain
ORDER BY ep.updated_at DESC NULLS LAST
LIMIT 20;
```

## Query 6 — Cross-domain entity (same name in 2+ silos)

```sql
SELECT ep.metadata->>'canonical_name' AS name,
       array_agg(DISTINCT ep.domain_key ORDER BY ep.domain_key) AS domains,
       COUNT(DISTINCT ep.domain_key) AS domain_count
FROM intelligence.entity_profiles ep
WHERE ep.metadata->>'canonical_name' IS NOT NULL
GROUP BY 1
HAVING COUNT(DISTINCT ep.domain_key) >= 2
ORDER BY domain_count DESC, name
LIMIT 25;
```

## Query 7 — Pipeline health (global)

```sql
SELECT phase, COUNT(*) AS runs_24h,
       ROUND(100.0 * COUNT(*) FILTER (WHERE success) / NULLIF(COUNT(*), 0), 1) AS pass_pct
FROM public.automation_run_history
WHERE started_at >= NOW() - INTERVAL '24 hours'
GROUP BY phase
ORDER BY runs_24h DESC
LIMIT 20;
```

## Query 8 — Per-domain storyline counts

```sql
SELECT 'politics' AS domain, COUNT(*) AS storylines,
       COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days') AS updated_7d
FROM politics.storylines
UNION ALL SELECT 'finance', COUNT(*), COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days') FROM finance.storylines
UNION ALL SELECT 'legal', COUNT(*), COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days') FROM legal.storylines
UNION ALL SELECT 'medicine', COUNT(*), COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days') FROM medicine.storylines
UNION ALL SELECT 'artificial-intelligence', COUNT(*), COUNT(*) FILTER (WHERE updated_at >= NOW() - INTERVAL '7 days') FROM artificial_intelligence.storylines
ORDER BY 1;
```

## Suggested agent workflow

1. **`list_schemas`** — confirm active domain schemas.
2. **Domain snapshot** (Query 1 + 8) — volume and storyline activity.
3. **Pick domain(s)** from user question → run Queries 2–5 with correct `{schema}` / `domain_key`.
4. **Cross-domain** (Query 6) when topic spans silos.
5. **Summarize in prose** — cite counts, titles, dates; link entity names to `ftm_id` / `canonical_entity_id` if investigating further.

## Optional: API RAG (when MCP is not enough)

For natural-language Q&A over recent articles (not raw SQL):

- `POST /api/{domain}/rag/query` — see `api/domains/intelligence_hub/routes/rag_queries.py`
- Requires NI API on Widow `:8000`, not Postgres MCP alone.

## Related

- [DATABASE.md](DATABASE.md) — schema layout
- [../AGENTS.md](../AGENTS.md) — terminology
- `HomeLab-AI-Stack/docs/NEWS_VAULT_AGENT.md` — Open WebUI investigator setup
- `HomeLab-AI-Stack/docs/prompts/news-editorial-automation.md` — vault gap workflow
