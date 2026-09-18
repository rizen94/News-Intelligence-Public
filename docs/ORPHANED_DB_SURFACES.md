# Orphaned database surfaces

Tables a migration created that no live code reads or writes. Kept, labelled, and listed here rather
than dropped: a table with no reader still costs backup volume, `pg_dump` time, and reviewer
attention, but dropping one needs a row-count and provenance check on Widow first.

Audited 2026-09 by matching every `CREATE TABLE` in `api/database/migrations/` against all tracked
sources. Marked with `COMMENT ON TABLE` by
[migration 306](../api/database/migrations/306_mark_orphaned_intelligence_tables.sql).

| Table | Created by | Why it is orphaned |
|-------|-----------|--------------------|
| `intelligence.unseeded_claims_parking_lot` | `261_create_unseeded_claims_parking_lot.sql` | No reader or writer. **Not** the *editorial* parking lot that `api/scripts/triage_editorial_parking_lot.py` operates on — that is a different table, which is why a name-based grep looks like a false negative here. |
| `intelligence.entity_alias_merge_log` | `262_entity_alias_merge_hygiene.sql` | Alias-merge audit trail that nothing writes. The merge hygiene logic in that migration landed, the log table never got wired to it. |

## Before dropping either

1. `SELECT count(*) FROM <table>;` on Widow — a non-zero count means something wrote to it at some
   point and the history may be worth exporting.
2. Confirm no out-of-tree consumer: Homelab `postgres-mcp` reads `news_intel` read-only, and vault or
   notebook queries are not in this repo.
3. Drop in its own migration so it is revertible from the migration log.

## Not on this list, and why

Three `intelligence.congress_*` tables from migration `300_congress_trade_signals.sql` are also
unreferenced, but that migration is part of in-flight congress trade signals work. Re-audit once it
lands.

`intelligence.investigation_parked_resolution` and `intelligence.investigation_provisional_mints`
look orphaned to a name-based scan but are **live** — they are reached through the
`T_PARKED_RESOLUTION` / `T_PROVISIONAL_MINTS` constants in `api/config/investigation_tables.py`, per
the SSOT rule against qualified `nri.` SQL literals. Any future audit of this kind has to resolve
those constants before believing a table is dead.

## Re-running the audit

There is no standing verifier for this, because a name-based scan cannot see tables reached through a
constant (see above) and would produce false positives. To repeat it by hand, extract
`CREATE TABLE` names from `api/database/migrations/*.sql`, grep the tree for each bare table name,
and then hand-check every hit — excluding `docs/_archive/`, `docs/archive/`, `diagnostics/`, and
`repomix-*` output, all of which are tracked and keep dead names alive.
