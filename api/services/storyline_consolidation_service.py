"""
Storyline Consolidation Service

Background service that automatically:
1. Reviews existing storylines for similarity
2. Merges highly similar storylines
3. Creates parent "mega-storylines" for recurring topics
4. Tracks storyline evolution over time
5. Pools articles into core recurring news items

Runs periodically via the AutomationManager.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
from psycopg2.extras import RealDictCursor

from services.ai_storyline_discovery import get_discovery_service
from shared.domain_registry import get_active_domain_keys

logger = logging.getLogger(__name__)

# Configuration
MERGE_SIMILARITY_THRESHOLD = 0.65  # Auto-merge above this
PARENT_SIMILARITY_THRESHOLD = 0.50  # Create parent storyline above this
MIN_ARTICLES_FOR_MEGA = 10  # Minimum articles for a mega-storyline
MAX_MERGES_PER_RUN = 20  # Limit merges per run to avoid overload
CONSOLIDATION_INTERVAL_MINUTES = 30  # How often to run


@dataclass
class StorylineInfo:
    """Lightweight storyline representation for consolidation"""

    id: int
    title: str
    description: str
    article_count: int
    created_at: datetime
    updated_at: datetime
    parent_id: int | None = None
    is_mega: bool = False
    centroid: np.ndarray | None = None
    entities: set[str] = field(default_factory=set)
    article_ids: list[int] = field(default_factory=list)


class StorylineConsolidationService:
    """
    Background service for consolidating and organizing storylines.

    Features:
    - Automatic merging of similar storylines
    - Creation of parent/mega storylines
    - Article pooling across related storylines
    - Evolution tracking
    - Cleanup of orphaned storylines
    """

    def __init__(self, db_config: dict[str, Any]):
        self.db_config = db_config
        self.discovery_service = get_discovery_service(db_config)
        self._running = False
        self._last_run = None
        self._stats = {
            "total_runs": 0,
            "total_merges": 0,
            "total_parents_created": 0,
            "last_run_at": None,
            "last_run_duration_ms": 0,
        }

    def get_db_connection(self):
        """Get database connection from shared pool."""
        from shared.database.connection import get_db_connection as _get_conn

        return _get_conn()

    def ensure_schema_columns(self, schema: str):
        """Ensure required columns exist for consolidation"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                # Add parent_storyline_id for hierarchy
                cur.execute(f"""
                    ALTER TABLE {schema}.storylines
                    ADD COLUMN IF NOT EXISTS parent_storyline_id INTEGER REFERENCES {schema}.storylines(id),
                    ADD COLUMN IF NOT EXISTS merged_into_id INTEGER REFERENCES {schema}.storylines(id),
                    ADD COLUMN IF NOT EXISTS merge_count INTEGER DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS is_mega_storyline BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS consolidation_score FLOAT DEFAULT 0.0,
                    ADD COLUMN IF NOT EXISTS last_consolidated_at TIMESTAMP
                """)
                conn.commit()
                logger.debug(f"Ensured consolidation columns in {schema}.storylines")
        except Exception as e:
            logger.warning(f"Could not add consolidation columns: {e}")
            conn.rollback()
        finally:
            conn.close()

    def fetch_storylines(self, domain: str, hours: int = 168) -> list[StorylineInfo]:
        """Fetch storylines with their embeddings for comparison"""
        schema = domain.replace("-", "_")

        logger.debug(f"[{domain}] Ensuring schema columns exist...")
        self.ensure_schema_columns(schema)

        logger.debug(f"[{domain}] Getting database connection...")
        conn = self.get_db_connection()
        storylines = []

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get active storylines - basic columns only
                logger.debug(f"[{domain}] Executing storylines query (hours={hours})...")
                # Include parent_storyline_id / is_mega_storyline so we do not re-parent children
                # or treat existing megas as new cluster members. Always load current mega parents
                # (by title dedup) even if created outside the rolling window.
                cur.execute(
                    f"""
                    SELECT s.id, s.title, s.description,
                           COALESCE(s.article_count, 0) as article_count,
                           s.created_at, s.updated_at,
                           s.parent_storyline_id,
                           COALESCE(s.is_mega_storyline, FALSE) AS is_mega_storyline
                    FROM {schema}.storylines s
                    WHERE s.merged_into_id IS NULL
                      AND (
                        s.is_mega_storyline IS TRUE
                        OR (
                          s.updated_at >= NOW() - INTERVAL '{hours} hours'
                          AND LOWER(COALESCE(s.status, '')) IN (
                            'active', 'suggested', 'ongoing', 'developing'
                          )
                        )
                      )
                    ORDER BY s.is_mega_storyline DESC NULLS LAST,
                             s.article_count DESC NULLS LAST
                    LIMIT 500
                """
                )

                rows = cur.fetchall()
                logger.debug(f"[{domain}] Query returned {len(rows)} rows")

                for row in rows:
                    storyline = StorylineInfo(
                        id=row["id"],
                        title=row["title"] or "",
                        description=row["description"] or "",
                        article_count=row["article_count"] or 0,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        parent_id=row.get("parent_storyline_id"),
                        is_mega=bool(row.get("is_mega_storyline")),
                    )

                    # Get article IDs for this storyline
                    cur.execute(
                        f"""
                        SELECT article_id FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    """,
                        (storyline.id,),
                    )
                    storyline.article_ids = [r["article_id"] for r in cur.fetchall()]

                    storylines.append(storyline)

                logger.info(f"Fetched {len(storylines)} storylines from {domain}")

        finally:
            conn.close()

        return storylines

    def compute_storyline_embeddings(
        self, domain: str, storylines: list[StorylineInfo]
    ) -> list[StorylineInfo]:
        """
        Compute embeddings for storylines by averaging article embeddings.

        Falls back to entity-based similarity if no embeddings exist.
        """
        schema = domain.replace("-", "_")
        conn = self.get_db_connection()

        embedding_count = 0
        entity_count = 0

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for storyline in storylines:
                    if not storyline.article_ids:
                        # Still try to get entities from the storyline title/description
                        storyline.entities = self.discovery_service.extract_entities(
                            f"{storyline.title} {storyline.description}"
                        )
                        entity_count += len(storyline.entities)
                        continue

                    # Get article embeddings AND titles (for fallback)
                    placeholders = ",".join(["%s"] * len(storyline.article_ids))
                    cur.execute(
                        f"""
                        SELECT embedding_vector, title
                        FROM {schema}.articles
                        WHERE id IN ({placeholders})
                    """,
                        storyline.article_ids,
                    )

                    embeddings = []
                    entities = set()
                    titles = []

                    for row in cur.fetchall():
                        # Collect embeddings if available
                        if row.get("embedding_vector"):
                            try:
                                emb = np.array(json.loads(row["embedding_vector"]))
                                embeddings.append(emb)
                            except Exception:
                                pass

                        # Always extract entities from titles
                        if row.get("title"):
                            titles.append(row["title"])
                            entities.update(self.discovery_service.extract_entities(row["title"]))

                    # Also extract entities from storyline title/description
                    entities.update(
                        self.discovery_service.extract_entities(
                            f"{storyline.title} {storyline.description}"
                        )
                    )

                    if embeddings:
                        # Compute centroid from existing embeddings
                        storyline.centroid = np.mean(embeddings, axis=0)
                        norm = np.linalg.norm(storyline.centroid)
                        if norm > 0:
                            storyline.centroid = storyline.centroid / norm
                        embedding_count += 1

                    storyline.entities = entities
                    entity_count += len(entities)

                logger.info(
                    f"[{domain}] Computed embeddings: {embedding_count} storylines "
                    f"have vector embeddings, {entity_count} total entities extracted"
                )

        except Exception as e:
            logger.error(f"[{domain}] Error computing storyline embeddings: {e}")
        finally:
            conn.close()

        return storylines

    def calculate_storyline_similarity(
        self, s1: StorylineInfo, s2: StorylineInfo
    ) -> dict[str, float]:
        """
        Calculate similarity between two storylines.

        Uses a dynamic weighting scheme:
        - If both have embeddings: 60% semantic, 25% entity, 15% article
        - If no embeddings: 70% entity, 30% article
        """
        result = {
            "semantic": 0.0,
            "entity": 0.0,
            "article": 0.0,
            "title": 0.0,
            "overall": 0.0,
            "has_embeddings": False,
        }

        # Semantic similarity (centroids)
        if s1.centroid is not None and s2.centroid is not None:
            result["semantic"] = float(np.dot(s1.centroid, s2.centroid))
            result["has_embeddings"] = True

        # Entity overlap (Jaccard similarity)
        if s1.entities and s2.entities:
            intersection = len(s1.entities & s2.entities)
            union = len(s1.entities | s2.entities)
            result["entity"] = intersection / union if union > 0 else 0.0

        # Article overlap (Jaccard similarity)
        if s1.article_ids and s2.article_ids:
            set1 = set(s1.article_ids)
            set2 = set(s2.article_ids)
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            result["article"] = intersection / union if union > 0 else 0.0

        # Title similarity (simple word overlap)
        if s1.title and s2.title:
            words1 = set(s1.title.lower().split())
            words2 = set(s2.title.lower().split())
            # Remove common words
            stop_words = {
                "the",
                "a",
                "an",
                "and",
                "or",
                "but",
                "in",
                "on",
                "at",
                "to",
                "for",
                "of",
                "is",
                "are",
            }
            words1 = words1 - stop_words
            words2 = words2 - stop_words
            if words1 and words2:
                intersection = len(words1 & words2)
                union = len(words1 | words2)
                result["title"] = intersection / union if union > 0 else 0.0

        # Dynamic weighting based on available data
        if result["has_embeddings"]:
            # Full weighting with semantic
            result["overall"] = (
                0.50 * result["semantic"]
                + 0.25 * result["entity"]
                + 0.15 * result["article"]
                + 0.10 * result["title"]
            )
        else:
            # No embeddings - rely more on entity and title overlap
            result["overall"] = (
                0.50 * result["entity"] + 0.20 * result["article"] + 0.30 * result["title"]
            )

        return result

    def find_merge_candidates(
        self, storylines: list[StorylineInfo], threshold: float = MERGE_SIMILARITY_THRESHOLD
    ) -> list[tuple[StorylineInfo, StorylineInfo, dict]]:
        """
        Find pairs of storylines that should be merged.

        Works with or without embeddings, using entity/title similarity as fallback.
        """
        candidates = []
        n = len(storylines)

        logger.debug(f"Comparing {n} storylines for merge candidates (threshold: {threshold:.0%})")

        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = storylines[i], storylines[j]

                # Do not merge mega parents via pairwise merge (use mega title dedup instead)
                if s1.is_mega or s2.is_mega:
                    continue

                # Skip if one is already a parent of the other
                if s1.parent_id == s2.id or s2.parent_id == s1.id:
                    continue

                # Skip if either has no entities and no centroid (can't compare)
                if not s1.entities and s1.centroid is None:
                    continue
                if not s2.entities and s2.centroid is None:
                    continue

                similarity = self.calculate_storyline_similarity(s1, s2)

                if similarity["overall"] >= threshold:
                    candidates.append((s1, s2, similarity))
                    logger.debug(
                        f"Merge candidate: '{s1.title[:30]}' + '{s2.title[:30]}' "
                        f"(sim: {similarity['overall']:.0%})"
                    )

        # Sort by similarity descending
        candidates.sort(key=lambda x: x[2]["overall"], reverse=True)

        logger.info(f"Found {len(candidates)} merge candidates above {threshold:.0%} threshold")

        return candidates[:MAX_MERGES_PER_RUN]

    def merge_storylines(
        self,
        domain: str,
        primary: StorylineInfo,
        secondary: StorylineInfo,
        similarity: dict[str, float],
    ) -> int | None:
        """
        Merge secondary storyline into primary.

        - Moves all articles from secondary to primary
        - Updates article counts
        - Marks secondary as merged
        - Creates merge history entry
        """
        schema = domain.replace("-", "_")
        conn = self.get_db_connection()

        try:
            with conn.cursor() as cur:
                # Move articles from secondary to primary
                cur.execute(
                    f"""
                    INSERT INTO {schema}.storyline_articles
                    (storyline_id, article_id, relevance_score, created_at)
                    SELECT %s, article_id, relevance_score, NOW()
                    FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                    ON CONFLICT (storyline_id, article_id) DO NOTHING
                """,
                    (primary.id, secondary.id),
                )

                moved_count = cur.rowcount

                # Update primary article count
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    merge_count = COALESCE(merge_count, 0) + 1,
                    consolidation_score = GREATEST(COALESCE(consolidation_score, 0), %s),
                    last_consolidated_at = NOW(),
                    updated_at = NOW()
                    WHERE id = %s
                """,
                    (primary.id, similarity["overall"], primary.id),
                )

                # Mark secondary as merged
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET merged_into_id = %s,
                        status = 'merged',
                        updated_at = NOW()
                    WHERE id = %s
                """,
                    (primary.id, secondary.id),
                )

                # Update description to mention merge
                new_desc = f"{primary.description or ''} [Merged with: {secondary.title[:50]}]"
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET description = %s
                    WHERE id = %s
                """,
                    (new_desc[:500], primary.id),
                )

                conn.commit()

                logger.info(
                    f"Merged storyline {secondary.id} into {primary.id} "
                    f"(sim: {similarity['overall']:.0%}, moved {moved_count} articles)"
                )

                return primary.id

        except Exception as e:
            logger.error(f"Error merging storylines: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def merge_storylines_by_ids(
        self,
        domain: str,
        primary_id: int,
        secondary_id: int,
        overall_confidence: float,
    ) -> int | None:
        """
        Merge secondary into primary when only ids are known (e.g. graph_connection worker).
        Loads minimal titles/descriptions from DB; no-ops if either row is missing or already merged.
        """
        if primary_id == secondary_id:
            return None
        schema = domain.replace("-", "_")
        conn = self.get_db_connection()
        rows: dict[int, tuple[str, str, int | None]] = {}
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, description, merged_into_id
                    FROM {schema}.storylines
                    WHERE id IN (%s, %s)
                    """,
                    (primary_id, secondary_id),
                )
                for rid, title, desc, merged_into in cur.fetchall():
                    rows[int(rid)] = (
                        str(title or ""),
                        str(desc or ""),
                        int(merged_into) if merged_into is not None else None,
                    )
        except Exception as e:
            logger.warning("merge_storylines_by_ids load %s: %s", domain, e)
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if primary_id not in rows or secondary_id not in rows:
            return None
        if rows[secondary_id][2] is not None or rows[primary_id][2] is not None:
            return None

        pt, pdesc, _ = rows[primary_id]
        st, _, _ = rows[secondary_id]
        primary = StorylineInfo(
            id=primary_id,
            title=pt,
            description=pdesc,
            article_count=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        secondary = StorylineInfo(
            id=secondary_id,
            title=st,
            description=sdesc,
            article_count=0,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        return self.merge_storylines(
            domain,
            primary,
            secondary,
            {"overall": float(overall_confidence)},
        )

    def find_mega_storyline_candidates(
        self, storylines: list[StorylineInfo], threshold: float = PARENT_SIMILARITY_THRESHOLD
    ) -> list[list[StorylineInfo]]:
        """
        Find groups of storylines that should have a common parent (mega-storyline).

        Works with or without embeddings.
        """
        groups = []
        used = set()
        n = len(storylines)

        logger.debug(
            f"Finding mega-storyline groups from {n} storylines (threshold: {threshold:.0%})"
        )

        # Build adjacency based on similarity
        adjacency = defaultdict(list)

        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = storylines[i], storylines[j]

                # Megas are parents, not members of a new child cluster; children already parented skip
                if s1.is_mega or s2.is_mega:
                    continue
                if s1.parent_id is not None or s2.parent_id is not None:
                    continue

                # Skip if neither has entities nor centroid
                if (not s1.entities and s1.centroid is None) or (
                    not s2.entities and s2.centroid is None
                ):
                    continue

                similarity = self.calculate_storyline_similarity(s1, s2)

                if similarity["overall"] >= threshold:
                    adjacency[i].append(j)
                    adjacency[j].append(i)

        # Find connected components
        for i in range(n):
            if i in used:
                continue

            if storylines[i].parent_id is not None:
                continue  # Already has a parent
            if storylines[i].is_mega:
                continue  # Existing mega is never a leaf in a new mega group

            # BFS to find connected component
            component = []
            queue = [i]

            while queue:
                node = queue.pop(0)
                if node in used:
                    continue

                used.add(node)
                component.append(storylines[node])

                for neighbor in adjacency[node]:
                    if neighbor not in used:
                        queue.append(neighbor)

            # Only create mega-storyline if group has multiple members
            # and enough total articles
            total_articles = sum(s.article_count for s in component)

            if len(component) >= 2 and total_articles >= MIN_ARTICLES_FOR_MEGA:
                groups.append(component)

        return groups

    def _fold_duplicate_mega_rows(
        self, cur, schema: str, mega_title: str, canonical_id: int
    ) -> None:
        """Merge extra mega rows with the same title into canonical_id (reparent + article pool)."""
        cur.execute(
            f"""
            SELECT id FROM {schema}.storylines
            WHERE COALESCE(is_mega_storyline, FALSE) = TRUE
              AND merged_into_id IS NULL
              AND id <> %s
              AND LOWER(TRIM(title)) = LOWER(TRIM(%s))
            ORDER BY id ASC
            """,
            (canonical_id, mega_title),
        )
        dup_rows = cur.fetchall()
        dup_ids = [r[0] for r in dup_rows]
        for dup_id in dup_ids:
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET parent_storyline_id = %s, last_consolidated_at = NOW()
                WHERE parent_storyline_id = %s AND merged_into_id IS NULL
                """,
                (canonical_id, dup_id),
            )
            cur.execute(
                f"""
                INSERT INTO {schema}.storyline_articles
                (storyline_id, article_id, relevance_score, created_at)
                SELECT %s, article_id, relevance_score * 0.9, NOW()
                FROM {schema}.storyline_articles
                WHERE storyline_id = %s
                ON CONFLICT (storyline_id, article_id) DO NOTHING
                """,
                (canonical_id, dup_id),
            )
            cur.execute(
                f"DELETE FROM {schema}.storyline_articles WHERE storyline_id = %s",
                (dup_id,),
            )
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET merged_into_id = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (canonical_id, dup_id),
            )

    def _refresh_mega_counts_from_db(self, cur, schema: str, mega_id: int) -> None:
        """Set description and article totals from actual child + storyline_articles rows."""
        cur.execute(
            f"""
            SELECT COUNT(*)::int FROM {schema}.storylines
            WHERE parent_storyline_id = %s AND merged_into_id IS NULL
            """,
            (mega_id,),
        )
        sub_n = cur.fetchone()[0]
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT article_id)::int
            FROM {schema}.storyline_articles
            WHERE storyline_id = %s
            """,
            (mega_id,),
        )
        art_n = cur.fetchone()[0]
        desc = (
            f"Mega-storyline covering {sub_n} related sub-stories "
            f"with {art_n} total articles"
        )
        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET article_count = %s,
                total_articles = %s,
                description = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (art_n, art_n, desc, mega_id),
        )

    def create_mega_storyline(self, domain: str, children: list[StorylineInfo]) -> int | None:
        """
        Create a parent mega-storyline for a group of related storylines.

        The mega-storyline:
        - Has a generated title based on common themes
        - Links all child storylines as sub-stories
        - Aggregates total article count
        - Serves as a "topic" or "recurring story"
        """
        if not children:
            return None

        schema = domain.replace("-", "_")
        self.ensure_schema_columns(schema)
        conn = self.get_db_connection()

        try:
            with conn.cursor() as cur:
                # Generate mega-storyline title from common entities
                entity_counts = defaultdict(int)
                for child in children:
                    for entity in child.entities:
                        entity_counts[entity] += 1

                if entity_counts:
                    top_entity = max(entity_counts, key=entity_counts.get)
                    mega_title = f"Ongoing: {top_entity.title()}"
                else:
                    # Use first child's title as base
                    mega_title = f"Related Stories: {children[0].title[:40]}..."

                # Reuse existing mega with the same canonical title (avoid duplicate "Ongoing: X" rows)
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.storylines
                    WHERE COALESCE(is_mega_storyline, FALSE) = TRUE
                      AND merged_into_id IS NULL
                      AND LOWER(TRIM(title)) = LOWER(TRIM(%s))
                    ORDER BY id ASC
                    LIMIT 1
                    """,
                    (mega_title,),
                )
                row = cur.fetchone()
                mega_id = row[0] if row else None
                created_new = mega_id is None

                if mega_id is not None:
                    self._fold_duplicate_mega_rows(cur, schema, mega_title, mega_id)
                else:
                    total_articles = sum(c.article_count for c in children)
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.storylines
                        (storyline_uuid, title, description, status, processing_status,
                         article_count, total_articles, is_mega_storyline,
                         consolidation_score, created_at, updated_at)
                        VALUES (
                            gen_random_uuid(), %s, %s, 'active', 'completed',
                            %s, %s, TRUE, %s, NOW(), NOW()
                        )
                        RETURNING id
                        """,
                        (
                            mega_title,
                            "Mega-storyline (initializing…)",
                            total_articles,
                            total_articles,
                            0.8,
                        ),
                    )
                    ins = cur.fetchone()
                    if not ins:
                        conn.rollback()
                        return None
                    mega_id = ins[0]

                child_ids = [c.id for c in children]
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET parent_storyline_id = %s,
                        last_consolidated_at = NOW()
                    WHERE id = ANY(%s) AND id <> %s
                    """,
                    (mega_id, child_ids, mega_id),
                )

                for child in children:
                    if child.id == mega_id:
                        continue
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.storyline_articles
                        (storyline_id, article_id, relevance_score, created_at)
                        SELECT %s, article_id, relevance_score * 0.9, NOW()
                        FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                        ON CONFLICT (storyline_id, article_id) DO NOTHING
                    """,
                        (mega_id, child.id),
                    )

                self._refresh_mega_counts_from_db(cur, schema, mega_id)

                conn.commit()

                logger.info(
                    f"{'Created' if created_new else 'Updated'} mega-storyline {mega_id}: "
                    f"'{mega_title}' ({len(children)} cluster members)"
                )

                return mega_id

        except Exception as e:
            logger.error(f"Error creating mega-storyline: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def run_consolidation(self, domain: str) -> dict[str, Any]:
        """
        Main consolidation run for a domain.

        Steps:
        1. Fetch all active storylines
        2. Compute embeddings
        3. Find merge candidates
        4. Perform merges
        5. Find mega-storyline candidates
        6. Create mega-storylines
        """
        start_time = datetime.now()

        result = {
            "domain": domain,
            "started_at": start_time.isoformat(),
            "storylines_analyzed": 0,
            "merges_performed": 0,
            "mega_storylines_created": 0,
            "merge_proposals_queued": 0,
            "hyperedge_proposals_queued": 0,
            "errors": [],
        }

        try:
            # Step 1: Fetch storylines
            logger.info(f"[{domain}] Fetching storylines...")
            try:
                storylines = self.fetch_storylines(domain)
            except Exception as fetch_error:
                logger.error(f"[{domain}] Error fetching storylines: {fetch_error}", exc_info=True)
                result["errors"].append(f"Fetch error: {fetch_error}")
                storylines = []

            result["storylines_analyzed"] = len(storylines)
            logger.info(f"[{domain}] Found {len(storylines)} storylines")

            if len(storylines) < 2:
                result["message"] = (
                    f"Not enough storylines to consolidate (found {len(storylines)})"
                )
                logger.info(f"[{domain}] {result['message']}")
                return result

            # Step 2: Compute embeddings (and extract entities as fallback)
            logger.info(
                f"[{domain}] Computing embeddings/entities for {len(storylines)} storylines..."
            )
            storylines = self.compute_storyline_embeddings(domain, storylines)

            # Filter to those with either embeddings OR entities (can be compared)
            comparable_storylines = [
                s for s in storylines if s.centroid is not None or len(s.entities) > 0
            ]

            result["storylines_with_embeddings"] = len(
                [s for s in storylines if s.centroid is not None]
            )
            result["storylines_with_entities"] = len([s for s in storylines if len(s.entities) > 0])
            result["storylines_comparable"] = len(comparable_storylines)

            if len(comparable_storylines) < 2:
                result["message"] = (
                    f"Not enough comparable storylines (need 2+, have {len(comparable_storylines)})"
                )
                logger.info(f"[{domain}] {result['message']}")
                return result

            storylines = comparable_storylines

            # Step 3: Find merge candidates
            logger.info(f"[{domain}] Finding merge candidates from {len(storylines)} storylines...")
            merge_candidates = self.find_merge_candidates(storylines)
            result["merge_candidates_found"] = len(merge_candidates)

            try:
                from services.graph_connection_queue_service import (
                    mark_storyline_merge_applied,
                    record_storyline_merge_candidates,
                )

                result["merge_proposals_queued"] = record_storyline_merge_candidates(
                    domain, merge_candidates
                )
            except Exception as qe:
                logger.debug("graph_connection merge queue: %s", qe)
                result["merge_proposals_queued"] = 0

            # Step 4: Perform merges
            merged_ids = set()
            for primary, secondary, similarity in merge_candidates:
                # Skip if either was already merged in this run
                if primary.id in merged_ids or secondary.id in merged_ids:
                    continue

                merge_result = self.merge_storylines(domain, primary, secondary, similarity)
                if merge_result:
                    merged_ids.add(secondary.id)
                    result["merges_performed"] += 1
                    try:
                        from services.graph_connection_queue_service import (
                            mark_storyline_merge_applied,
                        )

                        mark_storyline_merge_applied(domain, primary.id, secondary.id)
                    except Exception as me:
                        logger.debug("mark merge applied: %s", me)

            # Step 5: Re-fetch after merges (for accurate mega-storyline creation)
            if result["merges_performed"] > 0:
                storylines = self.fetch_storylines(domain)
                storylines = self.compute_storyline_embeddings(domain, storylines)
                storylines = [
                    s
                    for s in storylines
                    if s.centroid is not None or len(s.entities) > 0
                ]

            # Step 6: Find and create mega-storylines
            logger.info(f"[{domain}] Finding mega-storyline candidates...")
            mega_groups = self.find_mega_storyline_candidates(storylines)
            result["mega_candidates_found"] = len(mega_groups)

            try:
                from services.graph_connection_queue_service import (
                    record_storyline_hyperedge_groups,
                )

                result["hyperedge_proposals_queued"] = record_storyline_hyperedge_groups(
                    domain,
                    mega_groups[:5],
                    pairwise_confidence_fn=self.calculate_storyline_similarity,
                )
            except Exception as he:
                logger.debug("graph_connection hyperedge queue: %s", he)
                result["hyperedge_proposals_queued"] = 0

            for group in mega_groups[:5]:  # Limit to 5 mega-storylines per run
                mega_id = self.create_mega_storyline(domain, group)
                if mega_id:
                    result["mega_storylines_created"] += 1

            # Update stats
            self._stats["total_runs"] += 1
            self._stats["total_merges"] += result["merges_performed"]
            self._stats["total_parents_created"] += result["mega_storylines_created"]
            self._stats["last_run_at"] = start_time.isoformat()

        except Exception as e:
            logger.error(f"Consolidation error for {domain}: {e}")
            result["errors"].append(str(e))

        # Final timing
        duration = (datetime.now() - start_time).total_seconds() * 1000
        result["duration_ms"] = duration
        result["completed_at"] = datetime.now().isoformat()
        self._stats["last_run_duration_ms"] = duration

        logger.info(
            f"[{domain}] Consolidation complete: "
            f"{result['merges_performed']} merges, "
            f"{result['mega_storylines_created']} mega-storylines in {duration:.0f}ms"
        )

        return result

    def run_all_domains(self) -> dict[str, Any]:
        """Run consolidation for all domains"""
        domains = list(get_active_domain_keys())
        results = {}

        for domain in domains:
            try:
                results[domain] = self.run_consolidation(domain)
            except Exception as e:
                results[domain] = {"error": str(e)}

        return {"timestamp": datetime.now().isoformat(), "domains": results, "stats": self._stats}

    def get_stats(self) -> dict[str, Any]:
        """Get consolidation service stats"""
        return {
            **self._stats,
            "config": {
                "merge_threshold": MERGE_SIMILARITY_THRESHOLD,
                "parent_threshold": PARENT_SIMILARITY_THRESHOLD,
                "min_articles_for_mega": MIN_ARTICLES_FOR_MEGA,
                "max_merges_per_run": MAX_MERGES_PER_RUN,
                "interval_minutes": CONSOLIDATION_INTERVAL_MINUTES,
            },
        }


# Singleton instance
_consolidation_service = None


def get_consolidation_service(db_config: dict[str, Any] = None) -> StorylineConsolidationService:
    """Get or create the consolidation service singleton"""
    global _consolidation_service

    if _consolidation_service is None:
        if db_config is None:
            from shared.database.connection import get_db_config

            db_config = get_db_config()
        _consolidation_service = StorylineConsolidationService(db_config)

    return _consolidation_service


# Task function for AutomationManager
def consolidation_task() -> dict[str, Any]:
    """
    Background task function for the AutomationManager.
    Call this periodically to consolidate storylines.
    """
    service = get_consolidation_service()
    return service.run_all_domains()
