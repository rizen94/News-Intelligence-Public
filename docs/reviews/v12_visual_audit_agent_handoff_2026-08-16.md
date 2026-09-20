# v12 visual audit — agent handoff (2026-08-16)

**Purpose:** Give a second agent everything needed to diff the live SPA against the v12 visual audit checklist **without** fetching the site (CSR React shell only returns “enable JavaScript”).

**Authority:** Repo on Widow workspace `/home/pete/Documents/projects/News Intelligence`. Live API sampled at `http://127.0.0.1:8000` (OpenAPI + example GETs). Frontend source is SSOT for UI behavior.

**Do not invent pixel changes.** Only report stay / go / change when backed by routes, components, API shapes, or DB columns below.

---

## Context for the receiving agent

1. The product is a **client-side React SPA**. Raw HTML fetch is useless.
2. Shipped **v12.0** cutover (2026-08-16) focused on episode containers, THIN editorial `stakes_gate` (act-verb + citeable evidence), and UI strip — **not** the L1–L3 sentiment/motif surfaces in the checklist below.
3. Cutover follow-up explicitly holds **LAST bucket**: hops / Edition SPA / LLM stakes (`docs/reviews/v12_formal_cutover_2026-08-16.md`).
4. In this codebase, **`stakes_gate`** (`api/shared/stakes_gate.py`) = editorial package publish gate. It is **not** the four-feature intake stakes modulator (arousal / targeted_threat / source_surprise / frame_prior).

---

## How to get a usable view (if still needed)

| Preference | Method |
|------------|--------|
| Best | Paste rendered `<body>` after app load (DevTools → Elements) for each major route |
| Almost as good | Use API inventory + sample JSON in this doc |
| Acceptable | Screenshots + short description per page |
| Lazy (done here) | Route list from `web/src/App.tsx` + nav from `web/src/layout/AppNav.tsx` |

**If only two pages:** `/{domain}/articles/:id` and `/{domain}/investigate/entities/:entityId/dossier`.

---

## A. SPA route inventory

Base pattern: `/:domain/<path>`  
Domains: `politics`, `finance`, `legal`, `medicine`, `artificial-intelligence` (plus corpus `neurodiversity` when enabled).

### Router (`web/src/App.tsx`)

| Path under `/:domain` | Page / note |
|------------------------|-------------|
| `dashboard` | Dashboard |
| `discover`, `discover/contexts/:id` | Discover / context detail |
| `storylines` | Episodes list (URL still `/storylines`) |
| `storylines/review-queue` | HITL review (demo-hidden) |
| `storylines/discovery` | Redirect → episode list |
| `storylines/:id` | Episode detail |
| `storylines/:id/timeline` | Timeline |
| `storylines/:id/synthesized` | Legacy desk only / else redirect |
| `articles` | Article list |
| `articles/deduplication` | Dedup manager (demo-hidden) |
| `articles/:id` | **Article detail (priority)** |
| `briefings`, `report` | Redirect → `editor` |
| `arcs`, `arcs/rolling`, `arcs/reports` | Arc catalog / rolling / briefs |
| `arcs/:arcId/chronicle`, `.../spine`, `.../heatmap` | Arc views |
| `research/subjects` | Research subjects |
| `research`, `narrative`, `reduction` | Editorial modals |
| `editor`, `editor/packages/:packageId`, `editor/stories/:storyId` | Editor / packages / news stories |
| `dockets/:storylineId` | Legal matter docket |
| `signals/review` | Trade signals HITL |
| `rss_feeds` | Feeds (demo-hidden) |
| `topics` | Topics staging |
| `watchlist` | Watchlist (demo-hidden) |
| `events` | Timeline events |
| `investigate` | Investigate hub |
| `investigate/events/:id` | Event detail |
| `investigate/entities` | Entities list |
| `investigate/entities/:id` | Entity detail |
| `investigate/entities/:entityId/dossier` | **Entity dossier (priority)** |
| `investigate/search` | Search |
| `investigate/documents`, `.../:documentId` | Processed documents |
| `investigate/narrative-threads` | Narrative threads |
| `investigate/entity-resolution` | Entity resolution |
| `investigate/spine-browser` | Identity spine |
| `investigate/hypotheses` | Hypotheses |
| `monitor`, `monitor/sql-explorer` | Ops monitor |
| `audit-checklist` | Audit checklist |
| `operations/investigation-ops`, `operations/nri-ops` | Investigation ops |
| `operations/llm-activity` | LLM activity |
| Finance extras | `analysis`, `commodity/:commodity`, `credit-spread`, `usd-purchasing-power-tracker`, `congress-trading`, `trace`… |

