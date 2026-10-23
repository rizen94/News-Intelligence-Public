# Vault notes and Pull context

Two-level living knowledge for long-running arcs, surfaced on the **v2** reader (default News product).

Product intent (compounding clarity; vault as living twin of the Postgres narrative loop): [`KNOWLEDGE_LOOP.md`](KNOWLEDGE_LOOP.md).

**Brief layers (reader storyline page):** vault morning expansions / Pull context are the living authored brief; `{domain}.storylines.editorial_document` is the durable Postgres projection from package publish (`editorial_projection_service`) or desk promote. Reader preference: Pull → vault expansion → durable editorial → pack summary.

## Quality bar (readable vault)

Obsidian is for notes a human would open. Pipeline IDs stay in Postgres; empty entity dumps are not “saved knowledge.”

| Gate | Env (default) | Behavior |
|------|---------------|----------|
| Entity markdown create | `NI_VAULT_ENTITY_NOTE_MIN_HITS=3`, `NI_VAULT_ENTITY_NOTE_WINDOW_DAYS=14` | Write/update entity `.md` only if followed, cluster hub seed, or ≥N distinct article hits in the window (else PG-only / `lifecycle=index`) |
| Expansion coherence | `NI_VAULT_EXPANSION_COHERENCE_GATE=true` | Morning prime rejects junk titles, short bodies, title↔body mismatch, and magnet membership bags; keeps prior good expansion |
| Daily briefing citations | `NI_VAULT_BRIEFING_REQUIRE_CITATIONS=true` | Skip writing uncited filler; LLM assemble falls back to cited outline; reader/`get_latest_daily_briefing` and Reading MOC omit uncited living day cards; cleanup demotes them to `lifecycle=index` |
| Title hygiene | (always on) | Clippings + cluster hubs reject HTML / `class=` / tag-soup titles |

**Reading surface:** open `00_Reading.md` (expansions, daily, hubs). `00_Index.md` explains that `40_Reference/entities/` stubs are index cards.

**Cleanup:** `api/scripts/vault_quality_cleanup.py` marks stub entities `lifecycle=index`, archives junk hubs to `90_Archive/junk/`, flags mismatched expansions, writes MOCs.

Service: [`api/services/vault_quality_gates.py`](../api/services/vault_quality_gates.py).

## Second-brain MVP (primary filing path)

When `vault_mvp_spine` / `NI_VAULT_MVP_SPINE` is on (default), post-UIE filing follows CODE:

| Step | Action |
|------|--------|
| **Capture** | News: `20_Clippings/{date}-{article_id}-{slug}.md`. Science domains (`medicine`, `artificial-intelligence`, `neurodiversity`): `50_Science/20_Clippings/...` |
| **Organize** | Related wiki notes + stubs. Science *subjects* → `50_Science/40_Topics/`. Shared refs (orgs, places, people, labs, …) stay on `40_Reference/entities/` so both branches wikilink the same note. **Tags are fully shared** across branches (`place/*`, `entity/*`, soft relations, etc.) — branch only separates file layout |
| **Distill** | Append `<!-- ni:auto:timeline -->` bullet `(article:id)` + `[[clipping]]`; tag `update/new` + `branch/science` or `branch/news` |
| **Express** | Deferred to **`vault_morning_prime`** when that feature is on (no per-article Ollama). Morning job refreshes Situation briefs + writes expansions / daily briefing. If morning prime is off, legacy `express_briefs_from_mvp` still runs after Distill. |

Service: [`api/services/vault_mvp_ingest_service.py`](../api/services/vault_mvp_ingest_service.py) (`file_article_to_vault`). Path helpers: [`api/shared/vault_note_contract.py`](../api/shared/vault_note_contract.py). Legacy fanout is skipped while MVP is enabled.

**Parked for now:** hub discovery investment, PG-first hub timeline rebuild, editorial packages as binder, membership merges.

## Ownership

| Layer | Owns |
|-------|------|
| **Obsidian** | Soft/relational tags (`relation/*`), wikilinks, longform prose, clipping + wiki web |
| **Postgres** (`intelligence.vault_notes`, `vault_note_links`) | IDs, geo parent, lifecycle/status, mirrored tags/links for packs |

