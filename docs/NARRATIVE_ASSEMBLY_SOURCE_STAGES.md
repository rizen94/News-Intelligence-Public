# Narrative assembly — sources, stages, and constraints (agent SSOT)

**Purpose:** Single reference for **Cline Plan/Act** and Cursor agents working on ongoing events, long narratives, storyline assembly, reader Current/Situations, or the spine bridge. **Read this first** — do not re-derive history from archives unless this doc is stale.

**Authority:** Complements and tightens [`api/services/ASSEMBLY_MODEL.md`](../api/services/ASSEMBLY_MODEL.md) (object model). Supersedes ad-hoc assembly behavior for **product path** decisions. Integrity metrics: [`ASSEMBLY_INTEGRITY_LOOP.md`](ASSEMBLY_INTEGRITY_LOOP.md).

**Audience:** Agents (`ni-agent-plan`, `ni-agent-act`, `ni-golden-trace`), operators.  
**Status:** Draft SSOT for the **Source & Stage Patch (v1)** — architecture and constraints only; implementation is a follow-on Act slice.

---

## 0. Cline fast path (skip research)

| If the ticket is about… | Start here | Do not re-litigate |
|-------------------------|------------|-------------------|
| Current Events / Situations / hubs empty or 404 | §7 Reader projections + §6.C vault gate | Whether vault should own articles |
| Mixed / mega storylines | §5 Hard constraints + §4 Stage S4 | Embedding-only clustering as SSOT |
| `storyline_articles` not growing | §4 Stage S3→S4, §6.A attach | Topic clustering as bridge writer |
| Same topic across publishers | §3 Layer A (occurrence) | Article-level ILIKE attach |
| Long-running arc | §3 Layer B (episode) | `tracked_events` as article bags |
| Assembly timeouts / discovery | §6.B assembly allow-list | Raising `STORYLINE_DISCOVERY_ARTICLE_LIMIT` without cap |

**Golden trace:** Still required for reader/RSS tickets — [`GOLDEN_RSS_TO_READER.md`](GOLDEN_RSS_TO_READER.md). For assembly-only tickets, add **golden event id** (chronological_events cluster root) when Stage S2→S3 is in scope.

---

## 1. Problem statement (what went wrong — one paragraph)

The platform accumulated **parallel “same topic” definitions**: article bags (`storyline_articles`), embedding clusters (`ai_storyline_discovery`), topic assignments, vault `object_id`s, and hub member lists — while the **2026-07 episode model** (events → signatures → EEL) was only partly enforced. That produced **mixed bags** (kitchen-sink storylines), **EEL vs bag drift** (measured PRE: ~20k — see [`ASSEMBLY_INTEGRITY_BASELINE_PRE.md`](ASSEMBLY_INTEGRITY_BASELINE_PRE.md)), and **reader surfaces** (Current, Situations) that show vault prose while **DB episode rows are missing or merged away**.

**Design goal:** One internal story for **cross-source agreement** (occurrence) and **long narrative** (arc), with **projections** (bag, vault, reader) derived — never authoritative alone.

---

## 2. Canonical objects and data sources

### 2.1 Primary spine (authoritative for assembly)

| Object | SSOT tables / services | Answers |
|--------|------------------------|---------|
| **Source document** | `{domain}.articles` | What we ingested (RSS, fetch, PDF). |
| **Occurrence (event)** | `public.chronological_events` + Mode A coref (`event_deduplication_service`, `event_coreference_links`) | **Same happening**, multiple sources/articles. |
| **Arc (episode)** | `{domain}.storylines` + `anchor_signature` | **Long narrative** with locked identity tokens. |
| **Arc membership** | `intelligence.event_episode_links` (EEL) | **Only** admit path for “this event belongs to this arc.” |
| **Derived bag** | `{domain}.storyline_articles` | **Read/cache** of episode evidence — reconcile from EEL, not discover via ILIKE. |
| **Container / lens** | `intelligence.tracked_events`, hub facets, demoted `container_index` | **Index** episodes/events — **never** own article membership. |

### 2.2 Context spine (supports search, not membership)

| Object | SSOT | Role |
|--------|------|------|
| **Context** | `intelligence.contexts`, `article_to_context` | Article-sized memory for RAG, pull-context, entity linking. |
| **Mentions** | `{domain}.article_entities`, `entity_canonical` | Evidence for signatures and search — not admit by themselves. |
| **Topics** | `{domain}.topics`, `article_topic_assignments` | **Taxonomy / backlog** — **not** storyline membership when patch v1 is on. |

