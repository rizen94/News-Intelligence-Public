# Log Analysis — News Intelligence System

Created: 2026-03-07

This directory contains filtered log data, structured extracts, and system context for analyzing how the News Intelligence system is behaving and identifying areas for improvement.

---

## Contents

| File | What it is | Size |
|------|------------|------|
| `README.md` | This file | — |
| `LOG_SUMMARY_2026-03-07.md` | Human-readable analysis of all logs. Covers uptime, errors, performance, RSS collection, entity extraction, and a prioritized list of recommended improvements. | ~8 KB |
| `SYSTEM_CONTEXT.md` | Architecture overview, route inventory, database schemas, frontend polling behavior, service dependencies. Reference for understanding log entries. | ~6 KB |
| `errors_extract.jsonl` | Every HTTP 4xx/5xx response from `activity.jsonl`, filtered to key fields (timestamp, method, path, status_code, duration_ms, message). | 2.3 MB, 10,411 records |
| `slow_requests.jsonl` | Every request over 5 seconds from `activity.jsonl`, same fields as above. | 1.1 MB, 4,926 records |
| `hourly_stats.csv` | One row per hour: total requests, error count, error %, avg/p95/max latency. Ready for charting. | 3.4 KB, 72 rows |

---

## Quick analysis guide

### What went wrong?

Start with `LOG_SUMMARY_2026-03-07.md` sections 2 (Mar 2 outage) and 3 (error inventory).

### Is the system healthy right now?

Section 6 of the log summary — current session shows 14/14 routes healthy, 127ms avg latency, <1% error rate.

### Where are the bottlenecks?

- `slow_requests.jsonl` — every request that took over 5 seconds
- `hourly_stats.csv` — import into a spreadsheet and chart `avg_ms` and `error_pct` over time

### What should we fix first?

Section 9 of the log summary ranks improvements by severity: critical, high, medium, low.

### How does the system work?

`SYSTEM_CONTEXT.md` — architecture diagram, every API route, database schemas, polling intervals, and service dependencies.

---

## How to use the data files

### errors_extract.jsonl

Each line is a JSON object:

```json
{"timestamp": "2026-03-02T...", "method": "GET", "path": "/api/...", "status_code": 500, "duration_ms": 12289.1, "message": "..."}
```

Filter by status code:

```bash
python3 -c "
import json
for line in open('errors_extract.jsonl'):
    d = json.loads(line)
    if d['status_code'] == 500:
        print(d['timestamp'], d['path'])
" | head -20
```

### slow_requests.jsonl

Same format. Find the worst offenders:

```bash
python3 -c "
import json
for line in open('slow_requests.jsonl'):
    d = json.loads(line)
    if d['duration_ms'] > 20000:
        print(f\"{d['duration_ms']:8.0f}ms  {d['path']}\")
"
```

### hourly_stats.csv

Columns: `hour, total_requests, errors, error_pct, avg_ms, p95_ms, max_ms`

Import into any spreadsheet or use pandas:

```python
import pandas as pd
df = pd.read_csv('hourly_stats.csv')
df.plot(x='hour', y=['avg_ms', 'p95_ms'], figsize=(14,5), title='Response Time by Hour')
```

---

## Key findings (TL;DR)

1. **Mar 2 outage lasted ~33 hours** with 100% error rates — likely a database or network failure.
2. **Ollama is not auto-started**, so entity extraction and topic clustering fail after every reboot.
3. **6 out of 13 entity extractions failed** (46%) due to Ollama being down.
4. **0 out of 5 topic extractions found any topics** — needs investigation.
5. **RSS filtering rejects ~99% of articles** — the low-impact threshold (0.4) may be too aggressive.
6. **Missing `analysis_updated_at` column** causes pipeline errors and transaction aborts.
7. **Current session is clean**: 14/14 healthy, 0 issues, ~127ms avg latency, <1% errors.