NI never invents rivalry edges in Postgres; tag sync only mirrors Obsidian.

## Automation

| Phase | Role |
|-------|------|
| UIE → `file_article_to_vault` | Second-brain Capture/Organize/Distill (when `vault_mvp_spine`) |
| `vault_notes_writer` | Drain `vault_update_queue` — timeline bullets + optional significance (legacy fanout) |
| `vault_tag_link_sync` | Mirror frontmatter tags + wikilinks → PG |
| `vault_cluster_hub_refresh` | Discover topic clusters; Situation briefs (parked behind MVP focus) |
| **`vault_morning_prime`** | Once daily: **Briefing Manager** (advanced/70b + MemPalace) curates ongoing vs new slate → per-story vault RAG + optional web → expansions → **two-lane** daily briefing |

Feature flags: `vault_mvp_spine` / `NI_VAULT_MVP_SPINE`; `vault_notes_pipeline` / `NI_VAULT_NOTES_ENABLED`; `vault_cluster_hubs` / `NI_VAULT_CLUSTER_HUBS_ENABLED`; `vault_morning_prime` / `NI_VAULT_MORNING_PRIME`; `vault_morning_briefing_manager` / `NI_VAULT_MORNING_BRIEFING_MANAGER`.

Scheduler: `api/config/schedulers.yaml` → `vault_morning_prime` (86400s). Services: [`vault_morning_prime_service.py`](../api/services/vault_morning_prime_service.py), [`morning_briefing_manager_service.py`](../api/services/morning_briefing_manager_service.py), [`mempalace_brief_memory.py`](../api/services/mempalace_brief_memory.py).

### Morning Briefing Manager + MemPalace

| Piece | Role |
|-------|------|
| Manager LLM | `InvocationKind.STORYLINE_NARRATIVE_FINISH` (PopOS 70b overflow lane) |
| MemPalace wing | `News Intelligence` — rooms `watches`, `preferred_narratives`, `skip_list`, `brief_diary`, `morning_brief` |
| HTTP | `MEMPALACE_HTTP_BASE` default `http://127.0.0.1:18443/mempalace` |
| Slate lanes | **Ongoing updates** (recurring arcs) + **New of note** (shortlist of one-offs) |
| Per story | Vault-wide retrieval + optional DuckDuckGo/trafilatura web pack → expansion with lane tone |
| Fallback | Heuristics if manager LLM or MemPalace unavailable |

**Tight bags:** storyline membership uses raised `link_score_profile` floors (`auto_approve_combined` ~0.80, `max_member_articles`, `max_storylines_per_article`) so arcs stay a concise event series; breadth lives in vault + morning research, not bag absorb.

Schema: migration **244** adds `note_type` values `expansion` / `daily_briefing` and columns `body_md` / `summary_md` on `intelligence.vault_notes`.

## Morning prime → reader (cache-first)

Morning prime is the **only** LLM authoring path for living expansions and the daily briefing. Reader surfaces are read-only against that cache:

| Surface | Behavior |
|---------|----------|
| Home / News | Daily briefing lead + **expansion catalog** (ongoing then new) from PG mirrors |
| Storyline pack | Includes `vault_expansion` (primed body/summary for the arc) |
| Hub pack | `ensure_hub_brief_for_pack(..., allow_llm=False)` — never regenerates on read |
| **Pull context** | `enqueue_context_pull` serves expansion → prior ready pull → deferred message; all `status=ready` + `cached=True` |

**Pull context no longer calls Ollama on button click.** Reader routes schedule `run_context_pull_job` only when enqueue returns legacy `status=pending` (not when `ready` / `cached`).

Cache sources in the enqueue response:

| `cache_source` | Meaning |
|----------------|---------|
| `vault_expansion` | Morning-primed expansion body |
| `prior_pull` | Last successful pull for this article |
| `deferred` | No cache yet; ready stub asking the user to wait for next morning prime |

## Cluster hubs = Situations (reader spine)