### 2.3 Read models (projections only)

| Object | SSOT | Role |
|--------|------|------|
| **Vault note** | `intelligence.vault_notes` | Editorial memory, briefs, expansions. |
| **Situation hub** | vault cluster hub registry | Indexes **episode ids** + seeds — not a second bag. |
| **Editorial package** | package tables + `editorial_document` | Desk-quality narrative — publish path. |

**Hard rule:** No reader or vault row may be the **only** pointer to a storyline id without a live row in `{domain}.storylines` or an entry in **`storyline_id_lineage`** (see §6.C).

---

## 3. Two-layer “same topic” model (product language)

### Layer A — Same occurrence (multi-source)

- **Question:** “Are these articles describing the **same event**?”
- **Decision unit:** Event cluster root (`canonical_event_id` / cluster id).
- **Evidence:** Multiple `chronological_events` rows / `source_article_id`s; `source_count` on cluster.
- **Outputs:** Cluster graph, corroboration list, optional claims — **no** `storyline_articles` write.

### Layer B — Same narrative arc (long-running)

- **Question:** “Is this event part of the **same ongoing arc**?”
- **Decision unit:** Episode with **locked** `anchor_signature` (`identity` + `supporting`, hubs stripped per `episode_attach_gate`).
- **Evidence:** `event_episode_links` (founding / continuation / development).
- **Outputs:** Derived bag rows, finisher queue, container projection, vault expansion **optional**.

**Crosswalk (for operators):**

| User says | Layer | Wrong shortcut |
|-----------|-------|----------------|
| “Reuters and AP same story” | A | Embedding cluster on articles |
| “Gaza arc week 3” | B | Mega storyline bag |
| “Trump economy watch” | Container lens | One storyline with 500 articles |

---

## 4. Pipeline stages (what may run, what may write)

Stages are **ordered**. Later stages may **read** earlier artifacts; they may **not** skip a stage’s SSOT.

| Stage | Name | Reads | May write | Must not write |
|-------|------|-------|-----------|----------------|
| **S0** | Intake | RSS, URLs | `articles` | storylines, SA, EEL |
| **S1** | Enrichment | `articles` | body, summary, gates | membership |
| **S2** | Extraction (UIE) | enriched `articles` | `chronological_events`, contexts, entities | `storyline_articles`, EEL |
| **S3** | Occurrence merge (Mode A) | events | coref links, cluster roots | episodes, SA |
| **S4** | Arc attach (Mode B) | events, episodes, signatures | **EEL only** (+ optional derived SA via `membership_store`) | Direct SA INSERT; container article lists |
| **S5** | Narrative product | EEL, packages, vault | editorial_document, vault notes, briefs | Silent bag absorb |
| **S6** | Reader projection | reconciled episodes + vault + recent articles | cache, StoryUnits | New membership |

### Stage call rules (API / automation)

- **`unified_intake_extraction`** → S2; may request S3 when backlog says so.
- **`chronological_events_catchup`** / **`event_deduplication`** → S3 only.
- **`story_continuation`** → S4 only (when `episode_container_assembly` enabled).
- **`storyline_assembly`** (patch v1): **forbidden** to run S5-style discovery-as-membership in the same transaction as S4. Allowed subprocesses: listed in §6.B.
- **`topic_clustering`** → topics / assignments (S2 adjunct). **Classified as S2** for write permissions — not S4.
- **`vault_morning_prime`**, hub brief refresh → S5/S6 — **never** S4.

---

## 5. Hard constraints (mixed-bag suppression)

These are **non-negotiable** once Source & Stage Patch v1 is enabled. Violations are bugs, not tuning.

### 5.1 Membership

1. **Single writer:** `membership_store.admit()` / `admit_batch()` only path to new `storyline_articles` in automation (existing CI intent).
2. **No article-direct attach** when `episode_container_assembly` is on — articles link only via events → EEL.
3. **`STORYLINE_AUTOMATION_AUTO_ATTACH`** remains **off** in production; automation is **suggest / context feed** only.
4. **No ILIKE / entity-name SQL attach** as an admit rule (ranking/suggestions allowed; must not INSERT SA).
5. **Founding episodes** stay off unless `CONTINUATION_FOUNDING_ENABLED` explicitly on **and** HITL/editorial evidence documented.

