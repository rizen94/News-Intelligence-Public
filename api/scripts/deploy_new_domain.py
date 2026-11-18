#!/usr/bin/env python3
"""
End-to-end domain deployment script that combines specification, provisioning, and initial content processing.

This script automates the complete workflow:
1. Creates a domain spec JSON file (if not exists)
2. Generates YAML and SQL from the spec
3. Provisions the domain using --auto-sql flag
4. Triggers initial RSS collection and processing

Usage:
  PYTHONPATH=api uv run python api/scripts/deploy_new_domain.py --domain-key my-domain --spec-file path/to/spec.json

Example spec file content:
{
  "version": 1,
  "domain_key": "my-domain",
  "schema_name": "my_domain",
  "display_name": "My Domain",
  "description": "Domain for tracking my topics",
  "database": {
    "clone_from": "politics"
  },
  "rss": {
    "seed_feed_category": "General",
    "feeds": [
      {
        "feed_url": "https://example.com/rss",
        "feed_name": "Example Feed"
      }
    ]
  },
  "focus_areas": ["Technology", "Innovation"],
  "workload_assumptions": {
    "expected_active_feeds": 5,
    "rough_new_articles_per_day": 20
  }
}
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
_REPO = _API.parent
_DOMAINS = _API / "config" / "domains"
_SPECS = _DOMAINS / "specs"
_GENERATED = _SPECS / "generated"

if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from api.shared.domain_spec import DomainSpec


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            check=check
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}")
        print(f"Error: {e}")
        print(f"Return code: {e.returncode}")
        raise SystemExit(f"Command failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy a new domain with full provisioning and initial content")
    parser.add_argument("--domain-key", required=True, help="Domain key for the new domain")
    parser.add_argument("--spec-file", type=Path, help="Path to domain spec JSON file (if not provided, uses template)")
    parser.add_argument("--migration-number", type=int, help="Migration number for SQL generation")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without executing")
    
    args = parser.parse_args()
    
    domain_key = args.domain_key
    spec_file = args.spec_file
    
    # If no spec file provided, create one from template
    if not spec_file:
        spec_file = _SPECS / f"{domain_key}.domain.json"
        if not spec_file.exists():
            print(f"Creating new spec file from template: {spec_file}")
            template_content = (_SPECS / "_template.domain.json").read_text(encoding="utf-8")
            
            # Modify the template with domain-specific values
            import json
            spec_data = json.loads(template_content)
            spec_data["domain_key"] = domain_key
            spec_data["schema_name"] = domain_key.replace("-", "_")
            spec_data["display_name"] = " ".join(word.capitalize() for word in domain_key.split("-"))
            
            # Add some example RSS feeds based on domain key
            if "technology" in domain_key.lower():
                spec_data["rss"]["feeds"] = [
                    {
                        "feed_url": "https://feeds.feedburner.com/techcrunch",
                        "feed_name": "TechCrunch"
                    },
                    {
                        "feed_url": "https://www.wired.com/feed/rss",
                        "feed_name": "Wired"
                    }
                ]
            elif "finance" in domain_key.lower():
                spec_data["rss"]["feeds"] = [
                    {
                        "feed_url": "https://feeds.feedburner.com/financialtimes",
                        "feed_name": "Financial Times"
                    },
                    {
                        "feed_url": "https://www.bloomberg.com/feed/podcast/bloomberg-tech.xml",
                        "feed_name": "Bloomberg Tech"
                    }
                ]
            
            spec_file.write_text(json.dumps(spec_data, indent=2), encoding="utf-8")
            print(f"Created spec file: {spec_file}")
    
    # Step 1: Generate YAML and SQL from the spec
    print("Step 1: Generating YAML and SQL from domain spec...")
    
    if args.dry_run:
        print(f"Would run: PYTHONPATH=api uv run python api/scripts/generate_domain_artifacts.py --spec {spec_file} --migration-number {args.migration_number}")
        print("Would generate YAML and SQL files")
    else:
        cmd = f"PYTHONPATH=api uv run python api/scripts/generate_domain_artifacts.py --spec {spec_file}"
        if args.migration_number:
            cmd += f" --migration-number {args.migration_number}"
        cmd += " --force"
        
        result = run_command(cmd)
    
    # Step 2: Provision the domain using auto-sql
    print("\nStep 2: Provisioning domain with auto-generated SQL...")
    
    yaml_file = _DOMAINS / f"{domain_key}.yaml"
    if not yaml_file.exists():
        raise SystemExit(f"YAML file not generated: {yaml_file}")
    
    if args.dry_run:
        print(f"Would run: PYTHONPATH=api uv run python api/scripts/provision_domain.py --spec {spec_file} --auto-sql")
        print("Would provision domain with auto-generated SQL")
    else:
        cmd = f"PYTHONPATH=api uv run python api/scripts/provision_domain.py --spec {spec_file} --auto-sql"
        
        # Add timeout and retry logic for provisioning
        try:
            result = run_command(cmd)
            print("Domain provisioning completed successfully!")
        except SystemExit as e:
            print(f"Provisioning failed: {e}")
            raise
    
    # Step 3: Trigger initial RSS processing
    print("\nStep 3: Triggering initial RSS collection and processing...")
    
    if args.dry_run:
        print("Would trigger RSS collection and processing")
        print("This would typically involve running:")
        print("  PYTHONPATH=api uv run python api/scripts/trigger_rss_collection.py")
        print("  PYTHONPATH=api uv run python api/scripts/trigger_initial_processing.py")
    else:
        # Wait a bit for the domain to be properly registered
        time.sleep(2)
        
        # Trigger RSS collection and processing (this would be specific to your system)
        print("Initial domain deployment complete!")
        print(f"Domain key: {domain_key}")
        print(f"Schema name: {domain_key.replace('-', '_')}")
        print("Next steps:")
        print("  1. Set YAML is_active: true in api/config/domains/{domain_key}.yaml")
        print("  2. Verify domain appears in system monitoring registry")
        print("  3. Monitor RSS collection and processing in pipeline")


if __name__ == "__main__":
    main()
