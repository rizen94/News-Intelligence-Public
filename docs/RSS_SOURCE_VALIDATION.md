# RSS source validation (June 2026)

HTTP + feedparser validation of domain spec feeds (`api/config/domains/specs/*.domain.json`) and `news-intelligence-kit/config/setup/feed_hints.yaml`, run from Widow dev host.

**Apply DB changes:** migration **`248_rss_environment_feeds_and_url_fixes.sql`** on Widow Postgres `:5432`, then regenerate YAML if needed:

```bash
cd /path/to/News\ Intelligence
PYTHONPATH=api uv run python api/scripts/generate_domain_artifacts.py --domain politics
psql -h localhost -p 5432 -U newsapp -d news_intel -f api/database/migrations/248_rss_environment_feeds_and_url_fixes.sql
```

---

## Already in `politics.rss_feeds` (spec politics feeds)

All 17 original politics spec URLs were already present and active. Two URLs were **fixed in spec + migration 248**:

| Feed | Old URL | New URL |
|------|---------|---------|
| CSIS Analysis | `/analysis/feed` (404) | `https://www.csis.org/rss.xml` |
| Politico | `politico.com/.../politics08.xml` (403) | `https://rss.politico.com/politics-news.xml` |

---

## Added to `politics.rss_feeds` (from environment-climate spec)

`environment-climate` is **not** a pipeline silo (only five active domains). Valid environment feeds are routed into **politics** with `category = Environment`:

| Feed | URL | Validation |
|------|-----|------------|
| Carbon Brief | `https://www.carbonbrief.org/feed` | 200, 10+ entries |
| Climate.gov | `https://www.climate.gov/rss.xml` | 200, RSS |
| E&E News | `https://www.eenews.net/articles/feed/` | 200, RSS |
| Guardian Environment | `https://www.theguardian.com/environment/rss` | 200, RSS |
| Nature Climate | `https://www.nature.com/nclimate.rss` | 200, RSS |

---

## Other URL fixes (migration 248)

| Domain | Feed | Fix |
|--------|------|-----|
| artificial-intelligence | LangChain Blog | `blog.langchain.dev/rss/` → `blog.langchain.com/rss/` |
| medicine | FDA press releases | path under `about-fda/.../press-releases/rss.xml` |
| medicine | JAMA | `feeds/journals/jama` (403) → `rss/site_3/67.xml` |

---

## Valid RSS — no action (already seeded or working)

**Legal (8/8 spec):** Federal Register*, SCOTUSblog, Universal Hub, ABA Journal, Courthouse News, Jurist, Lexblog, Above the Law — *Federal Register returned HTTP 500 intermittently; retry from collector host.

**Medicine:** NEJM, Lancet, Nature Medicine, WHO news, ClinicalTrials.gov, medRxiv, bioRxiv — PubMed saved-search URLs return HTML landing pages (see non-RSS below).

**AI (32/34 active in DB):** arXiv lanes, OpenAI/Google/HF/MIT, Substack newsletters, most vendor blogs — see HTML/broken rows below.

**Politics (working):** Foreign Affairs, Foreign Policy, ICG, Atlantic Council, War on the Rocks, BBC/Guardian/FT/Economist world, Al Jazeera, Carnegie (Solr XML).

---

## No reliable public RSS — incorporation plan

These sources **do not offer a stable, automatable RSS/Atom endpoint** (blocked, retired, HTML-only, or licensed API only). Do **not** add as `{schema}.rss_feeds` until an alternate ingest path exists.