### 5.2 Discovery and clustering

6. **`ai_storyline_discovery` may seed** thin signed episodes only — max seed articles per `EPISODE_DISCOVERY_SEED_ARTICLES`; oversize clusters → `container_index`, not bag.
7. **Proactive promote** may not create episodes below `promote_min_articles` + coherence gate; junk entity tokens block promote (outbreak exception must be domain-configured).
8. **Embedding clustering** is **suggest-only** under patch v1 (no `save_to_db=true` on scheduled assembly without operator flag).
9. **Mega guard:** `is_mega_storyline` / magnet quarantine paths must run on promote and on scheduled hygiene (demote to container, drop bag).

### 5.3 Containers and vault

10. **Containers never receive `storyline_articles`.**
11. **Vault notes and hubs** never INSERT SA or EEL.
12. **Reader links** to `/storylines/{domain}/{id}` require id ∈ active storylines **or** resolvable lineage map — else card is **withheld** or links to **article** / **event cluster** view instead.

### 5.4 Quality gates before attach (A3 lesson)

13. **`is_false_enriched_body` / `not_yieldable`** → reject admit (assembly integrity A3).
14. **Membership scoring** (`score_article_storyline_membership`) is **rank/review only** unless paired with EEL intent — not standalone INSERT.

---

## 6. One-time patch — layer into the codebase (no code here)

The patch is a **governance bundle** applied once, then extended via contracts — not a forever feature flag soup.

### 6.A `NARRATIVE_SOURCE_STAGE_PATCH=v1` (conceptual master flag)

When on:

- Enforces §5 across automation and assembly.
- Enables stage annotations in logs (`assembly_stage=S4`).
- Turns on **assembly step allow-list** (below).

### 6.B `storyline_assembly` allow-list (replace “run everything”)

| Step | Patch v1 default | Writes | Notes |
|------|------------------|--------|-------|
| Proactive detection | **monitor-only** or promote → **seed signature only** | storylines + seed EEL | No auto SA |
| AI storyline discovery | **off** in cron; manual with cap | seeds only | Statement-timeout bound |
| Storyline automation | **suggest_only** | suggestions table / context APIs | No SA |
| Reconcile derived bag | **on** after continuation drain | SA from EEL | A1 pattern |

### 6.C `storyline_id_lineage` (reconciliation projection)

**One-time data patch + ongoing maintenance:**

- Table or view: `(domain_key, old_storyline_id, canonical_storyline_id, reason, merged_at)`.
- Populated from merge history, vault note metadata, hub members.
- **Reader / vault** resolve ids through lineage **before** emitting hrefs.
- **Constraint:** Situations index lists only ids that resolve to active episode or lineage target.

### 6.D `internal_search` surfaces (read-only contracts)

Documented API **facets** for agents (implementation later):

| Facet | Backing stage | Fields safe to expose |
|-------|---------------|---------------------|
| `occurrence` | S3 | cluster id, event titles, dates, source articles, domains |
| `arc` | S4 | episode id, signature, state, linked event ids, derived article ids |
| `situation` | S6 | hub id, brief, **resolved** member episode ids |
| `intake` | S0–S1 | recent unlinked articles (no faux storyline id) |

### 6.E Contract tests (extend existing pattern)

Mirror [`backlog_selection_contracts`](../api/shared/backlog_selection_contracts.py):

- **Assembly contract:** each automation phase declares `allowed_read_stages` / `allowed_write_stages`.
- **CI:** fail if new code path INSERTs `storyline_articles` outside `membership_store` + approved maintenance scripts.
- **CI:** fail if `storyline_assembly` imports discovery `save_to_db` without `OPERATOR_OVERRIDE`.

---

## 7. Reader projections (Current, Situations, News)

### News

- **Primary:** recent unbridged articles (`recent_article`) when bridge thin — allowed.
- **Secondary:** morning **new** expansions with **valid** storyline id.
- **Forbidden:** fake storyline ids for vault-only objects.

### Current Events

- **Primary (patch v1):** episodes in `active|forming` with recent EEL **or** open tracked arc — classifier `surface_kind: current_events`.
- **Secondary:** vault ongoing expansions **only if** storyline id resolves.
- **Forbidden:** vault-ranked list that replaces DB classifier entirely without id check (today’s failure mode).