### Nav labels (`web/src/layout/AppNav.tsx`) — operator vocabulary

- Modals: Intake → Research → Narrative → Reduction → Editor  
- Stories: **Episodes** (path `storylines`)  
- Investigate: Hub, Entities, Search, Documents, Narrative threads, Entity resolution, Identity spine, Hypotheses  
- Outputs: News stories (`editor`), Arc reports  

---

## B. Priority UI behavior (from source — not screenshots)

### Article detail — `web/src/pages/Articles/ArticleDetail.tsx`

**API:** `apiService.getArticle(id, domain)` → `GET /api/{domain}/articles/{id}`; events via `getArticleEvents` → established events.

**Renders:** back nav, title, share/bookmark, depth toggle (`narrative` | `structured` | `raw`), source/date/category, summary/body, structured fields (id, domain, **quality_score**, ml status, extracted event count), raw JSON dump, original URL, topics, provenance panel, extracted events list.

**Does not render:** sentiment score/label chips, frame badges, stakes feature breakdown, targeted polarity/spans, extractor provenance (`lexicon_v0` / `intake_classifier`), layer-precedence indicator.

**Events side panel:** shows `source_count` chip when `> 1` (raw source count — checklist flags this).

### Articles list — `web/src/pages/Articles/Articles.tsx`

Quick filters / chips: **`positive` | `neutral` | `negative`** only (not five-frame model).

### Entity dossier — `web/src/pages/Investigate/EntityDossierPage.tsx`

**API:** `/api/synthesis/entity/{id}` + `/api/entity_profiles` (see file header).

**Renders:** narrative summary, positions/stances (topic positions), article timeline, relationships, patterns tab (`pattern_type` chips from dossier discoveries), FtM bridge / provenance.

**Does not render:** aspect-split integrity vs performance tone, tone velocity z-score vs entity baseline, independence-corrected corroboration, 8-motif feed with citation gate, coordination cluster labels.

---

## C. API inventory (fetchable JSON)

Prefix: `/api`. Domain-scoped article routes use `/{domain}/...`.

### High-value endpoints

| Concern | Methods / paths |
|---------|-----------------|
| Articles | `GET /{domain}/articles`, `GET /{domain}/articles/{id}`, `GET /{domain}/articles/{id}/established_events`, `GET /articles/recent` |
| Entities / dossiers | `GET /entity_profiles`, `GET /entity_profiles/{id}`, `GET /synthesis/entity/{id}`, `GET /entity_positions`, `GET /entity_dossiers*` |
| Claims | `GET /claims`, `GET /claims/similar_clusters` |
| Causal / reasoning | `GET /causal_edges`, `GET /reasoning`, `GET /reasoning/event/{event_id}`, `GET /reasoning/{domain}/{storyline_id}` |
| Graph connections | `GET /graph_connection/proposals`, accept/reject |
| Patterns (legacy taxonomy) | `GET /pattern_discoveries`, `POST /context_centric/run_pattern_matching` |
| Editorial packages / stories | `/editorial/packages*`, `/editorial/stories*`, modal handoffs |
| Sentiment (legacy) | `POST /sentiment/analyze` |
| Signals | `GET /signals`, … |
| Episodes (intelligence) | `/intelligence/episodes/{domain}/{episode_id}/…` |

Full OpenAPI: `GET /openapi.json` on the API host.

### Live sample shapes (2026-08-16)

**Article list/detail fields (politics article `360635`):**

```json
{
  "id": 360635,
  "sentiment_score": 0.3,
  "sentiment_label": "negative",
  "quality_score": 0.85,
  "title": "...",
  "source": "...",
  "published_at": "..."
}
```

