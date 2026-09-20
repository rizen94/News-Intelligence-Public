This file is a merged representation of a subset of the codebase, containing specifically included files and files not matching ignore patterns, combined into a single document by Repomix.
The content has been processed where line numbers have been added, content has been compressed (code blocks are separated by ⋮---- delimiter).

# File Summary

## Purpose
This file contains a packed representation of a subset of the repository's contents that is considered the most important context.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.
- Pay special attention to the Repository Description. These contain important context and guidelines specific to this project.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Only files matching these patterns are included: api/nri_core/**/*.py, api/config/runtime.py, api/config/investigation_tables.py, api/config/database_targets.py, api/config/schedulers.yaml, api/domains/intelligence_hub/routes/investigation.py, api/database/migrations/237_investigation_schema_merge.sql, docs/INVESTIGATION.md, docs/UNIFICATION_BASELINE.md, docs/UNIFICATION_CUTOVER.md
- Files matching these patterns are excluded: **/__pycache__/**, **/.venv/**, **/venv/**, repomix-nri-output.*
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Line numbers have been added to the beginning of each line
- Content has been compressed - code blocks are separated by ⋮---- delimiter
- Files are sorted by Git change count (files with more changes are at the bottom)

# User Provided Header
NRI (Investigation) — Repomix bundle from api/nri_core/ after monorepo unification. Pre-cutover source was /opt/nri on Widow.

# Directory Structure
```
api/
  config/
    database_targets.py
    investigation_tables.py
    runtime.py
    schedulers.yaml
  database/
    migrations/
      237_investigation_schema_merge.sql
  domains/
    intelligence_hub/
      routes/
        investigation.py
  nri_core/
    evidence/
      tests/
        __init__.py
        test_entity_bridge.py
        test_subject_skip.py
      __init__.py
      __main__.py
      entity_bridge.py
      mention_resolver.py
      ni_reader.py
      parked_review.py
    llm/
      __init__.py
    loop/
      delta/
        __init__.py
        gather.py
      detect/
        __init__.py
        cooccurrence.py
      promote/
        __init__.py
        gate.py
      queue/
        __init__.py
        selector.py
      reason/
        __init__.py
        ach_synthesizer.py
      reassess/
        __init__.py
        rules.py
      scheduler/
        __init__.py
        __main__.py
        run_loop.py
      shadow/
        __init__.py
        seed.py
      skeptic/
        __init__.py
        agent.py
      tests/
        test_detect.py
        test_reassess.py
        test_shadow_prune.py
        test_skeptic.py
      __init__.py
    services/
      __init__.py
      bridge_qa.py
      entity_claims.py
      integration.py
      parked.py
    spine/
      api/
        __init__.py
        app.py
        lookup.py
      ingest/
        gleif/
          __init__.py
          loader.py
        icij/
          loader.py
        mappers/
          congress.py
          edgar.py
        opensanctions/
          loader.py
        wikidata/
          __init__.py
          crosswalk.py
          notable.py
        __init__.py
        __main__.py
      resolution/
        __init__.py
        anchor_join.py
        lazy_mint.py
        matcher.py
      resolver/
        __init__.py
        git_resolver.py
      store/
        __init__.py
        postgres_store.py
      tests/
        mappers/
          test_edgar_dedupe.py
          test_edgar.py
        test_lazy_mint.py
        test_match_perf.py
        test_match.py
        test_resolver.py
      __init__.py
    __init__.py
    config.py
    constants.py
    resolver_runner.py
docs/
  INVESTIGATION.md
  UNIFICATION_BASELINE.md
  UNIFICATION_CUTOVER.md
```

# Files

## File: api/config/database_targets.py
````python
"""
Database connection targets — news_intel pool vs identity_spine vs maintenance direct port.
"""
⋮----
def news_intel_connect_kwargs() -> dict[str, str | int]
⋮----
cfg = get_runtime_config()
⋮----
def news_intel_dsn() -> str
⋮----
kw = news_intel_connect_kwargs()
⋮----
def spine_dsn() -> str
⋮----
def maintenance_connect_kwargs() -> dict[str, str | int]
⋮----
"""
    Maintenance scripts bypass PgBouncer when DB_PORT=6432 on localhost.
    """
⋮----
host = str(cfg["db_host"])
env_port = int(cfg["db_port"])
⋮----
port = int(cfg["db_maintenance_port"])
⋮----
port = env_port
````

## File: api/config/investigation_tables.py
````python
"""
Qualified investigation table names — single source for SQL.

Pre-cutover: nri.resolved_mentions etc.
Post-cutover: set USE_INVESTIGATION_PREFIXED_TABLES=true → intelligence.investigation_* tables.
"""
⋮----
def _qualified(base: str) -> str
⋮----
schema = investigation_schema()
prefix = investigation_table_prefix()
⋮----
# Core investigation tables
T_WATERMARKS = _qualified("watermarks")
T_RESOLVED_MENTIONS = _qualified("resolved_mentions")
T_PARKED_RESOLUTION = _qualified("parked_resolution")
T_ENTITY_BRIDGE = _qualified("entity_bridge")
T_PROVISIONAL_MINTS = _qualified("provisional_mints")
T_FTM_ENTITY_CACHE = _qualified("ftm_entity_cache")
T_LOOP_RUN = _qualified("loop_run")
⋮----
# Intelligence tables (not migrated)
T_ENTITY_PROFILES = "intelligence.entity_profiles"
T_CONTEXTS = "intelligence.contexts"
T_CONTEXT_ENTITY_MENTIONS = "intelligence.context_entity_mentions"
T_EXTRACTED_CLAIMS = "intelligence.extracted_claims"
````

## File: api/config/runtime.py
````python
"""
Single source for environment variables (investigation / NRI unification).

Application code should import from here instead of os.environ.get.
Scripts may load dotenv before importing config modules.
"""
⋮----
def _env(name: str, default: str = "") -> str
⋮----
def _env_bool(name: str, default: bool = False) -> bool
⋮----
raw = _env(name)
⋮----
def _env_int(name: str, default: int) -> int
⋮----
def _env_float(name: str, default: float) -> float
⋮----
@lru_cache(maxsize=1)
def get_runtime_config() -> dict[str, Any]
⋮----
"""Merged runtime settings for NI + investigation (nri_core)."""
⋮----
# news_intel pool (see database_targets for DSN builders)
⋮----
# identity_spine (separate database)
⋮----
# Investigation schema (pre-migration: nri; post-migration: intelligence + prefix)
⋮----
# Legacy proxy (deprecated after unification)
⋮----
# Feature flags
⋮----
# Mention resolver / automation
⋮----
# Ollama
⋮----
def investigation_schema() -> str
⋮----
cfg = get_runtime_config()
⋮----
def investigation_table_prefix() -> str
⋮----
def mention_resolve_batch_limit() -> int
⋮----
def mention_resolve_budget_seconds() -> float
````

## File: api/config/schedulers.yaml
````yaml
# Single scheduler manifest — owner, enabled, notes.
# Env gates: AUTOMATION_DISABLED_SCHEDULES, schedulers.yaml enabled flag.

schedulers:
  automation_manager:
    owner: automation_manager
    interval_seconds: 5
    enabled: true
    note: Primary processing scheduler (all phases)

  orchestrator_coordinator:
    owner: orchestrator_coordinator
    interval_seconds: 60
    enabled: true
    note: Collection cadence + finance interest; processing nudge off via pipeline_conductor

  newsplatform_secondary:
    owner: systemd
    unit: newsplatform-secondary.service
    enabled: true
    note: RSS ingest ~10min when schedule allows

  widow_db_adjacent_cron:
    owner: cron
    file: infrastructure/widow-db-adjacent.cron
    interval: "*/15 * * * *"
    enabled: true
    jobs:
      - name: context_sync
        script_flag: --context-sync
        note: AUTHORITATIVE on Widow when in AUTOMATION_DISABLED_SCHEDULES for automation
      - name: entity_profile_sync
        script_flag: --entity-profile-sync
      - name: pending_db_flush
        script_flag: --pending-db-flush

  nri_mention_resolver_timer:
    owner: systemd
    unit: nri-mention-resolver.timer
    enabled: false
    replaced_by: mention_resolution
    note: Disabled after unification — use AutomationManager mention_resolution phase

  nri_loop_timer:
    owner: systemd
    unit: nri-loop.timer
    enabled: false
    note: Shadow loop; default off via NRI_LOOP_ENABLED

  nri_api:
    owner: systemd
    unit: nri-api.service
    enabled: false
    replaced_by: news-intelligence-api-public
    note: Retired after nri_core in-process routes