### Situations (`/hubs`)

- **Primary:** hub brief + **resolved** member episodes + timeline from **linked events**, not empty stub cards.
- **Forbidden:** member counts from hub row when 0 rows exist in `storylines`.

---

## 8. Mixed-bag definition (metric)

An episode is **mixed bag** if any of:

- `article_count` (bag) ≫ EEL-linked distinct source articles beyond `EPISODE_DISCOVERY_MEGA_THRESHOLD`.
- Coherence guard fails (`magnet_membership`, title↔signature mismatch).
- Majority of members linked only via legacy automation intent, no EEL.
- Classifier `is_mega_storyline` true without `container_index` demotion.

**Target:** mixed-bag rate among **active** episodes below **5%** per domain (operator dashboard — tie to A1-style integrity scripts).

---

## 9. Verification checklist (Act / ship)

Before claiming assembly or reader work is done:

1. **Stage movement:** golden article → event row → (if arc exists) EEL row → derived SA row.
2. **No writer drift:** reconcile job reports `drift_total = 0` or down week-over-week.
3. **Reader honesty:** sample Current page — **100%** hrefs resolve to storyline 200 or deliberate article link.
4. **Hub honesty:** top 5 hubs — **≥1** resolved member or explicit “unindexed” empty state (not fake counts).
5. **Assembly run:** `storyline_assembly` log shows only allow-listed steps with stage tags.

---

## 10. Related docs (read on demand)

| Doc | Use |
|-----|-----|
| [`api/services/ASSEMBLY_MODEL.md`](../api/services/ASSEMBLY_MODEL.md) | Object model, Mode A/B, retired metaphors |
| [`ASSEMBLY_INTEGRITY_LOOP.md`](ASSEMBLY_INTEGRITY_LOOP.md) | A1–A4 gates, reconcile |
| [`GOLDEN_RSS_TO_READER.md`](GOLDEN_RSS_TO_READER.md) | Reader golden trace |
| [`VAULT_NOTES_AND_PULL_CONTEXT.md`](VAULT_NOTES_AND_PULL_CONTEXT.md) | Vault vs assembly containers |
| [`KNOWLEDGE_LOOP.md`](KNOWLEDGE_LOOP.md) | Finisher / materiality |
| [`OPERATING_PRINCIPLES.md`](OPERATING_PRINCIPLES.md) | Done criteria |

---

## 12. Multi-domain rollout — politics model (operator)

Spread **suggest_only + honest reader + corpus hygiene** to all pipeline-active domains.

| Step | Action | Done when |
|------|--------|-----------|
| **A. Config** | `domain_synthesis_config.yaml` → `default_mode: suggest_only` (global + domains) | New storylines promote in suggest mode |
| **B. DB mode sync** | `PYTHONPATH=api uv run python scripts/enable_all_storyline_automation.py --mode suggest_only --no-reset-schedule` on Widow (dry-run first) | `automation_mode` matches config on active rows |
| **C. Corpus hygiene** | Per domain: `api/scripts/repair_duplicate_mega_storylines.py --domain <key>`; archive/merge stale megas; optional politics-style trim | Active storyline count matches EEL-backed arcs; mixed-bag rate ↓ |
| **D. Reader gate** | `intelligence.storyline_id_lineage` + `resolve_canonical_storyline_id`; backfill `api/scripts/backfill_storyline_id_lineage.py` | Current/News sample: no storyline 404s |
| **E. Assembly allow-list** | `NARRATIVE_SOURCE_STAGE_PATCH=v1` or `FEATURE_OVERRIDE_NARRATIVE_SOURCE_STAGE_PATCH=true` | Cron: discovery dry-run; `eel_reconcile` in assembly payload |
| **F. Corpus trim** | `api/scripts/prune_inactive_storyline_corpus.py --domain <key> --mega-only --dry-run` | Active count tracks EEL-backed episodes |

**Politics reference posture:** ~10 active episodes, heavy `recent_article` intake, vault secondary. Other domains keep larger corpora until **C** runs — suggest_only stops new silent absorb immediately.

---

## 11. Change log

| Date | Note |
|------|------|
| 2026-11-21 | §12 multi-domain politics-model rollout playbook |
| 2026-11-21 | Initial SSOT for Source & Stage Patch v1; agent no-research entrypoint |