List also exposes `sentiment` / `sentiment_label` for filters. Detail may include `metadata` (often null).

**DB columns (`politics.articles` sentiment-related):**  
`sentiment_score`, `sentiment_label`, `sentiment_confidence`, `quality_score`, `metadata`, `ml_data`  
**Absent:** `arousal`, `targeted_threat`, `source_surprise`, `frame_prior`, frame enum, extractor provenance tags.

**Claims (`GET /api/claims`):**

```json
{
  "id": 2705732,
  "context_id": 336250,
  "subject_text": "Bill Cassidy",
  "predicate_text": "denounced",
  "object_text": "...",
  "confidence": 0.95,
  "validation_status": null
}
```

**Absent:** `stance` / claim_stance.

**Causal edge (`GET /api/causal_edges`):**

```json
{
  "id": 96,
  "cause_kind": "tracked_event",
  "cause_id": 2429,
  "effect_kind": "tracked_event",
  "effect_id": 2462,
  "relation": "precedes_correlated",
  "confidence": 1.0,
  "evidence_grade": "weak",
  "evidence_context_ids": [],
  "source": "correlation_seed",
  "status": "active",
  "domain_key": "finance"
}
```

**Not** checklist edge types: `causal_candidate`, `claim_propagation`, `sentiment_congruent`, `same_playbook`.

**Pattern discovery (`GET /api/pattern_discoveries`):**

```json
{
  "id": 134413,
  "pattern_type": "temporal",
  "domain_key": null,
  "context_ids": [264769, "..."],
  "confidence": "...",
  "entity_profile_ids": []
}
```

Taxonomy in use: `behavioral` | `temporal` | `network` | `event` — **not** the eight motifs below.

**Graph proposals:** `proposal_kind` e.g. `merge`, with `evidence` object — entity-resolution style, not coordination fingerprint clusters.

---

## D. v12 visual audit checklist (requirements side)

### L1 — Intake sentiment surfaces

| Required surface | What to check |
|------------------|---------------|
| Stakes gate breakdown per article | Four features: `arousal`, `targeted_threat`, `source_surprise`, `frame_prior` as separate contributors; ~30% cap visibly enforced — not one opaque number |
| Frame badge on article cards | `critical` / `laudatory` / `neutral` / `alarmed` / `analytical` — not positive/negative |
| Targeted sentiment on article detail | Per-entity polarity + intensity, span-tied — not article-level mood |
| Extractor provenance | Every tone value tagged `lexicon_v0` / `intake_classifier` + `model_version` |

### L2 — Spine surfaces

| Required surface | What to check |
|------------------|---------------|
| Claim stance on claim rows | Stance on claims, not only articles |
| Event valence on event timelines | Valence per event feeding episode arcs |
| Aspect-split tone on entity/dossier | Integrity vs performance as separate lines; single aggregate sentiment = fail |
| Tone velocity with baseline | z-score vs entity’s rolling baseline |

### L3 — Research layer surfaces

| Required surface | What to check |
|------------------|---------------|
| Pattern/motif feed | Motifs: `backlash_cycle`, `escalation_ladder`, `aspect_inversion`, `denial_then_confirmation`, `convergence`, `exodus`, `quiet_period`, `coordinated_rollout` — state badges `candidate`/`confirmed`/`decayed`/`refuted` — **no render without** `evidence_observation_ids` |
| Connections view | Edges typed `causal_candidate`, `claim_propagation`, `sentiment_congruent`, `same_playbook` — weights + provenance |
| Coordination clusters | Fingerprint-grouped articles: wire copy / independent / talking-point propagation |
| Independence-corrected counts | Divergence/corroboration show corrected counts (5 coordinated → corroboration 1) |
| Episode resemblance | “This episode resembles X” from `episode_signatures` |
| Kernel dual treatment | Coordinated coverage: discounted-as-corroboration **and** flagged as meta-story — two treatments |

### Cross-cutting

- Layer precedence wherever tone shows: `claim_stance` > `targeted_classifier` > `intake_classifier` > `lexicon_v0`
- Feature-flag panel: `sentiment_intake`, `pattern_engine`, `connection_mining`
- Hops provenance: hop candidates from `causal_candidate` edges must say so

