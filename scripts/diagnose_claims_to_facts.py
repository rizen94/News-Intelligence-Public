#!/usr/bin/env python3
"""Quick diagnostic for claims_to_facts productivity issue."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

from shared.database.connection import get_db_connection

conn = get_db_connection()
if not conn:
    print("ERROR: no DB connection")
    sys.exit(1)

cur = conn.cursor()

print("=== extracted_claims status ===")
cur.execute("SELECT COUNT(*) FROM intelligence.extracted_claims")
total = cur.fetchone()[0]
print(f"Total extracted_claims: {total:,}")

cur.execute("SELECT COUNT(*) FROM intelligence.extracted_claims WHERE confidence >= 0.7")
high_conf = cur.fetchone()[0]
print(f"High confidence (>=0.7): {high_conf:,}")

cur.execute("""
    SELECT COUNT(*) FROM intelligence.extracted_claims ec
    WHERE ec.confidence >= 0.7
      AND NOT EXISTS (
          SELECT 1 FROM intelligence.versioned_facts vf
          WHERE vf.metadata->>'source_claim_id' = ec.id::text
      )
""")
unpromoted = cur.fetchone()[0]
print(f"Unpromoted high confidence: {unpromoted:,}")

print("\n=== Sample unpromoted claims ===")
cur.execute("""
    SELECT ec.id, ec.subject_text, ec.predicate_text, ec.confidence
    FROM intelligence.extracted_claims ec
    WHERE ec.confidence >= 0.7
      AND NOT EXISTS (
          SELECT 1 FROM intelligence.versioned_facts vf
          WHERE vf.metadata->>'source_claim_id' = ec.id::text
      )
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"  ID {row[0]}: '{row[1]}' {row[2]} (conf={row[3]:.2f})")

print("\n=== Entity resolution check ===")
cur.execute("""
    SELECT COUNT(DISTINCT ec.subject_text) FROM intelligence.extracted_claims ec
    WHERE ec.confidence >= 0.7
      AND NOT EXISTS (
          SELECT 1 FROM intelligence.versioned_facts vf
          WHERE vf.metadata->>'source_claim_id' = ec.id::text
      )
""")
unique_subjects = cur.fetchone()[0]
print(f"Unique unpromoted subjects: {unique_subjects:,}")

# Check if any subjects match entity_profiles
cur.execute("""
    SELECT COUNT(DISTINCT ec.subject_text) FROM intelligence.extracted_claims ec
    JOIN intelligence.entity_profiles ep ON LOWER(ep.metadata->>'canonical_name') = LOWER(ec.subject_text)
    WHERE ec.confidence >= 0.7
      AND NOT EXISTS (
          SELECT 1 FROM intelligence.versioned_facts vf
          WHERE vf.metadata->>'source_claim_id' = ec.id::text
      )
""")
resolvable = cur.fetchone()[0]
print(f"Subjects matching entity_profiles: {resolvable:,}")

cur.close()
conn.close()
