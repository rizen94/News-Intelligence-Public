"""
Domain onboarding manifest (JSON) — validation, YAML projection, SQL generation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.domain_registry_constants import RESERVED_SCHEMA_NAMES
from shared.domain_silo_contract import DEFAULT_CLONE_FROM_SCHEMA, SILO_CORE_TABLES, SILO_OPTIONAL_TABLES

SPECS_DIR = Path(__file__).resolve().parent.parent / "config" / "domains" / "specs"
SCHEMA_PATH = SPECS_DIR / "domain.spec.schema.json"
GENERATED_YAML_HEADER = "# Generated from specs/{domain_key}.domain.json — do not edit by hand\n"

_DOMAIN_KEY_RE = re.compile(r"^[a-z0-9-]+$")
_SCHEMA_NAME_RE = re.compile(r"^[a-z0-9_]+$")


class RssFeedSpec(BaseModel):
    feed_url: str
    feed_name: str | None = None
    fetch_interval_seconds: int | None = None
    arc_relevance: list[str] = Field(default_factory=list)

    @field_validator("feed_url")
    @classmethod
    def _url_non_empty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("feed_url must be non-empty")
        return s


class RssSpec(BaseModel):
    seed_feed_category: str = "General"
    feeds: list[RssFeedSpec] = Field(default_factory=list)


class DatabaseSpec(BaseModel):
    clone_from: str = DEFAULT_CLONE_FROM_SCHEMA
    include_article_topic_clusters: bool = True
    migration_ref: str | None = None


class WorkloadAssumptionsSpec(BaseModel):
    expected_active_feeds: int = 0
    rough_new_articles_per_day: int = 0
    llm_heavy_phases_enabled: bool = True


class DomainSpec(BaseModel):
    version: int = 1
    domain_key: str
    schema_name: str
    display_name: str
    description: str = ""
    display_order: int = 99
    is_active: bool = False
    database: DatabaseSpec = Field(default_factory=DatabaseSpec)
    rss: RssSpec = Field(default_factory=RssSpec)
    focus_areas: list[str] = Field(default_factory=list)
    llm_prompt_guidance: str = ""
    workload_assumptions: WorkloadAssumptionsSpec | None = None

    @field_validator("domain_key")
    @classmethod
    def _domain_key_pattern(cls, v: str) -> str:
        s = (v or "").strip()
        if not _DOMAIN_KEY_RE.fullmatch(s):
            raise ValueError("domain_key must match ^[a-z0-9-]+$")
        return s

    @field_validator("schema_name")
    @classmethod
    def _schema_name_pattern(cls, v: str) -> str:
        s = (v or "").strip()
        if not _SCHEMA_NAME_RE.fullmatch(s) or "-" in s:
            raise ValueError("schema_name must match ^[a-z0-9_]+$ (no hyphens)")
        if s != s.lower():
            raise ValueError("schema_name must be lowercase")
        return s

    @field_validator("display_name")
    @classmethod
    def _display_name_len(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("display_name is required")
        if len(s) > 100:
            raise ValueError("display_name must be ≤ 100 characters")
        return s

    @model_validator(mode="after")
    def _reserved_schema(self) -> DomainSpec:
        allowed_reserved = {
            ("politics", "politics"),
            ("finance", "finance"),
            ("artificial-intelligence", "artificial_intelligence"),
        }
        if (self.domain_key, self.schema_name) in allowed_reserved:
            return self
        if self.schema_name in RESERVED_SCHEMA_NAMES:
            raise ValueError(
                f"schema_name {self.schema_name!r} is reserved; pick a different schema for new silos"
            )
        if self.domain_key == "science-tech":
            raise ValueError("science-tech is retired; use split silos (e.g. artificial-intelligence)")
        return self

    @classmethod
    def from_json_file(cls, path: Path) -> DomainSpec:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def to_yaml_dict(self) -> dict[str, Any]:
        """Runtime onboarding YAML shape (provision_domain / domain_registry merge)."""
        seed_urls: list[str | dict[str, Any]] = []
        for f in self.rss.feeds:
            if f.feed_name or f.fetch_interval_seconds is not None:
                obj: dict[str, Any] = {"feed_url": f.feed_url}
                if f.feed_name:
                    obj["feed_name"] = f.feed_name
                if f.fetch_interval_seconds is not None:
                    obj["fetch_interval_seconds"] = f.fetch_interval_seconds
                if f.arc_relevance:
                    obj["arc_relevance"] = list(f.arc_relevance)
                seed_urls.append(obj)
            else:
                seed_urls.append(f.feed_url)

        out: dict[str, Any] = {
            "domain_key": self.domain_key,
            "schema_name": self.schema_name,
            "display_name": self.display_name,
            "is_active": self.is_active,
        }
        if self.description:
            out["description"] = self.description
        if self.display_order != 99:
            out["display_order"] = self.display_order
        if seed_urls or self.rss.seed_feed_category != "General":
            rss: dict[str, Any] = {"seed_feed_urls": seed_urls}
            if self.rss.seed_feed_category and self.rss.seed_feed_category != "General":
                rss["seed_feed_category"] = self.rss.seed_feed_category
            out["data_sources"] = {"rss": rss}
        elif self.rss.feeds:
            out["data_sources"] = {"rss": {"seed_feed_urls": seed_urls}}
        if self.focus_areas:
            out["focus_areas"] = list(self.focus_areas)
        if self.llm_prompt_guidance.strip():
            out["llm_prompt_guidance"] = self.llm_prompt_guidance.strip()
        if self.workload_assumptions is not None:
            out["workload_assumptions"] = self.workload_assumptions.model_dump()
        return out

    def render_yaml(self) -> str:
        import yaml

        body = yaml.safe_dump(
            self.to_yaml_dict(),
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )
        return GENERATED_YAML_HEADER.format(domain_key=self.domain_key) + body

    def render_sql_migration(self, migration_number: int) -> str:
        """Generate silo migration SQL (187-style + optional article_topic_clusters)."""
        sch = self.schema_name
        dk = self.domain_key
        clone = self.database.clone_from
        desc = (self.description or "").replace("'", "''")
        name = self.display_name.replace("'", "''")
        n = migration_number
        lines: list[str] = [
            f"-- Migration {n}: {self.display_name} domain silo (schema {sch}, public.domains row).",
            f"-- Generated from api/config/domains/specs/{dk}.domain.json",
            "-- Idempotent: safe to re-run with IF NOT EXISTS / ON CONFLICT DO NOTHING.",
            "-- Prerequisites: create_domain_table, add_domain_foreign_keys, create_domain_indexes, create_domain_triggers (migration 122).",
            "",
            "INSERT INTO public.domains (domain_key, name, schema_name, display_order, description)",
            "VALUES (",
            f"    '{dk}',",
            f"    '{name}',",
            f"    '{sch}',",
            f"    {int(self.display_order)},",
            f"    '{desc}'",
            ")",
            "ON CONFLICT (domain_key) DO NOTHING;",
            "",
            "INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)",
            "SELECT d.id, 0, 0, 0, 0",
            "FROM public.domains d",
            f"WHERE d.domain_key = '{dk}'",
            "ON CONFLICT (domain_id) DO NOTHING;",
            "",
            f"CREATE SCHEMA IF NOT EXISTS {sch};",
            "",
            f"GRANT USAGE ON SCHEMA {sch} TO newsapp;",
            f"GRANT CREATE ON SCHEMA {sch} TO newsapp;",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {sch} GRANT ALL ON TABLES TO newsapp;",
            "",
        ]
        for table in SILO_CORE_TABLES:
            lines.append(f"SELECT public.create_domain_table('{sch}', '{table}', '{clone}');")
        lines.append("")
        if self.database.include_article_topic_clusters:
            for table in SILO_OPTIONAL_TABLES:
                lines.append(f"SELECT public.create_domain_table('{sch}', '{table}', '{clone}');")
            lines.append("")
        lines.extend(
            [
                f"SELECT public.add_domain_foreign_keys('{sch}');",
                f"SELECT public.create_domain_indexes('{sch}');",
                f"SELECT public.create_domain_triggers('{sch}');",
                "",
                "DO $$",
                "BEGIN",
                f"  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = '{sch}' AND table_name = 'article_entities') THEN",
                f"    EXECUTE 'ALTER TABLE {sch}.article_entities DROP CONSTRAINT IF EXISTS article_entities_article_id_fkey';",
                f"    EXECUTE 'ALTER TABLE {sch}.article_entities ADD CONSTRAINT article_entities_article_id_fkey",
                f"      FOREIGN KEY (article_id) REFERENCES {sch}.articles(id) ON DELETE CASCADE';",
                f"    EXECUTE 'ALTER TABLE {sch}.article_entities DROP CONSTRAINT IF EXISTS article_entities_canonical_entity_id_fkey';",
                f"    EXECUTE 'ALTER TABLE {sch}.article_entities ADD CONSTRAINT article_entities_canonical_entity_id_fkey",
                f"      FOREIGN KEY (canonical_entity_id) REFERENCES {sch}.entity_canonical(id) ON DELETE SET NULL';",
                "  END IF;",
                "END $$;",
                "",
                f"CREATE TABLE IF NOT EXISTS {sch}.story_entity_index (",
                "    id SERIAL PRIMARY KEY,",
                f"    storyline_id INTEGER NOT NULL REFERENCES {sch}.storylines(id) ON DELETE CASCADE,",
                "    entity_name VARCHAR(255) NOT NULL,",
                "    entity_role VARCHAR(100),",
                "    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (",
                "        'person', 'organization', 'location', 'case_number',",
                "        'legislation_id', 'event', 'other'",
                "    )),",
                "    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,",
                "    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,",
                "    mention_count INTEGER DEFAULT 1,",
                "    is_core_entity BOOLEAN DEFAULT FALSE,",
                "    UNIQUE (storyline_id, entity_name, entity_type)",
                ");",
                f"CREATE INDEX IF NOT EXISTS idx_{sch}_sei_entity_name ON {sch}.story_entity_index (LOWER(entity_name));",
                f"CREATE INDEX IF NOT EXISTS idx_{sch}_sei_storyline ON {sch}.story_entity_index (storyline_id);",
                f"CREATE INDEX IF NOT EXISTS idx_{sch}_sei_core ON {sch}.story_entity_index (is_core_entity) WHERE is_core_entity = TRUE;",
                f"CREATE INDEX IF NOT EXISTS idx_{sch}_sei_entity_type ON {sch}.story_entity_index (entity_type);",
                f"COMMENT ON TABLE {sch}.story_entity_index IS 'v5: entity mentions per storyline for event→storyline matching (story_continuation)';",
                "",
                "DO $$",
                "BEGIN",
                f"  RAISE NOTICE 'Migration {n}: {dk} domain silo ensured (schema {sch})';",
                "END $$;",
                "",
            ]
        )
        return "\n".join(lines)

    def synthesis_stub_yaml(self) -> str:
        return (
            f"# Copy into api/config/domain_synthesis_config.yaml under domains:\n"
            f"#   {self.domain_key}:\n"
            f"#     # TODO: storyline_development / topic bias for {self.display_name}\n"
        )


def load_json_schema() -> dict[str, Any]:
    if SCHEMA_PATH.is_file():
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return {}