### Likely removal candidates (conditional)

- Single-number entity sentiment  
- Binary/ternary positive/negative scales  
- Raw source-count divergence/corroboration  
- Sentiment driving stakes directly (uncapped)  
- Patterns/alerts/connections without linked evidence  

---

## E. Evidence-based pre-diff (as of 2026-08-16)

| ID | Required | Verdict | Evidence |
|----|----------|---------|----------|
| L1-stakes | Four-feature stakes + cap | **Missing** | No columns/API fields; `stakes_gate.py` is package THIN gate |
| L1-frame | Five-frame badges | **Missing** | UI + API use pos/neg/neutral |
| L1-targeted | Span-tied entity polarity | **Missing** | Article detail has no targeted UI |
| L1-prov | Tone extractor tags | **Missing** | No provenance tags on sentiment fields |
| L2-stance | Claim stance | **Missing** | Claims JSON has no stance |
| L2-valence | Event valence | **Missing** | Article events UI has no valence |
| L2-aspect | Aspect-split dossier tone | **Missing** | Dossier has no aspect tone lines |
| L2-velocity | Tone z-score baseline | **Missing** | No API/UI |
| L3-motifs | 8-motif citation-gated feed | **Missing** | `pattern_type` = temporal/behavioral/… |
| L3-connections | Typed sentiment/causal graph | **Partial / mismatch** | `/causal_edges` + graph proposals exist; types ≠ checklist |
| L3-coord | Coordination clusters | **Missing** | Not in UI/API vocabulary above |
| L3-indep | Independence-corrected counts | **Fail where raw counts show** | Article events chip: `source_count` |
| L3-resemble | Episode resemblance block | **Unknown / likely missing in SPA** | Backend has `episode_signatures` scripts; no dedicated SPA block inventoried |
| L3-kernel | Dual coordinated treatment | **Missing in SPA** | Kernel = act-verb package seeding |
| X-precedence | Layer indicator | **Missing** | |
| X-flags | Feature flag panel | **Missing** | No `sentiment_intake` / `pattern_engine` / `connection_mining` operator panel found |
| X-hops | Hops causal provenance | **Deferred** | LAST bucket: hops held |

**Removal candidates already present in current UI (when those surfaces exist):** ternary sentiment filters/chips; raw `source_count` on events; article-level mood only (when shown on list cards).

---

## F. Related repo docs (do not confuse)

| Doc | Topic |
|-----|--------|
| `docs/reviews/v12_formal_cutover_2026-08-16.md` | MUST+THIN cutover smoke |
| `docs/reviews/v12_web_ui_strip_2026-08-16.md` | Episodes rename, briefings→editor |
| `docs/UPGRADE_12.0.md` | StakesGate + act-verb kernel product meaning |
| `api/shared/stakes_gate.py` | Editorial package gate implementation |
| `docs/ASSEMBLY_MODEL.md` | Matching → chains → storyline → package |

---

## G. Suggested task prompt for the receiving agent

```text
You are auditing News Intelligence UI/API against the v12 visual checklist in
docs/reviews/v12_visual_audit_agent_handoff_2026-08-16.md.

Rules:
- Do not fabricate pixel recommendations from the HTML shell.
- Use sections A–E as ground truth unless you verify newer rendered DOM or API.
- Produce a stay / go / change table mapped to L1 / L2 / L3 / cross-cutting.
- Call out naming collisions: stakes_gate (editorial THIN) ≠ four-feature intake stakes.
- Prefer article detail + entity dossier first.
- If you need more signal, request rendered <body> pastes or hit the listed JSON endpoints.
```

---

## H. Optional: minimal curl smoke

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -sS 'http://127.0.0.1:8000/api/politics/articles?limit=1' | jq .
curl -sS 'http://127.0.0.1:8000/api/claims?limit=2' | jq .
curl -sS 'http://127.0.0.1:8000/api/causal_edges?limit=2' | jq .
curl -sS 'http://127.0.0.1:8000/api/pattern_discoveries?limit=2' | jq .
```

Replace host with Widow API if not local.
