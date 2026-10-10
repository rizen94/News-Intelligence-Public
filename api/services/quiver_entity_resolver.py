"""
Quiver Entity Resolver - Maps politicians from Quiver trades to entity_profiles.
Politicians are stored as entities in domain_key='politics' with metadata for bioguide_id, chamber, party, state.
"""
import json
import logging
from typing import Any, Optional

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

POLITICIAN_ENTITY_TYPE = "politician"
POLITICIAN_SOURCE = "quiver_congress"


def resolve_politician_entity(
    politician_name: str,
    bioguide_id: str | None = None,
    chamber: str | None = None,
    party: str | None = None,
    state: str | None = None
) -> int | None:
    """
    Create or retrieve politician entity profile.
    Returns entity_profile.id
    """
    if not politician_name:
        return None
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Try to find by bioguide_id first (most reliable)
            if bioguide_id:
                cur.execute("""
                    SELECT id FROM intelligence.entity_profiles
                    WHERE metadata->>'bioguide_id' = %s
                    AND domain_key = 'politics'
                    LIMIT 1
                """, (bioguide_id,))
                existing = cur.fetchone()
                if existing:
                    return _update_politician_metadata(cur, existing[0], {
                        "canonical_name": politician_name,
                        "chamber": chamber,
                        "party": party,
                        "state": state
                    })
            
            # Fallback: fuzzy match by name
            cur.execute("""
                SELECT id FROM intelligence.entity_profiles
                WHERE domain_key = 'politics'
                AND metadata->>'canonical_name' ILIKE %s
                LIMIT 1
            """, (politician_name,))
            existing = cur.fetchone()
            if existing:
                return _update_politician_metadata(cur, existing[0], {
                    "bioguide_id": bioguide_id,
                    "chamber": chamber,
                    "party": party,
                    "state": state
                })
            
            # Create new politician entity
            canonical_entity_id = _generate_canonical_id(politician_name, bioguide_id)
            metadata = {
                "canonical_name": politician_name,
                "bioguide_id": bioguide_id,
                "chamber": chamber,
                "party": party,
                "state": state,
                "entity_type": POLITICIAN_ENTITY_TYPE,
                "source": POLITICIAN_SOURCE,
                "last_trade_date": None,
                "trade_count": 0
            }
            
            cur.execute("""
                INSERT INTO intelligence.entity_profiles
                (domain_key, canonical_entity_id, metadata, created_at, updated_at)
                VALUES ('politics', %s, %s, NOW(), NOW())
                RETURNING id
            """, (canonical_entity_id, json.dumps(metadata)))
            
            entity_id = cur.fetchone()[0]
            logger.info(f"Created politician entity: {politician_name} (id={entity_id})")
            return entity_id


def _update_politician_metadata(
    cur, 
    entity_id: int, 
    updates: dict[str, Any]
) -> int:
    """Update politician metadata with new info."""
    cur.execute("""
        UPDATE intelligence.entity_profiles
        SET metadata = jsonb_set(
            metadata, 
            '{canonical_name}', 
            to_jsonb(COALESCE(%s, metadata->>'canonical_name'))
        ),
        metadata = jsonb_set(
            metadata, 
            '{bioguide_id}', 
            to_jsonb(COALESCE(%s, metadata->>'bioguide_id'))
        ),
        metadata = jsonb_set(
            metadata, 
            '{chamber}', 
            to_jsonb(COALESCE(%s, metadata->>'chamber'))
        ),
        metadata = jsonb_set(
            metadata, 
            '{party}', 
            to_jsonb(COALESCE(%s, metadata->>'party'))
        ),
        metadata = jsonb_set(
            metadata, 
            '{state}', 
            to_jsonb(COALESCE(%s, metadata->>'state'))
        ),
        updated_at = NOW()
        WHERE id = %s
    """, (
        updates.get("canonical_name"),
        updates.get("bioguide_id"),
        updates.get("chamber"),
        updates.get("party"),
        updates.get("state"),
        entity_id
    ))
    return entity_id


def _generate_canonical_id(name: str, bioguide_id: str | None) -> str:
    """Generate stable canonical ID for politician."""
    import hashlib
    if bioguide_id:
        return f"politician_{bioguide_id.lower()}"
    # Hash name for stable ID
    name_hash = hashlib.sha256(name.lower().encode()).hexdigest()[:12]
    return f"politician_{name_hash}"


def increment_politician_trade_count(politician_name: str, bioguide_id: str | None = None) -> bool:
    """Increment trade counter for politician after new trade collected."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Find entity
            if bioguide_id:
                cur.execute("""
                    SELECT id, metadata FROM intelligence.entity_profiles
                    WHERE metadata->>'bioguide_id' = %s AND domain_key = 'politics'
                """, (bioguide_id,))
            else:
                cur.execute("""
                    SELECT id, metadata FROM intelligence.entity_profiles
                    WHERE metadata->>'canonical_name' ILIKE %s AND domain_key = 'politics'
                """, (politician_name,))
            
            row = cur.fetchone()
            if not row:
                return False
            
            entity_id, metadata = row
            new_count = (metadata.get("trade_count", 0) or 0) + 1
            
            cur.execute("""
                UPDATE intelligence.entity_profiles
                SET metadata = jsonb_set(metadata, '{trade_count}', %s::jsonb),
                    metadata = jsonb_set(metadata, '{last_trade_date}', to_jsonb(NOW()::text)),
                    updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(new_count), entity_id))
            
            return True


def get_politician_trade_summary(politician_name: str | None = None, limit: int = 50) -> list[dict]:
    """Get politician trading summary from quiver_congress_trades view."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if politician_name:
                cur.execute("""
                    SELECT * FROM intelligence.quiver_politician_trade_summary
                    WHERE politician_name ILIKE %s
                    ORDER BY total_trades DESC
                    LIMIT %s
                """, (f"%{politician_name}%", limit))
            else:
                cur.execute("""
                    SELECT * FROM intelligence.quiver_politician_trade_summary
                    ORDER BY total_trades DESC
                    LIMIT %s
                """, (limit,))
            
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_ticker_congress_activity(ticker: str | None = None, limit: int = 50) -> list[dict]:
    """Get Congress trading activity for a ticker or all tickers."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if ticker:
                cur.execute("""
                    SELECT * FROM intelligence.quiver_ticker_congress_activity
                    WHERE ticker = %s
                    ORDER BY total_trades DESC
                    LIMIT %s
                """, (ticker.upper(), limit))
            else:
                cur.execute("""
                    SELECT * FROM intelligence.quiver_ticker_congress_activity
                    ORDER BY total_trades DESC
                    LIMIT %s
                """, (limit,))
            
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def link_trades_to_politician_entities() -> dict[str, int]:
    """Backfill: link existing quiver trades to politician entities."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Get unique politicians from trades
            cur.execute("""
                SELECT DISTINCT 
                    politician_name, 
                    politician_bioguide_id,
                    chamber,
                    party,
                    state
                FROM intelligence.quiver_congress_trades
                WHERE politician_name IS NOT NULL
            """)
            politicians = cur.fetchall()
            
            created = 0
            updated = 0
            for name, bioguide, chamber, party, state in politicians:
                entity_id = resolve_politician_entity(name, bioguide, chamber, party, state)
                if entity_id:
                    # Check if this was a new entity (would need to track separately)
                    updated += 1
            
            return {"processed": len(politicians), "entities_resolved": updated}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test resolution
    result = link_trades_to_politician_entities()
    print(f"Entity resolution: {result}")