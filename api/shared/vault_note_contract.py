"""
Two-level knowledge contract: Postgres structure ↔ Obsidian vault longform.

Ownership (locked):
  - Postgres SSOT: canonical IDs, vault_path, note_status, lifecycle, mention
    counts, location / place hierarchy (geo_parent), datetimes.
  - Obsidian SSOT: relational tags, wikilinks, soft relations (rivalry, alliance
    narrative), longform significance / timeline prose.
  - Postgres mirrors Obsidian tags + wikilink adjacency for query / context packs
    only — it does not invent soft relational edges.
"""

from __future__ import annotations

import re
from typing import Any, Literal

NoteType = Literal[
    "entity",
    "connection",
    "event",
    "storyline",
    "cluster",
    "clipping",
    "expansion",
    "daily_briefing",
]
NoteStatus = Literal[
    "absent",
    "stub",
    "seeded",
    "living",
    "frozen",
    "structure_only",
    "note_pending",
    "note_ready",
]
Lifecycle = Literal["absent", "stub", "seeded", "living", "frozen", "index", "archived"]
VaultAction = Literal["create", "update", "seed", "significance"]
LinkKind = Literal["wikilink", "tag_ref"]
TagsSource = Literal["obsidian", "ni_structural", "merged"]

NOTE_TYPES: tuple[str, ...] = (
    "entity",
    "connection",
    "event",
    "storyline",
    "cluster",
    "clipping",
    "expansion",
    "daily_briefing",
)
LIFECYCLES: tuple[str, ...] = (
    "absent",
    "stub",
    "seeded",
    "living",
    "frozen",
    "index",
    "archived",
)

# Fan-out caps per article (plan)
MAX_ENTITY_NOTES_PER_ARTICLE = 3
MAX_EVENT_NOTES_PER_ARTICLE = 1
MAX_CONNECTION_NOTES_PER_ARTICLE = 1
# Second-brain MVP: wiki targets per clipping
MAX_MVP_WIKI_TARGETS = 8
# Morning prime caps (soft concurrency / budget — not product catalog size)
# Sized for PopOS shared 8b lane under MAX_CONCURRENT_OLLAMA_TASKS=1 (~3–5 min/expansion).
MAX_MORNING_NEWS_EXPANSIONS = 12
MAX_MORNING_SCIENCE_EXPANSIONS = 4
MORNING_DELTA_DAYS = 7
MORNING_BRIEF_ACTIVITY_DAYS = 7
MORNING_NEW_OF_NOTE_CAP = 4
MORNING_ONGOING_CAP = 8
MORNING_WEB_MAX_URLS_PER_STORY = 3
MORNING_VAULT_RETRIEVAL_LIMIT = 12
MORNING_VAULT_RETRIEVAL_CHARS = 12000
MEMPALACE_BRIEF_WING = "News Intelligence"
MEMPALACE_BRIEF_AGENT = "morning_briefing_manager"
MEMPALACE_ROOMS = (
    "morning_brief",
    "watches",
    "preferred_narratives",
    "brief_diary",
    "skip_list",
)

# Mention tiers (politics defaults; env-overridable in services)
DEFAULT_STUB_MENTION_TIER = 20
DEFAULT_LIVING_MENTION_TIER = 100
DEFAULT_COOLDOWN_HOURS = 6
DEFAULT_MAX_JOBS_PER_CYCLE = 8

# Context pack expansion
DEFAULT_PACK_HOPS = 2
DEFAULT_PACK_MAX_NOTES = 12

ENTITY_DIR = "40_Reference/entities"
TIMELINE_DIR = "40_Reference/timelines"
CONNECTION_DIR = "25_Connections"
EVENT_DIR = "40_Reference/events"
STORYLINE_DIR = "30_Stories"
CLUSTER_DIR = "40_Reference/clusters"
CLIPPING_DIR = "20_Clippings"
# Distinct science/medicine research branch (bioRxiv, AI papers, etc.)
SCIENCE_BRANCH_ROOT = "50_Science"
SCIENCE_CLIPPING_DIR = f"{SCIENCE_BRANCH_ROOT}/20_Clippings"
SCIENCE_TOPIC_DIR = f"{SCIENCE_BRANCH_ROOT}/40_Topics"
SCIENCE_EXPANSION_DIR = f"{SCIENCE_BRANCH_ROOT}/30_Expansions"
EXPANSION_DIR = f"{STORYLINE_DIR}/expansions"
DAILY_BRIEFING_DIR = "10_Daily"