Hubs are **indexes only** — they do not merge `storyline_articles` bags. In the News
reader they are the long-term **Situation** object: track a topic across episodes and
ask for a summary anytime.

| Piece | Location |
|-------|----------|
| Path convention | `40_Reference/clusters/{slug}.md` (legacy Iran: `40_Reference/entities/iran_war.md`) |
| Registry | `note_type=cluster`, `metadata.hub=true`, `cluster_key`, `member_storyline_ids`, `seed_entity_ids` |
| Current brief | `metadata.current_brief` + Obsidian `<!-- ni:auto:brief -->` fence |
| Discovery | `api/services/vault_cluster_discovery_service.py` |
| Writer | `api/services/vault_cluster_hub_service.py` |
| Brief builder | `api/services/vault_hub_brief_service.py` (fingerprint skip; refresh on maintenance + stale read) |
| Reader list | `GET /api/reader/vault-hubs` |
| Reader pack | `GET /api/reader/vault-hubs/{id_or_slug}` (includes `current_brief`) |
| UI | `/hubs/:idOrSlug` Situation page + home `surface_kind: vault_hub` cards |

Hub-facet people alone never form a cluster (need durable non-hub entities, tags, or events).
Person-pair-only candidates are skipped unless shared-event glue exists.

Assembly containers (`tracked_events` / YAML hub_facets) remain the **pipeline** index;
vault Situations are the **reader** long-term track + brief. Same “index only” rule.

## Reader APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/reader/vault-notes/context-pack` | 1–2 hop pack (entities / titles) |
| GET | `/api/reader/vault-hubs` | Active cluster hubs |
| GET | `/api/reader/vault-hubs/{id_or_slug}` | Situation pack (brief + note + members + timeline) |
| GET | `/api/reader/storylines/{id}?domain=` | Pack includes `vault_context_pack` + `vault_expansion` |
| POST | `/api/reader/articles/{id}/pull-context?domain=` | Cache-first brief (`ready` + optional `summary_markdown`; no Ollama when cached) |
| GET | `/api/reader/articles/context-pulls/{pull_id}` | Poll / fetch pull row (legacy pending only) |
| POST | `/api/reader/storylines/{id}/pull-context?domain=` | Storyline-level cache-first pull |

Narrative finisher and `comprehensive_rag` inject vault packs into prompts for long arcs.

## UI

- **Living context** — storyline reader (`/storylines/:domain/:id`)
- **Morning expansion** — same page when `vault_expansion` is present
- **Daily briefing** — home/news lead card (`surface_kind: daily_briefing`)
- **Situations** — `/hubs/:idOrSlug` (current brief + member episodes + timeline)
- **Pull context** — same page (header + per citation); displays enqueue `summary_markdown` immediately when `status=ready` / `cached` (no job poll)

## Seeds / density

- `api/scripts/preseed_vault_notes.py`, `seed_iran_war_vault.py` (thin CLI → `bootstrap_iran_war_hub`), `seed_distinct_arcs.py`
- `api/scripts/seed_finance_markets_vault.py` — finance Situations `resource_movements` + `market_trends` (+ inflation/Iran cross-hub)
- `api/scripts/seed_priority_situations_vault.py` — `us_institutions`, `china_trade_tech`, `russia_ukraine` promotion, `climate_resource_policy`
- `api/scripts/seed_remaining_vault_density.py` — `farage_reform_boats`, `venezuela_boe_gold`, `ai_governance`; living Fed/oil/gold/State/etc.; package Related-situations; finance clipping body sync
- `api/scripts/fill_situation_api_evidence.py` — non-RSS fill: activate AI RSS; patch Situation hubs with `## Non-RSS evidence (API)` from FRED/`macro_series_observations`, Federal Register, and (when enabled) OFAC/EU/UN `sanctions_actions`. Finance hubs `resource_movements` / `market_trends` also get a replaceable finance section: prefer Quiver (`quiver_congress_trades`), else EIA (`macro` source=`eia_api`), else recent FRED/macro history already in DB.
- `api/scripts/enrich_vault_wiki_rag.py` — Wikipedia wiki RAG: patch Situation hubs + living entities with replaceable `## Wikipedia background` (local `intelligence.wikipedia_knowledge` + summary API; no LLM). Service: [`vault_wiki_enrichment_service.py`](../api/services/vault_wiki_enrichment_service.py). See also [`docs/RAG_AND_WIKIPEDIA.md`](RAG_AND_WIKIPEDIA.md).
- `api/scripts/enrich_vault_entity_dossiers.py` — wire stored `intelligence.entity_dossiers` into living/priority vault entity notes as replaceable `## Entity dossier` (chronicle / positions / storyline refs / relationships; no new LLM). Service: [`vault_dossier_enrichment_service.py`](../api/services/vault_dossier_enrichment_service.py).
- `api/scripts/seed_unresolved_vault_links.py` — stub top unresolved wikilink titles + resync
- `api/scripts/sync_vault_tags_links.py` — refresh mirrors after Obsidian edits

