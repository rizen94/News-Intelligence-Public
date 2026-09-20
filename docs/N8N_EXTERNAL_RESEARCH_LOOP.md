# n8n external research loop

Spec for attaching SearXNG / Obsidian-captured web research into living editorial packages.

## NI endpoint

```
POST /api/editorial/packages/{package_id}/external_research/attach
```

Payload (array in body `items`):

```json
{
  "items": [
    {
      "url": "https://example.org/report",
      "title": "Example report",
      "summary_text": "Optional summary for theme gate",
      "quotes": ["Direct quote for citation"],
      "entities": ["ICE", "Minnesota"],
      "vault_note_path": "40_Reference/research/example.md",
      "captured_at": "2026-08-25T12:00:00Z"
    }
  ],
  "actor": "n8n_external_research"
}
```

Response: `{ attached, skipped, deduped, auto_republish }` per item.

**Feature flag:** `EXTERNAL_RESEARCH_INGEST_ENABLED` (default on). Attach triggers `auto_republish_for_new_members` when the package already has a published story.

**Demo host:** mutating — returns 403 (correct).

## n8n workflow (operator)

Importable template: [`docs/n8n/external_research_loop.workflow.json`](n8n/external_research_loop.workflow.json)

### Prerequisites

| Component | Notes |
|-----------|--------|
| **n8n** | Homelab instance with HTTP Request + Code nodes (PopOS or Widow-adjacent) |
| **SearXNG** | Local instance reachable from n8n (`SEARXNG_BASE`, e.g. `http://192.168.93.99:8080`) |
| **NI API** | Widow LAN or PopOS Caddy front door — **not** the public demo host (mutating routes return 403) |

### Environment variables (n8n)

| Key | Example | Purpose |
|-----|---------|---------|
| `NI_API_BASE` | `http://192.168.93.101:8000` | Widow API base (no trailing slash) |
| `SEARXNG_BASE` | `http://192.168.93.99:8080` | SearXNG JSON search endpoint |

Optional: configure n8n credentials if your NI API requires auth headers (internal LAN often does not).

### Import steps

1. In n8n: **Workflows → Import from file** → select `docs/n8n/external_research_loop.workflow.json`.
2. Set workflow env vars (`NI_API_BASE`, `SEARXNG_BASE`) under **Settings → Variables** or per-workflow env.
3. Leave workflow **inactive** until SearXNG + NI API smoke test passes.
4. Manual test: execute once; confirm `POST .../external_research/attach` returns `{ attached, skipped, deduped }`.
5. Activate cron (default every 6h) or replace Schedule Trigger with a webhook for on-demand runs.

### Workflow steps (template)

1. **Trigger:** cron every 6h (or webhook from living-follow poll).
2. **Input:** `GET /api/follows?tier=living` — uses `metadata.package_id` on each living follow.
3. **SearXNG:** query from follow title / episode id; limit 5 results.
4. **Obsidian (optional):** add a Code node to write vault notes under `40_Reference/external_research/` with URL, summary, quotes; pass `vault_note_path` in attach payload.
5. **HTTP Request:** `POST /api/editorial/packages/{package_id}/external_research/attach` with normalized `items` + `actor: n8n_external_research`.
6. **Branch:** if `attached.length > 0`, log success; living auto-republish picks up new `processed_document` members when published.

### Manual curl smoke test

```bash
curl -sS -X POST "${NI_API_BASE}/api/editorial/packages/PACKAGE_ID/external_research/attach" \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [{
      "url": "https://example.org/report",
      "title": "Example report",
      "summary_text": "Optional summary for theme gate",
      "quotes": [],
      "entities": [],
      "captured_at": "2026-08-25T12:00:00Z"
    }],
    "actor": "n8n_external_research"
  }'
```

Expect `{ "success": true, "data": { "attached": [...], "skipped": [], "deduped": [] } }` when gates pass.

## Gates (NI-side)

- URL dedup vs package members and `processed_documents`
- Domain `exclude_keywords` from `domain_synthesis_config.topic_filter`
- Theme attach gate (`editorial_package_attach_gate.attach_allowed`)

## Research rail honesty

Web captures are **gray literature**. Do not create `claim_evidence_appraisal` rows from `web_capture` / `searxng` origin in this phase — Europe PMC / PubMed paths remain the evidence-grade sources.

## Env

| Key | Purpose |
|-----|---------|
| `EXTERNAL_RESEARCH_INGEST_ENABLED` | Master switch for n8n/SearXNG attach (default on) |
| `LIVING_REPUBLISH_MIN_HOURS` | Throttle republish after attach |
| `LIVING_REPUBLISH_MIN_NEW_MEMBERS` | Bypass throttle when enough new members |
| `LIVING_COOLING_DAYS` | Days dormant before cooling sweep pauses a living follow (default 14) |
| `PULSE_DIGEST_ENABLED` | AutomationManager pulse digest job (default on) |
| `PULSE_STUBS_ENABLED` | Optional LLM movement stubs in digest snapshots (default off) |
| `PULSE_STUBS_TOP_N` | Max cards to stub per digest run (default 10) |
| `FOLLOW_REGISTRY_ENABLED` | Follow CRUD routes (default on) |
| `LIVING_STORIES_ENABLED` | Living promote + cooling sweep (default on) |

Widow `.env` can omit these — defaults are on. Set `=false` to disable a surface.

See also `docs/PULSE_AND_FOLLOWS.md`.
