# Widow: DB-adjacent cron

**Goal:** Run **light, SQL-heavy sync** next to PostgreSQL on **Widow**. **AutomationManager runs in the Widow API** (`news-intelligence-api-public.service`) — use `AUTOMATION_DISABLED_SCHEDULES` so cron and AutomationManager do not duplicate work.

**Boot / systemd:** [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md)

**How processing flows:** `collect_rss_feeds` inserts rows into domain **`articles`** tables. Downstream work (enrichment, entity extraction, LLM, topic clustering) is driven by **AutomationManager** in the Widow API process, which reads **database state**. The **`content_enrichment`** scheduled task drains pending full-text fetches on a **5-minute** cadence.

**Full operator checklist:** [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md)

---

## 1. Widow API `.env` (AutomationManager)

Add to **`/opt/news-intelligence/.env`** (systemd `news-intelligence-api-public`):

```bash
# RSS runs on Widow (systemd secondary and/or cron --rss); do not fetch feeds every collection_cycle here
AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true

# Phases run on Widow via api/scripts/run_widow_db_adjacent.py — disable here to avoid duplicate work
AUTOMATION_DISABLED_SCHEDULES=context_sync,entity_profile_sync,pending_db_flush
```

Restart the API after changing env: `sudo systemctl restart news-intelligence-api-public`.

---

## 2. Widow: RSS

**Option A (default):** Keep **`newsplatform-secondary.service`** — RSS every 10 minutes when the operating schedule allows (weekday 07:00–16:00 and nightly 00:00–07:00 local; see **`api/services/pipeline_schedule_service.py`**). During **quiet** windows the worker logs a skip and sleeps — no separate cron time math is required.

**Option B:** Stop the secondary service and run **`run_widow_db_adjacent.py --rss`** from cron instead. **Do not** run both on the same interval unless you want duplicate collection attempts (feeds should dedupe, but it wastes work). The `--rss`, `--context-sync`, and `--entity-profile-sync` flags honor the same schedule gates; **`--pending-db-flush`** always runs.

### New domain silos (medicine, artificial-intelligence, etc.)

RSS and automation discover domains from **`api/config/domains/*.yaml`** at runtime (`url_schema_pairs()` / `get_active_domain_keys()`). **Widow and the main PC must deploy the same Git tree** (or at least the same `api/config/domains/` files). If Widow is behind on commits, `collect_rss_feeds` there will only query the older domain list and new silos stay empty.

After each migration + `provision_domain.py`, run on any machine that can reach the DB:

```bash
PYTHONPATH=api uv run python api/scripts/ensure_domain_silo_alignment.py
```

That sets **`public.domains.is_active = TRUE`** for YAML-active keys and prints **active `rss_feeds` counts** so you can see a zero before a wasted night.

**Main vs Widow:** Keep **`AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true`** on the main host so only one place runs RSS (see §1). **Both** hosts still need identical YAML so the **one** RSS runner ingests **all** silos; the main PC does not need to fetch RSS twice.

---

## 3. Widow: context sync + entity profile sync + pending DB flush

Script: **`api/scripts/run_widow_db_adjacent.py`**

```bash
cd /opt/news-intelligence
mkdir -p logs
PYTHONPATH=api .venv/bin/python api/scripts/run_widow_db_adjacent.py \
  --context-sync --entity-profile-sync --pending-db-flush
```

Install cron from **`infrastructure/widow-db-adjacent.cron`** (edit user/path, then copy to `/etc/cron.d/`).

---

## 4. Widow API and AutomationManager (current architecture)

**Widow runs the full NI API** via `news-intelligence-api-public.service` (AutomationManager embedded). Do **not** start a second API or `start_system.sh` alongside systemd. DB-adjacent cron handles only the phases listed in `AUTOMATION_DISABLED_SCHEDULES`; all LLM-heavy phases run in-process on Widow (with optional PopOS overflow via `OLLAMA_DUAL_HOST_ROUTING_ENABLED`). See [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md) and [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md).

---

## 5. Adding more Widow-only phases later

Pick schedules that are **mostly DB / CPU** and **do not** require local Ollama on Widow. Extend `run_widow_db_adjacent.py` and add their names to **`AUTOMATION_DISABLED_SCHEDULES`** so AutomationManager does not duplicate them. LLM-heavy phases stay in AutomationManager on Widow (Ollama on `:11434`, PopOS overflow when dual routing is enabled).