# Domains whose Capture/Distill land under 50_Science (not news 20_Clippings).
SCIENCE_VAULT_DOMAINS: frozenset[str] = frozenset(
    {
        "medicine",
        "artificial-intelligence",
        "neurodiversity",
    }
)

# Cross-branch reference entities stay on shared ``40_Reference/entities/`` so
# news + science notes can wikilink/tag the same file. Examples (not exhaustive):
# orgs, colleges, labs, places/locations, people. Science *subjects* (genes,
# methods, diseases) still file under ``50_Science/40_Topics/``.
SHARED_VAULT_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "organization",
        "organisation",
        "company",
        "corporation",
        "university",
        "college",
        "school",
        "institution",
        "institute",
        "lab",
        "laboratory",
        "facility",
        "agency",
        "gov",
        "government",
        "ngo",
        "org",
        "person",
        "people",
        "individual",
        "place",
        "location",
        "city",
        "country",
        "region",
        "state",
        "province",
        "geo",
        "geography",
        "facility_place",
    }
)

VAULT_SYNC_ROOTS: tuple[str, ...] = (
    ENTITY_DIR,
    TIMELINE_DIR,
    CONNECTION_DIR,
    EVENT_DIR,
    STORYLINE_DIR,
    CLUSTER_DIR,
    CLIPPING_DIR,
    SCIENCE_CLIPPING_DIR,
    SCIENCE_TOPIC_DIR,
    SCIENCE_EXPANSION_DIR,
    EXPANSION_DIR,
    DAILY_BRIEFING_DIR,
)

# Frontmatter keys NI may set; all other keys (esp. tags) are Obsidian-owned
NI_OWNED_FRONTMATTER_KEYS: frozenset[str] = frozenset(
    {
        "ni_domain",
        "note_type",
        "canonical_entity_id",
        "storyline_id",
        "entity_ids",
        "object_id",
        "lifecycle",
        "mention_count",
        "ni_auto",
        "entity_type",
        "article_count",
        "status",
        "preseeded_at",
        "updated",
        "created",
        "geo_parent_entity_id",
        "place_kind",
        "cluster_key",
        "topic",
        "hub",
        "article_id",
        "source",
        "last_article_id",
        "clipping",
        "source_article_id",
        "storyline_id",
        "evidence_fingerprint",
        "window_start",
        "window_end",
        "briefing_day",
    }
)

# Tags NI may add structurally — never soft relations like "rival" / "hates"
STRUCTURAL_TAG_PREFIXES: tuple[str, ...] = (
    "entity/",
    "place/",
    "domain/",
    "note/",
    "branch/",
    "preseed",
    "seed",
)

AUTO_POSTURE_START = "<!-- ni:auto:posture -->"
AUTO_POSTURE_END = "<!-- /ni:auto:posture -->"
AUTO_TIMELINE_START = "<!-- ni:auto:timeline -->"
AUTO_TIMELINE_END = "<!-- /ni:auto:timeline -->"
AUTO_SIGNIFICANCE_START = "<!-- ni:auto:significance -->"
AUTO_SIGNIFICANCE_END = "<!-- /ni:auto:significance -->"
AUTO_BRIEF_START = "<!-- ni:auto:brief -->"
AUTO_BRIEF_END = "<!-- /ni:auto:brief -->"

_WIKILINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")
_HASH_TAG_RE = re.compile(r"(?<!\w)#([a-zA-Z][\w/-]*)")


def slugify_entity_name(name: str, *, max_len: int = 80) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (name or "").strip())
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return (s or "entity")[:max_len]


def is_science_vault_domain(domain_key: str | None) -> bool:
    """True when MVP filing should use the 50_Science branch."""
    dk = (domain_key or "").strip().lower().replace("_", "-")
    return dk in SCIENCE_VAULT_DOMAINS


def is_shared_vault_entity_type(entity_type: str | None) -> bool:
    """Cross-cutting refs (orgs, places, people, labs) stay on shared 40_Reference."""
    et = (entity_type or "").strip().lower().replace("-", "_")
    if not et:
        return False
    if et in SHARED_VAULT_ENTITY_TYPES:
        return True
    # Soft match: university_of_*, research_institute, geo_*, etc.
    return any(
        tok in et
        for tok in (
            "organiz",
            "universit",
            "college",
            "institut",
            "compan",
            "corporat",
            "laborator",
            "person",
            "people",
            "place",
            "locat",
            "geo",
            "city",
            "country",
            "region",
        )
    )