| Source | Spec / hint URL | Issue | Recommended ingest |
|--------|-----------------|-------|-------------------|
| **Reuters** (world, commodities, Arc) | `feeds.reuters.com`, `reuters.com/.../rss`, Arc outbound | DNS failure / 401 / Arc retired (migration 202) | **No free RSS.** Options: (1) licensed Reuters Connect/API if budget allows; (2) cross-link from BBC/Guardian/AP wire rewrite storylines; (3) manual `document_download_service` for PDF/HTML press releases; (4) defer. |
| **AP Top News** | `rsshub.app/apnews/...` | RSSHub 403; `apnews.com?output=rss` empty/redirect | **AP News API** (commercial) or ingest via **Yahoo/AP syndication** partner feeds if legally available; otherwise skip wire. |
| **Lawfare** | `lawfaremedia.org/rss.xml` | 403 bot block from probe host | Retry with production `RSS_COLLECTOR_USER_AGENT`; if still blocked use **`document_download_service`** on article pages from search/vault cues, or **email/newsletter** forward. |
| **Chatham House** | `chathamhouse.org/rss.xml` | 403 | Same as Lawfare — collector UA test; fallback periodic scrape of `/publications` with rate limit (new collector, not RSS). |
| **IEA News** | `iea.org/news/rss` | 403 | **IEA data services / email alerts**; no public RSS. Use **`trade_resources_import_service`** pattern for structured data; news via manual or GovDelivery if subscribed. |
| **USGS News** | `usgs.gov/news/all-news/rss` | 404 (path retired) | **USGS GovDelivery** topic RSS (per-topic signup) or **`gpr_epu_import_service`-style** CSV/API for minerals; news via `https://www.usgs.gov/news/news-release` HTML crawl. |
| **EPA News** | `epa.gov/newsreleases/rss.xml` | 404 | **`epa.gov/newsreleases/search/feed`** returns 202/empty — not useful. Use **GovDelivery EPA topics** or Federal Register EPA rule RSS once FR API stable. |
| **Environmental Health News** | `environmentalhealthnews.org/feed/` | TLS handshake failure | Fix client TLS / try from prod; else **weekly scrape** or drop. |
| **BMJ** | `bmj.com/content/current.rss` | 404 (paywall) | **No open RSS.** PubMed citation alerts or institutional access scrape — low priority. |
| **PubMed saved searches** (3 URLs) | `pubmed.ncbi.nlm.nih.gov/rss/create/...` | HTML UI, not direct XML in probe | Create feeds via PubMed UI **“Create RSS”** per search, copy **generated** XML URL; or use **NCBI E-utilities** (`esearch` + `efetch`) on schedule — better than RSS. |
| **Federal Register** | `federalregister.gov/.../search.rss` | HTTP 500 intermittent | **`federal_register` API** (already in legal stack docs) or retry RSS off-peak; legal silo already has this feed. |
| **Cohere / Google Cloud AI / Stability / HAI Stanford** | various | HTML landing, not XML | Find vendor blog Atom (`blog.langchain.com` pattern) or **deactivate**; monitor via existing AI newsletters (Import AI, Latent Space). |
| **Reuters Agency** (feed_hints) | `reutersagency.com/feed/` | 404 | Same as Reuters — licensed API only. |
| **Sports / entertainment / pop culture** (feed_hints) | ESPN, Variety, Billboard, … | RSS works | **Excluded by NI ingest policy** (`briefing_filters`, sports/entertainment hard reject). Do not add unless policy changes. |
| **Treasury press** | `home.treasury.gov/rss/...` | 404 (migration 202 deactivated) | **GovDelivery Treasury** or **`sanctions_ingest_service` / OFAC** for actionable finance intel. |
| **CFTC** | HTML index in `add_official_feeds.py` | Not RSS | GovDelivery or scrape press room. |
| **NSF news** (official feeds script) | HTML page URL | Not RSS | NSF RSS exists at `https://ncses.nsf.gov/rss.xml` (different path) — validate separately. |

### Implementation priority for non-RSS sources

1. **Phase A — structured APIs already in NI:** Federal Register API (legal), FRED/ALFRED (finance macro), ACLED/UCDP (politics events), sanctions OFAC/EU (finance/legal), NCBI E-utilities (medicine).
2. **Phase B — GovDelivery / email:** EPA, USGS, Treasury, FDIC (partially fixed via GovDelivery in migration 202).
3. **Phase C — polite HTML collectors:** Lawfare, Chatham House, IEA news index — new `api/collectors/` module with robots.txt respect, dedupe by URL, same `{schema}.articles` insert path as RSS.
4. **Phase D — licensed wires:** Reuters/AP only if you adopt commercial API keys.

---

## Re-verify after migration

```bash
PYTHONPATH=api uv run python api/scripts/check_rss_feed_http_status.py --attempts 2 -o /tmp/rss_after_248.csv
```

Focus on new Environment category rows and updated CSIS/Politico/LangChain/FDA/JAMA URLs.
