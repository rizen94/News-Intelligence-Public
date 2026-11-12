# Workspace Hygiene — Prevent Repo Bloat

## Rule: Zero Tolerance for Runtime Data in Repo

Never commit files that are **generated during runtime** or **data outputs**:

| Forbidden in repo | Allowed alternative |
|-------------------|--------------------|
| `*.log` | Write to `/dev/null` or OS journal (systemd) |
| `*.db`, `*.sqlite`, `postgres_data/` | Docker volumes / mounted dirs outside repo |
| `data/` dumps, CSV exports, JSON snapshots | External storage: MinIO, S3, NAS mount |
| `backups/`, `.bak`, `.backup` | Off-repo backups only |
| `__pycache__/`, `*.pyc`, `*.pyo` | Let Python cache live; never commit |
| `node_modules/`, `.venv/`, `env/` | Docker or local install only |
| `.env`, `.env.*` (secrets) | Vault / secrets manager; `.env.example` is OK |

**Threshold**: Any single file **>1 MB** must be audited before commit. If it's data, logs, cache, or build output — block it.

## Rule: Archive = Historical Only, Never Operational

When archiving old code/docs:

1. Move to `archive/` (root-level) for project-wide archives OR keep under the relevant module (e.g., `api/database/migrations/archive/`)
2. Root-level `archive/` is in `.gitignore` — never track it in git
3. Only commit archive files that have **active reference value** (migration SQL, key design docs)
4. Clean root-level archive entries quarterly or when they exceed 500 KB total

## Rule: No Duplicate Archives

If a feature/page/component is replaced by a new implementation:

1. Delete the old code immediately (don't leave it in `_archived_*` or `legacy_` directories)
2. If reference value exists, write a brief migration note and delete the rest
3. Never create `_archived_duplicates/`, `old_ui/`, `deprecated/` — just delete

**Rationale**: These accumulate into multi-MB dead weight (we had 1.7 MB of this alone).

## Rule: Pre-Commit Bloat Check

Before any commit that adds files, run:

```bash
# Quick check for oversized additions (>500 KB)
find . -maxdepth 3 -type f -size +500k \
  -not -path './.git/*' \
  -not -path './node_modules/*' \
  -not -name '*.md' | sort -rh | head -20
```

If any non-doc file over 500 KB appears, **do not commit** it — identify if it should be:
- Gitignored (runtime data) → add to `.gitignore` + `.clinerules/workspace-hygiene.md`
- External storage (large exports) → document alternative location
- Tracked source code (rare) → keep only if actively used

## Rule: .gitignore Must Be Comprehensive

Update `.gitignore` immediately when new runtime patterns appear. Add entries under these sections:

1. `# Runtime spill when DB is unavailable` — ephemeral local writes
2. `# Logs` — all log patterns
3. `# Temporary files` — temp/tmp patterns  
4. `# Backup files` — backup/bak patterns
5. `# Generated exports` — any script output directory

## Rule: Quarterly Cleanup Audit

Every quarter, run this from the repo root:

```bash
echo "=== Large tracked files ==="
git ls-tree -r HEAD --name-only | while read f; do
  size=$(du -s "$f" 2>/dev/null | awk '{print $1}')
  [ "$size" -gt 50 ] && echo "$size KB $f"
done | sort -rn | head -30

echo "=== Disk size ==="
du -sh .git/
du -sh ./web/
du -sh ./api/
```

If `.git/` exceeds 100 MB or tracked non-source files exceed 5 MB total:
- Run `git gc --aggressive`
- Delete unused local branches
- Audit large tracked files for archival (move to external storage)