def is_clipping_vault_path(rel_path: str | None) -> bool:
    p = (rel_path or "").replace("\\", "/")
    return p.startswith(CLIPPING_DIR + "/") or p.startswith(SCIENCE_CLIPPING_DIR + "/")


def entity_vault_rel_path(
    canonical_name: str,
    *,
    domain_key: str | None = None,
    entity_type: str | None = None,
) -> str:
    """
    Path for an entity/wiki note.

    Science-domain *subjects* (genes, methods, diseases) → ``50_Science/40_Topics/``.
    Shared refs (orgs, places, people, labs — any domain) and all news-domain
    entities → ``40_Reference/entities/``. Tags are free to cross branches.
    """
    slug = slugify_entity_name(canonical_name)
    if is_science_vault_domain(domain_key) and not is_shared_vault_entity_type(entity_type):
        return f"{SCIENCE_TOPIC_DIR}/{slug}.md"
    return f"{ENTITY_DIR}/{slug}.md"


def science_topic_vault_rel_path(title: str) -> str:
    return f"{SCIENCE_TOPIC_DIR}/{slugify_entity_name(title, max_len=40)}.md"


def connection_vault_rel_path(name_a: str, name_b: str) -> str:
    a = slugify_entity_name(name_a, max_len=40)
    b = slugify_entity_name(name_b, max_len=40)
    pair = "_".join(sorted([a.lower(), b.lower()]))
    return f"{CONNECTION_DIR}/{pair}.md"


def event_vault_rel_path(domain_key: str, event_id: int, title: str = "") -> str:
    slug = slugify_entity_name(title or f"event-{event_id}", max_len=50)
    return f"{EVENT_DIR}/{domain_key}-{event_id}-{slug}.md"


def storyline_vault_rel_path(domain_key: str, storyline_id: int, title: str = "") -> str:
    slug = slugify_entity_name(title or f"story-{storyline_id}", max_len=50)
    return f"{STORYLINE_DIR}/{domain_key}-{storyline_id}-{slug}.md"


def cluster_vault_rel_path(cluster_key: str) -> str:
    return f"{CLUSTER_DIR}/{slugify_entity_name(cluster_key)}.md"


def expansion_vault_rel_path(
    *,
    domain_key: str,
    object_id: int,
    title: str = "",
    anchor: str = "storyline",
) -> str:
    """Longform expansion path (news under 30_Stories; science under 50_Science)."""
    slug = slugify_entity_name(title or f"{anchor}-{object_id}", max_len=50)
    name = f"{domain_key}-{anchor}-{int(object_id)}-{slug}.md"
    if is_science_vault_domain(domain_key):
        return f"{SCIENCE_EXPANSION_DIR}/{name}"
    return f"{EXPANSION_DIR}/{name}"


def daily_briefing_vault_rel_path(
    day: str,
    *,
    branch: str = "news",
) -> str:
    """day = YYYY-MM-DD; branch news|science."""
    d = (day or "")[:10]
    if branch == "science":
        return f"{DAILY_BRIEFING_DIR}/{d}-science.md"
    return f"{DAILY_BRIEFING_DIR}/{d}.md"


def daily_briefing_object_id(day: str) -> int:
    """Stable int YYYYMMDD for registry object_id."""
    digits = "".join(c for c in (day or "")[:10] if c.isdigit())
    try:
        return int(digits) if len(digits) == 8 else int(digits or "0")
    except ValueError:
        return 0


def cluster_object_id(cluster_key: str) -> int:
    """Stable synthetic object_id for cluster registry rows (91xxxxxx range)."""
    import hashlib

    digest = hashlib.md5((cluster_key or "cluster").encode("utf-8")).hexdigest()
    return 91_000_000 + (int(digest[:8], 16) % 1_000_000)


def clipping_vault_rel_path(
    *,
    published: str,
    article_id: int,
    title: str = "",
    domain_key: str | None = None,
) -> str:
    day = (published or "")[:10] or "undated"
    slug = slugify_entity_name(title or f"article-{article_id}", max_len=50)
    base = SCIENCE_CLIPPING_DIR if is_science_vault_domain(domain_key) else CLIPPING_DIR
    return f"{base}/{day}-{int(article_id)}-{slug}.md"


def is_structural_tag(tag: str) -> bool:
    t = (tag or "").strip().lstrip("#").lower()
    if not t:
        return False
    if t in (
        "preseed",
        "seed",
        "entity",
        "storyline",
        "connection",
        "event",
        "cluster",
        "clipping",
        "update/new",
    ):
        return True
    return any(t.startswith(p) for p in STRUCTURAL_TAG_PREFIXES)


