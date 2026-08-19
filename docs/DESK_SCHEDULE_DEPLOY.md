# Desk schedule deploy checklist (Widow + PopOS)

After pulling the desk three-band schedule code, set these on **Widow**
`/opt/news-intelligence/.env` (and mirror hours on PopOS `.env.popos_worker` if present).

```bash
PIPELINE_SCHEDULE_TZ=America/New_York
PIPELINE_HEAVY_START_HOUR=1
PIPELINE_HEAVY_END_HOUR=6
PIPELINE_MORNING_START_HOUR=6
PIPELINE_MORNING_END_HOUR=10
PIPELINE_DESK_START_HOUR=10
PIPELINE_DESK_END_HOUR=1
NIGHTLY_PIPELINE_START_HOUR=1
NIGHTLY_PIPELINE_END_HOUR=6
NIGHTLY_PIPELINE_EXCLUSIVE=1
# Important: turn OFF catch-up override so desk GPU deferral works
PIPELINE_QUIET_HOURS_DISABLED=false
# Presence soft-gate (PopOS sensor); stale >90s falls back to wall-clock
DESK_PRESENCE_STALE_SEC=90
DESK_PRESENCE_DISABLED=false
OLLAMA_PRIORITY=low
```

Then:

1. Restart Widow API: `sudo systemctl restart news-intelligence-api-public`
2. Restart PopOS phase workers (user systemd target)
3. Enable desk presence on PopOS (user units):
   ```bash
   mkdir -p ~/.config/systemd/user
   ln -sf "$HOME/Documents/projects/News Intelligence/infrastructure/ni-desk-presence.user.service" \
     ~/.config/systemd/user/ni-desk-presence.user.service
   ln -sf "$HOME/Documents/projects/News Intelligence/infrastructure/ni-desk-presence.user.timer" \
     ~/.config/systemd/user/ni-desk-presence.user.timer
   systemctl --user daemon-reload
   systemctl --user enable --now ni-desk-presence.user.timer
   ```
4. Homelab ollama-proxy must expose `last_high_at` / `ni_cidrs` on `GET /api/proxy/stats`
   (rebuild `ai-lab-ollama-proxy` after pulling Homelab changes).
5. Confirm Monitor `backlog_status.pipeline_schedule`:
   - `schedule_model` = `desk_three_band_v1`
   - `presence_model` = `desk_presence_v1`
   - During desk hours (unlocked, idle): `active_window=desk_light`, `popos_gpu_work_allowed=false`
   - Locked screen (any band): `popos_gpu_work_allowed=true`, reason `session_locked`
   - Unlock + Open WebUI chat: reason `interactive_ollama`, workers may log `desk_gpu_deferred`
   - `rss_collection_allowed=true` always
6. Over 2–3 mornings: `PYTHONPATH=api python3 api/scripts/intake_catchup_latency.py`

## Presence rules (GPU bit only)

| Situation | `popos_gpu_work_allowed` |
|-----------|--------------------------|
| Session locked | true |
| Unlocked + HIGH/non-NI Ollama recent (`DESK_INTERACTIVE_IDLE_SEC`, default 120s) | false |
| Unlocked + idle + desk_light | false (clock) |
| Unlocked + idle + heavy/morning | true (clock) |
| Presence stale (> `DESK_PRESENCE_STALE_SEC`) | clock only |

NI traffic: Widow `192.168.93.101` via proxy LOW CIDRs; PopOS workers must send
`X-Ollama-Priority: low` (`OLLAMA_PRIORITY=low`). Other agents (OWUI, Cursor, Cline)
must **not** use the Widow IP — they stay HIGH/interactive.

See [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md) and [POPOS_PHASE_WORKER.md](POPOS_PHASE_WORKER.md).