### Beyond RSS (API / RAG already in NI)

| Store / phase | Fills |
|---------------|--------|
| `macro_series_refresh` + FRED/ALFRED (`macro_series_observations`) | Fed funds, CPI, UNRATE, USD, WTI on market/resource hubs |
| `sanctions_refresh` (`SANCTIONS_INGEST_ENABLED=true`) | OFAC/EU/UN rows for Venezuela/Iran/China hubs |
| Federal Register API (live in evidence service) | Energy/export-control/Venezuela license notices |
| **Package compose / evidence expand** | Loads ``vault_background`` (Situation hubs + living entities with wiki/dossier/API sections) plus ``enrichment`` (causal edges, open expectations, storyline Wikipedia/GDELT when vault is thin, MemPalace watch priority, congress trade signals) into the LLM payload as **framing only** — members remain citation SSOT (`[@mN]`). Services: [`package_vault_context_service.py`](../api/services/package_vault_context_service.py), [`package_compose_enrichment_service.py`](../api/services/package_compose_enrichment_service.py). Evidence expand also promotes embedding chunks + completed `rag_evidence_pull` docs into context/article members. |
| **Entity dossiers** (`vault_dossier_enrichment` / `enrich_vault_entity_dossiers.py`) | Stored dossier fields on living/priority entity notes (`## Entity dossier`) |
| **Finance API mirror** (Quiver → EIA → macro history) | `## Congress trades (Quiver)` or `## Energy (EIA)` or `## Energy / rates (macro series)` on `resource_movements` / `market_trends`. EIA: set `EIA_API_KEY` (public `DEMO_KEY` works for smoke) + `TRADE_RESOURCES_IMPORT_ENABLED=true`. Quiver: restore `api/collectors/quiver_collector.py` + set `QUIVER_API_KEY` via Homelab `set-widow-quiver-key.sh`, then AM `quiver_collector` phase. |
| `rag_evidence_pull` / `rag_enhancement` | arXiv PDF, court/FR/WHO-CDC when stimulus flags on |
| EIA / metals_dev / EDGAR / Quiver | Finance product + commodity history; vault finance section prefers Quiver DB rows when populated |
| External research ingest (n8n/SearXNG) | Package members when `external_research_ingest` enabled |

**Operator (wiki RAG):** on Widow, with vault write env set:

```bash
PYTHONPATH=api python3 api/scripts/enrich_vault_wiki_rag.py --force --sync --entity-limit 15
```

Use `--dry-run` first; `--local-only` skips Wikipedia HTTP (dump/cache only); `--hub KEY` limits hubs.

**Operator (entity dossiers):**

```bash
PYTHONPATH=api python3 api/scripts/enrich_vault_entity_dossiers.py --force --sync --limit 15
```

**Operator (finance hubs Quiver/EIA/macro):**

```bash
PYTHONPATH=api python3 api/scripts/fill_situation_api_evidence.py --force --sync \
  --hubs-only resource_movements market_trends --skip-ai-rss
```

Mesh is topic-agnostic; Iran/Hormuz is bootstrap density for the general cluster discoverer.