def merge_tags(
    obsidian_tags: list[str] | None,
    structural_tags: list[str] | None = None,
) -> list[str]:
    """Obsidian tags win; structural tags are unioned in. Soft relations preserved."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in list(obsidian_tags or []) + list(structural_tags or []):
        t = str(raw).strip().lstrip("#")
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def extract_wikilink_titles(text: str) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for m in _WIKILINK_RE.finditer(text or ""):
        raw = m.group(1).strip()
        # [[path|display]] or [[Title#heading]]
        title = raw.split("|", 1)[0].split("#", 1)[0].strip()
        if not title:
            continue
        # Prefer basename for path-like links
        if "/" in title:
            title = title.rsplit("/", 1)[-1]
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return titles


def extract_hash_tags(text: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for m in _HASH_TAG_RE.finditer(text or ""):
        t = m.group(1).strip()
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(t)
    return tags


def structural_tags_for_note(
    *,
    note_type: str,
    domain_key: str,
    entity_type: str | None = None,
    place_kind: str | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    tags = [
        f"note/{note_type}",
        f"domain/{domain_key}",
    ]
    if is_science_vault_domain(domain_key):
        tags.append("branch/science")
    else:
        tags.append("branch/news")
    if entity_type:
        tags.append(f"entity/{str(entity_type).strip().lower()}")
        if is_shared_vault_entity_type(entity_type):
            tags.append("vault/shared_ref")
    if place_kind:
        tags.append(f"place/{str(place_kind).strip().lower()}")
    if extra:
        tags.extend(extra)
    return merge_tags([], tags)


def entity_note_template(
    *,
    title: str,
    domain_key: str,
    entity_id: int,
    tier: str = "stub",
    tags: list[str] | None = None,
) -> str:
    """Initial markdown body with agent fences (frontmatter added by caller)."""
    tag_line = ""
    if tags:
        tag_line = " ".join(f"#{t.lstrip('#')}" for t in tags[:12])
    return f"""# {title}

## Basics

_Seed from Wikipedia / RAG when available._

## Current posture

{AUTO_POSTURE_START}
_No automated posture yet._
{AUTO_POSTURE_END}

## Relationships

- _Wikilinks appear as the note becomes living._
{f"{tag_line}" if tag_line else ""}

## Timeline

{AUTO_TIMELINE_START}
{AUTO_TIMELINE_END}

## Significance

{AUTO_SIGNIFICANCE_START}
_Significance synthesised when evidence accumulates._
{AUTO_SIGNIFICANCE_END}

## Open questions

- _

## Sources

- ni_domain: {domain_key}
- canonical_entity_id: {entity_id}
- tier: {tier}
"""


def split_frontmatter_body(text: str) -> tuple[dict[str, Any], str]:
    """Parse simple YAML frontmatter; returns (fm_dict, body_without_fm).

    Supports `tags: [...]` JSON lists and plain scalars. Full rich parsing
    lives in vault_bridge_service._parse_frontmatter_rich for sync.
    """
    fm_re = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
    m = fm_re.match(text or "")
    if not m:
        return {}, text or ""
    out: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        if val.startswith("[") or val.startswith("{"):
            try:
                import json

                out[key] = json.loads(val)
                continue
            except Exception:
                pass
        out[key] = val.strip('"').strip("'")
    body = fm_re.sub("", text or "", count=1).lstrip("\n")
    return out, body


def merge_frontmatter(
    existing: dict[str, Any],
    ni_updates: dict[str, Any],
    *,
    structural_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Merge NI structure keys into existing Obsidian frontmatter; preserve tags."""
    merged = dict(existing or {})
    for k, v in (ni_updates or {}).items():
        if k == "tags":
            continue
        if k in NI_OWNED_FRONTMATTER_KEYS or k not in merged:
            merged[k] = v
    file_tags: list[str] = []
    raw_tags = existing.get("tags") if existing else None
    if isinstance(raw_tags, list):
        file_tags = [str(t).strip().lstrip("#") for t in raw_tags if str(t).strip()]
    elif isinstance(raw_tags, str) and raw_tags.strip():
        file_tags = [t.strip().lstrip("#") for t in raw_tags.split(",") if t.strip()]
    ni_tags = ni_updates.get("tags") if isinstance((ni_updates or {}).get("tags"), list) else []
    structural = [
        str(t).strip().lstrip("#")
        for t in (structural_tags or ni_tags or [])
        if is_structural_tag(str(t))
    ]
    merged["tags"] = merge_tags(file_tags, structural)
    return merged
