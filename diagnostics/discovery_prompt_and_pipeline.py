#!/usr/bin/env python3
"""
discovery_prompt_and_pipeline.py

Scans the codebase to identify all files that need modification for:
1. Extraction prompt tightening
2. Pipeline state management (wiki_status)
3. Entity dedup/normalization
4. Bulk cleanup targets in the database

Run this BEFORE making changes. Use output to build the update script.
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# --- CONFIGURATION ---
PROJECT_ROOT = os.environ.get(
    "PROJECT_ROOT",
    "/home/pete/Documents/projects/Projects/News Intelligence",
)
DB_CONNECTION_STRING = os.environ.get("DATABASE_URL", None)

# File extensions to scan
SCAN_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".sql",
    ".yaml", ".yml", ".json", ".env", ".toml", ".cfg", ".ini", ".md",
}

# Patterns that indicate files we care about
PROMPT_PATTERNS = [
    r"entity_type|entity type|extract.*entit",
    r"person|organization|recurring_event|subject",
    r"system.*prompt|user.*prompt|assistant.*prompt",
    r"openai|anthropic|claude|gpt-4|gpt-3",
    r"chat\.completions|messages\s*=\s*\[",
    r"extract|extraction",
    r"None found|None specified|N/A",
]

PIPELINE_PATTERNS = [
    r"wikipedia|wiki_page|wiki.*lookup|wiki.*enrich",
    r"wikipedia_page_id|page_id",
    r"entity.*process|process.*entity|enrich.*entity",
    r"bulk.*insert|insert.*entity|save.*entity|create.*entity",
    r"celery|task|worker|queue|job",
    r"def\s+process|def\s+enrich|def\s+extract",
]

SCHEMA_PATTERNS = [
    r"CREATE\s+TABLE.*entit",
    r"ALTER\s+TABLE.*entit",
    r"class\s+Entity|class\s+WikipediaPage|class\s+Subject",
    r"models\.CharField|models\.TextField|Column\(",
    r"entity_type|wikipedia_page_id",
]

DB_QUERY_PATTERNS = [
    r"INSERT\s+INTO.*entit",
    r"UPDATE.*entit",
    r"SELECT.*FROM.*entit",
    r"\.filter\(|\.query\(|\.execute\(",
]


class FileMatch:
    def __init__(self, filepath, category, matches):
        self.filepath = filepath
        self.category = category
        self.matches = matches  # list of (line_num, line_text, pattern)


def scan_file(filepath, patterns):
    """Scan a single file for pattern matches."""
    matches = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    matches.append((i, line.strip()[:120], pattern))
                    break  # one match per line is enough
    except PermissionError:
        pass
    except Exception:
        pass
    return matches if matches else None


def scan_project(root):
    """Walk the project tree and categorize files by what they contain."""
    results = {
        "prompt_files": [],
        "pipeline_files": [],
        "schema_files": [],
        "db_query_files": [],
    }

    skip_dirs = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        "env", ".env", ".tox", ".mypy_cache", "dist", "build",
        "migrations", ".next", "coverage",
    }

    migration_files = []
    all_scanned = 0
    all_skipped = 0

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune directories we don't want
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            _, ext = os.path.splitext(filename)

            if ext not in SCAN_EXTENSIONS:
                all_skipped += 1
                continue

            # Track migration files separately
            if "migration" in dirpath.lower() or "migrate" in filename.lower():
                migration_files.append(filepath)
                continue

            all_scanned += 1
            rel_path = os.path.relpath(filepath, root)

            match = scan_file(filepath, PROMPT_PATTERNS)
            if match:
                results["prompt_files"].append(FileMatch(rel_path, "prompt", match))

            match = scan_file(filepath, PIPELINE_PATTERNS)
            if match:
                results["pipeline_files"].append(FileMatch(rel_path, "pipeline", match))

            match = scan_file(filepath, SCHEMA_PATTERNS)
            if match:
                results["schema_files"].append(FileMatch(rel_path, "schema", match))

            match = scan_file(filepath, DB_QUERY_PATTERNS)
            if match:
                results["db_query_files"].append(FileMatch(rel_path, "db_query", match))

    return results, all_scanned, all_skipped, migration_files


def score_file(file_match):
    """Score a file by how many distinct pattern matches it has."""
    unique_patterns = set(m[2] for m in file_match.matches)
    return len(unique_patterns)


def extract_prompts(root, prompt_files):
    """Try to extract actual prompt text from the most likely prompt files."""
    prompt_extracts = []
    for fm in sorted(prompt_files, key=score_file, reverse=True)[:10]:
        try:
            filepath = os.path.join(root, fm.filepath)
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Look for triple-quoted strings that might be prompts
            triple_quotes = re.findall(
                r'(""".*?"""|\'\'\'.*?\'\'\')',
                content,
                re.DOTALL | re.IGNORECASE,
            )
            for tq in triple_quotes:
                if re.search(r"entity|extract|person|organization", tq, re.IGNORECASE):
                    prompt_extracts.append({
                        "file": fm.filepath,
                        "type": "triple_quote_string",
                        "preview": tq[:500],
                    })

            # Look for prompt variable assignments
            var_matches = re.findall(
                r'((?:system_prompt|user_prompt|extraction_prompt|prompt_template|PROMPT|SYSTEM_MESSAGE)\s*=\s*.+?)(?:\n\n|\nclass |\ndef )',
                content,
                re.IGNORECASE | re.DOTALL,
            )
            for vm in var_matches:
                if vm.strip():
                    prompt_extracts.append({
                        "file": fm.filepath,
                        "type": "prompt_variable",
                        "preview": vm.strip()[:500],
                    })

            # Look for messages=[ patterns (OpenAI-style)
            msg_matches = re.findall(
                r'(messages\s*=\s*\[.*?\])',
                content,
                re.DOTALL | re.IGNORECASE,
            )
            for mm in msg_matches:
                if len(mm) > 50:
                    prompt_extracts.append({
                        "file": fm.filepath,
                        "type": "messages_array",
                        "preview": mm[:500],
                    })

        except PermissionError:
            pass
        except Exception:
            pass

    return prompt_extracts


def inspect_database(conn_string):
    """If we can connect to the DB, check current entity table schema."""
    try:
        import psycopg2
    except ImportError:
        return {"error": "psycopg2 not installed — run: pip install psycopg2-binary"}

    try:
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()

        # Find entity-related tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name ILIKE '%entit%'
            ORDER BY table_name;
        """)
        entity_tables = [row[0] for row in cur.fetchall()]

        # Get schema for each table
        table_schemas = {}
        for table in entity_tables:
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position;
            """, (table,))
            table_schemas[table] = cur.fetchall()

        # Check if wiki_status column already exists
        cur.execute("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND (column_name ILIKE '%wiki_status%'
                 OR column_name ILIKE '%wikipedia_status%'
                 OR column_name ILIKE '%enrichment_status%')
        """)
        existing_status_columns = cur.fetchall()

        # Count entities and enrichment status
        entity_counts = {}
        for table in entity_tables:
            cols = [row[0] for row in table_schemas.get(table, [])]
            if "wikipedia_page_id" in cols:
                try:
                    cur.execute(f"""
                        SELECT
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE wikipedia_page_id IS NOT NULL) as enriched,
                            COUNT(*) FILTER (WHERE wikipedia_page_id IS NULL) as not_enriched
                        FROM {table};
                    """)
                    row = cur.fetchone()
                    entity_counts[table] = {
                        "total": row[0],
                        "enriched": row[1],
                        "not_enriched": row[2],
                    }
                except Exception:
                    entity_counts[table] = {"error": "query failed"}
            else:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM {table};")
                    entity_counts[table] = {"total": cur.fetchone()[0]}
                except Exception:
                    entity_counts[table] = {"error": "query failed"}

        # Check for garbage entities
        garbage_samples = {}
        for table in entity_tables:
            cols = [row[0] for row in table_schemas.get(table, [])]
            name_col = None
            type_col = None
            for c in cols:
                if "name" in c.lower() and not name_col:
                    name_col = c
                if "type" in c.lower() and "entity" in c.lower():
                    type_col = c
            if not name_col:
                continue
            try:
                type_select = type_col if type_col else "''"
                type_group = f", {type_col}" if type_col else ", ''"
                cur.execute(f"""
                    SELECT {name_col}, {type_select}, COUNT(*) as dupes
                    FROM {table}
                    WHERE {name_col} IN (
                        'None found', 'None specified', 'N/A',
                        'Unknown', 'None', 'none', ''
                    )
                    GROUP BY {name_col}{type_group}
                    ORDER BY dupes DESC
                    LIMIT 50;
                """)
                garbage_samples[table] = cur.fetchall()
            except Exception:
                garbage_samples[table] = []

        # Check for duplicates
        duplicate_check = {}
        for table in entity_tables:
            cols = [row[0] for row in table_schemas.get(table, [])]
            name_col = None
            type_col = None
            for c in cols:
                if "name" in c.lower() and not name_col:
                    name_col = c
                if "type" in c.lower() and "entity" in c.lower():
                    type_col = c
            if not name_col or not type_col:
                continue
            try:
                cur.execute(f"""
                    SELECT {name_col}, {type_col}, COUNT(*) as cnt
                    FROM {table}
                    GROUP BY {name_col}, {type_col}
                    HAVING COUNT(*) > 1
                    ORDER BY cnt DESC
                    LIMIT 30;
                """)
                duplicate_check[table] = cur.fetchall()
            except Exception:
                duplicate_check[table] = []

        conn.close()

        return {
            "entity_tables": entity_tables,
            "table_schemas": table_schemas,
            "existing_status_columns": existing_status_columns,
            "entity_counts": entity_counts,
            "garbage_samples": garbage_samples,
            "duplicate_entities": duplicate_check,
        }

    except Exception as e:
        return {"error": str(e)}


