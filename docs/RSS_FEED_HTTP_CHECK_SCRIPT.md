# RSS feed HTTP check script — summary for link review

Hand this document to a reviewer (e.g. Claude) along with the CSV produced by the script. The reviewer can validate or replace URLs against current publisher RSS/Atom endpoints.

---

## What RSS feeds are used for (News Intelligence)

| Role | Description |
|------|-------------|
| **Primary news intake** | Scheduled **`collect_rss_feeds()`** (automation `collection_cycle` and/or orchestrator) reads every **active** row in **`{domain}.rss_feeds`** for each domain in **`shared.domain_registry`** (built-ins + active YAML under `api/config/domains/*.yaml`). |
| **Per-domain silos** | Each domain has its own Postgres schema (e.g. `politics`, `finance`, `science_tech`). Feeds in `politics.rss_feeds` populate **`politics.articles`** only — not mixed with other domains. |
| **Downstream pipeline** | New rows drive content enrichment, optional **`ensure_context_for_article`** at ingest, entity extraction, storylines, events, etc. **If a feed URL returns nothing useful, that silo gets no new articles from that feed.** |
| **Seeding** | Initial URLs often come from **`data_sources.rss.seed_feed_urls`** in domain YAML, applied by **`provision_domain.py`** or **`seed_domain_rss_from_yaml.py`**. Live URLs live in **`{schema}.rss_feeds`** (`feed_url`, `is_active`). |

**Not covered by this script:** Finance-specific collectors, PDF/document sources, or manual article APIs — only **HTTP checks for URLs stored in `rss_feeds`**.

---

## Script: `api/scripts/check_rss_feed_http_status.py`

**Purpose:** For every active RSS feed row in the database, perform several **GET** requests (default **3**) with a browser-like **User-Agent**, same as “curling” the link multiple times. Record **HTTP status**, **success flag**, **latency**, **errors** (DNS, TLS, timeout), **Content-Type**, and **response body size**.

**Requirements:** Database env vars as for the API (`DB_*`). **`PYTHONPATH=api`**.

**Typical run:**

```bash
cd /path/to/News Intelligence
PYTHONPATH=api uv run python api/scripts/check_rss_feed_http_status.py \
  --attempts 3 --timeout 20 -o rss_feed_probe.csv
```

**Useful flags:**

| Flag | Meaning |
|------|---------|
| `--attempts N` | Number of GETs per feed (default 3). |
| `--timeout SEC` | Per-request timeout (default 20). |
| `--pause SEC` | Delay between attempts for the same feed (default 0.4). |
| `--include-inactive` | Also probe rows with `is_active = false`. |
| `-o FILE` | Write CSV to `FILE`. |
| `--csv-only` | With `-o`, suppress stderr summary. |

Optional env: **`RSS_FEED_CHECK_USER_AGENT`** — custom User-Agent if sites block the default.

---

## Output format (CSV columns)

| Column | Meaning |
|--------|---------|
| `domain_key` | URL/API domain key (e.g. `politics`, `science-tech`, `artificial-intelligence`). |
| `schema` | Postgres schema for that silo (e.g. `science_tech`). |
| `feed_id` | Primary key in `{schema}.rss_feeds`. |
| `feed_name` | Human label in DB. |
| `feed_url` | Stored URL probed. |
| `is_active` | Whether the row is active in DB (`true`/`false`). |
| `attempt` | 1..N for the Nth GET for that feed. |
| `http_status` | Numeric status if a response was received (e.g. `200`, `404`); may be empty on connection errors. |
| `ok` | `True` if `requests` considers the response successful (typically **2xx–3xx**). |
| `elapsed_ms` | Round-trip time in milliseconds. |
| `error` | Exception message if no normal HTTP response (e.g. DNS, SSL, timeout). Empty if none. |
| `content_type` | `Content-Type` header (truncated). |
| `bytes_len` | Size of response body in bytes. |

**Stderr summary (unless `--csv-only`):** number of feeds probed and how many were **problematic on the last attempt** (non-OK HTTP, 4xx/5xx, or any `error` string).

---

## How a reviewer should interpret results

1. **`ok=True` + `text/xml` or `application/rss+xml` / `atom+xml` + reasonable `bytes_len`** — Strong signal the URL is a real feed endpoint (still verify items parse in a reader if unsure).
2. **`ok=True` + `text/html`** — Server returned a web page, not necessarily RSS. May still be a redirect or wrong path; **flag for manual check** or replace with the site’s documented RSS URL.
3. **`http_status` 404 / 410** — Endpoint removed or retired; **replace the URL** or deactivate the feed in DB.
4. **`error` contains `NameResolutionError` / DNS** — Hostname did not resolve on the machine that ran the script. Can be local network/DNS; **retry from the production collector host** (e.g. Widow) before deleting a URL that works elsewhere.
5. **`SSLError` / TLS errors** — Certificate, interception, or outdated TLS; **network or client** issue as well as bad URL.
6. **Inconsistent results across `attempt` 1..N** — Rate limiting or transient failures; consider increasing `--pause` or `--timeout`.

---

## What to return after review

For each problematic row, ideally note:

- **`feed_id` + `schema` (or `domain_key`)** — to update the correct DB row.
- **Recommended replacement `feed_url`** (or “deactivate — no public RSS”).
- **Short reason** (404, HTML landing page, DNS from test host only, etc.).

Updates can be done via SQL on `{schema}.rss_feeds`, or by editing domain YAML and re-seeding per `docs/DOMAIN_EXTENSION_TEMPLATE.md` / `api/config/domains/README.md`.

---

## Bulk refresh (Mar 2026 operator review)

A reviewed set of replacements (working URLs, Yahoo fallbacks for dead AP/Reuters hostnames, Reuters `arc/outboundfeeds` paths, deactivations for discontinued feeds, medicine/AI URL fixes) is in:

- **`api/database/migrations/192_rss_feed_url_refresh_reviewed.sql`**
- Runner: **`PYTHONPATH=api uv run python api/scripts/run_migration_192.py`**

The migration matches **`id` + `feed_name` ILIKE** so rows that do not match (different `id` order on another DB) are skipped safely. After apply, register ledger id **192** if you use `applied_migrations`.

**YAML aligned for new seeds:** `api/config/domains/medicine.yaml`, `api/config/domains/artificial-intelligence.yaml`.

**Politics / finance** feeds are not in domain YAML in this repo (DB-only history); use the migration or manual SQL for those silos.