# context_sync split-brain resolution: cron owns sync on Widow prod (see widow-db_adjacent)
````

## File: api/database/migrations/237_investigation_schema_merge.sql
````sql
-- Investigation schema unification: nri.* → intelligence.investigation_*
-- Apply during maintenance window. Set USE_INVESTIGATION_PREFIXED_TABLES=true after cutover.
-- Rollback: pg_restore from pre-cutover dump.

BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.investigation_watermarks (
    LIKE nri.watermarks INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_resolved_mentions (
    LIKE nri.resolved_mentions INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_parked_resolution (
    LIKE nri.parked_resolution INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_entity_bridge (
    LIKE nri.entity_bridge INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_provisional_mints (
    LIKE nri.provisional_mints INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_ftm_entity_cache (
    LIKE nri.ftm_entity_cache INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS intelligence.investigation_loop_run (
    LIKE nri.loop_run INCLUDING ALL
);

INSERT INTO intelligence.investigation_watermarks
SELECT * FROM nri.watermarks
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_resolved_mentions
SELECT * FROM nri.resolved_mentions
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_parked_resolution
SELECT * FROM nri.parked_resolution
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_entity_bridge
SELECT * FROM nri.entity_bridge
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_provisional_mints
SELECT * FROM nri.provisional_mints
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_ftm_entity_cache
SELECT * FROM nri.ftm_entity_cache
ON CONFLICT DO NOTHING;

INSERT INTO intelligence.investigation_loop_run
SELECT * FROM nri.loop_run
ON CONFLICT DO NOTHING;

-- Compatibility views for homelab postgres-mcp (optional; drop after MCP updated)
CREATE OR REPLACE VIEW nri.watermarks AS SELECT * FROM intelligence.investigation_watermarks;
CREATE OR REPLACE VIEW nri.resolved_mentions AS SELECT * FROM intelligence.investigation_resolved_mentions;
CREATE OR REPLACE VIEW nri.parked_resolution AS SELECT * FROM intelligence.investigation_parked_resolution;
CREATE OR REPLACE VIEW nri.entity_bridge AS SELECT * FROM intelligence.investigation_entity_bridge;
CREATE OR REPLACE VIEW nri.provisional_mints AS SELECT * FROM intelligence.investigation_provisional_mints;
CREATE OR REPLACE VIEW nri.ftm_entity_cache AS SELECT * FROM intelligence.investigation_ftm_entity_cache;
CREATE OR REPLACE VIEW nri.loop_run AS SELECT * FROM intelligence.investigation_loop_run;

COMMIT;
````

## File: api/domains/intelligence_hub/routes/investigation.py
````python
"""
Investigation API routes — /investigation/* (product) with /nri/* deprecation shims.
"""
⋮----
investigation_router = APIRouter(prefix="/api", tags=["investigation"])
nri_legacy_router = APIRouter(prefix="/api", tags=["nri-legacy"])
⋮----
@investigation_router.get("/investigation/health")
@nri_legacy_router.get("/nri/health")
def investigation_health() -> dict
⋮----
@investigation_router.patch("/investigation/parked/{parked_id}")
@nri_legacy_router.patch("/nri/parked/{parked_id}")
def investigation_review_parked(parked_id: int, body: dict = Body(...)) -> dict
⋮----
@investigation_router.get("/investigation/entity_bridge/{entity_profile_id}")
@nri_legacy_router.get("/nri/entity_bridge/{entity_profile_id}")
def investigation_entity_bridge(entity_profile_id: int) -> dict
⋮----
@investigation_router.get("/investigation/hypotheses/{hyp_id}")
@nri_legacy_router.get("/nri/hypotheses/{hyp_id}")
def investigation_hypothesis_detail(hyp_id: str) -> dict
⋮----
@investigation_router.post("/investigation/spine/match")
@nri_legacy_router.post("/nri/spine/match")
def investigation_spine_match(body: dict = Body(...)) -> dict
⋮----
@investigation_router.get("/investigation/resolution_stats")
@nri_legacy_router.get("/nri/resolution_stats")
def investigation_resolution_stats(domain_key: str | None = Query(None)) -> dict
⋮----
@investigation_router.get("/investigation/loop_runs")
@nri_legacy_router.get("/nri/loop_runs")
def investigation_loop_runs(limit: int = Query(20, ge=1, le=100)) -> dict
⋮----
@investigation_router.get("/investigation/ftm_cache_stats")
@nri_legacy_router.get("/nri/ftm_cache_stats")
def investigation_ftm_cache_stats() -> dict
````

## File: api/nri_core/evidence/tests/__init__.py
````python

````

## File: api/nri_core/evidence/tests/test_entity_bridge.py
````python
def test_bridge_auto_link_calls_upsert_and_cache()
⋮----
def test_upsert_entity_bridge_executes_sql()
⋮----
mock_conn = MagicMock()
mock_cur = MagicMock()
````

## File: api/nri_core/evidence/tests/test_subject_skip.py
````python
def test_subject_type_skipped_by_default(monkeypatch)
⋮----
def test_person_not_skipped()
⋮----
def test_non_entity_types_includes_subject()
````

## File: api/nri_core/evidence/__init__.py
````python
"""Store B evidence adapters — read-only NI tables."""
````

## File: api/nri_core/evidence/__main__.py
````python
"""Evidence CLI — mention resolution batches."""
⋮----
def main(argv: list[str] | None = None) -> int
⋮----
parser = argparse.ArgumentParser(description="NRI evidence adapter")
sub = parser.add_subparsers(dest="command", required=True)
⋮----
resolve_p = sub.add_parser("resolve", help="Run mention resolver batch or budgeted drain")
⋮----
args = parser.parse_args(argv)
⋮----
lim = args.limit if args.limit is not None else _resolve_batch_limit()
result = resolve_batch(limit=lim)
⋮----
result = resolve_drain(
````

## File: api/nri_core/evidence/entity_bridge.py
````python
"""Bridge NI entity_profile_id to identity spine ftm_id."""
⋮----
cfg = get_config()
⋮----
def sync_ftm_entity_cache(ftm_id: str) -> None
⋮----
entity = get_entity(ftm_id)
````

## File: api/nri_core/evidence/mention_resolver.py
````python
"""Resolve NI mentions → nri.resolved_mentions (NRI-owned writes)."""
⋮----
NON_ENTITY_TYPES = frozenset({"subject"})
⋮----
cfg = get_config()
⋮----
def _should_skip_mention(mention: dict[str, Any]) -> bool
⋮----
entity_type = (mention.get("entity_type") or "").lower()
⋮----
def resolve_batch(limit: int = 200) -> dict[str, Any]
⋮----
watermark = ni_reader.get_watermark("mention_resolver")
mentions = ni_reader.fetch_new_mentions(since_id=watermark, limit=limit)
⋮----
stats: dict[str, Any] = {
max_id = watermark
⋮----
max_id = max(max_id, int(mention["id"]))
⋮----
mention_text = str(mention["mention_text"])
⋮----
result = match_mention(text=mention_text)
ftm_id = result.ftm_id
score = result.score
tier = result.tier
status = result.status
park_reason = "below_auto_link_threshold"
⋮----
lazy = lazy_mint_on_miss(
⋮----
ftm_id = lazy.ftm_id
score = lazy.score
status = "provisional"
⋮----
# Downgrade auto_linked when bridge QA would reject the FtM pairing
⋮----
status = "parked"
park_reason = qa_reason
ftm_id = None
⋮----
pass  # provisional mints require human review — no entity_bridge
⋮----
candidate = result.candidates[0]["id"] if result.candidates else None
⋮----
def _resolve_batch_limit(default: int = 500) -> int
⋮----
def _resolve_drain_budget_seconds(default: float = 840.0) -> float
⋮----
"""
    Run mention resolver batches until idle, budget exhausted, or max_batches reached.

    Intended for systemd oneshot: one timer tick drains CEM backlog proportional to
    creation rate without starving other Widow work.
    """
batch_limit = int(limit) if limit is not None else _resolve_batch_limit()
budget = float(budget_seconds) if budget_seconds is not None else _resolve_drain_budget_seconds()
t0 = time.monotonic()
totals: dict[str, Any] = {
⋮----
stats = resolve_batch(limit=batch_limit)
⋮----
processed = int(stats.get("processed") or 0)
````

## File: api/nri_core/evidence/ni_reader.py
````python
"""Read-only adapter to news_intel.intelligence.* with watermark support."""
⋮----
@contextlib.contextmanager
def news_intel_connection() -> Generator[Any, None, None]
⋮----
cfg = get_config()
conn = psycopg2.connect(cfg.news_intel_dsn)
⋮----
def get_watermark(name: str) -> int
⋮----
row = cur.fetchone()
⋮----
def set_watermark(name: str, value: int) -> None
⋮----
def fetch_new_mentions(since_id: int = 0, limit: int = 500) -> list[dict[str, Any]]
⋮----
def fetch_context(context_id: int) -> dict[str, Any] | None
⋮----
def context_exists(context_id: int) -> bool
⋮----
def fetch_claims_for_context(context_id: int) -> list[dict[str, Any]]
⋮----
def fetch_entity_profiles(limit: int = 100) -> list[dict[str, Any]]
````

## File: api/nri_core/evidence/parked_review.py
````python
"""Review parked resolution queue entries."""
⋮----
cfg = get_config()
⋮----
row = cur.fetchone()
````

## File: api/nri_core/llm/__init__.py
````python

````

## File: api/nri_core/loop/delta/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/delta/gather.py
````python
"""Gather delta since last run for an entity."""
⋮----
def gather_delta(entity_ftm_id: str) -> dict[str, Any]
⋮----
cfg = get_config()
vault_root = Path(cfg.vault_path)
facts: list[str] = []
hypotheses: list[str] = []
new_fact_ids: list[str] = []
⋮----
section_dir = vault_root / section
⋮----
text = path.read_text(encoding="utf-8")
⋮----
meta = yaml.safe_load(text.split("---", 2)[1]) or {}
````

## File: api/nri_core/loop/detect/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/detect/cooccurrence.py
````python
"""Deterministic co-occurrence detection with mandatory base rates."""
⋮----
@dataclass
class DetectionCandidate
⋮----
pattern_type: str
entities: list[str]
observed_count: int
expected_count: float
base_rate: float
window: str
⋮----
def to_dict(self) -> dict[str, Any]
⋮----
DEFAULT_BASE_RATES = {
⋮----
"""Detect entity pair co-occurrence in shared contexts."""
base_rate = base_rate if base_rate is not None else DEFAULT_BASE_RATES["cooccurrence"]
pair_counts: dict[tuple[str, str], int] = defaultdict(int)
total_contexts = 0
⋮----
mentions = ni_reader.fetch_new_mentions(since_id=since_context_id, limit=5000)
by_context: dict[int, set[str]] = defaultdict(set)
⋮----
cfg = get_config()
⋮----
entity_set = set(entity_ftm_ids)
⋮----
present = entity_set & ftm_ids
⋮----
sorted_ids = sorted(present)
⋮----
expected = max(total_contexts * base_rate, 0.1)
candidates: list[DetectionCandidate] = []
⋮----
base_rate = base_rate if base_rate is not None else DEFAULT_BASE_RATES["velocity_spike"]
⋮----
baseline_count = 1
expected = baseline_count * base_rate
⋮----
def reject_missing_base_rate(candidate: dict[str, Any]) -> bool
````

## File: api/nri_core/loop/promote/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/promote/gate.py
````python
"""Promotion gate — facts only after ran_survived."""
⋮----
def check_promotion(hypothesis_meta: dict) -> bool
⋮----
result = validate_promotion(hypothesis_meta)
````

## File: api/nri_core/loop/queue/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/queue/selector.py
````python
"""Entity selection with fixed prune slots."""
⋮----
@dataclass
class SelectionBatch
⋮----
entity_ids: list[str]
prune_slots: int
⋮----
def select_entities(limit: int = 5, prune_slots: int = 2) -> SelectionBatch
⋮----
cfg = get_config()
entity_ids: list[str] = []
⋮----
entity_ids = [row["ftm_id"] for row in cur.fetchall()]
⋮----
entity_ids = []
````

## File: api/nri_core/loop/reason/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/reason/ach_synthesizer.py
````python
"""ACH-contract LLM reasoner with causal-language linter."""
⋮----
CAUSAL_TERMS = re.compile(
⋮----
ACH_SCHEMA = {
⋮----
@dataclass
class ACHResult
⋮----
mundane_explanation: str
competing_hypotheses: list[str]
cheapest_test: str
confidence: float
causal_flags: list[str]
raw: dict[str, Any]
⋮----
def lint_causal_language(text: str) -> list[str]
⋮----
def build_reasoner_prompt(candidate: dict[str, Any], dossier: dict[str, Any]) -> str
⋮----
def reason_candidate(candidate: dict[str, Any], dossier: dict[str, Any]) -> ACHResult
⋮----
prompt = build_reasoner_prompt(candidate, dossier)
raw = chat_json(prompt=prompt, role="reasoner")
mundane = str(raw.get("mundane_explanation", ""))
flags = lint_causal_language(mundane)
````

## File: api/nri_core/loop/reassess/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/reassess/rules.py
````python
"""Mandatory prune/kill/decay rules before new writes."""
⋮----
DECAY_FACTOR = 0.95
DORMANT_AFTER_ITERATIONS = 4
⋮----
@dataclass
class ReassessMetrics
⋮----
killed: int = 0
demoted: int = 0
dormant: int = 0
added: int = 0
⋮----
def net_negative_count(self) -> int
⋮----
def _parse_frontmatter(path: Path) -> dict[str, Any]
⋮----
text = path.read_text(encoding="utf-8")
⋮----
parts = text.split("---", 2)
⋮----
def _write_frontmatter(path: Path, meta: dict[str, Any], body: str) -> None
⋮----
header = yaml_lib.dump(meta, default_flow_style=False, allow_unicode=True)
⋮----
cfg = get_config()
vault_root = Path(cfg.vault_path)
hyp_dir = vault_root / "hypotheses"
metrics = ReassessMetrics()
⋮----
new_evidence_ids = new_evidence_ids or []
⋮----
meta = _parse_frontmatter(path)
⋮----
supports = set(meta.get("supports", []))
touched = bool(supports & set(new_evidence_ids))
confidence = float(meta.get("confidence", 0.5))
iterations_since = int(meta.get("iterations_since_support", 0))
⋮----
body = path.read_text(encoding="utf-8").split("---", 2)[-1].strip()
````

## File: api/nri_core/loop/scheduler/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/scheduler/__main__.py
````python
"""Loop scheduler entrypoint (M0 stub)."""
⋮----
def main() -> None
````

## File: api/nri_core/loop/scheduler/run_loop.py
````python
"""Eight-step loop orchestrator (shadow mode default)."""
⋮----
def run_iteration(iteration: int, shadow: bool = True) -> dict[str, Any]
⋮----
cfg = get_config()
⋮----
batch = select_entities(limit=5, prune_slots=2)
summary: dict[str, Any] = {
⋮----
total_metrics = ReassessMetrics()
⋮----
delta = gather_delta(ftm_id)
candidates = detect_cooccurrence([ftm_id], since_context_id=0)
candidates = [c for c in candidates if reject_missing_base_rate(c.to_dict())]
⋮----
metrics = reassess_hypotheses(ftm_id, new_evidence_ids=delta.get("new_fact_ids", []), iteration=iteration)
⋮----
dossier = {"facts": delta.get("facts", []), "hypotheses": delta.get("hypotheses", [])}
ach = reason_candidate(cand.to_dict(), dossier)
hyp_id = f"hyp-{ftm_id[:8]}-{iteration}-{cand.pattern_type}"
content = f"""---
⋮----
note_path = Path(cfg.vault_path) / "hypotheses" / f"{hyp_id}.md"
skeptic = review_note(note_path.read_text(encoding="utf-8"))
⋮----
reassess_label = "killed" if total_metrics.killed else "demoted" if total_metrics.demoted else "added"
````

## File: api/nri_core/loop/shadow/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/shadow/seed.py
````python
"""Seed falsifiable hypotheses for net-negative integration tests."""
⋮----
def seed_falsifiable_hypotheses(count: int = 20) -> int
⋮----
cfg = get_config()
vault_root = Path(cfg.vault_path)
hyp_dir = vault_root / "hypotheses"
⋮----
written = 0
⋮----
hyp_id = f"hyp-seed-{i:03d}"
path = hyp_dir / f"{hyp_id}.md"
````

## File: api/nri_core/loop/skeptic/__init__.py
````python
"""Package stub — implemented in later milestones."""
````

## File: api/nri_core/loop/skeptic/agent.py
````python
"""Skeptic agent — separate role from reasoner."""
⋮----
SKEPTIC_PROMPT = """You are a skeptic reviewer. Attack the hypothesis for overreach, missing mundane alternatives,
⋮----
@dataclass
class SkepticFinding
⋮----
findings: list[str]
confidence_downgrade: float | None
refutation_recommended: bool
causal_language_flags: list[str]
raw: dict[str, Any]
⋮----
def review_note(note_content: str) -> SkepticFinding
⋮----
prompt = SKEPTIC_PROMPT.format(note=note_content)
raw = chat_json(prompt=prompt, role="skeptic")
downgrade = raw.get("confidence_downgrade")
⋮----
def apply_skeptic_corrections(path: str, finding: SkepticFinding) -> bool
⋮----
"""Step 6b: amend note with skeptic corrections."""
⋮----
note_path = Path(path)
⋮----
text = note_path.read_text(encoding="utf-8")
parts = text.split("---", 2)
⋮----
meta = yaml.safe_load(parts[1]) or {}
body = parts[2].strip()
changed = False
⋮----
current = float(meta.get("confidence", 0.5))
⋮----
changed = True
⋮----
header = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
````

## File: api/nri_core/loop/tests/test_detect.py
````python
def test_candidate_has_base_rate()
⋮----
cand = DetectionCandidate(
⋮----
def test_missing_base_rate_rejected()
⋮----
def test_velocity_spike_detection()
⋮----
result = detect_velocity_spike("ent-1", recent_count=10, baseline_count=2)
````

## File: api/nri_core/loop/tests/test_reassess.py
````python
def test_confidence_decay(tmp_path, monkeypatch)
⋮----
hyp_dir = tmp_path / "hypotheses"
⋮----
hyp = hyp_dir / "hyp-decay.md"
⋮----
metrics = reassess_hypotheses("ent-abc", new_evidence_ids=[], iteration=1)
text = hyp.read_text()
````

## File: api/nri_core/loop/tests/test_shadow_prune.py
````python
def test_net_negative_after_seed(tmp_path, monkeypatch)
⋮----
total_killed = 0
⋮----
metrics = reassess_hypotheses("seed-entity-0", iteration=i)
````

## File: api/nri_core/loop/tests/test_skeptic.py
````python
def test_causal_language_linter()
⋮----
flags = lint_causal_language("This caused the merger because of timing")
⋮----
def test_skeptic_review_offline()
⋮----
finding = review_note("Hypothesis: Company A caused Company B to fail")
````

## File: api/nri_core/loop/__init__.py
````python
"""Iteration engine — eight-step investigative loop."""
````

## File: api/nri_core/services/__init__.py
````python
"""Investigation product services."""
````

## File: api/nri_core/services/bridge_qa.py
````python
"""Read-only QA assessment for nri.entity_bridge rows."""
⋮----
QaStatus = Literal["ok", "suspect", "mismatch", "unknown"]
⋮----
_ORG_TYPES = frozenset({"organization", "company", "legalentity", "legal_entity"})
_PERSON_TYPES = frozenset({"person", "family"})
_FTM_ORG_SCHEMAS = frozenset({"legalentity", "company", "organization"})
_FTM_PERSON_SCHEMAS = frozenset({"person"})
⋮----
def _norm_name(value: str | None) -> str
⋮----
def _python_name_similarity(a: str, b: str) -> float
⋮----
def _qid_from_anchors(anchors: dict[str, Any] | None) -> str | None
⋮----
qid = anchors.get("qid")
⋮----
text = str(qid).strip()
⋮----
ni = (ni_entity_type or "").strip().lower()
schema = (ftm_schema_name or "").strip().lower()
⋮----
"""
    Compute QA status for an entity_bridge without mutating storage.

    Returns dict with qa_status, name_similarity, qa_flags.
    """
flags: list[str] = []
sim = name_similarity
⋮----
sim = _python_name_similarity(ni_canonical_name, ftm_caption)
⋮----
na = _norm_name(ni_canonical_name)
caption_norm = _norm_name(ftm_caption)
⋮----
sim = 1.0
⋮----
anchor_qid = _qid_from_anchors(anchors if isinstance(anchors, dict) else None)
⋮----
sim = max(sim, 1.0)
⋮----
mention = (mention_text or ni_canonical_name or "").strip()
⋮----
status: QaStatus = "ok"
⋮----
status = "suspect"
⋮----
status = "mismatch"
⋮----
status = "mismatch" if sim < BRIDGE_QA_SUSPECT_SIMILARITY else "suspect"
⋮----
status = "unknown"
⋮----
def pg_trgm_similarity(cur, a: str, b: str) -> float | None
⋮----
"""Return pg_trgm similarity when extension is available."""
⋮----
row = cur.fetchone()
⋮----
"""Merge QA fields into a bridge dict."""
caption = bridge.get("caption")
sim = None
⋮----
sim = pg_trgm_similarity(cur, ni_canonical_name, caption)
⋮----
qa = assess_bridge_qa(
````

## File: api/nri_core/services/entity_claims.py
````python
"""Claims linked to FtM-resolved entity mentions."""
⋮----
logger = logging.getLogger(__name__)
⋮----
conn = get_db_connection()
⋮----
where = ["rm.entity_profile_id = %s", "rm.status = 'auto_linked'"]
params: list[Any] = [entity_profile_id]
⋮----
items = []
````

## File: api/nri_core/services/integration.py
````python
"""Read nri.* tables and proxy NRI API for Investigate UI."""
⋮----
logger = logging.getLogger(__name__)
⋮----
def _nri_api_url() -> str
⋮----
def _nri_proxy(method: str, path: str, body: dict | None = None) -> dict[str, Any]
⋮----
url = f"{_nri_api_url()}{path}"
data = json.dumps(body).encode() if body is not None else None
req = urllib.request.Request(
⋮----
detail = e.read().decode() if e.fp else str(e)
⋮----
conn = get_db_connection()
⋮----
where: list[str] = []
params: list[Any] = []
⋮----
where_sql = ("WHERE " + " AND ".join(where)) if where else ""
⋮----
rows = cur.fetchall()
items = [
⋮----
def get_entity_bridge(entity_profile_id: int) -> dict[str, Any]
⋮----
row = cur.fetchone()
⋮----
bridge = {
bridge = enrich_bridge_with_qa(
⋮----
where = ["1=1"]
⋮----
items = []
⋮----
enriched = enrich_bridge_with_qa(
⋮----
page = items[offset : offset + limit]
⋮----
def get_context_intel(context_id: int, claims_limit: int = 100) -> dict[str, Any]
⋮----
mentions = []
status_counts: dict[str, int] = {}
⋮----
status = row[5] or "unknown"
⋮----
qa = assess_bridge_qa(
⋮----
claims = [
⋮----
mention = row[0]
⋮----
def review_parked(parked_id: int, review_status: str, candidate_ftm_id: str | None = None) -> dict[str, Any]
⋮----
params = []
⋮----
qs = "&".join(params)
⋮----
def get_hypothesis(hyp_id: str) -> dict[str, Any]
⋮----
def get_investigation_health() -> dict[str, Any]
⋮----
"""In-process health (no :8010 proxy)."""
⋮----
def get_nri_health() -> dict[str, Any]
⋮----
def list_spine_entities(dataset: str | None = None, limit: int = 50) -> dict[str, Any]
⋮----
qs = f"limit={limit}"
⋮----
qs = f"dataset={dataset}&{qs}"
data = _nri_proxy("GET", f"/api/spine/entities?{qs}")
⋮----
def match_spine(text: str, schema_name: str | None = None) -> dict[str, Any]
⋮----
qs = f"text={urllib.parse.quote(text)}"
⋮----
def get_resolution_stats(domain_key: str | None = None) -> dict[str, Any]
⋮----
domain_filter = ""
⋮----
domain_filter = "AND ep.domain_key = %s"
⋮----
by_status = {r[0]: r[1] for r in cur.fetchall()}
⋮----
bridge_count = cur.fetchone()[0]
⋮----
wm = cur.fetchone()
watermark = int(wm[0]) if wm else 0
⋮----
max_mention = int(cur.fetchone()[0])
⋮----
total_cem = int(cur.fetchone()[0])
⋮----
resolved_total = int(cur.fetchone()[0])
⋮----
person_org = {k: v for k, v in by_status.items() if k != "non_entity_topic"}
po_total = sum(person_org.values()) or 1
auto_linked = by_status.get("auto_linked", 0)
parked = by_status.get("parked", 0)
backfill_pct = round(resolved_total / total_cem, 4) if total_cem else 0.0
watermark_pct = round(watermark / max_mention, 4) if max_mention else 0.0
⋮----
def list_loop_runs(limit: int = 20) -> dict[str, Any]
⋮----
cols = [d[0] for d in cur.description]
⋮----
d = dict(zip(cols, row))
⋮----
def get_ftm_cache_dataset_counts() -> dict[str, Any]
⋮----
bridged = {r[0]: r[1] for r in cur.fetchall()}
````

## File: api/nri_core/services/parked.py
````python
"""In-process parked resolution review (replaces NRI API proxy)."""
⋮----
conn = get_db_connection()
⋮----
row = cur.fetchone()
````

## File: api/nri_core/spine/api/__init__.py
````python
"""Spine lookup API."""
⋮----
__all__ = ["get_entity", "match_mention"]
````

## File: api/nri_core/spine/api/app.py
````python
"""Minimal FastAPI app for NRI health and lookup stubs."""
⋮----
app = FastAPI(title="News Review Investigator API", version="0.1.0")
⋮----
@app.get("/health")
def health() -> dict[str, str]
⋮----
@app.get("/entities/{entity_id}")
def entity_lookup(entity_id: str) -> dict
⋮----
result = get_entity(entity_id)
⋮----
@app.get("/match")
def mention_match(q: str, schema: str | None = None, limit: int = 5) -> dict
````

## File: api/nri_core/spine/api/lookup.py
````python
"""Read-only spine lookup API for loop and evidence adapters."""
⋮----
@dataclass
class EntityRecord
⋮----
ftm_id: str
schema_name: str
caption: str | None
dataset: str
anchors: dict[str, str]
⋮----
def get_entity(ftm_id: str) -> EntityRecord | None
⋮----
row = cur.fetchone()
⋮----
anchors = {r["anchor_type"]: r["anchor_value"] for r in cur.fetchall()}
⋮----
def list_entities(dataset: str | None = None, limit: int = 100) -> list[dict[str, Any]]
````

## File: api/nri_core/spine/ingest/gleif/__init__.py
````python

````

## File: api/nri_core/spine/ingest/gleif/loader.py
````python
"""GLEIF LEI Golden Copy bulk ingest."""
⋮----
# GLEIF Golden Copy LEI-CDF v3.1 typical columns (subset)
LEI_COL = "LEI"
LEGAL_NAME_COL = "Entity.LegalName"
STATUS_COL = "Entity.EntityStatus"
⋮----
def default_gleif_path() -> Path
⋮----
cfg = get_config()
⋮----
def _entity_id_for_lei(lei: str) -> str
⋮----
def iter_gleif_rows(path: Path) -> Iterator[dict[str, str]]
⋮----
reader = csv.DictReader(handle)
⋮----
def ingest_gleif_file(path: Path | None = None, limit: int | None = None) -> int
⋮----
export_path = path or default_gleif_path()
⋮----
count = 0
⋮----
lei = (row.get(LEI_COL) or row.get("lei") or "").strip()
⋮----
status = (row.get(STATUS_COL) or row.get("entity_status") or "ACTIVE").upper()
⋮----
legal_name = (
entity_id = _entity_id_for_lei(lei)
````

## File: api/nri_core/spine/ingest/icij/loader.py
````python
"""ICIJ offshore leaks sample ingest (FtM-native JSON lines)."""
⋮----
def iter_icij_entities(path: Path) -> Iterator[dict[str, Any]]
⋮----
line = line.strip()
⋮----
def ingest_icij_sample(path: Path | None = None, limit: int = 500) -> int
⋮----
cfg = get_config()
export_path = path or (Path(cfg.nas_datasets_root) / "icij" / "entities.ftm.json")
⋮----
count = 0
⋮----
entity_id = entity.get("id")
⋮----
schema_name = entity.get("schema", "LegalEntity")
caption = entity.get("caption")
⋮----
values = [values]
````

## File: api/nri_core/spine/ingest/mappers/congress.py
````python
"""unitedstates/congress-legislators → spine with bioguide/FEC/QID anchors."""
⋮----
LEGISLATORS_URL = (
⋮----
def _entity_id_for_bioguide(bioguide: str) -> str
⋮----
def fetch_legislators_yaml() -> list[dict[str, Any]]
⋮----
resp = client.get(LEGISLATORS_URL)
⋮----
def ingest_congress_legislators(limit: int | None = None) -> int
⋮----
legislators = fetch_legislators_yaml()
count = 0
⋮----
bio = leg.get("id") or {}
bioguide = bio.get("bioguide")
⋮----
name = leg.get("name") or {}
caption = name.get("official_full") or f"{name.get('first', '')} {name.get('last', '')}".strip()
entity_id = _entity_id_for_bioguide(bioguide)
⋮----
fec_raw = bio.get("fec")
⋮----
fec_id = fec_raw[0] if fec_raw else None
⋮----
fec_id = fec_raw
govtrack = bio.get("govtrack")
wikidata = bio.get("wikidata")
opensecrets = bio.get("opensecrets")
⋮----
qid = str(wikidata).upper()
⋮----
qid = f"Q{qid}"
````

## File: api/nri_core/spine/ingest/mappers/edgar.py
````python
"""SEC EDGAR CIK → FtM Company mapper (standalone, no NI imports)."""
⋮----
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_HEADERS = {"User-Agent": "NewsReviewInvestigator/0.1 (contact@example.com)"}
⋮----
# Instrument / fund tail patterns — shared CIKs that won't match news prose.
_INSTRUMENT_TITLE_RE = re.compile(
_INSTRUMENT_TICKER_RE = re.compile(r"[-+][WPUR]$|\.WS$|\.U$|\.RT$", re.I)
⋮----
@dataclass
class EdgarCompany
⋮----
cik: str
ticker: str
title: str
⋮----
def _pad_cik(cik: int | str) -> str
⋮----
def is_instrument_tail(company: EdgarCompany) -> bool
⋮----
"""Filter warrants, preferreds, units, ADRs, ETFs/trusts sharing issuer CIKs."""
title = company.title or ""
ticker = company.ticker or ""
⋮----
def _operating_company_score(company: EdgarCompany) -> tuple[int, int]
⋮----
"""Prefer shorter tickers and titles without instrument keywords."""
⋮----
penalty = 1 if _INSTRUMENT_TITLE_RE.search(title) else 0
⋮----
def dedupe_by_cik(companies: Iterable[EdgarCompany]) -> list[EdgarCompany]
⋮----
"""One canonical operating company per CIK."""
by_cik: dict[str, EdgarCompany] = {}
⋮----
existing = by_cik.get(company.cik)
⋮----
def fetch_company_tickers() -> list[EdgarCompany]
⋮----
resp = client.get(SEC_TICKERS_URL)
⋮----
payload = resp.json()
companies: list[EdgarCompany] = []
⋮----
def load_deduped_companies(limit: int | None = None) -> list[EdgarCompany]
⋮----
companies = dedupe_by_cik(fetch_company_tickers())
⋮----
def company_to_ftm_entity(company: EdgarCompany) -> dict[str, Any]
⋮----
entity_id = hashlib.sha1(f"edgar:{company.cik}".encode()).hexdigest()[:16]
⋮----
def ingest_edgar_subset(limit: int | None = None) -> int
⋮----
companies = load_deduped_companies(limit=limit)
count = 0
⋮----
entity = company_to_ftm_entity(company)
````

## File: api/nri_core/spine/ingest/opensanctions/loader.py
````python
"""OpenSanctions FtM bulk load from NAS-staged exports."""
⋮----
def iter_ftm_entities(export_path: Path) -> Iterator[dict[str, Any]]
⋮----
line = line.strip()
⋮----
def ingest_opensanctions_file(path: Path, limit: int | None = None) -> int
⋮----
count = 0
⋮----
entity_id = entity.get("id")
⋮----
schema_name = entity.get("schema", "LegalEntity")
caption = entity.get("caption") or entity.get("properties", {}).get("name", [None])[0]
⋮----
props = entity.get("properties", {})
⋮----
values = [values]
⋮----
def default_export_path() -> Path
⋮----
cfg = get_config()
````

## File: api/nri_core/spine/ingest/wikidata/__init__.py
````python

````

## File: api/nri_core/spine/ingest/wikidata/crosswalk.py
````python
"""Wikidata Phase 1 — crosswalk hub (entities with external ID statements only)."""
⋮----
# Property keys in export JSONL → spine anchor types
CROSSWALK_PROPS = {
⋮----
"P213": "cik",  # often formatted
"P2397": "youtube",  # skip
⋮----
ANCHOR_PROP_MAP = {
⋮----
def _entity_id_for_qid(qid: str) -> str
⋮----
def iter_crosswalk_entities(path: Path) -> Iterator[dict[str, Any]]
⋮----
line = line.strip()
⋮----
def _normalize_anchor(prop: str, value: str) -> tuple[str, str] | None
⋮----
anchor_type = ANCHOR_PROP_MAP.get(prop)
⋮----
value = str(value).strip()
⋮----
digits = "".join(c for c in value if c.isdigit())
⋮----
value = digits.zfill(10)
⋮----
value = f"Q{value}"
⋮----
def ingest_crosswalk_file(path: Path | None = None, limit: int | None = None) -> int
⋮----
cfg = get_config()
export_path = path or (Path(cfg.nas_datasets_root) / "wikidata" / "crosswalk.jsonl")
⋮----
count = 0
⋮----
qid = record.get("qid") or record.get("id")
⋮----
qid = str(qid).upper()
⋮----
qid = f"Q{qid}"
⋮----
crosswalk = record.get("crosswalk") or record.get("properties") or {}
anchors: list[tuple[str, str]] = []
⋮----
values = [values]
⋮----
parsed = _normalize_anchor(prop, str(val))
⋮----
entity_id = _entity_id_for_qid(qid)
caption = record.get("label") or record.get("caption") or qid
schema_name = record.get("schema") or "LegalEntity"
⋮----
def fetch_crosswalk_via_api(qid: str) -> dict[str, Any] | None
⋮----
"""Fetch crosswalk statements for a single QID (lazy enrichment)."""
⋮----
url = "https://www.wikidata.org/wiki/Special:EntityData/" + qid + ".json"
⋮----
resp = client.get(url, headers={"User-Agent": "NewsReviewInvestigator/0.1"})
````

## File: api/nri_core/spine/ingest/wikidata/notable.py
````python
"""Wikidata Phase 2 — notable slice (optional, if park rate still high after Phase 1)."""
⋮----
def ingest_notable_file(path: Path | None = None, limit: int | None = None) -> int
⋮----
"""Notable entities JSONL: qid, label, schema — may lack crosswalk (broader index)."""
cfg = get_config()
export_path = path or (Path(cfg.nas_datasets_root) / "wikidata" / "notable.jsonl")
⋮----
count = 0
⋮----
line = line.strip()
⋮----
record = json.loads(line)
qid = str(record.get("qid", "")).upper()
⋮----
qid = f"Q{qid}"
entity_id = _entity_id_for_qid(qid)
````

## File: api/nri_core/spine/ingest/__init__.py
````python
"""Spine ingest pipelines (FtM datasets, nomenklatura)."""
````

## File: api/nri_core/spine/ingest/__main__.py
````python
"""Spine ingest CLI — preload sources per revised strategy."""
⋮----
def main(argv: list[str] | None = None) -> int
⋮----
parser = argparse.ArgumentParser(description="NRI identity spine ingest")
sub = parser.add_subparsers(dest="command", required=True)
⋮----
edgar_p = sub.add_parser("edgar", help="SEC EDGAR companies (CIK-deduped)")
⋮----
gleif_p = sub.add_parser("gleif", help="GLEIF LEI Golden Copy CSV")
⋮----
wd_p = sub.add_parser("wikidata-crosswalk", help="Wikidata Phase 1 crosswalk hub")
⋮----
wd2_p = sub.add_parser("wikidata-notable", help="Wikidata Phase 2 notable slice")
⋮----
cong_p = sub.add_parser("congress", help="unitedstates/congress-legislators")
⋮----
all_p = sub.add_parser("preload-all", help="EDGAR + congress + anchor audit (NAS sources if present)")
⋮----
args = parser.parse_args(argv)
⋮----
n = ingest_edgar_subset(limit=args.limit)
⋮----
path = Path(args.path) if args.path else None
n = ingest_gleif_file(path=path, limit=args.limit)
⋮----
n = ingest_crosswalk_file(path=path, limit=args.limit)
⋮----
n = ingest_notable_file(path=path, limit=args.limit)
⋮----
n = ingest_congress_legislators(limit=args.limit)
⋮----
stats = run_anchor_join_audit()
⋮----
results = {
````

## File: api/nri_core/spine/resolution/__init__.py
````python
"""Mention-to-entity resolution logic."""
````

## File: api/nri_core/spine/resolution/anchor_join.py
````python
"""Deterministic cross-dataset merge on shared anchors (not fuzzy nomenklatura)."""
⋮----
def find_anchor_collisions(anchor_type: str) -> list[dict[str, Any]]
⋮----
"""Entities sharing the same anchor value across datasets."""
⋮----
def run_anchor_join_audit() -> dict[str, int]
⋮----
"""Audit cross-dataset collisions on high-value anchors; record judgements."""
stats = {"cik": 0, "lei": 0, "qid": 0, "fec_id": 0}
⋮----
collisions = find_anchor_collisions(anchor_type)
⋮----
ids = row["entity_ids"]
````

## File: api/nri_core/spine/resolution/lazy_mint.py
````python
"""Demand-driven provisional mint on resolution miss — Wikidata + OpenSanctions API."""
⋮----
WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php"
OPENSANCTIONS_MATCH = "https://api.opensanctions.org/match/default"
⋮----
@dataclass
class LazyMintResult
⋮----
ftm_id: str | None
score: float
source_api: str
status: str
evidence: dict[str, Any]
⋮----
def _provisional_entity_id(source: str, external_id: str) -> str
⋮----
def search_wikidata(name: str, limit: int = 3) -> list[dict[str, Any]]
⋮----
params = {
⋮----
resp = client.get(
⋮----
def match_opensanctions(name: str) -> dict[str, Any] | None
⋮----
payload = {
⋮----
resp = client.post(OPENSANCTIONS_MATCH, json=payload)
⋮----
data = resp.json()
responses = data.get("responses", {}).get("q1", {})
results = responses.get("results", [])
⋮----
cfg = get_config()
⋮----
# Wikidata first
wd_hits = search_wikidata(mention_text, limit=3)
⋮----
best = wd_hits[0]
qid = best.get("id", "")
label = best.get("label", mention_text)
score = 0.75  # search rank proxy
entity_id = _provisional_entity_id("wikidata", qid)
evidence = {"api": "wikidata_search", "response": best}
⋮----
# OpenSanctions lazy (no bulk)
⋮----
os_hit = match_opensanctions(mention_text)
⋮----
os_id = os_hit.get("id", "")
caption = os_hit.get("caption") or mention_text
score = float(os_hit.get("score", 0.7))
entity_id = _provisional_entity_id("opensanctions", os_id)
evidence = {"api": "opensanctions_match", "response": os_hit}
````

## File: api/nri_core/spine/resolution/matcher.py
````python
"""Two-tier mention matching: anchor exact then blocked fuzzy."""
⋮----
ANCHOR_KEYS = {
⋮----
@dataclass
class MatchResult
⋮----
ftm_id: str | None
score: float
tier: int
status: str
candidates: list[dict]
⋮----
def _normalize_name(text: str) -> str
⋮----
text = text.lower().strip()
text = re.sub(r"[^\w\s]", " ", text)
⋮----
def _fuzzy_score(a: str, b: str) -> float
⋮----
cfg = get_config()
anchors = anchors or {}
⋮----
# Tier 1: exact anchor lookup
⋮----
value = anchors.get(key) or anchors.get(anchor_type)
⋮----
hits = postgres_store.lookup_by_anchor(anchor_type, str(value))
⋮----
# Tier 2: blocked fuzzy against name index
candidates = postgres_store.search_name_candidates(text, schema_name=schema_name, limit=50)
scored: list[dict] = []
⋮----
caption = cand.get("caption") or ""
score = _fuzzy_score(text, caption)
⋮----
best = scored[0]
score = float(best["score"])
⋮----
status = "auto_linked"
ftm_id = best["id"]
⋮----
status = "parked"
ftm_id = None
````

## File: api/nri_core/spine/resolver/__init__.py
````python
"""Nomenklatura resolver integration."""
````

## File: api/nri_core/spine/resolver/git_resolver.py
````python
"""Version-controlled resolver judgements synced to git."""
⋮----
RESOLVER_DIR = Path(__file__).resolve().parents[1] / "data" / "resolver"
⋮----
def resolver_file() -> Path
⋮----
def load_judgements() -> list[dict[str, Any]]
⋮----
path = resolver_file()
⋮----
def save_judgements(judgements: list[dict[str, Any]]) -> None
⋮----
def add_judgement(left_id: str, right_id: str, score: float, judgement: str) -> None
⋮----
judgements = load_judgements()
entry = {
````

## File: api/nri_core/spine/store/__init__.py
````python
from nri_core.spine.store.postgres_store import *  # noqa: F403
````

## File: api/nri_core/spine/store/postgres_store.py
````python
"""Postgres persistence for identity_spine."""
⋮----
@contextlib.contextmanager
def spine_connection() -> Generator[Any, None, None]
⋮----
cfg = get_config()
conn = psycopg2.connect(cfg.identity_spine_dsn)
⋮----
def upsert_anchor(entity_id: str, anchor_type: str, anchor_value: str) -> None
⋮----
def lookup_by_anchor(anchor_type: str, anchor_value: str) -> list[dict[str, Any]]
⋮----
def bulk_upsert_entities(rows: Iterable[dict[str, Any]]) -> int
⋮----
count = 0
````

## File: api/nri_core/spine/tests/mappers/test_edgar_dedupe.py
````python
def test_instrument_tail_detects_warrant()
⋮----
def test_instrument_tail_keeps_operating_company()
⋮----
def test_dedupe_by_cik_keeps_one_per_cik()
⋮----
companies = [
deduped = dedupe_by_cik(companies)
⋮----
def test_load_deduped_filters_instruments(monkeypatch)
⋮----
def fake_fetch()
⋮----
result = load_deduped_companies()
````

## File: api/nri_core/spine/tests/mappers/test_edgar.py
````python
def test_known_cik_maps_to_ftm_entity()
⋮----
company = EdgarCompany(cik="0000320193", ticker="AAPL", title="Apple Inc.")
entity = company_to_ftm_entity(company)
````

## File: api/nri_core/spine/tests/test_lazy_mint.py
````python
def test_wikidata_search_returns_list_or_empty()
⋮----
# Live API — may return hits for well-known name
hits = search_wikidata("Donald Trump", limit=1)
````

## File: api/nri_core/spine/tests/test_match_perf.py
````python
def test_tier2_fuzzy_p95_under_100ms()
⋮----
samples = 200
start = time.perf_counter()
⋮----
elapsed_ms = (time.perf_counter() - start) * 1000
p95_estimate = elapsed_ms / samples
````

## File: api/nri_core/spine/tests/test_match.py
````python
def test_low_score_implies_parked_threshold()
⋮----
score = _fuzzy_score("Totally Different Corp", "Another Unrelated Entity LLC")
````

## File: api/nri_core/spine/tests/test_resolver.py
````python
def test_resolver_judgement_roundtrip(tmp_path, monkeypatch)
⋮----
judgements = [{"left_id": "a", "right_id": "b", "score": 0.9, "judgement": "match"}]
⋮----
loaded = load_judgements()
````

## File: api/nri_core/spine/__init__.py
````python
"""Store A — identity spine."""
````

## File: api/nri_core/__init__.py
````python
"""Investigation (NRI) package — entity resolution, spine, mention resolver."""
````

## File: api/nri_core/config.py
````python
"""
NRI-compatible config shim — delegates to api.config kernel.
"""
⋮----
@dataclass(frozen=True)
class NriCoreConfig
⋮----
news_intel_dsn: str
identity_spine_dsn: str
nri_schema: str
skip_subject_mentions: bool
write_resolved_mentions: bool
lazy_mint_enabled: bool
opensanctions_lazy_enabled: bool
allow_prod_news_intel: bool
vault_path: str
vault_write: bool
⋮----
def get_config() -> NriCoreConfig
⋮----
rt = get_runtime_config()
⋮----
def require_prod_safety() -> None
⋮----
cfg = get_config()
````

## File: api/nri_core/constants.py
````python
"""Re-export investigation triage constants (from legacy nri_resolution_config)."""
⋮----
__all__ = [
````

## File: api/nri_core/resolver_runner.py
````python
"""Automation entrypoint for mention resolution drain."""
````

## File: docs/INVESTIGATION.md
````markdown
# Investigation Product (formerly NRI)

> Internal package: `api/nri_core/` · Public API: `/api/investigation/*` · UI label: **Investigation**

## Overview

Investigation resolves entity mentions in news contexts to FollowTheMoney (FtM) identity spine records, parks ambiguous matches for human review, and exposes hypotheses, loop runs, and bridge QA for the Investigate UI.

NI and NRI are unified in-process after cutover — no standalone `:8010` API.

## API routes

| Route | Purpose |
|-------|---------|
| `GET /api/investigation/health` | Service health |
| `GET /api/investigation/resolved_mentions` | CEM → FtM resolution log |
| `GET /api/investigation/parked` | Ambiguous mentions awaiting review |
| `PATCH /api/investigation/parked/{id}` | Review parked mention |
| `GET /api/investigation/entity_bridge/{profile_id}` | NI profile ↔ FtM bridge |
| `GET /api/investigation/bridge_qa/audit` | Suspect/mismatch bridge audit |
| `GET /api/investigation/entity_claims` | Claims for bridged entity |
| `GET /api/investigation/context_intel/{context_id}` | Mentions + claims for context |
| `GET /api/investigation/hypotheses` | Shadow loop hypotheses |
| `GET /api/investigation/spine/entities` | Spine entity browser |
| `POST /api/investigation/spine/match` | Ad-hoc spine match |
| `GET /api/investigation/resolution_stats` | Resolver metrics |
| `GET /api/investigation/loop_runs` | Shadow loop history |
| `GET /api/investigation/ftm_cache_stats` | FtM cache by dataset |

Legacy shim: same handlers at `/api/nri/*`.

TypeScript client: `web/src/services/api/investigationApi.ts`  
Route constants: `web/src/config/apiRoutes.ts`

## Schema

Pre-migration: `nri.*` tables in `news_intel`  
Post-migration: `intelligence.investigation_*` (set `USE_INVESTIGATION_PREFIXED_TABLES=true`)

Qualified names via `api/config/investigation_tables.py` — never hardcode `nri.` in new code.

`identity_spine` database is separate — spine ingest/resolution uses `database_targets.spine_dsn()`.

## Automation

`mention_resolution` phase in AutomationManager drains the CEM resolver (replaces `nri-mention-resolver.timer`).

Executor: `api/services/automation/executor.py`  
Runner: `api/nri_core/resolver_runner.py`

## Package layout

```
api/nri_core/
  services/integration.py   # API handlers + DB reads
  services/bridge_qa.py       # Bridge quality assessment
  services/entity_claims.py   # Entity claim queries
  evidence/mention_resolver.py
  spine/                      # Identity spine ingest + resolution
  loop/                       # Shadow hypothesis loop
```

Shim services (delegate to nri_core): `nri_integration_service.py`, `nri_bridge_qa_service.py`, `nri_entity_claims_service.py`

## UI pages

| Path | Page |
|------|------|
| `/:domain/investigate/entity-resolution` | Resolved + parked mentions |
| `/:domain/investigate/spine-browser` | FtM spine search |
| `/:domain/investigate/hypotheses` | Shadow hypotheses |
| `/:domain/operations/investigation-ops` | Ops dashboard + bridge QA |

Component: `web/src/components/nri/FtmBridgePanel.tsx` (FtM bridge card on entity pages)

## Operator references

- Cutover: [UNIFICATION_CUTOVER.md](UNIFICATION_CUTOVER.md)
- Baseline: [UNIFICATION_BASELINE.md](UNIFICATION_BASELINE.md)
- System audit: [NI_NRI_SYSTEM_AUDIT_2026-06.md](NI_NRI_SYSTEM_AUDIT_2026-06.md)
````

## File: docs/UNIFICATION_BASELINE.md
````markdown
# NI + NRI Unification Baseline

> Generated June 2026 — pre-cutover snapshot for the `unification/big-bang` feature branch.

## Corpus scale (Widow dev workspace)

| Corpus | Files | Notes |
|--------|-------|-------|
| `api/` Python | 626 | incl. 73 in `api/nri_core/` |
| `web/src` TypeScript | 131 | Investigation product surface |
| `docs/` Markdown | 186 | target ≤40 active post-consolidation |
| Top LOC bucket | `api/services` ~75k | `automation_manager.py` god-object |

Run `python3 scripts/complexity_inventory.py` to refresh counts.

## Locked naming

| Layer | Name |
|-------|------|
| Internal Python package | `api/nri_core/` |
| UI product label | **Investigation** |
| Public API prefix | `/api/investigation/*` |
| Legacy shim | `/api/nri/*` (same handlers) |
| Post-migration tables | `intelligence.investigation_*` |

## Config kernel (SSOT)

| Module | Role |
|--------|------|
| `api/config/runtime.py` | Only module that reads `os.environ` for app code |
| `api/config/database_targets.py` | `news_intel_dsn()`, `spine_dsn()`, `maintenance_connect_kwargs()` |
| `api/config/investigation_tables.py` | Qualified table names (`T_RESOLVED_MENTIONS`, etc.) |
| `api/config/schedulers.yaml` | Scheduler manifest (5+ owners) |
| `web/src/config/apiRoutes.ts` | API path constants for TS |

Enforcement: `python3 scripts/verify_single_source_of_truth.py`

## Scheduler map (pre-unification)

| Owner | Unit / file | Status after cutover |
|-------|-------------|----------------------|
| AutomationManager | embedded 5s loop | **Primary** — includes `mention_resolution` phase |
| OrchestratorCoordinator | 60s | Active — collection cadence |
| newsplatform-secondary | systemd service | Active — RSS ingest |
| widow-db-adjacent | cron `infrastructure/widow-db-adjacent.cron` | Active — `context_sync` authoritative on Widow |
| nri-mention-resolver.timer | systemd | **Disabled** — replaced by `mention_resolution` |
| nri-loop.timer | systemd | **Disabled** — default off |
| nri-api.service | systemd :8010 | **Disabled** — in-process routes |

`context_sync` split-brain: cron owns sync on Widow prod when listed in `AUTOMATION_DISABLED_SCHEDULES`.

## Repomix packs

| Config | Output |
|--------|--------|
| `repomix-widow.config.json` | `repomix-output.md` (full NI) |
| `repomix-nri.config.json` | `repomix-nri-output.md` (nri_core + kernel) |

Regenerate:

```bash
repomix -c repomix-widow.config.json
repomix -c repomix-nri.config.json
```

## Schema migration

`api/database/migrations/237_investigation_schema_merge.sql` — `nri.*` → `intelligence.investigation_*` with compatibility views.

Toggle post-migration: `USE_INVESTIGATION_PREFIXED_TABLES=true`

`identity_spine` remains a **separate database** on `:5432`.

## Prune targets (Phase 1)

- `api/collectors/enhanced_rss_collector.py` → archived (superseded by `rss_collector`)
- Unrouted finance pages → `web/_archived_duplicates/pages/Finance/`
- `web/_archived_duplicates/` — excluded from builds (tsconfig, repomix)

## Verification commands

```bash
# Import smoke
cd api && PYTHONPATH=. python -c "from nri_core.services.integration import get_investigation_health; print(get_investigation_health())"

# SSOT lint
PYTHONPATH=api python3 scripts/verify_single_source_of_truth.py

# Post-cutover (on Widow)
scripts/verify_unification_cutover.sh
```

See [UNIFICATION_CUTOVER.md](UNIFICATION_CUTOVER.md) for maintenance-window steps.
````

## File: docs/UNIFICATION_CUTOVER.md
````markdown
# NI + NRI Unification Cutover Runbook

> Single maintenance-window deploy to Widow (`192.168.93.101`).  
> Prep all code on branch `unification/big-bang` before scheduling downtime.

## Preconditions

- [ ] All plan todos complete on feature branch
- [ ] `scripts/verify_single_source_of_truth.py` passes (or only allowlisted exceptions)
- [ ] `cd api && PYTHONPATH=. python -c "from nri_core.services.integration import get_investigation_health"`
- [ ] Web build succeeds with `investigationApi` routes
- [ ] `pg_dump` disk space available on Widow

## 1. Stop parallel runtimes

```bash
# On Widow as root/sudo
sudo systemctl stop nri-api.service 2>/dev/null || true
sudo systemctl stop nri-mention-resolver.timer nri-mention-resolver.service 2>/dev/null || true
sudo systemctl stop nri-loop.timer nri-loop.service 2>/dev/null || true
sudo systemctl disable nri-api.service
sudo systemctl disable nri-mention-resolver.timer
sudo systemctl disable nri-loop.timer
```

Disable permanently (optional, after bake):

```bash
sudo systemctl mask nri-api.service nri-mention-resolver.timer nri-loop.timer
```

## 2. Stop NI API (brief downtime starts)

```bash
sudo systemctl stop news-intelligence-api-public
```

## 3. Database backup

```bash
sudo -u postgres pg_dump -Fc news_intel > /var/backups/news_intel_pre_unification_$(date +%Y%m%d).dump
# identity_spine if schema changed:
sudo -u postgres pg_dump -Fc identity_spine > /var/backups/identity_spine_pre_unification_$(date +%Y%m%d).dump
```

## 4. Apply schema migration

```bash
cd /opt/news-intelligence
psql -U newsapp -d news_intel -f api/database/migrations/237_investigation_schema_merge.sql
```

Verify:

```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'intelligence' AND tablename LIKE 'investigation_%' LIMIT 5;
```

## 5. Deploy code

```bash
cd /home/pete/Documents/projects/News\ Intelligence   # or rsync to /opt/news-intelligence
git checkout unification/big-bang
git pull   # or rsync from dev workspace
sudo rsync -a --delete api/ /opt/news-intelligence/api/
sudo rsync -a --delete web/dist/ /var/www/news-intelligence/   # after npm run build
```

## 6. Merge environment

Add to `/opt/news-intelligence/.env` (or production env):

```env
USE_INVESTIGATION_PREFIXED_TABLES=true
INVESTIGATION_SCHEMA=intelligence
INVESTIGATION_TABLE_PREFIX=investigation_
# Retire standalone NRI API proxy:
# NRI_API_URL=   (unset or remove)
```

Ensure `AUTOMATION_DISABLED_SCHEDULES` includes `context_sync` on Widow prod (cron authoritative).

## 7. Python venv / dependencies

```bash
cd /opt/news-intelligence/api
source .venv/bin/activate
pip install -r requirements.txt   # merged nri_core deps
PYTHONPATH=. python -c "from nri_core.services.integration import get_investigation_health; print('ok')"
```

## 8. Start services

```bash
sudo systemctl start news-intelligence-api-public
sudo systemctl start newsplatform-secondary
```

## 9. Verify

```bash
cd /opt/news-intelligence
API_BASE_URL=http://127.0.0.1:8000 scripts/verify_unification_cutover.sh
```

Expected:

- `/api/investigation/health` → `status: ok`
- `/api/nri/health` → same (legacy shim)
- `/api/investigation/resolution_stats` → metrics JSON
- `mention_resolution` phase runs in automation status (no nri-mention-resolver.timer)
- SSOT script passes

## 10. Rollback (if needed)

```bash
sudo systemctl stop news-intelligence-api-public
sudo -u postgres pg_restore -c -d news_intel /var/backups/news_intel_pre_unification_YYYYMMDD.dump
git checkout main   # or previous release tag
# redeploy + restart
sudo systemctl enable --now nri-api.service nri-mention-resolver.timer  # if reverting fully
```

## Post-cutover bake (1–2 weeks)

1. Monitor `mention_resolution` drain stats in API logs
2. Confirm no traffic to `:8010`
3. Drop `nri` schema compatibility views per migration tail SQL
4. Remove `/api/nri/*` shims when clients migrated

## Related docs

- [UNIFICATION_BASELINE.md](UNIFICATION_BASELINE.md) — pre-cutover inventory
- [INVESTIGATION.md](INVESTIGATION.md) — product/API reference
- [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md) — systemd units
````