def find_snapshot_scripts(root):
    """Look for the snapshot script built yesterday."""
    candidates = []
    skip_dirs = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
    }

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if re.search(r"snapshot|backup", filename, re.IGNORECASE):
                fp = os.path.join(dirpath, filename)
                stat = os.stat(fp)
                candidates.append({
                    "path": os.path.relpath(fp, root),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size,
                })

    # Also check common names
    common_names = ["snapshot.py", "snapshot.sh", "backup.py", "backup.sh"]
    for cn in common_names:
        fp = os.path.join(root, cn)
        if os.path.exists(fp) and not any(c["path"] == cn for c in candidates):
            stat = os.stat(fp)
            candidates.append({
                "path": cn,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size": stat.st_size,
            })

    return candidates


def generate_report(
    scan_results, scanned, skipped, migrations,
    prompt_extracts, db_info, snapshot_scripts
):
    """Generate the full discovery report."""
    report = []

    report.append("=" * 70)
    report.append("DISCOVERY REPORT: Prompt & Pipeline Update Targets")
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append(f"Project root: {PROJECT_ROOT}")
    report.append(f"Files scanned: {scanned} | Skipped: {skipped}")
    report.append("=" * 70)

    # --- Section 0: Snapshot ---
    report.append("\n")
    report.append("SECTION 0: SNAPSHOT SCRIPT")
    report.append("=" * 40)
    if snapshot_scripts:
        report.append(f"Found {len(snapshot_scripts)} snapshot script(s):")
        for ss in snapshot_scripts:
            report.append(f"  {ss['path']}")
            report.append(f"    Last modified: {ss['modified']}")
            report.append(f"    Size: {ss['size']} bytes")
        report.append(f"\n>>> ACTION REQUIRED: Run snapshot before proceeding:")
        report.append(f"    python3 {snapshot_scripts[0]['path']}")
    else:
        report.append("WARNING: No snapshot script found!")
        report.append("  Searched for: *snapshot*.py, *snapshot*.sh, backup.py, backup.sh")
        report.append("  You need to take a database snapshot before making changes.")

    # --- Section 1: Prompt files ---
    report.append("\n")
    report.append("SECTION 1: EXTRACTION PROMPT FILES")
    report.append("These files contain entity extraction prompts that need tightening")
    report.append("=" * 40)

    prompt_files = scan_results["prompt_files"]
    if not prompt_files:
        report.append("  No prompt files found! Check SCAN_EXTENSIONS and PROJECT_ROOT.")
    else:
        scored = sorted(prompt_files, key=score_file, reverse=True)
        high_relevance = [f for f in scored if score_file(f) >= 4]
        medium_relevance = [f for f in scored if 2 <= score_file(f) < 4]
        low_relevance = [f for f in scored if score_file(f) < 2]

        report.append(f"\n  HIGH RELEVANCE ({len(high_relevance)} files) — likely contain the extraction prompt:")
        for fm in high_relevance:
            report.append(f"    {fm.filepath} (score: {score_file(fm)})")
            for line_num, line_text, _ in fm.matches[:5]:
                report.append(f"      L{line_num}: {line_text}")

        report.append(f"\n  MEDIUM RELEVANCE ({len(medium_relevance)} files) — may contain prompt config or helpers:")
        for fm in medium_relevance:
            report.append(f"    {fm.filepath} (score: {score_file(fm)})")
            for line_num, line_text, _ in fm.matches[:3]:
                report.append(f"      L{line_num}: {line_text}")

        report.append(f"\n  LOW RELEVANCE ({len(low_relevance)} files) — likely incidental mentions:")
        for fm in low_relevance[:10]:
            report.append(f"    {fm.filepath} (score: {score_file(fm)})")

    if prompt_extracts:
        report.append(f"\n  --- PROMPT CONTENT FOUND ({len(prompt_extracts)} extracts) ---")
        for pe in prompt_extracts:
            report.append(f"  File: {pe['file']}")
            report.append(f"  Type: {pe['type']}")
            report.append(f"  Preview:")
            lines = pe["preview"].split("\n")
            for line in lines[:15]:
                report.append(f"    | {line}")
            if len(lines) > 15:
                report.append(f"    | ... (truncated)")
            report.append("")

    # --- Section 2: Pipeline files ---
    report.append("\n")
    report.append("SECTION 2: PIPELINE / PROCESSING FILES")
    report.append("These files handle entity processing, Wikipedia enrichment, task queuing")
    report.append("=" * 40)

    pipeline_files = scan_results["pipeline_files"]
    if not pipeline_files:
        report.append("  No pipeline files found!")
    else:
        for fm in sorted(pipeline_files, key=score_file, reverse=True):
            report.append(f"  {fm.filepath} (score: {score_file(fm)})")
            for line_num, line_text, _ in fm.matches[:5]:
                report.append(f"      L{line_num}: {line_text}")

    # --- Section 3: Schema files ---
    report.append("\n")
    report.append("SECTION 3: SCHEMA / MODEL FILES")
    report.append("These define entity table structure — need wiki_status column added")
    report.append("=" * 40)

    schema_files = scan_results["schema_files"]
    if not schema_files:
        report.append("  No schema files found!")
    else:
        for fm in sorted(schema_files, key=score_file, reverse=True):
            report.append(f"  {fm.filepath} (score: {score_file(fm)})")
            for line_num, line_text, _ in fm.matches[:5]:
                report.append(f"      L{line_num}: {line_text}")

    # --- Section 4: DB query files ---
    report.append("\n")
    report.append("SECTION 4: DATABASE QUERY FILES")
    report.append("These insert/update/query entities — need dedup and status checks added")
    report.append("=" * 40)

    db_query_files = scan_results["db_query_files"]
    if not db_query_files:
        report.append("  No DB query files found!")
    else:
        for fm in sorted(db_query_files, key=score_file, reverse=True):
            report.append(f"  {fm.filepath} (score: {score_file(fm)})")
            for line_num, line_text, _ in fm.matches[:5]:
                report.append(f"      L{line_num}: {line_text}")

    if migrations:
        report.append(f"\n  Found {len(migrations)} migration files (not scanned, listed for reference):")
        for mf in migrations[:20]:
            report.append(f"    {mf}")

    # --- Section 5: Database state ---
    report.append("\n")
    report.append("SECTION 5: CURRENT DATABASE STATE")
    report.append("=" * 40)

    if db_info is None:
        report.append("  DATABASE_URL not set — skipping database inspection.")
        report.append("  Set DATABASE_URL environment variable to enable.")
    elif "error" in db_info:
        report.append(f"  Database connection error: {db_info['error']}")
    else:
        report.append(f"\n  Entity tables found: {db_info['entity_tables']}")

        for table, schema in db_info.get("table_schemas", {}).items():
            report.append(f"\n  Table: {table}")
            report.append(f"  {'Column':<35} {'Type':<20} {'Nullable':<10} {'Default'}")
            report.append(f"  {'-'*35} {'-'*20} {'-'*10} {'-'*20}")
            for col_name, data_type, nullable, default in schema:
                report.append(
                    f"  {col_name:<35} {data_type:<20} {nullable:<10} {str(default or '')[:30]}"
                )

        if db_info.get("existing_status_columns"):
            report.append(f"\n  Wiki status columns already exist:")
            for table, col in db_info["existing_status_columns"]:
                report.append(f"    {table}.{col}")
        else:
            report.append(f"\n  No wiki_status columns found — need to add them.")

        for table, counts in db_info.get("entity_counts", {}).items():
            report.append(f"\n  {table} counts:")
            for k, v in counts.items():
                report.append(f"    {k}: {v}")

        for table, garbage in db_info.get("garbage_samples", {}).items():
            if garbage:
                report.append(
                    f"\n  {table} — garbage/low-quality entities (candidates for bulk delete):"
                )
                report.append(f"  {'Name':<40} {'Type':<20} {'Dupes'}")
                report.append(f"  {'-'*40} {'-'*20} {'-'*5}")
                for row in garbage:
                    report.append(f"  {str(row[0]):<40} {str(row[1]):<20} {row[2]}")

        for table, dupes in db_info.get("duplicate_entities", {}).items():
            if dupes:
                report.append(
                    f"\n  {table} — duplicate entities (same name + type, multiple rows):"
                )
                report.append(f"  {'Name':<40} {'Type':<20} {'Count'}")
                report.append(f"  {'-'*40} {'-'*20} {'-'*5}")
                for row in dupes:
                    report.append(f"  {str(row[0]):<40} {str(row[1]):<20} {row[2]}")

    # --- Section 6: Summary ---
    report.append("\n")
    report.append("SECTION 6: SUMMARY — FILES THAT NEED CHANGES")
    report.append("=" * 40)

    all_files = defaultdict(set)
    for category, file_matches in scan_results.items():
        for fm in file_matches:
            all_files[fm.filepath].add(category)

    multi = {fp: cats for fp, cats in all_files.items() if len(cats) > 1}
    if multi:
        report.append("\n  FILES APPEARING IN MULTIPLE CATEGORIES (highest priority):")
        for fp, cats in sorted(multi.items(), key=lambda x: -len(x[1])):
            report.append(f"    {fp}")
            report.append(f"      Categories: {', '.join(sorted(cats))}")

    report.append("\n  CHANGE PLAN:")
    report.append("  " + "-" * 50)

    report.append("  Step 0: Run snapshot script")
    if snapshot_scripts:
        report.append(f"          python3 {snapshot_scripts[0]['path']}")
    else:
        report.append("          WARNING: snapshot script not found, create one first")

    report.append("  Step 1: Update extraction prompt")
    for fm in sorted(scan_results["prompt_files"], key=score_file, reverse=True)[:3]:
        report.append(f"          -> {fm.filepath}")

    report.append("  Step 2: Add wiki_status column to entity schema")
    for fm in sorted(scan_results["schema_files"], key=score_file, reverse=True)[:3]:
        report.append(f"          -> {fm.filepath}")

    report.append("  Step 3: Add dedup check + status routing to pipeline")
    for fm in sorted(scan_results["pipeline_files"], key=score_file, reverse=True)[:3]:
        report.append(f"          -> {fm.filepath}")

    report.append("  Step 4: Run bulk cleanup SQL against database")
    report.append("  Step 5: Process remaining pending entities (one-time backlog drain)")
    report.append("  Step 6: Verify pipeline with new articles flowing through")

    report.append("\n")
    report.append("END OF DISCOVERY REPORT")
    report.append("=" * 70)

    return "\n".join(report)


def main():
    print(f"Scanning {PROJECT_ROOT} ...")
    print(f"This may take a moment for large projects.\n")

    # 1. Scan project files
    scan_results, scanned, skipped, migrations = scan_project(PROJECT_ROOT)

    # 2. Extract prompt content
    prompt_extracts = extract_prompts(PROJECT_ROOT, scan_results["prompt_files"])

    # 3. Find snapshot scripts
    snapshot_scripts = find_snapshot_scripts(PROJECT_ROOT)

    # 4. Inspect database (if configured)
    db_info = None
    if DB_CONNECTION_STRING:
        db_info = inspect_database(DB_CONNECTION_STRING)

    # 5. Generate report
    report = generate_report(
        scan_results, scanned, skipped, migrations,
        prompt_extracts, db_info, snapshot_scripts,
    )

    # 6. Save report
    output_dir = os.path.join(PROJECT_ROOT, "diagnostics")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, "discovery_report.txt")
    with open(output_path, "w") as f:
        f.write(report)

    # 7. Save JSON summary
    json_output = {
        "generated": datetime.now().isoformat(),
        "project_root": PROJECT_ROOT,
        "snapshot_scripts": snapshot_scripts,
        "prompt_files": [
            {
                "path": fm.filepath,
                "score": score_file(fm),
                "match_count": len(fm.matches),
            }
            for fm in sorted(scan_results["prompt_files"], key=score_file, reverse=True)
        ],
        "pipeline_files": [
            {
                "path": fm.filepath,
                "score": score_file(fm),
                "match_count": len(fm.matches),
            }
            for fm in sorted(scan_results["pipeline_files"], key=score_file, reverse=True)
        ],
        "schema_files": [
            {
                "path": fm.filepath,
                "score": score_file(fm),
                "match_count": len(fm.matches),
            }
            for fm in sorted(scan_results["schema_files"], key=score_file, reverse=True)
        ],
        "db_query_files": [
            {
                "path": fm.filepath,
                "score": score_file(fm),
                "match_count": len(fm.matches),
            }
            for fm in sorted(scan_results["db_query_files"], key=score_file, reverse=True)
        ],
        "prompt_extracts": prompt_extracts,
        "database_state": db_info,
        "change_targets": {
            "prompt_files_to_edit": [
                fm.filepath
                for fm in sorted(scan_results["prompt_files"], key=score_file, reverse=True)[:5]
            ],
            "pipeline_files_to_edit": [
                fm.filepath
                for fm in sorted(scan_results["pipeline_files"], key=score_file, reverse=True)[:5]
            ],
            "schema_files_to_edit": [
                fm.filepath
                for fm in sorted(scan_results["schema_files"], key=score_file, reverse=True)[:5]
            ],
        },
    }

    json_path = os.path.join(output_dir, "discovery_report.json")
    with open(json_path, "w") as f:
        json.dump(json_output, f, indent=2, default=str)

    # 8. Print report
    print(report)
    print(f"\n{'=' * 60}")
    print(f"Report saved to: {output_path}")
    print(f"JSON data saved to: {json_path}")
    print(f"{'=' * 60}")
    print(f"\n>>> NEXT STEPS:")
    print(f"  1. Review the report above")
    if snapshot_scripts:
        print(f"  2. Run snapshot: python3 {snapshot_scripts[0]['path']}")
    else:
        print(f"  2. Create and run a snapshot/backup script first")
    print(f"  3. Paste the report back and we will write the update script")
    print(f"     targeting the exact files identified above")


if __name__ == "__main__":
    main()
